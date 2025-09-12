import os
import logging
from datetime import datetime
import pytz
from pathlib import Path
import shutil
from flask import Flask, render_template, request, jsonify, send_file, session, redirect, url_for, Response, send_from_directory
import configparser
from timezone_config import KST, get_korean_time, get_korean_time_str
from werkzeug.utils import secure_filename
from config.menu import MENU_CONFIG
from database_config import db_config, partner_manager
import re
import base64
import sqlite3
import math
from board_services import ColumnService, CodeService, ItemService
from column_service import ColumnConfigService
from search_popup_service import SearchPopupService
from column_sync_service import ColumnSyncService
from db_connection import get_db_connection
from db.upsert import safe_upsert
import schedule
import threading
import time


def generate_manual_accident_number(cursor):
    """수기입력 사고번호 자동 생성 (ACCYYMMDD00 형식)

    기준 테이블: accidents_cache (SOT)
    """
    today = get_korean_time()
    date_part = today.strftime('%y%m%d')  # 240822
    pattern = f'ACC{date_part}%'
    # accidents_cache에서 최신 번호 조회
    try:
        cursor.execute(
            """
            SELECT accident_number 
            FROM accidents_cache 
            WHERE accident_number LIKE ?
            ORDER BY accident_number DESC
            LIMIT 1
            """,
            (pattern,)
        )
        last = cursor.fetchone()
    except Exception:
        last = None
    if last:
        last_num = last[0] if not isinstance(last, dict) else last['accident_number']
    else:
        last_num = None
    if last_num and str(last_num).startswith('ACC'):
        try:
            seq = int(str(last_num)[-2:]) + 1
        except Exception:
            seq = 1
    else:
        seq = 1
    return f'ACC{date_part}{seq:02d}'

app = Flask(__name__, static_folder='static')

# Jinja2 템플릿 필터 정의
@app.template_filter('date_only')
def date_only_filter(datetime_str):
    """날짜시간 문자열에서 날짜만 추출 (YYYY-MM-DD)"""
    if not datetime_str:
        return ''
    # 2025-08-27 14:29:03 → 2025-08-27
    datetime_str = str(datetime_str)
    return datetime_str.split(' ')[0] if ' ' in datetime_str else datetime_str

@app.template_filter('date_korean')
def date_korean_filter(datetime_str):
    """날짜를 한국식 표기로 변환 (YYYY년 MM월 DD일)"""
    if not datetime_str:
        return ''
    datetime_str = str(datetime_str)
    date_part = datetime_str.split(' ')[0] if ' ' in datetime_str else datetime_str
    try:
        parts = date_part.split('-')
        if len(parts) == 3:
            return f"{parts[0]}년 {parts[1]}월 {parts[2]}일"
    except:
        pass
    return date_part

# 메뉴 설정
menu = MENU_CONFIG

# 설정 파일에서 환경 설정 로드
app.secret_key = db_config.config.get('DEFAULT', 'SECRET_KEY')
app.debug = db_config.config.getboolean('DEFAULT', 'DEBUG')

# Jinja2 필터 추가 (JSON 파싱용)
import json as pyjson  # GPT 권고: json 모듈 별칭 사용으로 충돌 방지
def from_json_filter(value):
    """JSON 필터 - dict/list는 그대로, 문자열은 파싱"""
    # 이미 dict나 list면 그대로 반환
    if isinstance(value, (list, dict)):
        return value
    # 문자열이면 파싱 시도
    if isinstance(value, str):
        v = value.strip()
        if not v:
            return []
        try:
            return pyjson.loads(v)
        except:
            return []
    # 그 외의 경우 빈 리스트
    return []
app.jinja_env.filters['from_json'] = from_json_filter

# 리스트 요약 필터: "첫번째이름 외 N명" 형태로 표시
@app.template_filter('list_summary')
def list_summary_filter(value):
    """value가 문자열(JSON) / 리스트 / 기타일 때 공통 요약 문자열 반환"""
    import json as _json
    # 1) normalize to list
    data = None
    try:
        if isinstance(value, (list, tuple)):
            data = list(value)
        elif isinstance(value, str):
            v = value.strip()
            if not v:
                data = []
            else:
                try:
                    parsed = _json.loads(v)
                    data = parsed if isinstance(parsed, list) else []
                except Exception:
                    data = []
        else:
            data = []
    except Exception:
        data = []

    if not data:
        return '-'

    # 2) pick first display name
    def extract_name(item):
        if isinstance(item, dict):
            for k in (
                'name', 'worker_name', 'violator_name', 'employee_name', 'person_name',
                'victim_name', 'value', 'label', 'title'
            ):
                if k in item and item[k]:
                    return str(item[k])
            # 아무 키도 못 찾으면 dict 전체를 문자열로
            return ''
        elif isinstance(item, str):
            return item
        else:
            return str(item)

    first = extract_name(data[0])
    others = max(0, len(data) - 1)

    if not first:
        # 이름을 못 뽑으면 개수만 표시
        return f"{len(data)}개 항목"

    return f"{first} 외 {others}명" if others > 0 else first

DB_PATH = db_config.local_db_path
PASSWORD = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
ADMIN_PASSWORD = db_config.config.get('DEFAULT', 'ADMIN_PASSWORD')

# 관리자 인증 함수
def require_admin_auth(f):
    """관리자 인증이 필요한 함수에 사용하는 decorator"""
    from functools import wraps
    
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에서 관리자 인증 확인
        if session.get('admin_authenticated') != True:
            # 인증이 안된 경우 비밀번호 입력 페이지로 리다이렉트
            return render_template('admin-login.html', 
                                 redirect_url=request.url,
                                 menu=MENU_CONFIG)
        return f(*args, **kwargs)
    return decorated_function

# 드롭다운 코드 매핑
DROPDOWN_MAPPINGS = {
    'column3': {
        'COLUMN3_001': '진행중',
        'COLUMN3_002': '완료대기',
        'COLUMN3_003': '보류',
        'COLUMN3_004': '보류3'
    }
}

def convert_dropdown_code(column_key, code):
    """드롭다운 코드를 실제 값으로 변환"""
    if column_key in DROPDOWN_MAPPINGS:
        return DROPDOWN_MAPPINGS[column_key].get(code, code)
    return code

# --- SQL boolean helpers for SQLite/Postgres portability ---
def sql_is_active_true(field_expr: str, conn) -> str:
    """Active=true condition portable for SQLite(int) and Postgres(bool/int).

    Postgres: cast to text and accept true markers ('1','t','true').
    SQLite: compare to 1 (integers are used for booleans).
    """
    if getattr(conn, 'is_postgres', False):
        return (
            f"(LOWER(COALESCE({field_expr}::text, '0')) IN ('1','t','true'))"
        )
    return f"(COALESCE({field_expr}, 0) = 1)"

def sql_is_deleted_false(field_expr: str, conn) -> str:
    """Deleted=false (or NULL) portable for SQLite(int) and Postgres(bool/int).

    Treat NULL as false (not deleted).
    """
    if getattr(conn, 'is_postgres', False):
        return (
            f"(LOWER(COALESCE({field_expr}::text, '0')) NOT IN ('1','t','true'))"
        )
    return f"(COALESCE({field_expr}, 0) = 0)"

# 로깅 설정
logging.basicConfig(
    level=getattr(logging, db_config.config.get('LOGGING', 'LOG_LEVEL')),
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(db_config.config.get('LOGGING', 'LOG_FILE')),
        logging.StreamHandler()
    ]
)

# Flask 템플릿 자동 리로드 설정
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# Jinja2 템플릿 캐시 비우기
app.jinja_env.cache = {}

# =====================
# SSO (OIDC-like) setup
# =====================
from sso import sso_bp
# Ensure blueprint routes are loaded before registration
import sso.routes  # noqa: F401
from sso.middleware import check_sso_authentication
from scoring_service import calculate_score as _calc_score

# Read SSO config
_cfg = configparser.ConfigParser()
try:
    _cfg.read('config.ini', encoding='utf-8')
except Exception:
    pass

app.config['SSO_CLIENT_ID'] = _cfg.get('SSO', 'idp_client_id', fallback='')
app.config['SSO_REDIRECT_URI'] = _cfg.get('SSO', 'sp_redirect_url', fallback='')
app.config['SSO_LOGOUT_URL'] = _cfg.get('SSO', 'idp_signout_url', fallback='')

# Register SSO blueprint (after routes imported)
app.register_blueprint(sso_bp)

# Enforce SSO (dev mode auto-seeds session)
@app.before_request
def _sso_before_request():
    resp = check_sso_authentication()
    return resp

# =====================
# Scoring API
# =====================
@app.route('/api/<board>/calculate-score', methods=['POST'])
def api_calculate_score(board):
    try:
        data = request.get_json(silent=True) or {}
        # Normalize board keys: allow hyphen
        board_norm = board.replace('-', '_')
        summary = _calc_score(board_norm, data, DB_PATH)
        return jsonify(summary)
    except Exception as e:
        logging.error(f"calculate-score error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 400

def init_db():
    """기본 설정 초기화 및 데이터 동기화"""
    # 로컬 DB 테이블 초기화 (partner_manager에서 처리)
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 페이지 테이블만 여기서 관리
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT UNIQUE,
            title TEXT,
            content TEXT
        )
    ''')

    # Dropdown v2 table (board-scoped) and migration from legacy v1
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                option_code TEXT NOT NULL,
                option_value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                UNIQUE(board_type, column_key, option_code)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_doc_v2_board_col ON dropdown_option_codes_v2(board_type, column_key, is_active)')
        # Migrate from v1 if v2 is empty and v1 exists
        cursor.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name='dropdown_option_codes'")
        v1_exists = cursor.fetchone()[0] > 0
        cursor.execute("SELECT COUNT(*) FROM dropdown_option_codes_v2")
        v2_count = cursor.fetchone()[0]
        if v1_exists and v2_count == 0:
            cursor.execute('''
                INSERT OR IGNORE INTO dropdown_option_codes_v2
                    (board_type, column_key, option_code, option_value, display_order, is_active)
                SELECT 'accident', column_key, option_code, option_value, display_order, is_active
                FROM dropdown_option_codes
            ''')
    except Exception as _e:
        logging.debug(f"Dropdown v2 ensure/migrate skipped: {_e}")
    
    # Ensure board-specific column config tables exist (avoid cross-board fallback)
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accident_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                dropdown_options TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                dropdown_options TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 동적 섹션 관리를 위한 테이블 추가
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_type TEXT NOT NULL,
                section_key TEXT NOT NULL,
                section_name TEXT NOT NULL,
                section_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(board_type, section_key)
            )
        ''')
        # 보강: is_deleted 컬럼이 없으면 추가(soft delete 일관성)
        try:
            cursor.execute("PRAGMA table_info(section_config)")
            cols = [r[1].lower() for r in cursor.fetchall()]
            if 'is_deleted' not in cols:
                cursor.execute("ALTER TABLE section_config ADD COLUMN is_deleted INTEGER DEFAULT 0")
        except Exception:
            pass
        
        # 기본 섹션 데이터 삽입 (없는 경우에만)
        cursor.execute("SELECT COUNT(*) FROM section_config WHERE board_type = 'safety_instruction'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO section_config (board_type, section_key, section_name, section_order) VALUES
                ('safety_instruction', 'basic_info', '기본정보', 1),
                ('safety_instruction', 'violation_info', '위반정보', 2),
                ('safety_instruction', 'additional', '추가기입정보', 3)
            ''')
        
        # 사고게시판용 섹션 데이터 삽입 (없는 경우에만)
        cursor.execute("SELECT COUNT(*) FROM section_config WHERE board_type = 'accident'")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO section_config (board_type, section_key, section_name, section_order) VALUES
                ('accident', 'basic_info', '기본정보', 1),
                ('accident', 'accident_info', '사고정보', 2),
                ('accident', 'location_info', '장소정보', 3),
                ('accident', 'additional', '추가정보', 4)
            ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partner_standards_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                dropdown_options TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Follow SOP 컬럼 설정 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_sop_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                dropdown_options TEXT,
                tab TEXT,
                column_span INTEGER DEFAULT 1,
                linked_columns TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Follow SOP 테이블에 is_deleted 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(follow_sop_column_config)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE follow_sop_column_config ADD COLUMN is_deleted INTEGER DEFAULT 0")
        
        # Full Process 컬럼 설정 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS full_process_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                dropdown_options TEXT,
                tab TEXT,
                column_span INTEGER DEFAULT 1,
                linked_columns TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Full Process 테이블에 is_deleted 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(full_process_column_config)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE full_process_column_config ADD COLUMN is_deleted INTEGER DEFAULT 0")
        
        # Safety Instruction 테이블에 누락된 컬럼들 추가 (startup 보강)
        cursor.execute("PRAGMA table_info(safety_instruction_column_config)")
        safety_columns = [col[1] for col in cursor.fetchall()]
        if 'is_deleted' not in safety_columns:
            cursor.execute("ALTER TABLE safety_instruction_column_config ADD COLUMN is_deleted INTEGER DEFAULT 0")
        if 'tab' not in safety_columns:
            cursor.execute("ALTER TABLE safety_instruction_column_config ADD COLUMN tab TEXT")
        if 'column_span' not in safety_columns:
            cursor.execute("ALTER TABLE safety_instruction_column_config ADD COLUMN column_span INTEGER DEFAULT 1")
        
        # Follow SOP 데이터 테이블 (동적 컬럼 데이터 저장용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_sop (
                work_req_no TEXT PRIMARY KEY,
                custom_data TEXT DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        ''')
        
        # Follow SOP 테이블에 is_deleted 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(follow_sop)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE follow_sop ADD COLUMN is_deleted INTEGER DEFAULT 0")
        
        # Follow SOP sections 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_sop_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Follow SOP sections 테이블에 section_order 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(follow_sop_sections)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'section_order' not in columns:
            cursor.execute("ALTER TABLE follow_sop_sections ADD COLUMN section_order INTEGER DEFAULT 1")
            logging.info("follow_sop_sections 테이블에 section_order 컬럼 추가")
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE follow_sop_sections ADD COLUMN is_active INTEGER DEFAULT 1")
            logging.info("follow_sop_sections 테이블에 is_active 컬럼 추가")
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE follow_sop_sections ADD COLUMN is_deleted INTEGER DEFAULT 0")
            logging.info("follow_sop_sections 테이블에 is_deleted 컬럼 추가")
        
        # Full Process 데이터 테이블 (동적 컬럼 데이터 저장용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS full_process (
                fullprocess_number TEXT PRIMARY KEY,
                custom_data TEXT DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        ''')
        
        # Full Process 테이블에 is_deleted 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(full_process)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE full_process ADD COLUMN is_deleted INTEGER DEFAULT 0")
        
        # Full Process sections 테이블 생성
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS full_process_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER,
                is_active INTEGER DEFAULT 1
            )
        ''')
        
        # Full Process sections 테이블에 section_order 컬럼 추가 (기존 테이블 업데이트)
        cursor.execute("PRAGMA table_info(full_process_sections)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'section_order' not in columns:
            cursor.execute("ALTER TABLE full_process_sections ADD COLUMN section_order INTEGER DEFAULT 1")
            logging.info("full_process_sections 테이블에 section_order 컬럼 추가")
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE full_process_sections ADD COLUMN is_active INTEGER DEFAULT 1")
            logging.info("full_process_sections 테이블에 is_active 컬럼 추가")
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE full_process_sections ADD COLUMN is_deleted INTEGER DEFAULT 0")
            logging.info("full_process_sections 테이블에 is_deleted 컬럼 추가")
            
        # safety_instruction_sections 테이블 생성 및 보정
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_instruction_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        
        # safety_instruction_sections 스키마 보정
        cursor.execute("PRAGMA table_info(safety_instruction_sections)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'section_order' not in columns:
            cursor.execute("ALTER TABLE safety_instruction_sections ADD COLUMN section_order INTEGER DEFAULT 1")
            logging.info("safety_instruction_sections 테이블에 section_order 컬럼 추가")
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE safety_instruction_sections ADD COLUMN is_active INTEGER DEFAULT 1")
            logging.info("safety_instruction_sections 테이블에 is_active 컬럼 추가")
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE safety_instruction_sections ADD COLUMN is_deleted INTEGER DEFAULT 0")
            logging.info("safety_instruction_sections 테이블에 is_deleted 컬럼 추가")
            
        # 섹션 초기 데이터 시드
        # Safety Instruction 섹션
        cursor.execute("SELECT COUNT(*) FROM safety_instruction_sections")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO safety_instruction_sections (section_key, section_name, section_order, is_active, is_deleted)
                VALUES 
                    ('basic_info', '기본정보', 1, 1, 0),
                    ('violation_info', '위반정보', 2, 1, 0),
                    ('additional', '추가정보', 3, 1, 0)
            """)
            logging.info("safety_instruction_sections 초기 데이터 추가")
            
        # Follow SOP 섹션
        cursor.execute("SELECT COUNT(*) FROM follow_sop_sections")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active, is_deleted)
                VALUES 
                    ('basic_info', '기본정보', 1, 1, 0),
                    ('work_info', '작업정보', 2, 1, 0),
                    ('additional', '추가정보', 3, 1, 0)
            """)
            logging.info("follow_sop_sections 초기 데이터 추가")
            
        # Full Process 섹션
        cursor.execute("SELECT COUNT(*) FROM full_process_sections")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO full_process_sections (section_key, section_name, section_order, is_active, is_deleted)
                VALUES 
                    ('basic_info', '기본정보', 1, 1, 0),
                    ('process_info', '프로세스정보', 2, 1, 0),
                    ('additional', '추가정보', 3, 1, 0)
            """)
            logging.info("full_process_sections 초기 데이터 추가")
            
        # 컬럼 tab 매핑 수정 - NULL인 경우 적절한 섹션으로 자동 배정
        # Safety Instruction
        cursor.execute("""
            UPDATE safety_instruction_column_config 
            SET tab = 'basic_info' 
            WHERE tab IS NULL AND column_key IN (
                'issue_number', 'company_name', 'business_number', 'created_at', 
                'issue_date', 'improvement_deadline', 'status', 'issuer', 'recipient'
            )
        """)
        
        cursor.execute("""
            UPDATE safety_instruction_column_config 
            SET tab = 'violation_info' 
            WHERE tab IS NULL AND column_key IN (
                'violation_type', 'violation_details', 'legal_basis', 'penalty',
                'violation_location', 'violation_date', 'violation_severity'
            )
        """)
        
        # 나머지 NULL은 모두 additional로
        _wa_si = sql_is_active_true('is_active', conn)
        _wd_si = sql_is_deleted_false('is_deleted', conn)
        cursor.execute(f"""
            UPDATE safety_instruction_column_config 
            SET tab = 'additional' 
            WHERE (tab IS NULL OR tab = '') 
              AND {_wa_si}
              AND {_wd_si}
        """)
        
        # Follow SOP
        cursor.execute("""
            UPDATE follow_sop_column_config 
            SET tab = 'basic_info' 
            WHERE tab IS NULL AND column_key IN (
                'work_req_no', 'company_name', 'business_number', 'created_at',
                'created_by', 'request_date', 'department'
            )
        """)
        
        cursor.execute("""
            UPDATE follow_sop_column_config 
            SET tab = 'work_info' 
            WHERE tab IS NULL AND column_key IN (
                'work_type', 'work_location', 'work_content', 'work_status',
                'worker_count', 'work_duration', 'safety_measures'
            )
        """)
        
        _wa_fs = sql_is_active_true('is_active', conn)
        _wd_fs = sql_is_deleted_false('is_deleted', conn)
        cursor.execute(f"""
            UPDATE follow_sop_column_config 
            SET tab = 'additional' 
            WHERE (tab IS NULL OR tab = '') 
              AND {_wa_fs}
              AND {_wd_fs}
        """)
        
        # Full Process
        cursor.execute("""
            UPDATE full_process_column_config 
            SET tab = 'basic_info' 
            WHERE tab IS NULL AND column_key IN (
                'fullprocess_number', 'company_name', 'business_number', 'created_at',
                'created_by', 'process_date', 'department'
            )
        """)
        
        cursor.execute("""
            UPDATE full_process_column_config 
            SET tab = 'process_info' 
            WHERE tab IS NULL AND column_key IN (
                'process_type', 'process_name', 'process_status', 'process_owner',
                'process_steps', 'process_duration', 'process_output'
            )
        """)
        
        _wa_fp = sql_is_active_true('is_active', conn)
        _wd_fp = sql_is_deleted_false('is_deleted', conn)
        cursor.execute(f"""
            UPDATE full_process_column_config 
            SET tab = 'additional' 
            WHERE (tab IS NULL OR tab = '') 
              AND {_wa_fp}
              AND {_wd_fp}
        """)
        
        # Accident
        cursor.execute("""
            UPDATE accident_column_config 
            SET tab = 'basic_info' 
            WHERE tab IS NULL AND column_key IN (
                'accident_number', 'company_name', 'business_number', 'created_at',
                'accident_date', 'reporter', 'department'
            )
        """)
        
        cursor.execute("""
            UPDATE accident_column_config 
            SET tab = 'accident_info' 
            WHERE tab IS NULL AND column_key IN (
                'accident_type', 'accident_cause', 'injury_type', 'injury_severity',
                'accident_description', 'victim_name', 'victim_age'
            )
        """)
        
        cursor.execute("""
            UPDATE accident_column_config 
            SET tab = 'location_info' 
            WHERE tab IS NULL AND column_key IN (
                'accident_location', 'location_detail', 'building', 'floor'
            )
        """)
        
        _wa_ac = sql_is_active_true('is_active', conn)
        _wd_ac = sql_is_deleted_false('is_deleted', conn)
        cursor.execute(f"""
            UPDATE accident_column_config 
            SET tab = 'additional' 
            WHERE (tab IS NULL OR tab = '') 
              AND {_wa_ac}
              AND {_wd_ac}
        """)
        
        logging.info("컬럼 tab 매핑 업데이트 완료")
    except Exception as _e:
        logging.debug(f"Column config table ensure failed: {_e}")
        # PostgreSQL에서 트랜잭션 오류가 발생한 경우 롤백
        try:
            conn.rollback()
        except:
            pass
    
    # 메뉴 설정에서 페이지 자동 생성
    for category in MENU_CONFIG:
        for submenu in category['submenu']:
            cursor.execute("SELECT COUNT(*) FROM pages WHERE url = ?", (submenu['url'],))
            if cursor.fetchone()[0] == 0:
                cursor.execute(
                    "INSERT INTO pages (url, title, content) VALUES (?, ?, ?)",
                    (submenu['url'], submenu['title'], 
                     f"<h1>{submenu['title']}</h1><p>이 페이지의 내용을 편집하세요.</p>")
                )
    
    conn.commit()
    conn.close()
    
    # 샘플 데이터 초기화 (SEED_DUMMY=true일 때만)
    if db_config.config.getboolean('DEFAULT', 'SEED_DUMMY', fallback=False):
        init_sample_data()

    # 외부 DB 동기화 실행 (EXTERNAL_DB_ENABLED=True일 때만)
    if db_config.external_db_enabled:
        logging.info("외부 DB 동기화 시작...")
        try:
            from database_config import maybe_daily_sync
            maybe_daily_sync(force=False)  # 하루에 한 번만 동기화
        except Exception as e:
            logging.error(f"외부 DB 동기화 실패: {e}")
    else:
        logging.info("EXTERNAL_DB_ENABLED=False - 샘플 데이터만 사용")

def sync_all_master_data():
    """모든 마스터 데이터 동기화 함수 (스케줄러용)"""
    logging.info("=" * 50)
    logging.info(f"스케줄 동기화 시작: {get_korean_time_str()}")
    logging.info("=" * 50)
    
    try:
        # 외부 DB 활성화 확인
        external_db_enabled = partner_manager.config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED', fallback=False)
        
        if not external_db_enabled:
            logging.info("외부 DB가 비활성화되어 있어 동기화를 건너뜁니다.")
            return
        
        # 각 데이터 동기화
        sync_results = {
            '협력사': False,
            '사고': False,
            '임직원': False,
            '부서': False,
            '건물': False,
            '협력사 근로자': False
        }
        
        # 1. 협력사 데이터 동기화
        try:
            logging.info("협력사 데이터 동기화 중...")
            sync_results['협력사'] = partner_manager.sync_partners_from_external_db()
        except Exception as e:
            logging.error(f"협력사 동기화 오류: {e}")
        
        # 2. 사고 데이터 동기화
        try:
            if partner_manager.config.has_option('SQL_QUERIES', 'ACCIDENTS_QUERY'):
                logging.info("사고 데이터 동기화 중...")
                sync_results['사고'] = partner_manager.sync_accidents_from_external_db()
        except Exception as e:
            logging.error(f"사고 동기화 오류: {e}")
        
        # 3. 임직원 데이터 동기화
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'EMPLOYEE_QUERY'):
                logging.info("임직원 데이터 동기화 중...")
                sync_results['임직원'] = partner_manager.sync_employees_from_external_db()
        except Exception as e:
            logging.error(f"임직원 동기화 오류: {e}")
        
        # 4. 부서 데이터 동기화
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'DEPARTMENT_QUERY'):
                logging.info("부서 데이터 동기화 중...")
                sync_results['부서'] = partner_manager.sync_departments_from_external_db()
        except Exception as e:
            logging.error(f"부서 동기화 오류: {e}")
        
        # 5. 건물 데이터 동기화
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'BUILDING_QUERY'):
                logging.info("건물 데이터 동기화 중...")
                sync_results['건물'] = partner_manager.sync_buildings_from_external_db()
        except Exception as e:
            logging.error(f"건물 동기화 오류: {e}")
        
        # 6. 협력사 근로자 데이터 동기화
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'CONTRACTOR_QUERY'):
                logging.info("협력사 근로자 데이터 동기화 중...")
                sync_results['협력사 근로자'] = partner_manager.sync_contractors_from_external_db()
        except Exception as e:
            logging.error(f"협력사 근로자 동기화 오류: {e}")
        
        # 결과 로깅
        logging.info("=" * 50)
        logging.info("동기화 결과:")
        for name, result in sync_results.items():
            status = "✅ 성공" if result else "❌ 실패"
            logging.info(f"  {name}: {status}")
        logging.info("=" * 50)
        logging.info(f"스케줄 동기화 완료: {get_korean_time_str()}")
        logging.info("=" * 50)
        
    except Exception as e:
        logging.error(f"스케줄 동기화 중 전체 오류: {e}")

def run_scheduler():
    """스케줄러 실행 함수"""
    while True:
        schedule.run_pending()
        time.sleep(60)  # 1분마다 스케줄 체크

def init_sample_data():
    """외부 DB 없을 때 샘플 데이터 생성"""
    conn = partner_manager.db_config.get_sqlite_connection()
    cursor = conn.cursor()
    
    # 이미 데이터가 있는지 확인
    try:
        cursor.execute("SELECT COUNT(*) FROM partners_cache")
        count = cursor.fetchone()[0]
        
        # permanent_workers 컬럼이 있는지 확인
        cursor.execute("PRAGMA table_info(partners_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # permanent_workers 컬럼이 없으면 기존 데이터에 랜덤값 추가
        if 'permanent_workers' not in columns:
            logging.info("permanent_workers 컬럼이 없어서 기존 데이터에 값을 추가합니다")
            import random
            cursor.execute("SELECT business_number FROM partners_cache")
            existing_partners = cursor.fetchall()
            for partner in existing_partners:
                permanent_workers = random.randint(5, 500)
                cursor.execute("UPDATE partners_cache SET permanent_workers = ? WHERE business_number = ?", 
                             (permanent_workers, partner[0]))
            conn.commit()
            logging.info(f"기존 {len(existing_partners)}개 협력사에 상시근로자 데이터 추가 완료")
        
        # 데이터가 충분히 있으면 종료
        if count > 0:
            conn.close()
            return
    except Exception as e:
        logging.warning(f"데이터 확인 중 오류: {e}")
    
    logging.info("샘플 데이터 생성 중...")
    
    import random
    random.seed(42)  # 고정된 시드
    
    # 샘플 데이터 생성 로직 (기존과 동일)
    base_companies = [
        '삼성전자', 'LG전자', '현대자동차', 'SK하이닉스', 'POSCO홀딩스',
        '네이버', '카카오', '신한금융지주', '한국전력공사', 'KT',
        'LG화학', '현대중공업', '한화솔루션', 'SK텔레콤', '기아',
        '롯데케미칼', 'S-Oil', 'GS칼텍스', '두산에너빌리티', 'HD현대중공업'
    ]
    
    business_types_data = {
        '제조업': ['전자제품', '자동차', '기계', '화학', '섬유', '식품', '의약품', '철강', '플라스틱', '기타제조'],
        '건설업': ['건축공사', '토목공사', '전기공사', '통신공사', '설비공사', '조경공사', '인테리어', '기타건설'],
        'IT업': ['소프트웨어개발', '시스템통합', '데이터베이스', '네트워크', '보안', '게임개발', '웹개발', '모바일앱'],
        '서비스업': ['컨설팅', '교육', '의료', '법률', '회계', '인사', '마케팅', '디자인', '청소', '보안서비스'],
        '운수업': ['육상운송', '해상운송', '항공운송', '물류', '창고', '택배', '렌터카', '기타운송'],
        '유통업': ['도매', '소매', '전자상거래', '백화점', '마트', '편의점', '온라인쇼핑몰', '기타유통'],
        '금융업': ['은행', '증권', '보험', '카드', '리스', '투자', '자산관리', '핀테크'],
        '에너지업': ['전력', '가스', '석유', '신재생에너지', '원자력', '석탄', '기타에너지']
    }
    
    business_types = list(business_types_data.keys())
    certifications = ['ISO 9001', 'ISO 14001', 'ISO 45001', 'KS인증', 'GMP', 'HACCP', '없음']
    safety_ratings = ['A등급', 'B등급', 'C등급', 'D등급']
    products = ['전자부품', '자동차부품', '화학원료', '기계부품', '소프트웨어', '통신장비', '건설자재', '의료기기', '식품', '기타']
    
    # 203개 샘플 데이터 생성
    for i in range(203):
        if i < 20:
            company_name = f"{base_companies[i % len(base_companies)]}(주)"
            business_number = f"{100 + i:03d}81{random.randint(10000, 99999):05d}"
        else:
            company_name = f"협력업체{i-19:03d}(주)"
            business_number = f"{random.randint(100, 999)}81{random.randint(10000, 99999):05d}"
        
        representative = f"대표자{i+1:03d}"
        permanent_workers = random.randint(5, 500)  # 상시근로자 수 (5명~500명)
        partner_class = random.choice(['-', 'A', 'B', 'C'])
        
        business_type_major = random.choice(business_types)
        minor_count = random.randint(1, 2)
        selected_minors = random.sample(business_types_data[business_type_major], min(minor_count, len(business_types_data[business_type_major])))
        business_type_minor = ', '.join(selected_minors)
        
        hazard_work_flag = random.choice(['O', 'X', ''])  # O: 위험작업, X: 비위험작업, '': 미분류
        address = f"서울특별시 {random.choice(['강남구', '서초구', '송파구', '영등포구', '마포구', '종로구', '중구', '용산구'])} 샘플로{random.randint(1, 999)}"
        average_age = random.randint(25, 55)  # 평균 연령
        annual_revenue = random.randint(1, 1000) * 100000000  # 연매출 (억원 단위)
        transaction_count = random.randint(1, 50)  # 거래 차수
        
        cursor.execute('''
            INSERT INTO partners_cache (
                business_number, company_name, partner_class, business_type_major, 
                business_type_minor, hazard_work_flag, representative, address,
                average_age, annual_revenue, transaction_count, permanent_workers
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            business_number, company_name, partner_class, business_type_major,
            business_type_minor, hazard_work_flag, representative, address,
            average_age, annual_revenue, transaction_count, permanent_workers
        ))
        
        # 일부 협력사에 실제 존재하는 샘플 첨부파일 추가
        if i < 5:  # 처음 5개 협력사에만 추가
            # uploads 폴더에 실제 존재하는 파일들 사용
            real_files = [
                ('sample_for_you_1755663410.xlsx', 'uploads/sample_for_you_1755663410.xlsx', '샘플 엑셀 파일'),
                ('[Quick Guide] DS사업장 내방신청 v.03_1755666638.pdf', 'uploads/[Quick Guide] DS사업장 내방신청 v.03_1755666638.pdf', 'DS사업장 가이드'),
                ('[Quick Guide] 상생협력포털(PCMS) 회원가입 v.02_1755674307.pdf', 'uploads/[Quick Guide] 상생협력포털(PCMS) 회원가입 v.02_1755674307.pdf', 'PCMS 가입 가이드')
            ]
            
            # 하나의 실제 파일만 추가 (확실히 다운로드되도록)
            file_info = real_files[i % len(real_files)]
            file_path = os.path.join(os.getcwd(), file_info[1])
            
            # 파일이 실제로 존재하는지 확인
            if os.path.exists(file_path):
                file_size = os.path.getsize(file_path)
                cursor.execute('''
                    INSERT INTO partner_attachments (
                        business_number, file_name, file_path, file_size, description
                    ) VALUES (?, ?, ?, ?, ?)
                ''', (
                    business_number,
                    file_info[0],
                    file_path,  # 전체 경로로 저장
                    file_size,
                    file_info[2]
                ))
    
    conn.commit()
    conn.close()
    logging.info("샘플 데이터 생성 완료")


# ======================================================================
# 부트 동기화 훅 - 첫 요청시 한번만 실행
# ======================================================================
from flask import current_app

boot_sync_done = False

def boot_sync_once():
    """
    서버 프로세스가 어떤 방식으로 떠도(WSGI/리로더/워커), 첫 요청 들어올 때 1회 실행.
    - 마스터 데이터: 매일 1회
    - 컨텐츠 데이터: 최초 1회(또는 force)
    """
    global boot_sync_done
    if boot_sync_done:
        return
    boot_sync_done = True

    try:
        # 0) 항상 코어 스키마 보장 (pages 등 기본 테이블 생성)
        #    WSGI로 실행 시 __main__ 블록이 호출되지 않아 Postgres에서
        #    pages 등 기본 테이블이 없어지는 문제가 발생할 수 있음.
        #    idempotent하므로 안전하게 1회 실행한다.
        try:
            init_db()
        except Exception as _e:
            try:
                current_app.logger.error(f"[BOOT] init_db failed: {_e}")
            except Exception:
                pass

        from database_config import maybe_daily_sync_master, maybe_one_time_sync_content, db_config

        ext_on = db_config.config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED', fallback=False)
        init_on = db_config.config.getboolean('DATABASE', 'INITIAL_SYNC_ON_FIRST_REQUEST', fallback=False)
        current_app.logger.info(f"[BOOT] EXTERNAL_DB_ENABLED={ext_on}, INITIAL_SYNC_ON_FIRST_REQUEST={init_on}")

        # 필수 키 점검(빠르게 조기 경보)
        req_master = ['PARTNERS_QUERY','ACCIDENTS_QUERY','EMPLOYEE_QUERY','DEPARTMENT_QUERY','BUILDING_QUERY','CONTRACTOR_QUERY']
        missing_master = [k for k in req_master if not db_config.config.has_option('MASTER_DATA_QUERIES', k)]
        if missing_master:
            current_app.logger.warning(f"[BOOT] MASTER_DATA_QUERIES missing keys: {missing_master}")

        # 컨텐츠 쿼리는 옵션(있으면 사용)
        if not db_config.config.has_section('CONTENT_DATA_QUERIES'):
            current_app.logger.info("[BOOT] CONTENT_DATA_QUERIES section not found (skip content one-time sync)")

        if ext_on and init_on:
            # 1) 마스터: 매일 체크 → 필요 시 동기화
            if db_config.config.getboolean('DATABASE', 'MASTER_DATA_DAILY', fallback=True):
                current_app.logger.info("[BOOT] Master daily sync check...")
                maybe_daily_sync_master(force=False)  # 24시간 경과 시에만
                current_app.logger.info("[BOOT] Master daily sync done/kept")

            # 2) 컨텐츠: 최초 1회만
            if db_config.config.getboolean('DATABASE', 'CONTENT_DATA_ONCE', fallback=True):
                current_app.logger.info("[BOOT] Content one-time sync check...")
                maybe_one_time_sync_content(force=False)  # 최초 1회만
                current_app.logger.info("[BOOT] Content one-time sync done/kept")
        else:
            current_app.logger.info("[BOOT] Initial sync skipped (flag off or external off)")
    except Exception as e:
        current_app.logger.error(f"[BOOT] Initial sync error: {e}")

# Flask 2.3+ 호환 방식으로 첫 요청 훅 등록
@app.before_request
def check_first_request():
    if not hasattr(app, '_first_request_done'):
        app._first_request_done = True
        boot_sync_once()

@app.route("/api/test-simple")
def test_simple():
    return jsonify({"status": "ok"})

# ===== 검색 팝업 공통 API =====
@app.route("/api/search-popup/search", methods=["GET"])
def api_search_popup():
    """공통 검색 팝업 API"""
    search_type = request.args.get('type', 'company')
    search_field = request.args.get('value', '')  # 검색할 필드
    query = request.args.get('q', '')  # 검색어
    limit = int(request.args.get('limit', '50'))
    
    try:
        # SearchPopupService 사용
        search_service = SearchPopupService(DB_PATH)
        result = search_service.search(search_type, query, search_field, limit)
        
        return jsonify({
            'success': True,
            'results': result['results'],
            'total': result.get('total', len(result['results'])),
            'config': result.get('config', {})
        })
    except Exception as e:
        logging.error(f"Search popup API error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route("/api/search-popup/autocomplete", methods=["GET"])
def api_search_popup_autocomplete():
    """검색 팝업 자동완성 API"""
    search_type = request.args.get('type', 'company')
    query = request.args.get('query', '')
    
    try:
        # SearchPopupService 사용 (자동완성은 최대 10개만)
        search_service = SearchPopupService(DB_PATH)
        result = search_service.search(search_type, query, limit=10)
        
        # 자동완성 형식으로 변환
        config = search_service.search_configs.get(search_type, {})
        display_fields = config.get('display_fields', [])
        
        items = []
        for row in result['results'][:10]:
            # 첫 번째 필드를 메인으로, 나머지를 서브로
            if display_fields:
                main = row.get(display_fields[0], '')
                sub = ' | '.join([str(row.get(field, '')) for field in display_fields[1:] if row.get(field)])
                items.append({
                    'main': main,
                    'sub': sub,
                    'data': row
                })
        
        return jsonify({
            'success': True,
            'items': items
        })
    except Exception as e:
        logging.error(f"Autocomplete API error: {e}")
        return jsonify({
            'success': False,
            'items': []
        }), 500

@app.route("/")
def index():
    # 대시보드 설정 가져오기 (단순화)
    dashboard_config = {
        'url': db_config.config.get('DASHBOARD', 'DASHBOARD_URL', 
                                   fallback='https://your-dashboard.com'),
        'enabled': db_config.config.getboolean('DASHBOARD', 'DASHBOARD_ENABLED', 
                                              fallback=True)
    }
    return render_template("index.html", menu=MENU_CONFIG, dashboard_config=dashboard_config)

# ===== 검색 팝업 라우트 =====
@app.route("/search-popup")
def search_popup():
    """공통 검색 팝업"""
    search_type = request.args.get('type', 'company')
    callback = request.args.get('callback', 'handleSelection')
    
    # SearchPopupService 사용
    search_service = SearchPopupService(DB_PATH)
    
    # 설정 정보 가져오기
    config = search_service.search_configs.get(search_type, {})
    
    # search_fields를 search_options로 변환
    search_options = []
    if 'search_fields' in config:
        for field_info in config['search_fields']:
            search_options.append({
                'value': field_info['field'],
                'label': field_info['label']
            })
    
    # config에 필요한 URL 추가
    display_labels = config.get('display_labels', {})
    enhanced_config = {
        **config,
        'searchUrl': '/api/search-popup/search',
        'autocompleteUrl': '/api/search-popup/autocomplete',
        'callback': callback,
        'columns': [{'field': field, 'label': display_labels.get(field, field)} for field in config.get('display_fields', [])]
    }
    
    # 템플릿 렌더링을 시도하고, 실패하면 간단한 HTML 반환
    try:
        return render_template('search-popup.html',
                             search_type=search_type,
                             search_title=config.get('title', '검색'),
                             search_options=search_options,
                             placeholder=config.get('placeholder', '검색어를 입력하세요'),
                             config=enhanced_config,
                             menu=MENU_CONFIG)
    except:
        # 템플릿이 없으면 간단한 HTML 반환
        return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{result['config'].get('title', '검색')}</title>
        <style>
            body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; margin: 0; padding: 20px; background: #f5f5f5; }}
            .search-container {{ background: white; border-radius: 8px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
            h2 {{ margin-top: 0; color: #333; }}
            .search-box {{ display: flex; gap: 10px; margin-bottom: 20px; }}
            input[type="text"] {{ flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 4px; font-size: 14px; }}
            button {{ padding: 10px 20px; background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
            button:hover {{ background: #0056b3; }}
            .results {{ max-height: 400px; overflow-y: auto; }}
            .result-item {{ padding: 12px; border-bottom: 1px solid #eee; cursor: pointer; transition: background 0.2s; }}
            .result-item:hover {{ background: #f8f9fa; }}
            .result-item:last-child {{ border-bottom: none; }}
            .no-results {{ text-align: center; color: #666; padding: 20px; }}
            .field-label {{ font-size: 12px; color: #666; }}
            .field-value {{ font-size: 14px; color: #333; margin-top: 2px; }}
        </style>
    </head>
    <body>
        <div class="search-container">
            <h2>{result['config'].get('title', '검색')}</h2>
            <form class="search-box" method="get">
                <input type="hidden" name="type" value="{search_type}">
                <input type="hidden" name="callback" value="{callback}">
                <select name="search_field" style="padding: 10px; border: 1px solid #ddd; border-radius: 4px; margin-right: 5px;">
                    {"".join([f'<option value="{field["field"] if isinstance(field, dict) else field}" {"selected" if (search_field == (field["field"] if isinstance(field, dict) else field)) or (not search_field and (field["field"] if isinstance(field, dict) else field) == result["config"].get("default_search_field")) else ""}>{field["label"] if isinstance(field, dict) else field}</option>' for field in result["config"].get("search_fields", [])])}
                </select>
                <input type="text" name="q" value="{query}" placeholder="{result['config'].get('placeholder', '검색어를 입력하세요')}" autofocus>
                <button type="submit">검색</button>
            </form>
            <div class="results">
                {"".join([f'''
                <div class="result-item" onclick="selectItem('{row.get(result['config']['id_field'])}', '{row.get(result['config']['display_fields'][0])}')">
                    {"".join([f'<div><span class="field-label">{field}:</span> <div class="field-value">{row.get(field, "")}</div></div>' for field in result['config'].get('display_fields', [])])}
                </div>
                ''' for row in result['results']]) if result['results'] else '<div class="no-results">검색 결과가 없습니다.</div>'}
            </div>
        </div>
        <script>
            function selectItem(id, name) {{
                if (window.opener && !window.opener.closed) {{
                    if (window.opener.{callback}) {{
                        window.opener.{callback}(id, name);
                    }}
                    window.close();
                }} else {{
                    alert('부모 창을 찾을 수 없습니다.');
                }}
            }}
        </script>
    </body>
    </html>
    """

# 개별 라우트들을 catch-all 라우트보다 먼저 정의
@app.route("/partner-standards")
def partner_standards_route():
    """협력사 기준정보 페이지 라우트"""
    return partner_standards()

@app.route("/partner-change-request")
def partner_change_request_route():
    """기준정보 변경요청 페이지 라우트"""
    return partner_change_request()

@app.route("/change-request-detail/<int:request_id>")
def change_request_detail_route(request_id):
    """변경요청 상세정보 페이지 라우트"""
    return change_request_detail(request_id)

@app.route("/accident")
def accident_route():
    """사고 메인 페이지 라우트"""
    return accident()

def accident():
    """사고 목록 페이지 (메인)"""
    from common_mapping import smart_apply_mappings
    import math
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'accident_date_start': request.args.get('accident_date_start'),
        'accident_date_end': request.args.get('accident_date_end'),
        'workplace': request.args.get('workplace', '').strip(),
        'accident_grade': request.args.get('accident_grade', '').strip()
    }
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 섹션 정보 가져오기 (단일 소스: section_config via SectionConfigService)
    from section_service import SectionConfigService
    section_service = SectionConfigService('accident', DB_PATH)
    sections = section_service.get_sections() or []
    
    # 동적 컬럼 설정 가져오기
    _wa3 = sql_is_active_true('is_active', conn)
    _wd3 = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(
        f"""
        SELECT * FROM accident_column_config 
        WHERE {_wa3} AND {_wd3}
        ORDER BY column_order
        """
    ).fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]

    # 정렬 일관성 보장: 섹션 순서(section_order) → 섹션 내 column_order → id
    try:
        sec_order_map = {s['section_key']: int(s.get('section_order') or 0) for s in sections}
        def _to_int(v):
            try:
                return int(v)
            except Exception:
                return 0
        def _sort_key(c):
            so = sec_order_map.get(c.get('tab'), 999)
            co = _to_int(c.get('column_order'))
            cid = _to_int(c.get('id'))
            return (so, co, cid)
        dynamic_columns.sort(key=_sort_key)
    except Exception:
        pass

    # 키 집합은 활성/비활성 모두 포함하여 그룹 추론에 사용 (렌더는 활성만)
    try:
        _wd4 = sql_is_deleted_false('is_deleted', conn)
        all_keys_rows = conn.execute(
            f"SELECT column_key FROM accident_column_config WHERE {_wd4}"
        ).fetchall()
        all_keys = {r[0] if isinstance(r, (list, tuple)) else (r['column_key'] if 'column_key' in r.keys() else None) for r in all_keys_rows}
        all_keys = {k for k in all_keys if k}
    except Exception:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}

    # Normalize table/popup types for base columns using sibling keys
    try:
        suffixes = ['_id', '_dept', '_bizno', '_business_number', '_code', '_company']
        def base_key_of(key: str) -> str:
            if not isinstance(key, str):
                return ''
            for s in suffixes:
                if key.endswith(s):
                    return key[:-len(s)]
            return key
        key_set = all_keys
        # Determine group by presence of sibling suffix keys (across all sections)
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            # support irregular 'd' variant like incharge -> incharged_code
            variants = [bk, bk + 'd']
            if any(((v + '_bizno') in key_set) or ((v + '_business_number') in key_set) for v in variants):
                return 'company'
            if any((v + '_dept') in key_set for v in variants):
                return 'person'
            if any((v + '_code') in key_set for v in variants):
                return 'department'
            if any((v + '_company') in key_set for v in variants):
                return 'contractor'
            return ''
        popup_map = {
            'person': 'popup_person',
            'company': 'popup_company',
            'department': 'popup_department',
            'contractor': 'popup_contractor',
        }
        for col in dynamic_columns:
            ck = col.get('column_key')
            ct = col.get('column_type')
            bk = base_key_of(ck)
            grp = infer_group(bk)
            # Base column: exact base key and has a recognized group
            if grp and ck == bk:
                if not ct or ct in ('text', 'popup', 'table', 'table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                # Mark as table input for robust rendering
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.error(f"accident_detail: normalize popup types failed: {_e}")
    
    # 섹션 키 정규화: 잘못된/없음(tab) → 유효 섹션으로 귀속 (목록도 동일 기준)
    try:
        known_keys = {s.get('section_key') for s in sections if s.get('section_key')}
        alias_map = {'violation_info': 'accident_info'}
        fallback_key = (
            ('additional' if 'additional' in known_keys else None)
            or ('basic_info' if 'basic_info' in known_keys else None)
            or (next(iter(known_keys)) if known_keys else None)
        )
        for col in dynamic_columns:
            tab = col.get('tab')
            if tab in alias_map and alias_map[tab] in known_keys:
                col['tab'] = alias_map[tab]
                tab = col['tab']
            if not tab or tab not in known_keys:
                if fallback_key:
                    col['tab'] = fallback_key
    except Exception as _e:
        logging.warning(f"섹션 키 정규화(목록) 경고: {_e}")

    # 섹션별로 컬럼 그룹핑
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns 
            if col.get('tab') == section['section_key'] 
            and col['column_key'] not in ['detailed_content']
        ]
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 정보 추가
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            col['code_mapping'] = get_dropdown_options_for_display('accident', col['column_key'])
    
    # 사고 목록 조회
    _wd5 = sql_is_deleted_false('is_deleted', conn)
    query = f"""
        SELECT * FROM accidents_cache 
        WHERE {_wd5}
    """
    params = []
    
    # 필터링 적용
    if filters['accident_date_start']:
        query += " AND accident_date >= %s"
        params.append(filters['accident_date_start'])
    
    if filters['accident_date_end']:
        query += " AND accident_date <= %s"
        params.append(filters['accident_date_end'])
    
    if filters['workplace']:
        query += " AND workplace LIKE %s"
        params.append(f"%{filters['workplace']}%")
    
    if filters['accident_grade']:
        query += " AND accident_grade LIKE %s"
        params.append(f"%{filters['accident_grade']}%")
    
    # 정렬 컬럼(report_date)은 초기화 단계에서 보장되어야 함. 요청 중 DDL 금지.

    query += " ORDER BY (report_date IS NULL) ASC, report_date DESC, created_at DESC, accident_number DESC"
    
    # 전체 건수 조회 (ORDER BY 제거 후 COUNT)
    import re as _re
    count_query = _re.sub(r"ORDER BY[\s\S]*$", "", query, flags=_re.IGNORECASE)
    count_query = count_query.replace("SELECT *", "SELECT COUNT(*)")
    total_count = conn.execute(count_query, tuple(params)).fetchone()[0]
    
    # 페이징 적용
    offset = (page - 1) * per_page
    query += f" LIMIT {per_page} OFFSET {offset}"
    
    accidents_rows = conn.execute(query, tuple(params)).fetchall()
    accidents = []
    
    for idx, row in enumerate(accidents_rows):
        accident = dict(row)
        accident['no'] = total_count - offset - idx
        
        # 안전 병합: custom_data를 파싱하여 빈값 미덮어쓰기 + K사고 기본필드 보호
        if accident.get('custom_data'):
            try:
                if isinstance(accident['custom_data'], dict):
                    custom_data = accident['custom_data']
                else:
                    custom_data = json.loads(accident['custom_data'])
                # ensure dict form is available to templates and later fallbacks
                accident['custom_data'] = custom_data
                # Ensure fallback reads parsed dict, not raw string
                accident['custom_data'] = custom_data

                def _is_empty(v):
                    try:
                        if v is None:
                            return True
                        if isinstance(v, str) and v.strip() == '':
                            return True
                        return False
                    except Exception:
                        return False

                protected_keys_for_k = {
                    'accident_number','accident_name','workplace','accident_grade','major_category',
                    'injury_form','injury_type','building','floor','location_category','location_detail',
                    'accident_date','created_at','report_date','day_of_week',
                    'responsible_company1','responsible_company1_no','responsible_company2','responsible_company2_no'
                }

                acc_no = str(accident.get('accident_number') or '')
                is_direct = acc_no.startswith('ACC')

                safe_updates = {}
                for k, v in custom_data.items():
                    if _is_empty(v):
                        continue
                    if k in protected_keys_for_k:
                        if not is_direct:
                            # K사고: 기본 필드 보호
                            continue
                        # ACC: 상위가 비어 있을 때만 보완
                        if _is_empty(accident.get(k)):
                            safe_updates[k] = v
                    else:
                        safe_updates[k] = v

                if safe_updates:
                    accident.update(safe_updates)
            except Exception as e:
                print(f"Error parsing/merging custom_data: {e}")
        
        # K사고와 A사고 구분해서 등록일 필드 설정
        accident_number = accident.get('accident_number', '')
        if accident_number.startswith('K'):
            # K사고는 report_date를 등록일로 사용
            accident['display_created_at'] = accident.get('report_date', accident.get('created_at', '-'))
        else:
            # ACC사고는 created_at을 등록일로 사용
            accident['display_created_at'] = accident.get('created_at', '-')
        
        # accident_name 최종 폴백 (parsed custom_data 우선)
        if not accident.get('accident_name'):
            nm = None
            try:
                cd = accident.get('custom_data')
                if isinstance(cd, dict):
                    nm = cd.get('accident_name')
            except Exception:
                nm = None
            accident['accident_name'] = (nm if (nm and str(nm).strip()) else '-')
        
        accidents.append(accident)
    
    # 드롭다운 매핑 (리스트 전체 기준) - 상단 분기에서도 동일하게 적용
    try:
        from common_mapping import smart_apply_mappings as _smart_map
        accidents = _smart_map(accidents, 'accident', dynamic_columns, DB_PATH)
    except Exception as _e:
        logging.error(f"accident mapping error(top): {_e}")
    conn.close()
    
    # 페이지네이션 객체 (다른 보드와 동일한 인터페이스)
    class Pagination:
        def __init__(self, page, per_page, total_count):
            import math as _math
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = _math.ceil(total_count / per_page) if total_count > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page, per_page, total_count)
    
    return render_template('partner-accident.html',  # 동일한 템플릿 사용
                         accidents=accidents,
                         dynamic_columns=dynamic_columns,
                         sections=sections,
                         section_columns=section_columns,
                         pagination=pagination,
                         search_params=filters,
                         total_count=total_count,
                         menu=MENU_CONFIG)

@app.route("/partner-accident")
def partner_accident_route():
    """구경로 호환: /accident로 리다이렉트"""
    return redirect(url_for('accident_route'))

def partner_accident():
    """협력사 사고 목록 페이지"""
    from common_mapping import smart_apply_mappings
    import math
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'accident_date_start': request.args.get('accident_date_start'),
        'accident_date_end': request.args.get('accident_date_end'),
        'workplace': request.args.get('workplace', '').strip(),
        'accident_grade': request.args.get('accident_grade', '').strip()
    }
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 섹션 정보 가져오기 (단일 소스: section_config via SectionConfigService)
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        sections = section_service.get_sections() or []
    except Exception as _e:
        logging.error(f"섹션 로드 실패, 기본값 사용: {_e}")
        sections = []
    
    # 동적 컬럼 설정 가져오기 (활성화되고 삭제되지 않은 것만)
    _wa3 = sql_is_active_true('is_active', conn)
    _wd3 = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(
        f"""
        SELECT * FROM accident_column_config 
        WHERE {_wa3} AND {_wd3}
        ORDER BY column_order
        """
    ).fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]

    # 전역 키(활성/비활성 포함) 수집 - 상세 화면 팝업 타입 보정에 사용
    try:
        _wd4 = sql_is_deleted_false('is_deleted', conn)
        _all_keys_rows = conn.execute(
            f"SELECT column_key FROM accident_column_config WHERE {_wd4}"
        ).fetchall()
        all_keys = set()
        for r in _all_keys_rows:
            try:
                all_keys.add(r['column_key'])
            except Exception:
                try:
                    all_keys.add(r[0])
                except Exception:
                    pass
        all_keys = {k for k in all_keys if k}
    except Exception:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
    
    # 섹션별로 컬럼 그룹핑 (detailed_content 제외)
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns 
            if col.get('tab') == section['section_key'] 
            and col['column_key'] not in ['detailed_content']
        ]
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 정보 추가
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            col['code_mapping'] = get_dropdown_options_for_display('accident', col['column_key'])
    
    # 사고 목록 조회
    _wd5 = sql_is_deleted_false('is_deleted', conn)
    query = f"""
        SELECT * FROM accidents_cache 
        WHERE {_wd5}
    """
    params = []
    
    # 필터링 적용
    if filters['accident_date_start']:
        query += " AND accident_date >= %s"
        params.append(filters['accident_date_start'])
    
    if filters['accident_date_end']:
        query += " AND accident_date <= %s"
        params.append(filters['accident_date_end'])
    
    if filters['workplace']:
        query += " AND workplace LIKE %s"
        params.append(f"%{filters['workplace']}%")
    
    if filters['accident_grade']:
        query += " AND accident_grade LIKE %s"
        params.append(f"%{filters['accident_grade']}%")
    
    # 전체 개수 조회 (ORDER BY 제거 후 COUNT)
    import re as _re
    count_query = _re.sub(r"ORDER BY[\s\S]*$", "", query, flags=_re.IGNORECASE)
    count_query = count_query.replace("SELECT *", "SELECT COUNT(*)")
    total_count = conn.execute(count_query, params).fetchone()[0]
    
    # ORDER BY는 데이터 조회시에만 추가 - created_at 기준으로 최신순 정렬
    # 정렬 컬럼(report_date)은 초기화 단계에서 보장되어야 함. 요청 중 DDL 금지.

    query += " ORDER BY (report_date IS NULL) ASC, report_date DESC, created_at DESC, accident_number DESC"
    
    # 페이지네이션 적용
    query += f" LIMIT {per_page} OFFSET {(page - 1) * per_page}"
    accidents = conn.execute(query, params).fetchall()
    accidents = [dict(row) for row in accidents]
    
    # No 컬럼 추가 (역순 번호)
    offset = (page - 1) * per_page
    for i, accident in enumerate(accidents):
        accident['no'] = total_count - offset - i
        
        # custom_data 파싱 및 플래튼 (PostgreSQL JSONB vs SQLite JSON 호환)
        if accident.get('custom_data'):
            try:
                import json as pyjson
                
                # PostgreSQL JSONB는 이미 dict로 반환됨, SQLite는 JSON 문자열
                if isinstance(accident['custom_data'], dict):
                    custom_data = accident['custom_data']
                else:
                    custom_data = pyjson.loads(accident['custom_data'])
                
                # accident_name이 이미 있으면 custom_data의 빈 값으로 덮어쓰지 않음
                if 'accident_name' in custom_data and not custom_data['accident_name']:
                    del custom_data['accident_name']
                
                accident.update(custom_data)  # 최상위 레벨에 병합
            except Exception as e:
                logging.error(f"custom_data 파싱 오류: {e}")
    
    conn.close()
    
    # smart_apply_mappings 적용 (드롭다운 코드를 라벨로 변환)
    if accidents:
        from common_mapping import smart_apply_mappings
        accidents = smart_apply_mappings(accidents, 'accident', dynamic_columns, DB_PATH)
    
    # 페이지네이션 객체 생성
    import math
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page) if total_count > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page, per_page, total_count)
    
    return render_template('partner-accident.html',
                         accidents=accidents,
                         total_count=total_count,
                         pagination=pagination,
                         sections=sections,
                         section_columns=section_columns,
                         dynamic_columns=dynamic_columns,
                         menu=MENU_CONFIG)

@app.route("/safety-instruction")
def safety_instruction_route():
    """환경안전 지시서 페이지 라우트"""
    from common_mapping import smart_apply_mappings
    import math
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip(),
        'violation_date_from': request.args.get('violation_date_from'),
        'violation_date_to': request.args.get('violation_date_to')
    }
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 섹션 정보 가져오기 (safety_instruction 전용, 삭제되지 않은 것만)
    # 먼저 safety_instruction_sections 테이블 사용 시도, 없으면 section_config 사용
    try:
        _wa = sql_is_active_true('is_active', conn)
        _wd = sql_is_deleted_false('is_deleted', conn)
        sections = conn.execute(f"""
            SELECT * FROM safety_instruction_sections 
            WHERE {_wa}
              AND {_wd}
            ORDER BY section_order
        """).fetchall()
        sections = [dict(row) for row in sections]
    except Exception as e:
        # PostgreSQL 트랜잭션 오류 처리
        conn.close()
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        try:
            # safety_instruction_sections 테이블이 없으면 section_config 사용
            _wa2 = sql_is_active_true('is_active', conn)
            _wd2 = sql_is_deleted_false('is_deleted', conn)
            sections = conn.execute(f"""
                SELECT * FROM section_config 
                WHERE board_type = 'safety_instruction' AND {_wa2}
                  AND {_wd2}
                ORDER BY section_order
            """).fetchall()
            sections = [dict(row) for row in sections]
        except:
            # 둘 다 실패하면 빈 리스트
            sections = []
    
    # 동적 컬럼 설정 가져오기 (활성화되고 삭제되지 않은 것만)
    _wa3 = sql_is_active_true('is_active', conn)
    _wd3 = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(f"""
        SELECT * FROM safety_instruction_column_config 
        WHERE {_wa3} AND {_wd3}
        ORDER BY column_order
    """).fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # 섹션별로 컬럼 그룹핑 (detailed_content와 violation_content 제외)
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns 
            if col.get('tab') == section['section_key'] 
            and col['column_key'] not in ['detailed_content', 'violation_content']
        ]
    
    # tab이 None인 컬럼들은 추가하지 않음 (관리자가 섹션을 지정하지 않은 컬럼은 표시하지 않음)
    
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 정보 추가
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            col['code_mapping'] = get_dropdown_options_for_display('safety_instruction', col['column_key'])
    
    # 메인 테이블에서 직접 조회 (삭제되지 않은 것만)
    base_query = f"SELECT * FROM safety_instructions WHERE {sql_is_deleted_false('is_deleted', conn)}"
    query = base_query
    params = []
    
    # 필터링 적용
    if filters['company_name']:
        query += " AND (primary_company LIKE ? OR subcontractor LIKE ?)"
        params.extend([f"%{filters['company_name']}%", f"%{filters['company_name']}%"])
    
    if filters['business_number']:
        query += " AND (primary_business_number LIKE ? OR subcontractor_business_number LIKE ?)"
        params.extend([f"%{filters['business_number']}%", f"%{filters['business_number']}%"])
    
    if filters['violation_date_from']:
        # JSON 필드에서 날짜 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            query += " AND (custom_data->>'violation_date') >= %s"
        else:
            query += " AND json_extract(custom_data, '$.violation_date') >= ?"
        params.append(filters['violation_date_from'])
    
    if filters['violation_date_to']:
        # JSON 필드에서 날짜 검색 (Postgres/SQLite 분기)
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            query += " AND (custom_data->>'violation_date') <= %s"
        else:
            query += " AND json_extract(custom_data, '$.violation_date') <= ?"
        params.append(filters['violation_date_to'])
    
    # 전체 개수 조회 (ORDER BY 전에 실행)
    # SELECT 절을 COUNT(*)로 교체 (컬럼 리스트가 있는 경우도 처리)
    count_query = query
    if "SELECT" in count_query.upper():
        # FROM 앞까지의 SELECT 절을 COUNT(*)로 교체
        from_index = count_query.upper().find("FROM")
        if from_index > 0:
            count_query = "SELECT COUNT(*) " + count_query[from_index:]
    
    result = conn.execute(count_query, params).fetchone()
    total_count = int(result[0]) if result and result[0] is not None else 0
    
    # 정렬 (최신순) - NULL을 마지막으로
    query += " ORDER BY created_at DESC NULLS LAST, issue_number DESC"
    
    # 페이지네이션 적용
    query += f" LIMIT {per_page} OFFSET {(page - 1) * per_page}"
    
    # 데이터 조회
    safety_instructions = conn.execute(query, params).fetchall()
    safety_instructions = [dict(row) for row in safety_instructions]
    
    # No 컬럼 추가 (역순 번호)
    offset = (page - 1) * per_page
    for i, instruction in enumerate(safety_instructions):
        instruction['no'] = total_count - offset - i
        
        # custom_data 파싱 및 플래튼
        if instruction.get('custom_data'):
            try:
                import json as pyjson
                raw = instruction.get('custom_data')
                
                # dict/str 분기 처리
                if isinstance(raw, dict):
                    custom_data = raw
                elif isinstance(raw, str):
                    custom_data = pyjson.loads(raw) if raw else {}
                else:
                    custom_data = {}
                    
                # 기본 필드를 보호하면서 custom_data 병합
                BASE_FIELDS = {'issue_number', 'created_at', 'updated_at', 'is_deleted', 'synced_at', 'no'}
                for k, v in custom_data.items():
                    if k not in BASE_FIELDS:
                        instruction[k] = v
            except Exception as e:
                logging.error(f"Custom data parsing error: {e}")
                pass

        # 키 호환 레이어 적용 (구/신 키 양방향 보완)
        try:
            def _alias_fill_row(d, pairs):
                for old, new in pairs:
                    if old in d and (new not in d or d.get(new) in (None, '')):
                        d[new] = d[old]
                    if new in d and (old not in d or d.get(old) in (None, '')):
                        d[old] = d[new]

            _alias_fill_row(instruction, [
                ('issuer_department', 'issuer_dept'),
                ('discipline_department', 'issuer_incharge_dept'),
                ('primary_business_number', 'primary_company_bizno'),
                ('primary_company_business_number', 'primary_company_bizno'),
                ('primary_business_number', 'primary_bizno'),
                ('primary_company_bizno', 'primary_bizno'),
                ('secondary_company_business_number', 'secondary_company_bizno'),
                ('subcontractor_business_number', 'subcontractor_bizno'),
            ])
        except Exception:
            pass
    
    # smart_apply_mappings 적용 (드롭다운 코드를 라벨로 변환)
    if safety_instructions:
        safety_instructions = smart_apply_mappings(
            safety_instructions, 
            'safety_instruction', 
            dynamic_columns,
            DB_PATH
        )
    
    # 페이지네이션 객체 생성
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page) if total_count > 0 else 1
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page, per_page, total_count)
    conn.close()
    
    return render_template('safety-instruction.html',
                         safety_instructions=safety_instructions,
                         total_count=total_count,
                         sections=sections,
                         section_columns=section_columns,
                         dynamic_columns=dynamic_columns,
                         filters=filters,
                         pagination=pagination,
                         menu=MENU_CONFIG)

@app.route("/safety-instruction-register")
def safety_instruction_register():
    """환경안전 지시서 등록 페이지"""
    logging.info("환경안전 지시서 등록 페이지 접근")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 동적 컬럼 설정 가져오기 (safety_instruction 전용 테이블 사용)
    _wa = sql_is_active_true('is_active', conn)
    _wd = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(f"""
        SELECT * FROM safety_instruction_column_config 
        WHERE {_wa} AND {_wd}
        ORDER BY column_order
    """).fetchall()
    
    # Row 객체를 딕셔너리로 변환
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # column_span을 정수로 변환
    for col in dynamic_columns:
        if col.get('column_span'):
            col['column_span'] = int(col['column_span'])
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # 코드-값 매핑 방식으로 옵션 가져오기
            code_options = get_dropdown_options_for_display('safety_instruction', col['column_key'])
            # 코드-값 매핑 방식 사용 (DB dropdown_option_codes_v2 테이블)
            col['dropdown_options_mapped'] = code_options if code_options else []
    
    # 기본정보 드롭다운 옵션 로드 (accident-register와 동일한 패턴)
    basic_options = {}
    from board_services import CodeService
    code_service = CodeService('safety_instruction', DB_PATH)
    
    # 기본정보 필드들의 드롭다운 옵션 로드
    basic_fields = [
        'classification',           # 분류
        'employment_type',          # 고용형태
        'discipline_type',          # 징계유형
        'accident_type',            # 사고유형
        'accident_grade',           # 사고등급
        'safety_violation_grade',   # 환경안전수칙 위반등급
        'violation_type',           # 위반유형
        'work_grade'                # 작업등급
    ]
    
    for field in basic_fields:
        codes = code_service.list(field)
        # 템플릿이 기대하는 형식으로 변환 (option_code -> code, option_value -> value)
        if codes and len(codes) > 0 and 'option_code' in codes[0]:
            codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
        basic_options[field] = codes
        logging.info(f"드롭다운 옵션 로드: {field} -> {len(codes)}개")
    
    conn.close()
    
    logging.info(f"동적 컬럼 {len(dynamic_columns)}개 로드됨")
    logging.info(f"기본 옵션 {len(basic_options)}개 필드 로드됨")
    
    # 동적 컬럼 타입 보정: 링크드/팝업 추론 (discipline(d)_person* 등)
    try:
        # 전역 키 수집
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
        suffixes = ['_id','_dept','_department','_department_code','_bizno','_company_bizno','_business_number','_code','_company']

        def base_key_of(key: str) -> str:
            if not isinstance(key, str):
                return ''
            for s in suffixes:
                if key.endswith(s):
                    return key[:-len(s)]
            return key

        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk + 'd']  # 오타/변형 케이스 지원(disciplined vs displined)
            # 특수 규칙: 징계대상자는 기본 contractor로 간주
            if bk in {'disciplined_person'}:
                return 'contractor'
            # 협력사 근로자 그룹 우선 (회사명 키 존재)
            if any(((v + '_company') in all_keys) for v in variants):
                return 'contractor'
            # 사람/ID 그룹
            if any(((v + '_id') in all_keys) for v in variants):
                return 'person'
            # 회사 그룹: *_bizno, *_company_bizno
            if any(((v + '_company_bizno') in all_keys) or ((v + '_bizno') in all_keys) or ((v + '_business_number') in all_keys) for v in variants):
                return 'company'
            # 부서 그룹
            if any(((v + '_dept') in all_keys) or ((v + '_department') in all_keys) or ((v + '_department_code') in all_keys) for v in variants):
                return 'department'
            return ''

        popup_map = {
            'person': 'popup_person',
            'company': 'popup_company',
            'department': 'popup_department',
            'contractor': 'popup_contractor',
        }

        for col in dynamic_columns:
            ck = col.get('column_key') or ''
            bk = base_key_of(ck)
            grp = infer_group(bk)
            # 보조(링크드) 필드 렌더링 힌트 부여
            if ck.endswith('_id') or ck.endswith('_company') or ck.endswith('_company_bizno') or ck.endswith('_bizno') or ck.endswith('_business_number'):
                col['column_type'] = 'linked_text'
                continue
            if ck.endswith('_dept') or ck.endswith('_department') or ck.endswith('_department_code'):
                col['column_type'] = 'linked_dept'
                continue
            # 베이스 필드에 팝업 타입 지정
            if grp and ck == bk:
                ct = col.get('column_type')
                if not ct or ct in ('text','popup','table','table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                # 입력 타입 힌트
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.warning(f"safety_instruction register: normalize types failed: {_e}")

    # 섹션 정보 로드
    from section_service import SectionConfigService
    section_service = SectionConfigService('safety_instruction', DB_PATH)
    sections = section_service.get_sections()
    logging.info(f"섹션 {len(sections)}개 로드됨")
    
    # 섹션별로 컬럼 분류 (동적)
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns if col.get('tab') == section['section_key']
        ]
        logging.info(f"섹션 '{section['section_name']}': {len(section_columns[section['section_key']])}개 컬럼")
    
    # 하위 호환성을 위한 변수 유지 (템플릿이 아직 하드코딩된 경우)
    basic_info_columns = section_columns.get('basic_info', [])
    violation_info_columns = section_columns.get('violation_info', [])
    additional_columns = section_columns.get('additional', [])
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    # 현재 날짜 추가 (한국 시간)
    # 상단에서 이미 get_korean_time을 임포트함. 함수 내부 재임포트로 인한
    # UnboundLocalError를 방지하기 위해 재임포트를 제거한다.
    today_date = get_korean_time().strftime('%Y-%m-%d')
    
    return render_template('safety-instruction-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,  # 섹션 정보 추가
                         section_columns=section_columns,  # 섹션별 컬럼 추가
                         basic_info_columns=basic_info_columns,  # 하위 호환성
                         violation_info_columns=violation_info_columns,  # 하위 호환성
                         additional_columns=additional_columns,  # 하위 호환성
                         basic_options=basic_options,  # basic_options 추가
                         today_date=today_date,  # 오늘 날짜 추가
                         menu=MENU_CONFIG,
                         is_popup=is_popup)

@app.route("/safety-instruction-detail/<issue_number>")
def safety_instruction_detail(issue_number):
    """환경안전 지시서 상세정보 페이지"""
    # json already imported globally
    logging.info(f"환경안전 지시서 상세 정보 조회: {issue_number}")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 실제 데이터베이스에서 조회 시도 (메인 테이블 우선)
    instruction = None
    try:
        _wd = sql_is_deleted_false('is_deleted', conn)
        instruction = conn.execute(f"""
            SELECT * FROM safety_instructions 
            WHERE issue_number = ? AND {_wd}
        """, (issue_number,)).fetchone()
    except sqlite3.OperationalError:
        # 테이블이 없는 경우 더미 데이터 사용
        logging.info("safety_instructions 테이블이 없음 - 더미 데이터 사용")
        instruction = None
    
    # if not instruction:
    #     # 더미 데이터에서 찾기 (개발 중이므로)
    #     # safety-instruction 라우트와 동일한 더미 데이터 사용
    #     month_counters = {}
    #     all_instructions = []
        
    #     for i in range(30):
    #         year = 2024
    #         month = (i % 12) + 1
    #         year_month = f'{year}-{month:02d}'
            
    #         if year_month not in month_counters:
    #             month_counters[year_month] = 0
    #         month_counters[year_month] += 1
            
    #         dummy_issue_number = f'{year_month}-{month_counters[year_month]:02d}'
            
    #         if dummy_issue_number == issue_number:
    #             classifications = ['환경', '안전', '보건', '품질']
    #             employment_types = ['정규직', '계약직', '파견직', '임시직']
    #             discipline_types = ['경고', '견책', '정직', '출입정지']
    #             violation_types = ['작업절차위반', '안전장비미착용', '무단작업', '환경오염']
    #             accident_types = ['추락', '협착', '절단', '화재', '누출']
    #             grades = ['경미', '일반', '중대', '치명']
                
    #             instruction_data = {
    #                 'id': i + 1,
    #                 'issue_number': dummy_issue_number,
    #                 'issuer': f'발행인{i+1}',
    #                 'issuer_department': f'안전관리팀{(i % 3) + 1}',
    #                 'classification': classifications[i % 4],
    #                 'employment_type': employment_types[i % 4],
    #                 'primary_company': f'협력사{(i % 20) + 1}',
    #                 'primary_business_number': f'{1000000000 + i * 11111}',
    #                 'subcontractor': f'하도급사{(i % 10) + 1}' if i % 3 == 0 else '-',
    #                 'subcontractor_business_number': f'{2000000000 + i * 22222}' if i % 3 == 0 else '-',
    #                 'disciplined_person': f'징계자{i+1}',
    #                 'gbm': f'GBM{(i % 5) + 1}',
    #                 'business_division': f'사업부{(i % 4) + 1}',
    #                 'team': f'팀{(i % 8) + 1}',
    #                 'department': f'부서{(i % 6) + 1}',
    #                 'violation_date': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d}',
    #                 'discipline_date': f'2024-{(i % 12) + 1:02d}-{((i % 28) + 2):02d}',
    #                 'discipline_department': f'징계발의부서{(i % 3) + 1}',
    #                 'discipline_type': discipline_types[i % 4],
    #                 'accident_type': accident_types[i % 5],
    #                 'accident_grade': grades[i % 4],
    #                 'safety_violation_grade': grades[i % 4],
    #                 'violation_type': violation_types[i % 4],
    #                 'violation_content': f'위반내용 상세설명 {i+1}번 항목',
    #                 'access_ban_start_date': f'2024-{(i % 12) + 1:02d}-{((i % 28) + 3):02d}' if i % 4 == 0 else '-',
    #                 'access_ban_end_date': f'2024-{(i % 12) + 1:02d}-{((i % 28) + 10):02d}' if i % 4 == 0 else '-',
    #                 'period': f'{(i % 30) + 1}일' if i % 4 == 0 else '-',
    #                 'work_grade': f'등급{(i % 5) + 1}',
    #                 'penalty_points': (i % 10) + 1,
    #                 'disciplined_person_id': f'EMP{1000 + i}',
    #                 'custom_data': '{}',
    #                 'created_at': f'2024-{(i % 12) + 1:02d}-{(i % 28) + 1:02d} 09:00:00'
    #             }
    #             instruction = instruction_data
    #             break
    
    if not instruction:
        # 메인 테이블에 없으면 캐시에서 폴백
        try:
            cache_row = conn.execute(
                "SELECT * FROM safety_instructions_cache WHERE issue_number = ?",
                (issue_number,)
            ).fetchone()
            if cache_row:
                logging.info("[SI detail] 메인 없음 → 캐시 폴백 사용")
                # 캐시의 모든 컬럼을 dict로 반영하여 동적 컬럼 키가 바로 매칭되도록 함
                instruction = dict(cache_row)
                # 메인 스키마와의 최소 호환 필드 보정
                instruction.setdefault('detailed_content', instruction.get('detailed_content'))
                instruction.setdefault('is_deleted', 0)
            else:
                logging.warning(f"환경안전 지시서를 찾을 수 없습니다: {issue_number}")
                conn.close()
                return "환경안전 지시서 정보를 찾을 수 없습니다.", 404
        except Exception as _e:
            logging.error(f"SI 캐시 폴백 실패: {_e}")
            conn.close()
            return "환경안전 지시서 정보를 찾을 수 없습니다.", 404
    
    # 동적 컬럼 설정 가져오기 (활성+미삭제)
    _wa = sql_is_active_true('is_active', conn)
    _wd = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(f"""
        SELECT * FROM safety_instruction_column_config 
        WHERE {_wa} AND {_wd}
        ORDER BY column_order
    """).fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # column_span을 정수로 변환
    for col in dynamic_columns:
        if col.get('column_span'):
            col['column_span'] = int(col['column_span'])
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # 코드-값 매핑 방식으로 옵션 가져오기
            code_options = get_dropdown_options_for_display('safety_instruction', col['column_key'])
            # 코드-값 매핑 방식 사용 (DB dropdown_option_codes_v2 테이블)
            col['dropdown_options_mapped'] = code_options if code_options else []
    
    # 섹션 정보 로드
    from section_service import SectionConfigService
    section_service = SectionConfigService('safety_instruction', DB_PATH)
    sections = section_service.get_sections()
    logging.info(f"섹션 {len(sections)}개 로드됨")
    
    # 섹션별로 컬럼 분류 (동적)
    section_columns = {}
    for section in sections:
        section_columns[section['section_key']] = [
            col for col in dynamic_columns if col.get('tab') == section['section_key']
        ]
        logging.info(f"섹션 '{section['section_name']}': {len(section_columns[section['section_key']])}개 컬럼")
    
    # 하위 호환성을 위한 변수 유지 (템플릿이 아직 하드코딩된 경우)
    basic_info_columns = section_columns.get('basic_info', [])
    violation_info_columns = section_columns.get('violation_info', [])
    additional_columns = section_columns.get('additional', [])
    
    # 첨부파일 조회 - AttachmentService 사용 (공통 모듈)
    from board_services import AttachmentService
    attachment_service = AttachmentService('safety_instruction', DB_PATH, conn)
    attachments = attachment_service.list(issue_number)
    logging.info(f"Safety instruction {issue_number}: {len(attachments)} attachments found")
    
    # instruction을 항상 dict로 변환하여 템플릿에서 일관되게 처리
    if isinstance(instruction, dict):
        instruction_dict = instruction
    else:
        # SQLite Row 객체를 dict로 변환
        instruction_dict = dict(instruction)

    # custom_data 파싱 및 병합
    custom_data = {}
    def _parse_json_maybe(v):
        if v is None:
            return {}
        if isinstance(v, dict):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s or s in ('{}', 'null', 'None'):
                return {}
            try:
                return pyjson.loads(s)
            except Exception:
                return {}
        return {}

    if 'custom_data' in instruction_dict:
        custom_data = _parse_json_maybe(instruction_dict.get('custom_data'))
        if isinstance(custom_data, dict):  # custom_data 조건 제거!
            instruction_dict.update(custom_data)

    # 캐시에서 항상 보강: 메인에 키가 있어도 비어있으면 캐시로 채움
    try:
        cache_row = conn.execute(
            "SELECT * FROM safety_instructions_cache WHERE issue_number = ?",
            (issue_number,)
        ).fetchone()
        if cache_row:
            cache_map = dict(cache_row)
            cache_cd = _parse_json_maybe(cache_map.get('custom_data'))
            # 캐시의 명시 컬럼값으로 먼저 보강 (custom_data보다 우선)
            for k, v in cache_map.items():
                if k == 'custom_data':
                    continue
                if k not in instruction_dict or instruction_dict.get(k) in (None, ''):
                    instruction_dict[k] = v
            # custom_data 병합: 메인에 없거나 빈 값만 채움
            if isinstance(cache_cd, dict) and cache_cd:
                merged_cd = dict(custom_data) if isinstance(custom_data, dict) else {}
                for k, v in cache_cd.items():
                    if k not in merged_cd or merged_cd.get(k) in (None, '', []):
                        merged_cd[k] = v
                    # instruction_dict에도 없으면 채움
                    if k not in instruction_dict or instruction_dict.get(k) in (None, ''):
                        instruction_dict[k] = v
                custom_data = merged_cd
    except Exception as _e:
        logging.debug(f"SI cache merge skip: {_e}")
    
    # DB 연결 종료
    conn.close()

    # 키 호환 레이어: 구/신 키를 양방향으로 보완하여 UI가 둘 다 찾을 수 있도록 함
    try:
        def _alias_fill(d, pairs):
            for old, new in pairs:
                if old in d and (new not in d or d.get(new) in (None, '')):
                    d[new] = d[old]
                if new in d and (old not in d or d.get(old) in (None, '')):
                    d[old] = d[new]

        alias_pairs = [
            # 부서/담당
            ('issuer_department', 'issuer_dept'),
            ('discipline_department', 'issuer_incharge_dept'),
            # 사업자번호 계열 (다양한 키 보정)
            ('primary_business_number', 'primary_company_bizno'),
            ('primary_company_business_number', 'primary_company_bizno'),
            ('primary_business_number', 'primary_bizno'),
            ('primary_company_bizno', 'primary_bizno'),
            ('secondary_company_business_number', 'secondary_company_bizno'),
            ('subcontractor_business_number', 'subcontractor_bizno'),
        ]
        _alias_fill(instruction_dict, alias_pairs)
        if isinstance(custom_data, dict) and custom_data:
            _alias_fill(custom_data, alias_pairs)
    except Exception:
        pass
    
    # person_name 추출
    person_name = instruction_dict.get('disciplined_person', '알 수 없음')
    
    logging.info(f"환경안전 지시서 {issue_number} ({person_name}) 상세 페이지 로드")
    
    # 동적 컬럼 타입 보정: 링크드/팝업 추론 (discipline(d)_person* 등)
    try:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
        suffixes = ['_id','_dept','_department','_department_code','_bizno','_company_bizno','_business_number','_code','_company']
        def base_key_of(key: str) -> str:
            if not isinstance(key, str):
                return ''
            for s in suffixes:
                if key.endswith(s):
                    return key[:-len(s)]
            return key
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk + 'd']
            # 특수 규칙: 징계대상자 기본 contractor
            if bk in {'disciplined_person'}:
                return 'contractor'
            # contractor 우선
            if any(((v + '_company') in all_keys) for v in variants):
                return 'contractor'
            # person 다음
            if any(((v + '_id') in all_keys) for v in variants):
                return 'person'
            # company 다음
            if any(((v + '_company_bizno') in all_keys) or ((v + '_bizno') in all_keys) or ((v + '_business_number') in all_keys) for v in variants):
                return 'company'
            # department 마지막
            if any(((v + '_dept') in all_keys) or ((v + '_department') in all_keys) or ((v + '_department_code') in all_keys) for v in variants):
                return 'department'
            return ''
        popup_map = {
            'person': 'popup_person',
            'company': 'popup_company',
            'department': 'popup_department',
            'contractor': 'popup_contractor',
        }
        for col in dynamic_columns:
            ck = col.get('column_key') or ''
            bk = base_key_of(ck)
            grp = infer_group(bk)
            if ck.endswith('_id') or ck.endswith('_company') or ck.endswith('_company_bizno') or ck.endswith('_bizno') or ck.endswith('_business_number'):
                col['column_type'] = 'linked_text'
                continue
            if ck.endswith('_dept') or ck.endswith('_department') or ck.endswith('_department_code'):
                col['column_type'] = 'linked_dept'
                continue
            if grp and ck == bk:
                ct = col.get('column_type')
                if not ct or ct in ('text','popup','table','table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.warning(f"safety_instruction detail: normalize types failed: {_e}")

    # 기본정보 드롭다운 옵션 로드
    basic_options = {}
    from board_services import CodeService
    code_service = CodeService('safety_instruction', DB_PATH)
    
    # 기본정보 필드들의 드롭다운 옵션 로드
    basic_fields = [
        'classification',           # 분류
        'employment_type',          # 고용형태
        'discipline_type',          # 징계유형
        'accident_type',            # 사고유형
        'accident_grade',           # 사고등급
        'safety_violation_grade',   # 환경안전수칙 위반등급
        'violation_type',           # 위반유형
        'work_grade'                # 작업등급
    ]
    
    for field in basic_fields:
        codes = code_service.list(field)
        # 템플릿이 기대하는 형식으로 변환 (option_code -> code, option_value -> value)
        if codes and len(codes) > 0 and 'option_code' in codes[0]:
            codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
        basic_options[field] = codes
        logging.info(f"드롭다운 옵션 로드: {field} -> {len(codes)}개")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('safety-instruction-detail.html',
                         instruction=instruction_dict,
                         attachments=[dict(att) for att in attachments],
                         dynamic_columns=dynamic_columns,
                         sections=sections,  # 섹션 정보 추가
                         section_columns=section_columns,  # 섹션별 컬럼 추가
                         basic_info_columns=basic_info_columns,  # 하위 호환성
                         violation_info_columns=violation_info_columns,  # 하위 호환성
                         additional_columns=additional_columns,  # 하위 호환성
                         custom_data=custom_data,
                         basic_options=basic_options,  # basic_options 추가
                         menu=MENU_CONFIG,
                         is_popup=is_popup)


@app.route('/update-safety-instruction', methods=['POST'])
def update_safety_instruction():
    """환경안전 지시서 수정 API - 메인 테이블 사용 + 첨부 처리"""
    from board_services import AttachmentService
    conn = None

    try:
        issue_number = request.form.get('issue_number')
        detailed_content = request.form.get('detailed_content', '')

        if not issue_number:
            return jsonify({"success": False, "message": "발부번호가 필요합니다."}), 400

        # deleted_attachments 파싱
        try:
            deleted_attachments = pyjson.loads(request.form.get('deleted_attachments', '[]'))
        except Exception:
            deleted_attachments = []

        files = request.files.getlist('files')

        # 다양한 요청 포맷 지원: base_fields/custom_data 우선, 없으면 basic_info/violation_info 합치기
        custom_data_raw = request.form.get('custom_data', '{}')
        base_fields_raw = request.form.get('base_fields', '{}')
        basic_info_raw = request.form.get('basic_info', '{}')
        violation_info_raw = request.form.get('violation_info', '{}')

        try:
            custom_data = pyjson.loads(custom_data_raw) if isinstance(custom_data_raw, str) else (custom_data_raw or {})
        except Exception:
            custom_data = {}

        # 구버전 호환: basic_info/violation_info 병합
        try:
            basic_info = pyjson.loads(basic_info_raw) if isinstance(basic_info_raw, str) else (basic_info_raw or {})
        except Exception:
            basic_info = {}
        try:
            violation_info = pyjson.loads(violation_info_raw) if isinstance(violation_info_raw, str) else (violation_info_raw or {})
        except Exception:
            violation_info = {}
        if basic_info or violation_info:
            tmp = {}
            tmp.update(basic_info)
            tmp.update(violation_info)
            # issue_number는 보호
            tmp.pop('issue_number', None)
            # custom_data에 병합 (클라이언트 전송이 우선)
            for k, v in tmp.items():
                custom_data.setdefault(k, v)

        # base_fields도 custom_data에 흡수 (필요 시)
        try:
            base_fields = pyjson.loads(base_fields_raw) if isinstance(base_fields_raw, str) else (base_fields_raw or {})
        except Exception:
            base_fields = {}
        if base_fields:
            base_fields.pop('issue_number', None)
            custom_data.update(base_fields)

        # 리스트 필드 문자열을 배열로 정규화
        for key, value in list(custom_data.items()):
            if isinstance(value, str) and value.strip().startswith('[') and value.strip().endswith(']'):
                try:
                    custom_data[key] = pyjson.loads(value)
                except Exception:
                    pass

        conn = get_db_connection()
        cursor = conn.cursor()

        # 기존 custom_data 로드 (리스트 필드 병합 시 필요)
        existing_row = cursor.execute(
            "SELECT custom_data FROM safety_instructions WHERE issue_number = ?",
            (issue_number,)
        ).fetchone()

        existing_custom = {}
        if existing_row and existing_row[0]:
            if isinstance(existing_row[0], dict):
                existing_custom = pyjson.loads(pyjson.dumps(existing_row[0]))
            elif isinstance(existing_row[0], str):
                try:
                    existing_custom = pyjson.loads(existing_row[0])
                except Exception:
                    existing_custom = {}

        # 리스트 병합 유틸
        def is_list_field(val):
            if isinstance(val, list):
                return True
            if isinstance(val, str) and val.strip():
                return val.startswith('[') and val.endswith(']')
            return False

        for k, v in list(custom_data.items()):
            if is_list_field(v) or is_list_field(existing_custom.get(k, [])):
                old = existing_custom.get(k, [])
                if isinstance(old, str):
                    try:
                        old = pyjson.loads(old)
                    except Exception:
                        old = []
                if not isinstance(old, list):
                    old = []

                new_list = []
                if isinstance(v, list):
                    new_list = v
                elif isinstance(v, str) and v.strip().startswith('['):
                    try:
                        parsed = pyjson.loads(v)
                        if isinstance(parsed, list):
                            new_list = parsed
                    except Exception:
                        new_list = []

                # 단순 대체(프론트에서 전체 전달) 우선, 아니면 병합
                if new_list and old:
                    existing_custom[k] = new_list
                else:
                    existing_custom[k] = new_list if new_list else old

        # 리스트 병합 반영 + 상세내용은 별도 컬럼
        final_custom = dict(existing_custom)
        def _is_empty(val):
            try:
                if val is None:
                    return True
                if isinstance(val, str) and val.strip() == '':
                    return True
                return False
            except Exception:
                return False
        for k, v in custom_data.items():
            if not is_list_field(v):
                # 빈값은 기존값 보존 (일반 동적 컬럼 보호)
                if _is_empty(v):
                    continue
                final_custom[k] = v

        from db.upsert import safe_upsert
        upsert_data = {
            'issue_number': issue_number,
            'custom_data': pyjson.dumps(final_custom),
            'detailed_content': detailed_content,
            'updated_at': None  # UPSERT 유틸이 타임스탬프 처리
        }
        safe_upsert(
            conn,
            'safety_instructions',
            upsert_data,
            conflict_cols=['issue_number'],
            update_cols=['custom_data', 'detailed_content', 'updated_at']
        )

        # 첨부파일 처리
        attachment_service = AttachmentService('safety_instruction', DB_PATH, conn)
        if deleted_attachments:
            attachment_service.delete(deleted_attachments)
            logging.info(f"첨부파일 {len(deleted_attachments)}개 삭제")
        if files:
            uploaded_ids = attachment_service.bulk_add(
                issue_number,
                files,
                {'uploaded_by': session.get('user_id', 'user')}
            )
            logging.info(f"첨부파일 {len(uploaded_ids)}개 업로드: {uploaded_ids}")

        conn.commit()
        logging.info(f"Safety Instruction 업데이트 완료: {issue_number}")
        return jsonify({"success": True, "message": "수정이 완료되었습니다."})

    except Exception as e:
        import traceback
        logging.error(f"Safety Instruction 업데이트 오류: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/update-follow-sop', methods=['POST'])
def update_follow_sop():
    """Follow SOP 정보 업데이트"""
    from board_services import AttachmentService
    conn = None
    
    try:
        work_req_no = request.form.get('work_req_no')
        detailed_content = request.form.get('detailed_content', '')
        custom_data = request.form.get('custom_data', '{}')
        base_fields = request.form.get('base_fields', '{}')
        
        # 안전하게 JSON 파싱 (pyjson 사용)
        try:
            deleted_attachments = pyjson.loads(request.form.get('deleted_attachments', '[]'))
        except:
            deleted_attachments = []
        
        try:
            attachment_data_raw = request.form.get('attachment_data', '[]')
            if isinstance(attachment_data_raw, str):
                attachment_data = pyjson.loads(attachment_data_raw)
            else:
                attachment_data = attachment_data_raw
            if not isinstance(attachment_data, list):
                attachment_data = []
        except Exception as e:
            logging.warning(f"attachment_data 파싱 실패: {e}")
            attachment_data = []
        
        files = request.files.getlist('files')
        
        # custom_data 파싱
        if isinstance(custom_data, str):
            try:
                custom_data = pyjson.loads(custom_data)
            except Exception as e:
                logging.error(f"Custom Data parsing failed: {e}")
                custom_data = {}
        
        # base_fields 파싱
        if isinstance(base_fields, str):
            try:
                base_fields = pyjson.loads(base_fields)
            except Exception as e:
                logging.error(f"Base fields parsing failed: {e}")
                base_fields = {}
        
        # 리스트 필드 정규화
        for key, value in list(custom_data.items()):
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                try:
                    custom_data[key] = pyjson.loads(value)
                    logging.info(f"List field {key} normalized from string to array")
                except:
                    pass
        
        # base_fields가 있으면 custom_data에 병합
        if base_fields:
            custom_data.update(base_fields)
        
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # 기존 데이터 조회 (리스트 필드 병합을 위해) - 메인 테이블에서 조회
        cursor.execute("""
            SELECT custom_data 
            FROM follow_sop 
            WHERE work_req_no = ?
        """, (work_req_no,))
        
        existing_row = cursor.fetchone()
        existing_custom_data = {}
        
        if existing_row and existing_row[0]:
            if isinstance(existing_row[0], dict):
                # PostgreSQL JSONB - 깊은 복사로 안전하게 처리
                existing_custom_data = pyjson.loads(pyjson.dumps(existing_row[0]))
            elif isinstance(existing_row[0], str):
                # SQLite JSON 문자열
                try:
                    existing_custom_data = pyjson.loads(existing_row[0])
                except:
                    existing_custom_data = {}
        
        # 리스트 필드 병합 처리
        def is_list_field(field_value):
            """필드가 리스트 타입인지 확인"""
            if isinstance(field_value, list):
                return True
            if isinstance(field_value, str) and field_value.strip():
                return field_value.startswith('[') and field_value.endswith(']')
            return False
        
        for key, value in custom_data.items():
            if is_list_field(value) or is_list_field(existing_custom_data.get(key, [])):
                logging.info(f"[MERGE DEBUG] {key} 리스트 필드로 감지, 병합 처리 시작")
                
                # 기존 데이터 파싱
                existing_list = existing_custom_data.get(key, [])
                if isinstance(existing_list, str) and existing_list.strip():
                    try:
                        existing_list = pyjson.loads(existing_list)
                    except:
                        existing_list = []
                if not isinstance(existing_list, list):
                    existing_list = []
                
                # 새 데이터 파싱
                new_list = []
                if isinstance(value, list):
                    new_list = value
                elif isinstance(value, str) and value.strip():
                    if value.startswith('[') and value.endswith(']'):
                        try:
                            new_list = pyjson.loads(value)
                            if not isinstance(new_list, list):
                                new_list = []
                        except:
                            new_list = []
                
                logging.info(f"[MERGE DEBUG] {key} - 기존: {len(existing_list)}개, 새로: {len(new_list)}개")
                
                # 프론트에서 전체 배열을 보냈다면 그대로 사용, 아니면 병합
                if len(new_list) > 0 and len(existing_list) > 0:
                    # 새로운 데이터에 기존 데이터의 첫 번째 항목이 포함되어 있다면 전체 교체로 간주
                    first_existing_id = existing_list[0].get('id', '') if existing_list and isinstance(existing_list[0], dict) else ''
                    has_existing_data = any(
                        isinstance(item, dict) and item.get('id') == first_existing_id
                        for item in new_list
                    ) if first_existing_id else False
                    
                    if has_existing_data:
                        # 전체 데이터를 보냈으므로 그대로 사용
                        existing_custom_data[key] = new_list
                        logging.info(f"[MERGE DEBUG] {key} 전체 교체: {len(new_list)}개 항목")
                    else:
                        # 새 항목만 추가하므로 병합 처리
                        merged_list = list(existing_list)
                        existing_ids = {item.get('id', '') for item in existing_list if isinstance(item, dict)}
                        
                        for new_item in new_list:
                            if isinstance(new_item, dict) and new_item.get('id') not in existing_ids:
                                merged_list.append(new_item)
                                existing_ids.add(new_item.get('id'))
                        
                        existing_custom_data[key] = merged_list
                        logging.info(f"[MERGE DEBUG] {key} 병합 완료: 기존 {len(existing_list)}개 + 새로 {len(new_list)}개 = 최종 {len(merged_list)}개 항목")
                else:
                    # 하나가 비어있으면 비어있지 않은 것을 사용
                    existing_custom_data[key] = new_list if len(new_list) > 0 else existing_list
                    logging.info(f"[MERGE DEBUG] {key} 단순 대체: {len(existing_custom_data[key])}개 항목")
            else:
                # 일반 필드: 빈값은 보존, 값이 있으면 업데이트
                try:
                    if value is None:
                        continue
                    if isinstance(value, str) and value.strip() == '':
                        continue
                except Exception:
                    pass
                existing_custom_data[key] = value
        
        # detailed_content를 custom_data에 추가
        if detailed_content:
            existing_custom_data['detailed_content'] = detailed_content
            logging.info(f"detailed_content를 custom_data에 추가")
        
        # 메인 테이블에 UPSERT (issue_number와 동일한 방식)
        from db.upsert import safe_upsert
        safe_upsert(
            conn,
            'follow_sop',
            {
                'work_req_no': work_req_no,
                'custom_data': existing_custom_data,
                'updated_at': None
            },
            conflict_cols=['work_req_no'],
            update_cols=['custom_data', 'updated_at']
        )
        
        # 2. followsop_details 테이블 관련 코드 제거 (더 이상 사용하지 않음)
        
        # 3. 첨부파일 처리
        attachment_service = AttachmentService('follow_sop', DB_PATH, conn)
        
        # 삭제된 첨부파일 처리 (delete는 리스트를 받음)
        if deleted_attachments:
            attachment_service.delete(deleted_attachments)
        
        # 기존 첨부파일 설명 업데이트
        for item in attachment_data:
            if isinstance(item, dict) and item.get('id') and not item.get('isNew'):
                attachment_service.update_meta(
                    item['id'],
                    {'description': item.get('description', '')}
                )
        
        # 새 첨부파일 개별 추가 (add 메서드 사용)
        for idx, file in enumerate(files):
            if file and file.filename:
                # 각 파일의 설명 찾기
                description = ''
                if idx < len(attachment_data):
                    desc_info = attachment_data[idx]
                    if isinstance(desc_info, dict):
                        description = desc_info.get('description', '')
                
                # 파일 추가
                attachment_service.add(
                    work_req_no,
                    file,
                    {
                        'description': description,
                        'uploaded_by': session.get('user_id', 'user')
                    }
                )
        
        conn.commit()
        logging.info(f"Follow SOP {work_req_no} 업데이트 성공")
        
        return jsonify({
            "success": True,
            "message": "Follow SOP가 성공적으로 수정되었습니다.",
            "work_req_no": work_req_no
        })
        
    except Exception as e:
        import traceback
        logging.error(f"Follow SOP 업데이트 오류: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route('/update-full-process', methods=['POST'])
def update_full_process():
    """Full Process 정보 업데이트"""
    from board_services import AttachmentService
    conn = None
    
    try:
        fullprocess_number = request.form.get('fullprocess_number')
        detailed_content = request.form.get('detailed_content', '')
        custom_data = request.form.get('custom_data', '{}')
        base_fields = request.form.get('base_fields', '{}')
        
        # 안전하게 JSON 파싱 (pyjson 사용)
        try:
            deleted_attachments = pyjson.loads(request.form.get('deleted_attachments', '[]'))
        except:
            deleted_attachments = []
        
        try:
            attachment_data_raw = request.form.get('attachment_data', '[]')
            if isinstance(attachment_data_raw, str):
                attachment_data = pyjson.loads(attachment_data_raw)
            else:
                attachment_data = attachment_data_raw
            if not isinstance(attachment_data, list):
                attachment_data = []
        except Exception as e:
            logging.warning(f"attachment_data 파싱 실패: {e}")
            attachment_data = []
        
        files = request.files.getlist('files')
        
        # custom_data 파싱
        if isinstance(custom_data, str):
            try:
                custom_data = pyjson.loads(custom_data)
            except Exception as e:
                logging.error(f"Custom Data parsing failed: {e}")
                custom_data = {}
        
        # base_fields 파싱
        if isinstance(base_fields, str):
            try:
                base_fields = pyjson.loads(base_fields)
            except Exception as e:
                logging.error(f"Base fields parsing failed: {e}")
                base_fields = {}
        
        # 리스트 필드 정규화
        for key, value in list(custom_data.items()):
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                try:
                    custom_data[key] = pyjson.loads(value)
                    logging.info(f"List field {key} normalized from string to array")
                except:
                    pass
        
        # base_fields가 있으면 custom_data에 병합
        if base_fields:
            custom_data.update(base_fields)
        
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # 기존 데이터 조회 (리스트 필드 병합을 위해) - 메인 테이블
        cursor.execute("""
            SELECT custom_data 
            FROM full_process 
            WHERE fullprocess_number = ?
        """, (fullprocess_number,))
        
        existing_row = cursor.fetchone()
        existing_custom_data = {}
        
        if existing_row and existing_row[0]:
            if isinstance(existing_row[0], dict):
                # PostgreSQL JSONB - 깊은 복사로 안전하게 처리
                existing_custom_data = pyjson.loads(pyjson.dumps(existing_row[0]))
            elif isinstance(existing_row[0], str):
                # SQLite JSON 문자열
                try:
                    existing_custom_data = pyjson.loads(existing_row[0])
                except:
                    existing_custom_data = {}
        
        # 리스트 필드 병합 처리
        def is_list_field(field_value):
            """필드가 리스트 타입인지 확인"""
            if isinstance(field_value, list):
                return True
            if isinstance(field_value, str) and field_value.strip():
                return field_value.startswith('[') and field_value.endswith(']')
            return False
        
        for key, value in custom_data.items():
            if is_list_field(value) or is_list_field(existing_custom_data.get(key, [])):
                logging.info(f"[MERGE DEBUG] {key} 리스트 필드로 감지, 병합 처리 시작")
                
                # 기존 데이터 파싱
                existing_list = existing_custom_data.get(key, [])
                if isinstance(existing_list, str) and existing_list.strip():
                    try:
                        existing_list = pyjson.loads(existing_list)
                    except:
                        existing_list = []
                if not isinstance(existing_list, list):
                    existing_list = []
                
                # 새 데이터 파싱
                new_list = []
                if isinstance(value, list):
                    new_list = value
                elif isinstance(value, str) and value.strip():
                    if value.startswith('[') and value.endswith(']'):
                        try:
                            new_list = pyjson.loads(value)
                            if not isinstance(new_list, list):
                                new_list = []
                        except:
                            new_list = []
                
                logging.info(f"[MERGE DEBUG] {key} - 기존: {len(existing_list)}개, 새로: {len(new_list)}개")
                
                # 프론트에서 전체 배열을 보냈다면 그대로 사용, 아니면 병합
                if len(new_list) > 0 and len(existing_list) > 0:
                    # 새로운 데이터에 기존 데이터의 첫 번째 항목이 포함되어 있다면 전체 교체로 간주
                    first_existing_id = existing_list[0].get('id', '') if existing_list and isinstance(existing_list[0], dict) else ''
                    has_existing_data = any(
                        isinstance(item, dict) and item.get('id') == first_existing_id
                        for item in new_list
                    ) if first_existing_id else False
                    
                    if has_existing_data:
                        # 전체 데이터를 보냈으므로 그대로 사용
                        existing_custom_data[key] = new_list
                        logging.info(f"[MERGE DEBUG] {key} 전체 교체: {len(new_list)}개 항목")
                    else:
                        # 새 항목만 추가하므로 병합 처리
                        merged_list = list(existing_list)
                        existing_ids = {item.get('id', '') for item in existing_list if isinstance(item, dict)}
                        
                        for new_item in new_list:
                            if isinstance(new_item, dict) and new_item.get('id') not in existing_ids:
                                merged_list.append(new_item)
                                existing_ids.add(new_item.get('id'))
                        
                        existing_custom_data[key] = merged_list
                        logging.info(f"[MERGE DEBUG] {key} 병합 완료: 기존 {len(existing_list)}개 + 새로 {len(new_list)}개 = 최종 {len(merged_list)}개 항목")
                else:
                    # 하나가 비어있으면 비어있지 않은 것을 사용
                    existing_custom_data[key] = new_list if len(new_list) > 0 else existing_list
                    logging.info(f"[MERGE DEBUG] {key} 단순 대체: {len(existing_custom_data[key])}개 항목")
            else:
                # 일반 필드는 정상 업데이트
                existing_custom_data[key] = value
        
        # detailed_content를 custom_data에 추가
        if detailed_content:
            existing_custom_data['detailed_content'] = detailed_content
            logging.info(f"detailed_content를 custom_data에 추가")
        
        # 메인 테이블 UPSERT
        from db.upsert import safe_upsert
        safe_upsert(
            conn,
            'full_process',
            {
                'fullprocess_number': fullprocess_number,
                'custom_data': existing_custom_data,
                'updated_at': None
            },
            conflict_cols=['fullprocess_number'],
            update_cols=['custom_data', 'updated_at']
        )
        
        # 2. fullprocess_details 테이블 관련 코드 제거 (더 이상 사용하지 않음)
        
        # 3. 첨부파일 처리
        attachment_service = AttachmentService('full_process', DB_PATH, conn)
        
        # 삭제된 첨부파일 처리 (delete는 리스트를 받음)
        if deleted_attachments:
            attachment_service.delete(deleted_attachments)
        
        # 기존 첨부파일 설명 업데이트
        for item in attachment_data:
            if isinstance(item, dict) and item.get('id') and not item.get('isNew'):
                attachment_service.update_meta(
                    item['id'],
                    {'description': item.get('description', '')}
                )
        
        # 새 첨부파일 개별 추가 (add 메서드 사용)
        for idx, file in enumerate(files):
            if file and file.filename:
                # 각 파일의 설명 찾기
                description = ''
                if idx < len(attachment_data):
                    desc_info = attachment_data[idx]
                    if isinstance(desc_info, dict):
                        description = desc_info.get('description', '')
                
                # 파일 추가
                attachment_service.add(
                    fullprocess_number,
                    file,
                    {
                        'description': description,
                        'uploaded_by': session.get('user_id', 'user')
                    }
                )
        
        conn.commit()
        logging.info(f"Full Process {fullprocess_number} 업데이트 성공")
        
        return jsonify({
            "success": True,
            "message": "Full Process가 성공적으로 수정되었습니다.",
            "fullprocess_number": fullprocess_number
        })
        
    except Exception as e:
        import traceback
        logging.error(f"Full Process 업데이트 오류: {e}")
        logging.error(f"Traceback: {traceback.format_exc()}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()


@app.route("/data-recovery")
def data_recovery():
    """데이터 복구 페이지"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 삭제된 사고 조회
    deleted_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        WHERE is_deleted = 1
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    deleted_accidents = [dict(row) for row in deleted_accidents_rows]
    
    # 삭제된 협력사 조회
    deleted_partners_rows = conn.execute("""
        SELECT * FROM partners_cache 
        WHERE is_deleted = 1
        ORDER BY company_name
    """).fetchall()
    
    deleted_partners = [dict(row) for row in deleted_partners_rows]
    conn.close()
    
    return render_template('data-recovery.html', 
                         deleted_accidents=deleted_accidents,
                         deleted_partners=deleted_partners,
                         menu=MENU_CONFIG,
                         active_slug='data-recovery')

def partner_standards():
    """협력사 기준정보 페이지"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip(),
        'business_type_major': request.args.get('business_type_major', '').strip(),
        'business_type_minor': request.args.get('business_type_minor', '').strip(),
        'workers_min': request.args.get('workers_min', type=int),
        'workers_max': request.args.get('workers_max', type=int)
    }
    
    # 컬럼 설정 가져오기
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    dynamic_columns_rows = conn.execute("""
        SELECT * FROM partner_standards_column_config 
        WHERE is_active = 1 
        ORDER BY column_order
    """).fetchall()
    
    dynamic_columns = []
    for row in dynamic_columns_rows:
        dynamic_columns.append({
            'key': row['column_key'],
            'name': row['column_name'],
            'type': row['column_type'],
            'order': row['column_order'],
            'table_display': True  # partner_standards는 모든 컬럼 표시
        })
    
    # 새로운 데이터 매니저를 통해 협력사 목록 조회
    partners_rows, total_count = partner_manager.get_all_partners(
        page=page, 
        per_page=per_page, 
        filters=filters
    )
    
    # Row 객체를 딕셔너리로 변환하고 No 컬럼 추가 (역순 번호)
    offset = (page - 1) * per_page
    partners = []
    for i, row in enumerate(partners_rows):
        partner = dict(row)
        partner['no'] = total_count - offset - i
        partners.append(partner)
    
    # 페이지네이션 정보
    class Pagination:
        def __init__(self, page, per_page, total_count):
            self.page = page
            self.per_page = per_page
            self.total_count = total_count
            self.pages = math.ceil(total_count / per_page)
            self.has_prev = page > 1
            self.prev_num = page - 1 if self.has_prev else None
            self.has_next = page < self.pages
            self.next_num = page + 1 if self.has_next else None
        
        def iter_pages(self, window_size=10):
            # 현재 페이지를 기준으로 10개 페이지 윈도우 생성
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            for num in range(start, end + 1):
                yield num
        
        def get_window_info(self, window_size=10):
            # 현재 윈도우의 시작과 끝 페이지
            start = ((self.page - 1) // window_size) * window_size + 1
            end = min(start + window_size - 1, self.pages)
            has_prev_window = start > 1
            has_next_window = end < self.pages
            prev_window_start = max(1, start - window_size)
            next_window_start = min(end + 1, self.pages)
            return {
                'start': start,
                'end': end,
                'has_prev_window': has_prev_window,
                'has_next_window': has_next_window,
                'prev_window_start': prev_window_start,
                'next_window_start': next_window_start
            }
    
    pagination = Pagination(page, per_page, total_count)
    
    conn.close()
    
    return render_template('partner-standards.html',
                         partners=partners,
                         total_count=total_count,
                         pagination=pagination,
                         dynamic_columns=dynamic_columns,
                         menu=MENU_CONFIG)


def partner_change_request():
    """기준정보 변경요청 페이지"""
    from common_search import DynamicSearchBuilder, get_static_columns
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    
    # 검색 조건
    filters = {
        'requester_name': request.args.get('requester_name', '').strip(),
        'company_name': request.args.get('company_name', '').strip(),
        'business_number': request.args.get('business_number', '').strip()
    }
    
    # 실제 데이터베이스에서 조회
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # DynamicSearchBuilder로 검색 조건 생성
        base_query = "FROM partner_change_requests"
        where_clause = ""
        params = []
        
        search_builder = DynamicSearchBuilder('sqlite')
        static_cols = ['id', 'requester_name', 'requester_department', 'company_name', 
                      'business_number', 'change_type', 'current_value', 'new_value', 
                      'change_reason', 'created_at', 'status', 'request_number']
        
        # is_deleted 컬럼 존재 여부 확인
        cursor.execute("PRAGMA table_info(partner_change_requests)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 각 필터 적용
        where_conditions = []
        
        # is_deleted 컬럼이 있으면 필터 적용
        if 'is_deleted' in columns:
            where_conditions.append("(is_deleted::integer = 0 OR is_deleted IS NULL)")
        # is_deleted 컬럼이 없으면 추가
        else:
            cursor.execute("""
                ALTER TABLE partner_change_requests 
                ADD COLUMN is_deleted INTEGER DEFAULT 0
            """)
            conn.commit()
            # 컬럼 추가 후에도 필터 적용
            where_conditions.append("(is_deleted::integer = 0 OR is_deleted IS NULL)")
        
        for field_name, field_value in filters.items():
            if not field_value:
                continue
            
            # 동적 컬럼 여부 판단 (현재는 모두 정적 컬럼)
            is_dynamic = field_name not in static_cols
            
            if is_dynamic:
                # JSON 필드 검색 (Postgres/SQLite 분기)
                if hasattr(conn, 'is_postgres') and conn.is_postgres:
                    where_conditions.append(f"(custom_data->>'{field_name}') ILIKE %s")
                else:
                    where_conditions.append(f"json_extract(custom_data, '$.{field_name}') LIKE ?")
                params.append(f"%{field_value}%")
            else:
                # 일반 컬럼 검색
                where_conditions.append(f"{field_name} LIKE ?")
                params.append(f"%{field_value}%")
        
        if where_conditions:
            where_clause = "WHERE " + " AND ".join(where_conditions)
        
        # 총 개수 조회
        count_query = f"SELECT COUNT(*) as total FROM partner_change_requests {where_clause}"
        cursor.execute(count_query, params)
        total_count = cursor.fetchone()['total']
        
        # 페이지네이션 적용하여 데이터 조회
        offset = (page - 1) * per_page
        data_query = f"""
            SELECT id, requester_name, requester_department, company_name, business_number,
                   change_type, current_value, new_value, change_reason, 
                   created_at, status, request_number, custom_data
            FROM partner_change_requests 
            {where_clause}
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """
        cursor.execute(data_query, params + [per_page, offset])
        rows = cursor.fetchall()
        
        # 드롭다운 옵션 로드 (change_type 등을 위해)
        from board_services import CodeService
        code_service = CodeService('change_request', DB_PATH)
        
        # change_type 드롭다운 옵션 조회
        change_type_codes = code_service.list('change_type')
        change_type_map = {code['option_code']: code['option_value'] for code in change_type_codes}
        
        # status 드롭다운 옵션 조회
        status_codes = code_service.list('status')
        status_map = {code['option_code']: code['option_value'] for code in status_codes}
        
        # 데이터 변환
        change_requests = []
        for i, row in enumerate(rows):
            # status 필드 안전하게 처리
            try:
                status = row['status'] if 'status' in row.keys() else 'pending'
            except:
                status = 'pending'
            
            # custom_data 파싱
            custom_data = {}
            if row['custom_data']:
                try:
                    custom_data = pyjson.loads(row['custom_data'])
                except:
                    custom_data = {}
                
            # 드롭다운 값을 라벨로 변환
            change_type_value = row['change_type']
            change_type_label = change_type_map.get(change_type_value, change_type_value) if change_type_value else ''
            
            status_label = status_map.get(status, status) if status else 'pending'
                
            change_request = type('obj', (object,), {
                'id': row['id'],
                'no': total_count - offset - i,  # No 컬럼 (역순)
                'request_number': row['request_number'],  # request_number 추가
                'requester_name': row['requester_name'],
                'requester_department': row['requester_department'],
                'company_name': row['company_name'],
                'business_number': row['business_number'],
                'change_type': change_type_value,
                'change_type_label': change_type_label,  # 라벨 추가
                'current_value': row['current_value'],
                'new_value': row['new_value'],
                'change_reason': row['change_reason'],
                'created_at': row['created_at'],
                'status': status,
                'status_label': status_label,  # 라벨 추가
                'custom_data': custom_data  # custom_data 추가
            })()
            change_requests.append(change_request)
            
        conn.close()
        
    except Exception as e:
        logging.error(f"변경요청 목록 조회 중 오류: {e}")
        change_requests = []
        total_count = 0
    
    # 페이지네이션 객체 생성
    class DummyPagination:
        def __init__(self, page, per_page, total):
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = (total + per_page - 1) // per_page
            
        def iter_pages(self):
            for i in range(max(1, self.page - 5), min(self.pages + 1, self.page + 6)):
                yield i
                
        def get_window_info(self):
            return type('obj', (object,), {
                'has_prev_window': self.page > 10,
                'has_next_window': self.page + 10 <= self.pages,
                'prev_window_start': max(1, self.page - 10),
                'next_window_start': min(self.pages, self.page + 10)
            })()
    
    pagination = DummyPagination(page, per_page, total_count)
    return render_template('partner-change-request.html', 
                         menu=MENU_CONFIG, 
                         pagination=pagination, 
                         total_count=total_count,
                         change_requests=change_requests)


def change_request_detail(request_id):
    """변경요청 상세정보 페이지"""
    logging.info(f"변경요청 상세 정보 조회: {request_id}")
    
    # 실제 데이터베이스에서 조회
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 먼저 partner_change_requests 테이블에서 조회 (주 테이블)
    cursor.execute("""
        SELECT * FROM partner_change_requests 
        WHERE id = %s
    """, (request_id,))
    
    request_row = cursor.fetchone()
    
    # partner_change_requests에 없으면 change_requests 테이블에서 조회 (호환성)
    if not request_row:
        cursor.execute("""
            SELECT * FROM change_requests 
            WHERE id = %s
        """, (request_id,))
        request_row = cursor.fetchone()
    
    if request_row:
        # 실제 DB 데이터 사용
        request_dict = dict(request_row)
        
        # change_request_details 테이블에서 detailed_content 조회
        cursor.execute("""
            SELECT detailed_content FROM change_request_details 
            WHERE request_number = %s
        """, (request_dict.get('request_number', ''),))
        detail_row = cursor.fetchone()
        
        if detail_row:
            request_dict['detailed_content'] = detail_row['detailed_content']
            logging.info(f"detailed_content 로드 완료: 길이={len(detail_row['detailed_content']) if detail_row['detailed_content'] else 0}")
        else:
            request_dict['detailed_content'] = ''
            logging.info("detailed_content가 없음")
        
        request_data = type('obj', (object,), request_dict)()
        logging.info(f"DB에서 변경요청 데이터 로드: ID={request_id}")
    else:
        # DB에 없으면 기본값
        request_data = type('obj', (object,), {
            'id': request_id,
            'change_reason': '',
            'approval_comments': '',
            'custom_data': '{}',
            'detailed_content': ''
        })()
        logging.info(f"변경요청 데이터 없음, 기본값 사용: ID={request_id}")
    
    conn.close()
    
    # Phase 1: 동적 컬럼 설정 가져오기  
    conn = get_db_connection()
    
    # change_request_column_config 테이블 사용
    try:
        cursor = conn.cursor()
        _wa = sql_is_active_true('is_active', conn)
        _wd = sql_is_deleted_false('is_deleted', conn)
        dynamic_columns_rows = conn.execute(f"""
            SELECT * FROM change_request_column_config 
            WHERE {_wa} AND {_wd}
            ORDER BY column_order
        """).fetchall()
        
        conn.close()
        
    except Exception as e:
        logging.error(f"동적 컬럼 로딩 중 오류: {e}")
        dynamic_columns_rows = []
        conn.close()
    
    # Phase 2: 동적 컬럼 처리 - 코드 테이블 기반으로 옵션 구성(등록 화면과 동일)
    dynamic_columns = []
    for row in dynamic_columns_rows:
        col_dict = dict(row)
        if col_dict.get('column_type') == 'dropdown':
            try:
                code_options = get_dropdown_options_for_display('change_request', col_dict['column_key'])
                col_dict['dropdown_options_mapped'] = (
                    [{"code": opt["code"], "value": opt["value"]} for opt in code_options]
                    if code_options else []
                )
            except Exception:
                col_dict['dropdown_options_mapped'] = []
        dynamic_columns.append(type('Column', (), col_dict)())
    
    # custom_data를 DB에서 가져온 데이터에서 파싱
    custom_data = {}
    if hasattr(request_data, 'custom_data') and request_data.custom_data:
        try:
            # json already imported globally
            custom_data = pyjson.loads(request_data.custom_data)
            logging.info(f"custom_data 파싱 성공: {len(custom_data)}개 필드")
        except Exception as e:
            logging.error(f"custom_data 파싱 실패: {e}")
            custom_data = {}
    
    logging.info(f"변경요청 동적 컬럼 {len(dynamic_columns)}개 로드됨, custom_data {len(custom_data)}개 필드")
    
    # 첨부파일 조회 추가
    from board_services import AttachmentService
    attachment_service = AttachmentService('change_request', DB_PATH)
    # 실제 request_number 사용 (DB에서 가져온 값)
    actual_request_number = request_data.request_number if hasattr(request_data, 'request_number') and request_data.request_number else f"CR-{request_id}"
    # custom_data가 비어있다면(초기 등록이 컬럼 단위 저장인 경우) 컬럼 값에서 복원
    if not custom_data:
        try:
            rebuilt = {}
            for row in dynamic_columns_rows:
                key = row['column_key'] if isinstance(row, sqlite3.Row) else row.get('column_key')
                if key and hasattr(request_data, key):
                    rebuilt[key] = getattr(request_data, key)
            if rebuilt:
                custom_data = rebuilt
                logging.info(f"custom_data 재구성: {len(custom_data)}개 필드")
        except Exception as e:
            logging.error(f"custom_data 재구성 실패: {e}")

    attachments = attachment_service.list(actual_request_number)
    logging.info(f"변경요청 첨부파일 조회: {actual_request_number} → {len(attachments)}개 로드됨")
    
    # popup 파라미터 확인
    is_popup = request.args.get('popup', '0') == '1'
    
    return render_template('change-request-detail.html', 
                         request_data=request_data,
                         dynamic_columns=dynamic_columns,
                         custom_data=custom_data,
                         attachments=attachments,
                         is_popup=is_popup,
                         menu=MENU_CONFIG)


@app.route('/update-change-request', methods=['POST'])
def update_change_request():
    """변경요청 수정 API - AttachmentService 사용"""
    from board_services import AttachmentService
    conn = None
    
    try:
        request_id = request.form.get('request_id')  # ID 받기
        request_number = request.form.get('request_number')  # 실제 request_number도 받기
        change_reason = request.form.get('change_reason', '')  # change_content 대신 change_reason
        detailed_content = request.form.get('detailed_content', '')  # 추가
        custom_data = request.form.get('custom_data', '{}')
        
        # 상세내용 처리
        final_content = detailed_content
        logging.info(f"변경요청 업데이트: ID={request_id}, 내용 길이={len(final_content) if final_content else 0}자")
        
        # deleted_attachments 파싱
        deleted_attachments_str = request.form.get('deleted_attachments', '[]')
        try:
            deleted_attachments = pyjson.loads(deleted_attachments_str) if deleted_attachments_str else []
        except:
            deleted_attachments = []
            
        files = request.files.getlist('files')
        print(f"[CHANGE_REQUEST DEBUG] files count: {len(files)}")
        
        if not request_number:
            return jsonify({"success": False, "message": "요청번호가 필요합니다."}), 400
        
        # JSON 파싱
        try:
            custom_data_dict = pyjson.loads(custom_data) if custom_data != '{}' else {}
        except ValueError:  # JSONDecodeError is a subclass of ValueError
            return jsonify({"success": False, "message": "잘못된 데이터 형식입니다."}), 400
        
        # 상태 값 검증 (수정 시에만 변경 허용)
        if 'status' in custom_data_dict:
            allowed_statuses = ['requested', 'approved', 'rejected']  # applied -> approved로 수정
            if custom_data_dict['status'] not in allowed_statuses:
                custom_data_dict['status'] = 'requested'  # 잘못된 값은 기본값으로
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # partner_change_requests 테이블 업데이트 (올바른 테이블)
        # change_request_details 테이블 생성 (상세내용용) - 필요한 경우
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS change_request_details (
                request_number TEXT PRIMARY KEY,
                detailed_content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 기존 변경요청이 있는지 확인 - ID로 확인
        cursor.execute("SELECT id, request_number, status FROM partner_change_requests WHERE id = %s", (request_id,))
        existing = cursor.fetchone()
        
        if existing:
            # 실제 request_number 사용
            actual_request_number = existing[1] if existing[1] else request_number
            
            # 업데이트 - ID 기준
            # custom_data에서 status 추출
            status_value = custom_data_dict.get('status', existing[2])  # 기존 상태 유지
            
            # custom_data에서 각 컬럼 값 추출
            update_query = """
                UPDATE partner_change_requests 
                SET status = %s, 
                    custom_data = %s, 
                    updated_at = CURRENT_TIMESTAMP
            """
            
            params = [status_value, pyjson.dumps(custom_data_dict)]
            
            # 동적으로 컬럼 업데이트 추가
            for key, value in custom_data_dict.items():
                if key != 'status':  # status는 이미 처리됨
                    # PostgreSQL용 컬럼 존재 확인
                    cursor.execute("""
                        SELECT column_name FROM information_schema.columns 
                        WHERE table_name='partner_change_requests' AND column_name=%s
                    """, (key,))
                    if cursor.fetchone():
                        update_query += f", {key} = %s"
                        params.append(value)
            
            update_query += " WHERE id = %s"
            params.append(request_id)
            
            cursor.execute(update_query, params)
            
            logging.info(f"partner_change_requests 업데이트: ID={request_id}, status={status_value}")
        else:
            logging.error(f"변경요청을 찾을 수 없습니다: ID={request_id}")
            return jsonify({"success": False, "message": "변경요청을 찾을 수 없습니다."}), 404
        
        # 상세내용을 custom_data에 추가
        if final_content:
            custom_data_dict['detailed_content'] = final_content
            # custom_data 업데이트
            cursor.execute("""
                UPDATE partner_change_requests 
                SET custom_data = %s
                WHERE id = %s
            """, (pyjson.dumps(custom_data_dict), request_id))
            logging.info(f"상세내용 custom_data에 업데이트 완료: {len(final_content)}자")
        
        # AttachmentService 사용하여 첨부파일 처리 (기존 연결 전달)
        attachment_service = AttachmentService('change_request', DB_PATH, conn)
        
        # 삭제할 첨부파일 처리
        if deleted_attachments:
            attachment_service.delete(deleted_attachments)
            logging.info(f"첨부파일 {len(deleted_attachments)}개 삭제")
        
        # 새 첨부파일 업로드 - 실제 request_number 사용
        if files:
            actual_request_number = existing[1] if existing and existing[1] else request_number
            uploaded_ids = attachment_service.bulk_add(
                actual_request_number, 
                files,
                {'uploaded_by': session.get('user_id', 'user')}
            )
            logging.info(f"첨부파일 {len(uploaded_ids)}개 업로드: {uploaded_ids}")
        
        conn.commit()
        logging.info(f"Change Request 업데이트 완료: {request_number}")
        
        return jsonify({"success": True, "message": "수정이 완료되었습니다."})
        
    except Exception as e:
        logging.error(f"Change Request 업데이트 오류: {e}")
        if conn:
            conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        if conn:
            conn.close()



@app.route("/partner/<business_number>")
@app.route("/partner-detail/<business_number>")
def partner_detail(business_number):
    """협력사 상세정보 페이지"""
    logging.info(f"협력사 상세 정보 조회: {business_number}")
    
    # 새로운 데이터 매니저를 통해 협력사 정보 조회
    partner = partner_manager.get_partner_by_business_number(business_number)
    
    if not partner:
        logging.warning(f"협력사를 찾을 수 없습니다: {business_number}")
        return "협력사 정보를 찾을 수 없습니다.", 404
    
    # 첨부파일 정보 가져오기
    conn = partner_manager.db_config.get_sqlite_connection()
    conn.row_factory = sqlite3.Row
    attachments = conn.execute("""
        SELECT * FROM partner_attachments 
        WHERE business_number = ? 
        ORDER BY upload_date DESC
    """, (business_number,)).fetchall()
    conn.close()
    
    logging.info(f"협력사 {business_number} ({partner['company_name']}) 상세 페이지 로드 - 첨부파일 {len(attachments)}개")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    return render_template('partner-detail.html', 
                         partner=partner, 
                         attachments=attachments,
                         menu=MENU_CONFIG, 
                         is_popup=is_popup,
                         board_type='partner')  # 게시판 타입 전달

@app.route("/accident-detail/<accident_id>")
def accident_detail(accident_id):
    """사고 상세정보 페이지"""
    print(f"[DEBUG] accident_detail 함수 호출됨: ID={accident_id}", flush=True)
    logging.info(f"사고 상세 정보 조회: {accident_id}")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 섹션 정보 가져오기
    # 먼저 accident_sections 테이블 사용 시도, 없으면 section_config 사용
    try:
        _wa = sql_is_active_true('is_active', conn)
        _wd = sql_is_deleted_false('is_deleted', conn)
        sections = conn.execute(f"""
            SELECT * FROM accident_sections 
            WHERE {_wa}
              AND {_wd}
            ORDER BY section_order
        """).fetchall()
        sections = [dict(row) for row in sections]
    except:
        # accident_sections 테이블이 없으면 section_config 사용
        _wa2 = sql_is_active_true('is_active', conn)
        sections = conn.execute(f"""
            SELECT * FROM section_config 
            WHERE board_type = 'accident' AND {_wa2}
            ORDER BY section_order
        """).fetchall()
        sections = [dict(row) for row in sections]
    # 섹션이 비어 있으면 안전한 기본값 제공 (DB 상태 불완전 시 UI 보호)
    if not sections:
        sections = [
            {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
            {'section_key': 'accident_info', 'section_name': '사고정보', 'section_order': 2},
            {'section_key': 'location_info', 'section_name': '장소정보', 'section_order': 3},
            {'section_key': 'additional', 'section_name': '추가정보', 'section_order': 4},
        ]
    
    # 실제 DB에서 사고 데이터 조회 (id 우선, 실패 시 accident_number로 폴백)
    accident = None
    custom_data = {}
    
    # accidents_cache 테이블에서 조회 (id가 숫자일 때만 id로, 아니면 번호로)
    try:
        _wd_acc = sql_is_deleted_false('is_deleted', conn)
        accident_row = None
        acc_id_str = str(accident_id)
        # id 조회는 숫자인 경우에만 시도하여 캐스팅 오류 방지
        if acc_id_str.isdigit():
            try:
                accident_row = conn.execute(
                    f"SELECT * FROM accidents_cache WHERE id = %s AND {_wd_acc}",
                    (accident_id,)
                ).fetchone()
            except Exception as _e_id:
                # 안전 회복
                try:
                    conn.rollback()
                except Exception:
                    pass
                accident_row = None
        # 번호로 조회
        if not accident_row:
            accident_row = conn.execute(
                f"SELECT * FROM accidents_cache WHERE accident_number = %s AND {_wd_acc}",
                (accident_id,)
            ).fetchone()
        
        if accident_row:
            accident = dict(accident_row)
            # custom_data JSON 파싱 (PostgreSQL JSONB vs SQLite JSON 호환)
            if accident.get('custom_data'):
                try:
                    # PostgreSQL JSONB는 이미 dict로 반환됨, SQLite는 JSON 문자열
                    if isinstance(accident['custom_data'], dict):
                        custom_data = accident['custom_data']
                    else:
                        custom_data = json.loads(accident['custom_data'])
                    
                    print(f"[DEBUG] accident_detail custom_data keys: {list(custom_data.keys())}")
                    if 'injured_person' in custom_data:
                        injured_data = custom_data['injured_person']
                        print(f"[DEBUG] injured_person type: {type(injured_data)}, length: {len(injured_data) if hasattr(injured_data, '__len__') else 'No length'}")
                        print(f"[DEBUG] injured_person content: {injured_data}")
                    else:
                        print("[DEBUG] injured_person NOT FOUND in custom_data")
                    # 주의: 여기서는 accident에 custom_data를 즉시 병합하지 않는다.
                    # 실제 병합은 아래의 안전 병합 로직에서 수행된다.
                    # 다만 화면 표시 품질을 위해 created_at 같은 표시용 기본 필드는
                    # 상위에 값이 비어 있을 경우에 한해 폴백으로 보강한다.
                    try:
                        if (not accident.get('created_at')) and isinstance(custom_data, dict) and custom_data.get('created_at'):
                            accident['created_at'] = custom_data.get('created_at')
                    except Exception:
                        pass
                except:
                    custom_data = {}
        else:
            # DB에 없으면 더미 데이터 사용
            dummy_accidents = []
    except Exception as e:
        logging.error(f"DB 조회 오류: {e}")
        try:
            conn.rollback()
        except Exception:
            pass
        dummy_accidents = []
        
    # 더미 데이터 생성 (DB에 없는 경우)
    # if not accident:
    #     dummy_accidents = []
    #     for i in range(50):
    #         # 사고번호 생성: K + 연월일 + 순서(3자리) - 고정된 값
    #         months = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]
    #         days = [1, 5, 10, 15, 20, 25]
    #         accident_date_fixed = f'2024-{months[i % 12]:02d}-{days[i % 6]:02d}'
    #         accident_number = f'K{accident_date_fixed.replace("-", "")}{i+1:03d}'
        
    #     # 고정된 값들로 변경
    #     grades = ['경미', '중대', '치명']
    #     types = ['추락', '협착', '절단', '화재']
    #     disaster_types = ['안전사고', '보건사고']
    #     disaster_forms = ['낙하', '충돌', '전도']
    #     days_of_week = ['월', '화', '수', '목', '금', '토', '일']
        
    #     # 새로운 필드 추가
    #     major_categories = ['제조업', '건설업', 'IT업', '서비스업', '운수업']
    #     location_categories = ['사무실', '생산현장', '창고', '야외', '기타']
        
    #     dummy_accidents.append({
    #         'id': i + 1,
    #         'accident_number': accident_number,
    #         'accident_name': f'사고사례{i+1:03d}',
    #         'accident_date': accident_date_fixed,
    #         'accident_grade': grades[i % 3],
    #         'major_category': major_categories[i % 5],  # 대분류 추가
    #         'accident_type': types[i % 4],
    #         'disaster_type': disaster_types[i % 2],
    #         'disaster_form': disaster_forms[i % 3],
    #         'injury_form': disaster_forms[i % 3],  # 재해형태
    #         'injury_type': disaster_types[i % 2],  # 재해유형
    #         'workplace': f'사업장{(i % 5) + 1}',
    #         'building': f'건물{(i % 10) + 1}',
    #         'floor': f'{(i % 20) + 1}층',
    #         'location_category': location_categories[i % 5],  # 장소구분 추가
    #         'location_detail': f'상세위치{i+1:03d}',  # 세부장소
    #         'created_at': accident_date_fixed,  # 등록일 추가
    #         'day_of_week': days_of_week[i % 7],
    #         'accident_content': f'사고내용{i+1}에 대한 상세 설명입니다.'
    #     })
    
    # DB에서 실제 사고 데이터 가져오기
    conn = get_db_connection(timeout=30.0, row_factory=True)
    cursor = conn.cursor()
    
    # accidents_cache에서 먼저 찾기
    # accident_id가 숫자인지 문자열인지 확인
    if str(accident_id).isdigit():
        cursor.execute("""
            SELECT * FROM accidents_cache 
            WHERE id = ?
            LIMIT 1
        """, (accident_id,))
    else:
        # 문자열 ID인 경우 (ACC로 시작하는 경우 등)
        cursor.execute("""
            SELECT * FROM accidents_cache 
            WHERE accident_number = ?
            LIMIT 1
        """, (accident_id,))
    
    accident = cursor.fetchone()
    
    # 없으면 더미 데이터에서 찾기
    if not accident:
        for acc in dummy_accidents:
            if acc['id'] == accident_id:
                accident = dict(acc)
                break
    else:
        accident = dict(accident)  # Row를 dict로 변환
        
        # ACC 사고의 경우 created_at가 없으면 오늘 날짜로 설정
        if accident.get('accident_number', '').startswith('ACC'):
            if not accident.get('created_at'):
                accident['created_at'] = get_korean_time().strftime('%Y-%m-%d')
    
    if not accident:
        logging.warning(f"사고를 찾을 수 없습니다: {accident_id}")
        conn.close()
        return "사고 정보를 찾을 수 없습니다.", 404
    
    # detailed_content를 custom_data에서 가져오기
    print(f"[DEBUG] accident type before detail query: {type(accident)}")
    if isinstance(accident, dict):
        accident_number = accident['accident_number']
        # custom_data에서 detailed_content 가져오기
        custom_data = accident.get('custom_data', {})
        if isinstance(custom_data, str):
            try:
                custom_data = pyjson.loads(custom_data)
            except:
                custom_data = {}
        elif isinstance(custom_data, dict):
            # PostgreSQL JSONB인 경우 이미 dict
            pass
        else:
            custom_data = {}
        
        # detailed_content 추출
        accident['detailed_content'] = custom_data.get('detailed_content', '')
    else:
        accident_number = getattr(accident, 'accident_number', str(accident))
    
    # accident_attachments 테이블도 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accident_attachments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            accident_number TEXT,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            file_size INTEGER,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 첨부파일 정보 가져오기 - AttachmentService 사용 (공통 모듈)
    from board_services import AttachmentService
    attachment_service = AttachmentService('accident', DB_PATH, conn)
    attachments = attachment_service.list(accident['accident_number'])
    logging.info(f"Accident {accident['accident_number']}: {len(attachments)} attachments found")
    
    # 동적 컬럼 설정 가져오기 (활성+미삭제)
    _wa3 = sql_is_active_true('is_active', conn)
    _wd3 = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(
        f"""
        SELECT * FROM accident_column_config 
        WHERE {_wa3} AND {_wd3}
        ORDER BY column_order
        """
    ).fetchall()
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    # 컬럼 설정이 하나도 없으면 최소 표시 컬럼 세트로 폴백 (DB 시드 누락 보호)
    if not dynamic_columns:
        fallback_cols = [
            # (key, name, type, tab, order)
            ('accident_number','사고번호','text','basic_info',1),
            ('accident_name','사고명','text','basic_info',2),
            ('accident_date','사고일자','date','basic_info',3),
            ('workplace','사업장','text','basic_info',4),
            ('accident_grade','사고등급','dropdown','basic_info',5),
            ('major_category','대분류','dropdown','accident_info',6),
            ('injury_form','상해형태','dropdown','accident_info',7),
            ('injury_type','상해유형','dropdown','accident_info',8),
            ('building','건물','text','location_info',9),
            ('floor','층','text','location_info',10),
            ('location_category','장소분류','text','location_info',11),
            ('location_detail','상세위치','text','location_info',12),
            ('detailed_content','상세내용','textarea','additional',99),
        ]
        dynamic_columns = [
            {
                'column_key': k,
                'column_name': n,
                'column_type': t,
                'tab': tab,
                'column_order': order,
                'is_active': 1,
                'is_deleted': 0,
                'column_span': 1,
            }
            for (k,n,t,tab,order) in fallback_cols
        ]

    # 전역 컬럼 키(활성/비활성 포함) 수집 - 상세 렌더 보정에 사용
    try:
        _wd4 = sql_is_deleted_false('is_deleted', conn)
        _ak_rows = conn.execute(
            f"SELECT column_key FROM accident_column_config WHERE {_wd4}"
        ).fetchall()
        all_keys = set()
        for r in _ak_rows:
            try:
                all_keys.add(r['column_key'])
            except Exception:
                try:
                    all_keys.add(r[0])
                except Exception:
                    pass
        all_keys = {k for k in all_keys if k}
    except Exception:
        all_keys = {c.get('column_key') for c in dynamic_columns if c.get('column_key')}
    
    # column_span을 정수로 변환
    for col in dynamic_columns:
        if col.get('column_span'):
            try:
                col['column_span'] = int(col['column_span'])
            except Exception:
                pass

    # 전역 키 기반으로 베이스 컬럼의 popup_* 타입 보정
    try:
        suffixes = ['_id', '_dept', '_bizno', '_code', '_company']
        def base_key_of(key: str) -> str:
            if not isinstance(key, str):
                return ''
            for s in suffixes:
                if key.endswith(s):
                    return key[:-len(s)]
            return key
        key_set = all_keys
        def infer_group(bk: str) -> str:
            if not bk:
                return ''
            variants = [bk, bk + 'd']
            if any((v + '_bizno') in key_set for v in variants):
                return 'company'
            if any((v + '_dept') in key_set for v in variants):
                return 'person'
            if any((v + '_code') in key_set for v in variants):
                return 'department'
            if any((v + '_company') in key_set for v in variants):
                return 'contractor'
            return ''
        popup_map = {
            'person': 'popup_person',
            'company': 'popup_company',
            'department': 'popup_department',
            'contractor': 'popup_contractor',
        }
        for col in dynamic_columns:
            ck = col.get('column_key')
            ct = col.get('column_type')
            bk = base_key_of(ck)
            grp = infer_group(bk)
            if grp and ck == bk:
                if not ct or ct in ('text', 'popup', 'table', 'table_select'):
                    col['column_type'] = popup_map.get(grp, ct)
                col['input_type'] = col.get('input_type') or 'table'
    except Exception as _e:
        logging.error(f"accident_detail normalize failed: {_e}")

    # 드롭다운 컬럼에 대해 코드-값 매핑 적용
    for col in dynamic_columns:
        if col.get('column_type') == 'dropdown':
            code_options = get_dropdown_options_for_display('accident', col.get('column_key'))
            col['dropdown_options_mapped'] = code_options if code_options else []
    
    # 섹션 키 정규화: 잘못된/없음(tab) → 유효 섹션으로 귀속
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        sections = section_service.get_sections() or []
        known_keys = {s.get('section_key') for s in sections if s.get('section_key')}
        # 과거 키 호환
        alias_map = {'violation_info': 'accident_info'}
        # 기본 귀속 섹션 선택 우선순위: additional → basic_info → 첫 섹션
        fallback_key = (
            ('additional' if 'additional' in known_keys else None)
            or ('basic_info' if 'basic_info' in known_keys else None)
            or (next(iter(known_keys)) if known_keys else None)
        )
        for col in dynamic_columns:
            tab = col.get('tab')
            # alias 보정
            if tab in alias_map and alias_map[tab] in known_keys:
                col['tab'] = alias_map[tab]
                tab = col['tab']
            # 유효하지 않으면 fallback으로 귀속
            if not tab or tab not in known_keys:
                if fallback_key:
                    col['tab'] = fallback_key
    except Exception as _e:
        logging.warning(f"섹션 키 정규화 중 경고: {_e}")

    # 섹션별로 컬럼 그룹핑 + 섹션 내 정렬(column_order, id)
    section_columns = {}
    for section in sections:
        cols = [col for col in dynamic_columns if col.get('tab') == section['section_key']]
        # 안정적인 정렬: column_order -> id
        def _order_key(c):
            try:
                return (int(c.get('column_order') or 0), int(c.get('id') or 0))
            except Exception:
                return (c.get('column_order') or 0, c.get('id') or 0)
        cols.sort(key=_order_key)
        
        # 첫 번째 섹션(basic_info)에 사고번호와 등록일을 강제로 맨 앞에 추가
        if section['section_key'] == 'basic_info':
            # 기존 컬럼에서 사고번호와 등록일 제거
            cols = [c for c in cols if c.get('column_key') not in ['accident_number', 'created_at', 'report_date']]
            
            # 사고번호와 등록일을 강제로 첫 번째 줄에 추가
            mandatory_cols = []
            
            # 사고번호 - 항상 첫 번째
            mandatory_cols.append({
                'column_key': 'accident_number',
                'column_name': '사고번호',
                'column_type': 'text',
                'tab': 'basic_info',
                'column_order': -2,
                'is_active': 1,
                'is_readonly': 1,
                'column_span': 1
            })
            
            # 등록일 - 항상 두 번째 (K사고는 report_date, A사고는 created_at)
            mandatory_cols.append({
                'column_key': 'created_at',  # 템플릿에서 K/A 구분 처리
                'column_name': '등록일',
                'column_type': 'date',
                'tab': 'basic_info',
                'column_order': -1,
                'is_active': 1,
                'is_readonly': 1,
                'column_span': 1
            })
            
            # 강제 컬럼을 앞에 추가
            cols = mandatory_cols + cols
        
        section_columns[section['section_key']] = cols
        logging.info(f"섹션 '{section['section_name']}': {len(section_columns[section['section_key']])}개 컬럼")
    
    # 하위 호환성을 위한 변수 유지 (템플릿이 아직 하드코딩된 경우)
    basic_info_columns = section_columns.get('basic_info', [])
    violation_info_columns = section_columns.get('accident_info', [])  # accident_info로 수정
    additional_columns = section_columns.get('additional', [])
    
    conn.close()
    
    # 딕셔너리를 객체처럼 사용할 수 있도록 변환 (None 값 처리 개선)
    class DictAsAttr:
        def __init__(self, d):
            self._data = d
            for k, v in d.items():
                setattr(self, k, v if v is not None else '')
        
        def __getattr__(self, name):
            # 속성이 없으면 빈 문자열 반환
            return self._data.get(name, '')
    
    # custom_data 파싱 (PostgreSQL JSONB는 이미 dict로 반환됨)
    # json already imported globally
    custom_data = {}
    if 'custom_data' in accident and accident['custom_data']:
        try:
            # PostgreSQL JSONB는 이미 dict, SQLite는 JSON 문자열
            if isinstance(accident['custom_data'], dict):
                custom_data = accident['custom_data']
            else:
                custom_data = pyjson.loads(accident['custom_data'])
            
            # 리스트 필드 추가 처리 (이중 인코딩 문제 해결)
            for key, value in custom_data.items():
                if isinstance(value, str) and value.startswith('['):
                    try:
                        parsed = pyjson.loads(value)
                        if isinstance(parsed, list):
                            custom_data[key] = parsed
                            logging.info(f"Converted string to list for {key}: {len(parsed)} items")
                    except:
                        pass
            
            # custom_data 병합 시 안전 규칙 적용
            # - K사고: 기본(원본) 필드는 보호
            # - 공통: 빈값('' 또는 None)은 상위 필드를 덮지 않음
            # - ACC사고: 기본 필드도 상위가 비어있을 때만 보완적으로 채움
            base_protected_keys = {
                'accident_number','accident_name','workplace','accident_grade','major_category',
                'injury_form','injury_type','building','floor','location_category','location_detail',
                'accident_date','created_at','report_date','day_of_week',
                'responsible_company1','responsible_company1_no','responsible_company2','responsible_company2_no'
            }

            def _is_empty(v):
                try:
                    if v is None:
                        return True
                    if isinstance(v, str) and v.strip() == '':
                        return True
                    return False
                except Exception:
                    return False

            safe_updates = {}
            # 사고번호 기준으로 ACC/K 구분
            acc_no = str(accident.get('accident_number') or '')
            is_direct = acc_no.startswith('ACC')

            for k, v in custom_data.items():
                # 빈값은 덮어쓰지 않음
                if _is_empty(v):
                    continue
                if k in base_protected_keys:
                    if not is_direct:
                        # K사고: 기본키 보호
                        continue
                    # ACC사고: 상위가 비어 있으면 보완 채움
                    top = accident.get(k)
                    if _is_empty(top):
                        safe_updates[k] = v
                else:
                    # 비기본 키는 항상 병합 (값이 비어있지 않을 때)
                    safe_updates[k] = v

            if safe_updates:
                accident.update(safe_updates)
            
            logging.info(f"Loaded and merged custom_data: {custom_data}")
        except Exception as e:
            logging.error(f"Error parsing custom_data: {e}")
            custom_data = {}
    
    # 디버깅: 사고 데이터 확인
    logging.info(f"사고 데이터: {accident}")
    logging.info(f"accident_number: {accident.get('accident_number')}")
    logging.info(f"accident_name: {accident.get('accident_name')}")
    logging.info(f"accident_grade: {accident.get('accident_grade')}")
    logging.info(f"major_category: {accident.get('major_category')}")
    logging.info(f"injury_form: {accident.get('injury_form')}")
    logging.info(f"injury_type: {accident.get('injury_type')}")
    
    accident = DictAsAttr(accident)
    
    logging.info(f"사고 {accident_id} ({accident.accident_name}) 상세 페이지 로드")
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    # ACC로 시작하는 사고번호인지 확인 (직접 등록한 데이터)
    accident_number = accident.accident_number if hasattr(accident, 'accident_number') else accident.get('accident_number', '')
    is_direct_entry = str(accident_number).startswith('ACC')
    logging.info(f"사고번호: {accident_number}, 직접등록여부: {is_direct_entry}")
    
    # 기본정보 드롭다운 옵션 로드 (ACC 사고용)
    basic_options = {}
    if is_direct_entry:
        from board_services import CodeService
        code_service = CodeService('accident', DB_PATH)
        
        # 기본정보 필드들의 드롭다운 옵션 로드
        # injury_form, injury_type이 실제 사용되는 필드명
        basic_fields = ['workplace', 'accident_grade', 'major_category', 
                       'injury_form', 'injury_type', 'floor', 
                       'location_category', 'building']
        
        for field in basic_fields:
            codes = code_service.list(field)
            # 템플릿이 기대하는 형식으로 변환 (option_code -> code, option_value -> value)
            if codes and len(codes) > 0 and 'option_code' in codes[0]:
                codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
            basic_options[field] = codes
            logging.info(f"드롭다운 옵션 로드: {field} -> {len(codes)}개")
        
        # 건물은 마스터 DB에서 우선 로드 (있다면)
        try:
            cursor.execute("""
                SELECT DISTINCT building_code as option_code, 
                       building_name as option_value
                FROM buildings_cache 
                ORDER BY building_name
            """)
            building_rows = cursor.fetchall()
            if building_rows:
                basic_options['building'] = [dict(row) for row in building_rows]
                logging.info(f"건물 마스터에서 {len(building_rows)}개 로드")
        except:
            # 건물 마스터 테이블이 없으면 드롭다운 코드 사용
            pass
    
    # 템플릿 파일 경로 확인 (디버깅)
    import os
    template_path = os.path.join(app.template_folder, 'accident-detail.html')
    print(f"[DEBUG] 렌더링할 템플릿 경로: {template_path}", flush=True)
    print(f"[DEBUG] 템플릿 파일 존재: {os.path.exists(template_path)}", flush=True)
    if os.path.exists(template_path):
        with open(template_path, 'r', encoding='utf-8') as f:
            first_100_lines = f.readlines()[:100]
            for i, line in enumerate(first_100_lines):
                if '기본정보' in line or '사고번호' in line or '대분류' in line:
                    print(f"[DEBUG] 템플릿 라인 {i+1}: {line.strip()}", flush=True)
    
    # 템플릿으로 전달되는 데이터 디버그
    logging.debug(f"accident_detail: accident type {type(accident)}, custom_data type {type(custom_data)}")
    
    return render_template('accident-detail.html', 
                         instruction=accident,  # accident를 instruction으로도 전달 (템플릿 호환성)
                         accident=accident,
                         attachments=attachments,
                         sections=sections,
                         section_columns=section_columns,
                         dynamic_columns=dynamic_columns,  # 동적 컬럼 정보
                         all_column_keys=list(all_keys),  # 전역 컬럼 키 (활성/비활성 포함)
                         basic_info_columns=basic_info_columns,  # 하위 호환성
                         violation_info_columns=violation_info_columns,  # 하위 호환성
                         additional_columns=additional_columns,  # 하위 호환성
                         custom_data=custom_data,  # 기존 데이터
                         basic_options=basic_options,  # 기본정보 드롭다운 옵션
                         menu=MENU_CONFIG, 
                         is_popup=is_popup,
                         is_direct_entry=is_direct_entry,  # ACC 여부 전달
                         board_type='accident')  # 게시판 타입 전달  # 게시판 타입 전달  # 게시판 타입 전달

def get_dropdown_options_for_display(board_type, column_key):
    """보드별 드롭다운 옵션을 코드-값 매핑 방식으로 가져오기
    
    Args:
        board_type: 보드 타입 ('accident', 'safety_instruction', 'change_request' 등)
        column_key: 컬럼 키
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # v2 테이블 우선 확인 (board_type 포함)
        codes = conn.execute("""
            SELECT option_code, option_value 
            FROM dropdown_option_codes_v2
            WHERE board_type = ? AND column_key = ? AND is_active = 1
            ORDER BY display_order
        """, (board_type, column_key)).fetchall()
        
        # v2에서만 조회 (v1 폴백 제거)
        
        conn.close()
        
        if codes:
            # 🔐 방탄: 만약 '단 1행'이고 그 값이 JSON 배열 문자열이면 바로 분해해서 반환
            if len(codes) == 1:
                v = codes[0]['option_value']
                if isinstance(v, str):
                    s = v.strip()
                    if s.startswith('[') and s.endswith(']'):
                        try:
                            arr = pyjson.loads(s)
                            if isinstance(arr, list):
                                # 경고를 디버그 레벨로 변경 (운영 환경에서는 표시되지 않음)
                                logging.debug(
                                    f"[{column_key}] option_value가 배열 문자열로 저장됨. 런타임 분해 처리. "
                                    f"원본={v} (len={len(arr)})"
                                )
                                return [
                                    {'code': f"{column_key.upper()}_{i+1:03d}", 'value': str(item)}
                                    for i, item in enumerate(arr)
                                ]
                        except Exception as e:
                            logging.error(f"[{column_key}] 배열 문자열 파싱 실패: {e}")
            
            # 정상 케이스
            return [{'code': row['option_code'], 'value': row['option_value']} for row in codes]
        else:
            return None
    except:
        return None

def convert_code_to_value_scoped(board_type, column_key, code):
    """보드 스코프에서 코드값을 표시값으로 변환 (v2 우선, v1 폴백)"""
    if not code:
        return code
    if column_key in DROPDOWN_MAPPINGS:
        return DROPDOWN_MAPPINGS[column_key].get(code, code)
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        # v2: board_type 포함 조회
        result = cursor.execute(
            """
            SELECT option_value
            FROM dropdown_option_codes_v2
            WHERE board_type = ? AND column_key = ? AND option_code = ?
            """,
            (board_type, column_key, code),
        ).fetchone()
        if result:
            conn.close()
            return result[0]
        # v1 폴백 제거
        conn.close()
        return code
    except Exception:
        return code

# REMOVED: convert_code_to_value 레거시 함수 제거됨
# 대신 convert_code_to_value_scoped(board_type, column_key, code) 사용

def convert_accident_codes_to_values(accident_data, dynamic_columns):
    """사고 데이터의 코드를 표시 값으로 일괄 변환"""
    if not accident_data or not accident_data.get('custom_data'):
        return accident_data
    
    try:
        custom_data = pyjson.loads(accident_data['custom_data'])
        
        for col in dynamic_columns:
            if col['column_type'] == 'dropdown' and col['column_key'] in custom_data:
                code = custom_data[col['column_key']]
                if code:
                    # 코드를 값으로 변환
                    custom_data[col['column_key']] = convert_code_to_value_scoped('accident', col['column_key'], code)
        
        accident_data['custom_data'] = pyjson.dumps(custom_data, ensure_ascii=False)
    except:
        pass
    
    return accident_data

@app.route("/accident-register")
def accident_register():
    """사고 등록 페이지"""
    logging.info("사고 등록 페이지 접근")
    
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 동적 컬럼 설정 가져오기 - is_deleted 체크 추가
    _wa = sql_is_active_true('is_active', conn)
    _wd = sql_is_deleted_false('is_deleted', conn)
    dynamic_columns_rows = conn.execute(f"""
        SELECT * FROM accident_column_config 
        WHERE {_wa} AND {_wd}
        ORDER BY column_order
    """).fetchall()
    
    # Row 객체를 딕셔너리로 변환
    dynamic_columns = [dict(row) for row in dynamic_columns_rows]
    
    # column_span을 정수로 변환
    for col in dynamic_columns:
        if col.get('column_span'):
            col['column_span'] = int(col['column_span'])
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # 코드-값 매핑 방식으로 옵션 가져오기
            code_options = get_dropdown_options_for_display('accident', col['column_key'])
            # 코드-값 매핑 방식 사용 (DB dropdown_option_codes_v2 테이블)
            col['dropdown_options_mapped'] = code_options if code_options else []
    
    # 기본정보 드롭다운 옵션 로드 (safety-instruction과 동일한 패턴)
    basic_options = {}
    from board_services import CodeService
    code_service = CodeService('accident', DB_PATH)
    
    # 기본정보 필드들의 드롭다운 옵션 로드
    basic_fields = [
        'workplace',            # 사업장
        'accident_grade',       # 사고등급
        'major_category',       # 대분류
        'injury_form',          # 재해형태
        'injury_type',          # 재해유형
        'floor',                # 층수
        'location_category',    # 장소구분
        'building'              # 건물
    ]
    
    for field in basic_fields:
        codes = code_service.list(field)
        # 템플릿이 기대하는 형식으로 변환 (option_code -> code, option_value -> value)
        if codes and len(codes) > 0 and 'option_code' in codes[0]:
            codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
        basic_options[field] = codes
        logging.info(f"드롭다운 옵션 로드: {field} -> {len(codes)}개")
    
    # 건물은 마스터 DB에서 우선 로드 (있다면)
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT building_code as option_code, 
                   building_name as option_value
            FROM buildings_cache 
            WHERE is_active = 1
            ORDER BY building_name
        """)
        building_rows = cursor.fetchall()
        if building_rows:
            basic_options['building'] = [dict(row) for row in building_rows]
            logging.info(f"건물 마스터에서 {len(building_rows)}개 로드")
    except:
        # 건물 마스터 테이블이 없으면 드롭다운 코드 사용
        pass
    
    conn.close()
    
    logging.info(f"동적 컬럼 {len(dynamic_columns)}개 로드됨")
    logging.info(f"기본 옵션 {len(basic_options)}개 필드 로드됨")
    
    # 섹션 정보 로드 - safety-instruction과 동일한 방식
    from section_service import SectionConfigService
    section_service = SectionConfigService('accident', DB_PATH)
    sections = section_service.get_sections()
    logging.info(f"섹션 {len(sections)}개 로드됨")

    # 섹션 키 정규화: 잘못된/없음(tab) → 유효 섹션으로 귀속
    try:
        known_keys = {s.get('section_key') for s in sections if s.get('section_key')}
        alias_map = {'violation_info': 'accident_info'}
        fallback_key = (
            ('additional' if 'additional' in known_keys else None)
            or ('basic_info' if 'basic_info' in known_keys else None)
            or (next(iter(known_keys)) if known_keys else None)
        )
        for col in dynamic_columns:
            tab = col.get('tab')
            if tab in alias_map and alias_map[tab] in known_keys:
                col['tab'] = alias_map[tab]
                tab = col['tab']
            if not tab or tab not in known_keys:
                if fallback_key:
                    col['tab'] = fallback_key
    except Exception as _e:
        logging.warning(f"섹션 키 정규화(등록화면) 경고: {_e}")

    # 섹션별로 컬럼 분류 (동적) + 섹션 내 정렬(column_order, id)
    section_columns = {}
    for section in sections:
        cols = [col for col in dynamic_columns if col.get('tab') == section['section_key']]
        def _order_key(c):
            try:
                return (int(c.get('column_order') or 0), int(c.get('id') or 0))
            except Exception:
                return (c.get('column_order') or 0, c.get('id') or 0)
        cols.sort(key=_order_key)
        
        # 첫 번째 섹션(basic_info)에 사고번호와 등록일을 강제로 맨 앞에 추가
        if section['section_key'] == 'basic_info':
            # 기존 컬럼에서 사고번호와 등록일 제거
            cols = [c for c in cols if c.get('column_key') not in ['accident_number', 'created_at', 'report_date']]
            
            # 사고번호와 등록일을 강제로 첫 번째 줄에 추가
            mandatory_cols = []
            
            # 사고번호 - 항상 첫 번째 (등록 시 자동 생성)
            mandatory_cols.append({
                'column_key': 'accident_number',
                'column_name': '사고번호',
                'column_type': 'text',
                'tab': 'basic_info',
                'column_order': -2,
                'is_active': 1,
                'is_readonly': 1,
                'column_span': 1,
                'default_value': 'ACC' + get_korean_time().strftime('%y%m%d%H%M')  # 자동 생성
            })
            
            # 등록일 - 항상 두 번째
            mandatory_cols.append({
                'column_key': 'created_at',
                'column_name': '등록일',
                'column_type': 'date',
                'tab': 'basic_info',
                'column_order': -1,
                'is_active': 1,
                'is_readonly': 1,
                'column_span': 1,
                'default_value': get_korean_time().strftime('%Y-%m-%d')
            })
            
            # 강제 컬럼을 앞에 추가
            cols = mandatory_cols + cols
        
        section_columns[section['section_key']] = cols
        logging.info(f"섹션 '{section['section_name']}': {len(section_columns[section['section_key']])}개 컬럼")
    
    # 하위 호환성을 위한 변수 유지 (템플릿이 아직 하드코딩된 경우)
    basic_info_columns = section_columns.get('basic_info', [])
    violation_info_columns = section_columns.get('accident_info', [])  # accident_info로 수정
    additional_columns = section_columns.get('additional', [])
    
    # 팝업 모드인지 확인
    is_popup = request.args.get('popup') == '1'
    
    # 현재 날짜 추가 (한국 시간)
    today_date = get_korean_time().strftime('%Y-%m-%d')
    
    return render_template('accident-register.html',
                         dynamic_columns=dynamic_columns,
                         sections=sections,  # 섹션 정보 추가
                         section_columns=section_columns,  # 섹션별 컬럼 추가
                         basic_info_columns=basic_info_columns,  # 하위 호환성
                         violation_info_columns=violation_info_columns,  # 하위 호환성
                         additional_columns=additional_columns,  # 하위 호환성
                         basic_options=basic_options,  # basic_options 추가
                         today_date=today_date,  # 오늘 날짜 추가
                         menu=MENU_CONFIG,
                         is_popup=is_popup)

@app.route("/register-change-request", methods=["POST"])
def register_change_request():
    """새 변경요청 등록"""
    conn = None
    try:
        from board_services import AttachmentService
        from timezone_config import get_korean_time, get_korean_time_str
        
        # FormData로 전송된 데이터 파싱
        data = pyjson.loads(request.form.get('data', '{}'))
        attachment_data = pyjson.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        logging.info(f"변경요청 등록 요청 받음 - 데이터: {data}")
        logging.info(f"첨부파일 개수: {len(files)}")
        
        # 변경요청 번호 생성 (CR-YYYYMM-NN 형식으로 통일)
        today = get_korean_time()
        year_month = today.strftime('%Y%m')
        request_number_prefix = f"CR-{year_month}-"
        
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # request_id 초기화
        request_id = None
        
        # 오늘 날짜의 마지막 요청번호 찾기 - partner_change_requests 테이블에서
        cursor.execute("""
            SELECT request_number FROM partner_change_requests 
            WHERE request_number LIKE ? 
            ORDER BY request_number DESC 
            LIMIT 1
        """, (f"{request_number_prefix}%",))
        
        last_request = cursor.fetchone()
        if last_request:
            last_num = int(last_request[0][-2:])
            new_num = str(last_num + 1).zfill(2)
        else:
            new_num = "01"
        
        request_number = f"{request_number_prefix}{new_num}"
        
        # partner_change_requests 테이블에 저장 (메인 테이블)
        try:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS partner_change_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    request_number TEXT UNIQUE,
                    requester_name TEXT,
                    requester_department TEXT,
                    company_name TEXT,
                    business_number TEXT,
                    change_type TEXT,
                    current_value TEXT,
                    new_value TEXT,
                    change_reason TEXT,
                    status TEXT DEFAULT 'requested',
                    created_at TIMESTAMP,
                    updated_at TIMESTAMP,
                    custom_data TEXT,
                    is_deleted INTEGER DEFAULT 0
                )
            """)
            
            # 상태를 강제로 'requested' (요청)으로 설정
            data['status'] = 'requested'
            
            cursor.execute("""
                INSERT INTO partner_change_requests 
                (request_number, requester_name, requester_department, company_name, 
                 business_number, change_reason, status, created_at, updated_at, custom_data,
                 change_type, current_value, new_value)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                request_number,
                data.get('requester_name', data.get('req_name', '')),
                data.get('requester_department', data.get('req_name_dept', '')),
                data.get('company_name', data.get('compname', '')),
                data.get('business_number', data.get('compname_bizno', '')),
                data.get('change_reason', ''),
                'requested',
                get_korean_time_str(),
                get_korean_time_str(),
                pyjson.dumps(data),
                data.get('change_type', ''),
                data.get('current_value', ''),
                data.get('new_value', '')
            ))
            request_id = cursor.fetchone()[0]  # RETURNING id 결과 가져오기
            logging.info(f"partner_change_requests 테이블에 저장 완료: ID={request_id}")
        except Exception as e:
            logging.error(f"partner_change_requests 테이블 저장 실패: {e}")

        # 첨부파일 저장: request_number 를 item_id로 사용
        try:
            if files:
                from board_services import AttachmentService as _AS
                _asvc = _AS('change_request', DB_PATH, conn)
                for idx, _f in enumerate(files):
                    _desc = ''
                    if idx < len(attachment_data) and isinstance(attachment_data[idx], dict):
                        _desc = attachment_data[idx].get('description', '')
                    _asvc.add(request_number, _f, {'description': _desc, 'uploaded_by': session.get('user_id', 'user')})
        except Exception as _e:
            logging.error(f"첨부파일 저장 실패: {_e}")
        
        # 첨부파일 처리 (AttachmentService 사용)
        # 첨부파일 처리 (현재 비활성화)
        if False and (files or attachment_data):
            # AttachmentService 사용시 올바른 패턴
            # attachment_service = AttachmentService('change_request', DB_PATH, conn)
            # for file in files:
            #     attachment_service.add(request_number, file, {'uploaded_by': 'user'})
            pass
        
        conn.commit()
        conn.close()
        
        logging.info(f"변경요청 등록 완료 - 번호: {request_number}, ID: {request_id if request_id else 'N/A'}")
        
        return jsonify({
            "success": True,
            "request_id": request_id,
            "request_number": request_number,
            "message": "변경요청이 성공적으로 등록되었습니다."
        })
        
    except Exception as e:
        logging.error(f"변경요청 등록 중 오류: {e}")
        if conn:
            conn.rollback()
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/register-accident", methods=["POST"])
def register_accident():
    """새 사고 등록"""
    conn = None
    try:
        # json already imported globally
        import datetime
        
        # 기본정보 필드들 받기 (ACCIDENTS_QUERY와 동일한 14개 필드 + α)
        accident_number = ''  # 자동생성
        accident_name = request.form.get('accident_name', '')
        print(f"[DEBUG] accident_name received: '{accident_name}'")  # 디버깅
        workplace = request.form.get('workplace', '')
        accident_grade = request.form.get('accident_grade', '')
        major_category = request.form.get('major_category', '')
        injury_form = request.form.get('injury_form', '')
        injury_type = request.form.get('injury_type', '')
        accident_date = request.form.get('accident_date', '')
        day_of_week = request.form.get('day_of_week', '')
        # 등록일은 항상 오늘 날짜(한국 시간)로 설정
        created_at = get_korean_time().strftime('%Y-%m-%d')
        building = request.form.get('building', '')
        floor = request.form.get('floor', '')
        location_category = request.form.get('location_category', '')
        location_detail = request.form.get('location_detail', '')
        
        detailed_content = request.form.get('detailed_content')
        custom_data = pyjson.loads(request.form.get('custom_data', '{}'))  # 동적 컬럼
        attachment_data = pyjson.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        print(f"=== 등록 요청 받음 ===")
        print(f"사고명: {accident_name}")
        print(f"사고 날짜: {accident_date}")
        print(f"받은 모든 form 데이터:")
        for key in request.form.keys():
            print(f"  {key}: {request.form.get(key)}")
        
        print(f"custom_data 원본: {request.form.get('custom_data', 'None')}")
        print(f"custom_data 파싱 후: {custom_data}")
        print(f"custom_data 키: {list(custom_data.keys())}")
        print(f"첨부파일 개수: {len(files)}")
        
        # 리스트 타입 필드 확인 및 처리
        list_fields = []
        for key, value in custom_data.items():
            # 이미 리스트인 경우 (클라이언트에서 제대로 파싱한 경우)
            if isinstance(value, list):
                list_fields.append(key)
                print(f"✅ 리스트 필드 정상 - {key}: {len(value)}개 항목")
            # 문자열로 저장된 리스트 (이중 인코딩 문제)
            elif isinstance(value, str) and value.startswith('['):
                list_fields.append(key)
                print(f"⚠️ 문자열로 된 리스트 필드 발견 - {key}: {value}")
                try:
                    # 문자열을 실제 리스트로 변환
                    parsed_value = pyjson.loads(value)
                    custom_data[key] = parsed_value
                    print(f"   → 리스트로 변환 성공: {len(parsed_value)}개 항목")
                except:
                    print(f"   → 리스트로 변환 실패, 빈 배열로 설정")
                    custom_data[key] = []
        print(f"발견된 리스트 필드: {list_fields}")
        
        logging.info(f"등록 요청 받음 - 사고명: {accident_name}")
        logging.info(f"동적 컬럼 데이터: {custom_data}")
        logging.info(f"리스트 필드: {list_fields}")
        
        # 새 사고번호 생성 (수기입력: ACCYYMMDD00 형식)
        # 한국 시간 기준으로 생성
        korean_now = get_korean_time()
        date_part = korean_now.strftime('%y%m%d')  # YYMMDD 형식
        accident_number_prefix = f"ACC{date_part}"
        
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # 오늘 날짜의 마지막 사고번호 찾기
        cursor.execute("""
            SELECT accident_number FROM accidents_cache 
            WHERE accident_number LIKE %s 
            ORDER BY accident_number DESC 
            LIMIT 1
        """, (f"{accident_number_prefix}%",))
        
        last_accident = cursor.fetchone()
        if last_accident:
            # 마지막 번호에서 1 증가 (뒤 2자리)
            last_num = int(last_accident[0][-2:])
            accident_number = f"{accident_number_prefix}{str(last_num + 1).zfill(2)}"
        else:
            accident_number = f"{accident_number_prefix}01"
        
        logging.info(f"새 사고 등록: {accident_number}")
        
        # 1. 기본 사고 정보 등록 (기본정보 + 동적 컬럼)
        # 필요한 컬럼들이 없는 경우 추가
        cursor.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        # 필수 컬럼들 체크 및 추가
        required_columns = [
            ('accident_number', 'TEXT'),
            ('accident_name', 'TEXT'),
            ('accident_date', 'TEXT'),
            ('accident_datetime', 'TEXT'),
            ('accident_grade', 'TEXT'),
            ('accident_type', 'TEXT'),
            ('injury_type', 'TEXT'),
            ('injury_form', 'TEXT'),
            ('workplace', 'TEXT'),
            ('report_date', 'TEXT'),
            ('building', 'TEXT'),
            ('floor', 'TEXT'),
            ('location_detail', 'TEXT'),
            ('day_of_week', 'TEXT'),
            ('major_category', 'TEXT'),
            ('location_category', 'TEXT'),
            ('created_at', 'TEXT'),
            ('custom_data', 'TEXT')
        ]
        
        for col_name, col_type in required_columns:
            if col_name not in columns:
                cursor.execute(f"ALTER TABLE accidents_cache ADD COLUMN {col_name} {col_type}")
                logging.info(f"컬럼 추가: {col_name}")
        
        # datetime 조합 (정렬용)
        if accident_date:
            accident_datetime = f"{accident_date} 00:00"
        else:
            accident_datetime = get_korean_time().strftime('%Y-%m-%d %H:%M')
        
        print(f"[DEBUG] Inserting accident with name: '{accident_name or f'사고_{accident_number}'}'")  # 디버깅
        # report_date: 사고일자 있으면 그것, 없으면 오늘 날짜
        report_date_value = (accident_date or created_at)
        cursor.execute("""
            INSERT INTO accidents_cache (
                accident_number,
                accident_name,
                workplace,
                accident_grade,
                major_category,
                injury_form,
                injury_type,
                accident_date,
                day_of_week,
                report_date,
                created_at,
                building,
                floor,
                location_category,
                location_detail,
                custom_data
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            accident_number,
            accident_name or f"사고_{accident_number}",
            workplace or '',
            accident_grade or '',
            major_category or '',
            injury_form or '',
            injury_type or '',
            accident_date or korean_now.strftime('%Y-%m-%d'),
            day_of_week or '',
            report_date_value,
            created_at or korean_now.strftime('%Y-%m-%d'),
            building or '',
            floor or '',
            location_category or '',
            location_detail or '',
            pyjson.dumps(custom_data)
        ))
        
        # 2. 상세내용을 custom_data에 저장
        if detailed_content:
            # 기존 custom_data 가져오기
            cursor.execute("SELECT custom_data FROM accidents_cache WHERE accident_number = ?", (accident_number,))
            row = cursor.fetchone()
            existing_custom_data = {}
            if row and row[0]:
                if isinstance(row[0], str):
                    try:
                        existing_custom_data = pyjson.loads(row[0])
                    except:
                        existing_custom_data = {}
                elif isinstance(row[0], dict):
                    existing_custom_data = row[0]
            
            # detailed_content 추가
            existing_custom_data['detailed_content'] = detailed_content
            
            # custom_data 업데이트
            cursor.execute("""
                UPDATE accidents_cache 
                SET custom_data = ?
                WHERE accident_number = ?
            """, (pyjson.dumps(existing_custom_data), accident_number))
        
        # 3. 첨부파일 처리
        if files:
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'accidents')
            os.makedirs(upload_folder, exist_ok=True)
            
            for i, file in enumerate(files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = get_korean_time().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{accident_number}_{timestamp}_{filename}"
                    file_path = os.path.join(upload_folder, unique_filename)
                    
                    file.save(file_path)
                    
                    # 첨부파일 정보 저장
                    description = attachment_data[i]['description'] if i < len(attachment_data) else ''
                    cursor.execute("""
                        INSERT INTO accident_attachments (accident_number, file_name, file_path, file_size, description)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (accident_number, filename, file_path, os.path.getsize(file_path), description))
        
        conn.commit()
        
        # 저장 확인
        cursor.execute("SELECT custom_data FROM accidents_cache WHERE accident_number = ?", (accident_number,))
        saved_data = cursor.fetchone()
        if saved_data:
            print(f"DB에 저장된 custom_data: {saved_data[0]}")
            try:
                parsed_saved = pyjson.loads(saved_data[0]) if saved_data[0] else {}
                print(f"DB에서 파싱된 데이터: {parsed_saved}")
            except:
                print("DB에서 JSON 파싱 실패")
        
        logging.info(f"사고 {accident_number} 등록 완료")
        print(f"=== 등록 완료: {accident_number} ===")
        
        return jsonify({"success": True, "accident_number": accident_number})
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"사고 등록 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)})
    finally:
        if conn:
            conn.close()

@app.route("/register-safety-instruction", methods=["POST"])
def register_safety_instruction():
    """새 환경안전 지시서 등록"""
    conn = None
    try:
        # json already imported globally
        import datetime
        
        # basic_info와 violation_info JSON 파싱
        basic_info = pyjson.loads(request.form.get('basic_info', '{}'))
        violation_info = pyjson.loads(request.form.get('violation_info', '{}'))
        
        # 개별 필드 추출 (basic_info에서)
        issue_number = basic_info.get('issue_number', '')  # 발부번호 (자동생성)
        issuer = basic_info.get('issuer', '')  # 발행인
        issuer_department = basic_info.get('issuer_department', '')  # 발행부서
        classification = basic_info.get('classification', '')  # 분류
        employment_type = basic_info.get('employment_type', '')  # 고용형태
        primary_company = basic_info.get('primary_company', '')  # 1차사명
        primary_business_number = basic_info.get('primary_business_number', '')  # 1차사_사업자번호
        subcontractor = basic_info.get('subcontractor', '')  # 하도사명
        subcontractor_business_number = basic_info.get('subcontractor_business_number', '')  # 하도사_사업자번호
        disciplined_person = basic_info.get('disciplined_person', '')  # 징계자
        gbm = basic_info.get('gbm', '')  # GBM
        business_division = basic_info.get('business_division', '')  # 사업부
        team = basic_info.get('team', '')  # 팀
        department = basic_info.get('department', '')  # 소속부서
        
        # 개별 필드 추출 (violation_info에서)
        violation_date = violation_info.get('violation_date', '')  # 위반일자
        discipline_date = violation_info.get('discipline_date', '')  # 징계일자
        discipline_department = violation_info.get('discipline_department', '')  # 징계발의부서
        discipline_type = violation_info.get('discipline_type', '')  # 징계유형
        accident_type = violation_info.get('accident_type', '')  # 사고유형
        accident_grade = violation_info.get('accident_grade', '')  # 사고등급
        safety_violation_grade = violation_info.get('safety_violation_grade', '')  # 환경안전수칙 위반등급
        violation_type = violation_info.get('violation_type', '')  # 위반유형
        access_ban_start_date = violation_info.get('access_ban_start_date', '')  # 출입정지 시작일
        access_ban_end_date = violation_info.get('access_ban_end_date', '')  # 출입정지 종료일
        period = violation_info.get('period', '')  # 기간
        work_grade = violation_info.get('work_grade', '')  # 작업등급
        penalty_points = violation_info.get('penalty_points', '')  # 감점
        disciplined_person_id = violation_info.get('disciplined_person_id', '')  # 징계자ID
        
        # 상세내용
        detailed_content = request.form.get('detailed_content', '')  # 상세내용
        
        # 동적 컬럼 및 첨부파일
        custom_data = pyjson.loads(request.form.get('custom_data', '{}'))
        attachment_data = pyjson.loads(request.form.get('attachment_data', '[]'))
        files = request.files.getlist('files')
        
        logging.info(f"환경안전 지시서 등록 요청 받음 - 징계자: {disciplined_person}")
        logging.info(f"위반일자: {violation_date}, 징계일자: {discipline_date}")
        logging.info(f"동적 컬럼 데이터: {custom_data}")
        logging.info(f"첨부파일 개수: {len(files)}")
        
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # 발부번호 자동 생성 (YYYY-MM-00 형식)
        if violation_date:
            # 위반일자를 기준으로 년월 추출
            try:
                date_obj = datetime.datetime.strptime(violation_date, '%Y-%m-%d')
                year_month = f"{date_obj.year}-{date_obj.month:02d}"
            except ValueError:
                # 파싱 실패시 한국 시간 기준 현재 날짜 사용
                korean_now = get_korean_time()
                year_month = f"{korean_now.year}-{korean_now.month:02d}"
        else:
            # 위반일자가 없으면 한국 시간 기준 현재 날짜 사용
            korean_now = get_korean_time()
            year_month = f"{korean_now.year}-{korean_now.month:02d}"
        
        # 해당 년월의 마지막 발부번호 찾기 (메인 테이블에서)
        cursor.execute("""
            SELECT issue_number FROM safety_instructions 
            WHERE issue_number LIKE ? 
            ORDER BY issue_number DESC 
            LIMIT 1
        """, (f"{year_month}-%",))
        
        last_instruction = cursor.fetchone()
        if last_instruction:
            # 마지막 번호에서 1 증가 (뒤 2자리)
            last_num = int(last_instruction[0].split('-')[2])
            generated_issue_number = f"{year_month}-{str(last_num + 1).zfill(2)}"
        else:
            generated_issue_number = f"{year_month}-01"
        
        logging.info(f"새 환경안전 지시서 발부번호 생성: {generated_issue_number}")
        
        # 모든 동적 데이터를 custom_data에 포함
        all_custom_data = {
            'issuer': issuer,
            'issuer_department': issuer_department,
            'classification': classification,
            'employment_type': employment_type,
            'primary_company': primary_company,
            'primary_business_number': primary_business_number,
            'subcontractor': subcontractor,
            'subcontractor_business_number': subcontractor_business_number,
            'disciplined_person': disciplined_person,
            'disciplined_person_id': disciplined_person_id,
            'gbm': gbm,
            'business_division': business_division,
            'team': team,
            'work_grade': work_grade,
            'violation_date': violation_date,
            'discipline_date': discipline_date,
            'discipline_department': discipline_department,
            'discipline_type': discipline_type,
            'accident_type': accident_type,
            'accident_grade': accident_grade,
            'safety_violation_grade': safety_violation_grade,
            'violation_type': violation_type,
            'access_ban_start_date': access_ban_start_date,
            'access_ban_end_date': access_ban_end_date,
            'period': period,
            'penalty_points': int(penalty_points) if penalty_points else None,
            'detailed_content': detailed_content
        }
        
        # 기존 custom_data와 병합
        all_custom_data.update(custom_data)
        
        # 메인 테이블에 등록 - created_at은 DEFAULT 사용, 상세내용은 컬럼에 저장
        from db.upsert import safe_upsert
        main_data = {
            'issue_number': generated_issue_number,
            'custom_data': pyjson.dumps(all_custom_data),
            'detailed_content': detailed_content,
            'is_deleted': 0,
            'created_at': None,   # DEFAULT CURRENT_TIMESTAMP
            'updated_at': None    # 자동 처리
        }
        # 안전한 UPSERT (issue_number 기준)
        safe_upsert(
            conn,
            'safety_instructions',
            main_data,
            conflict_cols=['issue_number'],
            update_cols=['custom_data', 'detailed_content', 'updated_at', 'is_deleted']
        )
        
        # 첨부파일 처리
        if files:
            # 첨부파일 테이블 생성
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS safety_instruction_attachments (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    issue_number TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    description TEXT,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (issue_number) REFERENCES safety_instructions (issue_number)
                )
            """)
            
            upload_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads', 'safety_instructions')
            os.makedirs(upload_folder, exist_ok=True)
            
            for i, file in enumerate(files):
                if file and file.filename:
                    filename = secure_filename(file.filename)
                    timestamp = get_korean_time().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{generated_issue_number}_{timestamp}_{filename}".replace('-', '_')
                    file_path = os.path.join(upload_folder, unique_filename)
                    
                    file.save(file_path)
                    
                    # 첨부파일 정보 저장
                    description = attachment_data[i]['description'] if i < len(attachment_data) else ''
                    cursor.execute("""
                        INSERT INTO safety_instruction_attachments (issue_number, file_name, file_path, file_size, description)
                        VALUES (%s, %s, %s, %s, %s)
                    """, (generated_issue_number, filename, file_path, os.path.getsize(file_path), description))
        
        conn.commit()
        logging.info(f"환경안전 지시서 {generated_issue_number} 등록 완료")
        
        return jsonify({"success": True, "issue_number": generated_issue_number})
        
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"환경안전 지시서 등록 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)})
    finally:
        if conn:
            conn.close()

@app.route("/verify-password", methods=["POST"])
def verify_password():
    """게시판별 비밀번호 검증"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "message": "No data received"}), 400
            
        password = data.get('password')
        board_type = data.get('board_type', 'default')  # partner, accident, 또는 default
        
        if not password:
            return jsonify({"success": False, "message": "Password not provided"}), 400
        
        # 게시판 타입별 비밀번호 확인
        correct_password = None
        
        if board_type == 'partner':
            # 협력사 게시판 비밀번호
            correct_password = db_config.config.get('PASSWORDS', 'PARTNER_EDIT_PASSWORD', fallback=None)
        elif board_type == 'accident':
            # 사고 게시판 비밀번호
            correct_password = db_config.config.get('PASSWORDS', 'ACCIDENT_EDIT_PASSWORD', fallback=None)
        else:
            # 기본 비밀번호 (기존 호환성)
            correct_password = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
        
        # 비밀번호가 설정되지 않은 경우 기본 비밀번호 사용
        if not correct_password:
            correct_password = db_config.config.get('DEFAULT', 'EDIT_PASSWORD')
        
        logging.info(f"비밀번호 검증 요청: board_type={board_type}")
        
        if password == correct_password:
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "message": "비밀번호가 올바르지 않습니다."})
    except Exception as e:
        logging.error(f"비밀번호 검증 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-partner", methods=["POST"])
def update_partner():
    """협력사 정보 업데이트"""
    conn = None
    try:
        # json already imported globally
        
        business_number = request.form.get('business_number')
        detailed_content = request.form.get('detailed_content')
        
        # 안전하게 JSON 파싱
        try:
            deleted_attachments = pyjson.loads(request.form.get('deleted_attachments', '[]'))
        except:
            deleted_attachments = []
        
        try:
            attachment_data_raw = request.form.get('attachment_data', '[]')
            if isinstance(attachment_data_raw, str):
                attachment_data = pyjson.loads(attachment_data_raw)
            else:
                attachment_data = attachment_data_raw
            # 리스트가 아닌 경우 빈 리스트로
            if not isinstance(attachment_data, list):
                attachment_data = []
        except Exception as e:
            logging.warning(f"attachment_data 파싱 실패: {e}")
            attachment_data = []
        
        files = request.files.getlist('files')
        
        print(f"Business Number: {business_number}")
        print(f"Files count: {len(files)}")
        print(f"Attachment data: {attachment_data}")
        
        # 협력사 존재 여부 확인 (먼저 확인)
        partner = partner_manager.get_partner_by_business_number(business_number)
        if not partner:
            from flask import jsonify
            return jsonify({"success": False, "message": "협력사를 찾을 수 없습니다."})
        
        print(f"Connecting to database (unified backend)")
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        logging.info(f"업데이트 대상 협력사: {business_number}")
        
        # 1. 협력사 상세내용 업데이트 (partner_details 테이블)
        logging.info(f"상세내용 업데이트: {detailed_content[:50]}...")
        # partner_details safe_upsert 사용
        detail_data = {
            'business_number': business_number,
            'detailed_content': detailed_content,
            'updated_at': None  # 자동으로 처리됨
        }
        safe_upsert(conn, 'partner_details', detail_data)
        logging.info("상세내용 업데이트 완료")
        
        # 2. 삭제된 첨부파일 처리
        for attachment_id in deleted_attachments:
            cursor.execute("DELETE FROM partner_attachments WHERE id = ?", (attachment_id,))
        
        # 3. 기존 첨부파일 정보 업데이트
        for attachment in attachment_data:
            # attachment가 딕셔너리인지 확인
            if isinstance(attachment, dict):
                if attachment.get('id') and not attachment.get('isNew'):
                    cursor.execute("""
                        UPDATE partner_attachments 
                        SET description = ? 
                        WHERE id = ?
                    """, (attachment.get('description', ''), attachment['id']))
            else:
                logging.warning(f"attachment가 딕셔너리가 아님: {type(attachment)}")
        
        # 4. 새 파일 업로드 처리
        import os
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # 새 파일들과 새 첨부파일 데이터 매칭
        new_attachments = [a for a in attachment_data if isinstance(a, dict) and a.get('isNew')]
        print(f"New attachments: {new_attachments}")
        
        for i, file in enumerate(files):
            if file.filename and i < len(new_attachments):
                filename = file.filename
                # 파일명에 타임스탬프 추가하여 중복 방지
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}{ext}"
                file_path = os.path.join(upload_folder, unique_filename)
                
                print(f"Saving file: {filename} as {unique_filename}")
                file.save(file_path)
                
                attachment_info = new_attachments[i]
                cursor.execute("""
                    INSERT INTO partner_attachments 
                    (business_number, file_name, file_path, file_size, description)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    business_number,
                    filename,  # 원본 파일명으로 저장
                    file_path,
                    os.path.getsize(file_path),
                    attachment_info.get('description', '')
                ))
                logging.info(f"첨부파일 추가: {filename} - {attachment_info.get('description', '')}")
        
        # 커밋 전 확인
        check_result = cursor.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
        logging.info(f"커밋 전 {business_number} 협력사 첨부파일 개수: {check_result[0]}개")
        
        try:
            conn.commit()
            logging.info("데이터베이스 커밋 성공")
            
            # 커밋 후 다시 확인
            check_result2 = cursor.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
            logging.info(f"커밋 후 {business_number} 협력사 첨부파일 개수: {check_result2[0]}개")
            
            conn.close()
            
            # 새로운 연결로 다시 확인
            logging.info("새 연결로 데이터 지속성 확인...")
            verify_conn = get_db_connection()
            verify_result = verify_conn.execute("SELECT COUNT(*) FROM partner_attachments WHERE business_number = ?", (business_number,)).fetchone()
            logging.info(f"새 연결 확인: {business_number} 협력사 첨부파일 개수: {verify_result[0]}개")
            verify_conn.close()
            
            from flask import jsonify
            return jsonify({"success": True})
        except Exception as commit_error:
            print(f"Commit failed: {commit_error}")
            conn.rollback()
            conn.close()
            from flask import jsonify
            return jsonify({"success": False, "message": f"Commit failed: {str(commit_error)}"})
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        from flask import jsonify
        logging.error(f"업데이트 중 오류 발생: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/update-accident", methods=["POST"])
def update_accident():
    """사고 정보 업데이트"""
    conn = None
    try:
        # json already imported globally
        
        accident_number = request.form.get('accident_number')
        
        # K 사고도 수정 가능하되, 기본정보는 업데이트하지 않고 custom_data/첨부만 반영
        
        detailed_content = request.form.get('detailed_content', '')
        custom_data = request.form.get('custom_data', '{}')  # Phase 2: 동적 컬럼 데이터
        base_fields = request.form.get('base_fields', '{}')  # ACC 사고일 때 기본정보
        
        # 상세내용 디버깅
        print(f"[FORM DEBUG] detailed_content RAW: '{detailed_content}'")
        print(f"[FORM DEBUG] detailed_content length: {len(detailed_content) if detailed_content else 0}")
        print(f"[FORM DEBUG] detailed_content type: {type(detailed_content)}")
        
        # detailed_content만 사용하도록 통일
        final_content = detailed_content
        print(f"[FORM DEBUG] 최종 사용할 내용: '{final_content[:100] if final_content else None}'...")
        print(f"[FORM DEBUG] 최종 내용 길이: {len(final_content) if final_content else 0}")
        
        # 안전하게 JSON 파싱
        try:
            deleted_attachments = pyjson.loads(request.form.get('deleted_attachments', '[]'))
        except:
            deleted_attachments = []
        
        try:
            attachment_data_raw = request.form.get('attachment_data', '[]')
            if isinstance(attachment_data_raw, str):
                attachment_data = pyjson.loads(attachment_data_raw)
            else:
                attachment_data = attachment_data_raw
            # 리스트가 아닌 경우 빈 리스트로
            if not isinstance(attachment_data, list):
                attachment_data = []
        except Exception as e:
            logging.warning(f"attachment_data 파싱 실패: {e}")
            attachment_data = []
        files = request.files.getlist('files')
        
        print(f"=== UPDATE_ACCIDENT FULL DEBUG START ===")
        print(f"Accident Number: {accident_number}")
        print(f"Custom Data received: {custom_data}")
        print(f"Custom Data type: {type(custom_data)}")
        print(f"Detailed Content received: '{detailed_content}'")
        print(f"Detailed Content length: {len(detailed_content) if detailed_content else 0}")
        print(f"Request form keys: {list(request.form.keys())}")
        print(f"Attachment data received: {attachment_data}")
        print(f"Files received: {len(files)} files")
        
        # 모든 form 데이터 출력
        print(f"=== ALL FORM DATA ===")
        for key in request.form.keys():
            value = request.form.get(key)
            if key == 'custom_data':
                print(f"  {key}: {value[:100]}... (length: {len(value)})")
            else:
                print(f"  {key}: '{value}'")
        
        # custom_data 파싱
        if isinstance(custom_data, str):
            try:
                custom_data = pyjson.loads(custom_data)
                print(f"Custom Data parsed: {custom_data}")
                print(f"Custom Data keys: {list(custom_data.keys())}")
                if 'injured_person' in custom_data:
                    injured_person = custom_data['injured_person']
                    print(f"injured_person type: {type(injured_person)}, value: {injured_person}")
            except Exception as e:
                print(f"Custom Data parsing failed: {e}")
                custom_data = {}
        
        # 리스트 필드 정규화 (이중 JSON 인코딩 방지)
        for key, value in custom_data.items():
            if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
                try:
                    # 이미 JSON 문자열인 리스트 필드를 배열로 변환
                    custom_data[key] = pyjson.loads(value)
                    print(f"List field {key} normalized from string to array")
                except:
                    pass
        
        print(f"Files count: {len(files)}")
        print(f"Attachment data: {attachment_data}")
        
        print(f"Connecting to database: {DB_PATH}")
        conn = get_db_connection(timeout=30.0)
        cursor = conn.cursor()
        
        # 사고번호가 없으면 자동 생성 (수기입력용)
        if not accident_number:
            accident_number = generate_manual_accident_number(cursor)
            logging.info(f"자동 생성된 사고번호: {accident_number}")
        
        # 사고 형식 검증 (K로 시작하는 외부시스템 사고 또는 ACC로 시작하는 수기입력 사고)
        if not (accident_number.startswith('K') or accident_number.startswith('ACC')):
            from flask import jsonify
            return jsonify({"success": False, "message": "잘못된 사고번호 형식입니다."})
        
        logging.info(f"업데이트 대상 사고: {accident_number}")
        
        # 기본정보 업데이트 정책
        # - K사고: 기본정보 미수정 (custom_data/첨부만 반영)
        # - ACC사고: 기본정보 수정 허용하되, 빈값('' 또는 None)은 덮어쓰지 않음
        is_direct_entry = accident_number.startswith('ACC')
        if is_direct_entry and base_fields != '{}':
            try:
                base_data = pyjson.loads(base_fields)
                logging.info(f"ACC 사고 기본정보 업데이트 요청: {base_data}")

                # 허용된 필드만 업데이트 (SQL injection 방지)
                allowed_fields = [
                    'accident_name', 'accident_date', 'workplace', 'accident_grade',
                    'major_category', 'injury_form', 'injury_type', 'building', 'floor',
                    'location_category', 'location_detail', 'created_at', 'day_of_week'
                ]

                def _is_empty(v):
                    try:
                        if v is None:
                            return True
                        if isinstance(v, str) and v.strip() == '':
                            return True
                        return False
                    except Exception:
                        return False

                # 업데이트할 필드와 값 준비 (빈값은 스킵)
                update_fields = []
                update_values = []
                for field in allowed_fields:
                    if field in base_data:
                        value = base_data[field]
                        if _is_empty(value):
                            # 빈값은 기존 데이터를 덮어쓰지 않음
                            continue
                        update_fields.append(f"{field} = %s")
                        update_values.append(value)

                if update_fields:
                    update_values.append(accident_number)  # WHERE 절용
                    update_query = f"""
                        UPDATE accidents_cache 
                        SET {', '.join(update_fields)}
                        WHERE accident_number = %s
                    """
                    cursor.execute(update_query, update_values)
                    logging.info(f"ACC 사고 기본정보 업데이트 완료: {len(update_fields)}개 필드")
                else:
                    logging.info("ACC 사고 기본정보 변경 없음(모든 값이 빈값/미포함)")
            except Exception as e:
                logging.error(f"ACC 사고 기본정보 업데이트 중 오류: {e}")
        
        # 먼저 해당 사고가 accidents_cache에 있는지 확인
        cursor.execute("SELECT id FROM accidents_cache WHERE accident_number = %s", (accident_number,))
        accident_row = cursor.fetchone()
        
        if accident_row:
            # 기존 custom_data를 먼저 가져와서 병합
            cursor.execute("SELECT custom_data FROM accidents_cache WHERE accident_number = %s", (accident_number,))
            existing_row = cursor.fetchone()
            existing_custom_data = {}
            
            if existing_row and existing_row[0]:
                if isinstance(existing_row[0], dict):
                    # PostgreSQL JSONB - 깊은 복사로 안전하게 처리
                    existing_custom_data = pyjson.loads(pyjson.dumps(existing_row[0]))
                elif isinstance(existing_row[0], str):
                    # SQLite JSON 문자열
                    try:
                        existing_custom_data = pyjson.loads(existing_row[0])
                    except:
                        existing_custom_data = {}
            
            print(f"[MERGE DEBUG] 기존 데이터 keys: {list(existing_custom_data.keys())}")
            print(f"[MERGE DEBUG] 새 데이터 keys: {list(custom_data.keys())}")
            
            # 특별히 injured_person은 덮어쓰지 않고 보존
            if 'injured_person' in existing_custom_data and 'injured_person' not in custom_data:
                print(f"[MERGE DEBUG] injured_person 보존: {type(existing_custom_data['injured_person'])}")
                # injured_person이 새 데이터에 없으면 기존 것 보존
            elif 'injured_person' in custom_data:
                # injured_person이 새 데이터에 있으면 그것 사용
                print(f"[MERGE DEBUG] injured_person 업데이트: {type(custom_data['injured_person'])}")
            
            # K사고 보호 및 안전 병합 규칙
            # - K사고: IQADB(원본) 기본 필드는 custom_data로 덮지 않음
            # - 공통: 빈값('' 또는 None)은 기존 값을 덮지 않음
            protected_keys_for_k = {
                'accident_number','accident_name','workplace','accident_grade','major_category',
                'injury_form','injury_type','building','floor','location_category','location_detail',
                'accident_date','created_at','report_date','day_of_week',
                # 확장: 책임회사/번호(원본 보호)
                'responsible_company1','responsible_company1_no','responsible_company2','responsible_company2_no'
            }

            # 주의: 화면 렌더 단계에서 안전 병합을 적용하므로 custom_data 키를 삭제하지 않는다

            def _is_empty_value(v):
                try:
                    if v is None:
                        return True
                    if isinstance(v, str) and v.strip() == '':
                        return True
                    return False
                except Exception:
                    return False

            # 안전한 병합: 리스트 타입 필드는 병합 처리
            def is_list_field(field_value):
                """리스트 필드인지 확인"""
                if isinstance(field_value, list):
                    return True
                if isinstance(field_value, str) and field_value.strip():
                    return field_value.startswith('[') and field_value.endswith(']')
                return False

            # 추가정보 섹션 키를 조회하여 '덮어쓰기 허용' 집합 구성
            additional_keys = set()
            try:
                _tab_rows = cursor.execute(
                    "SELECT column_key, tab FROM accident_column_config"
                ).fetchall()
                for _r in _tab_rows:
                    try:
                        k = _r['column_key'] if hasattr(_r, 'keys') else _r[0]
                        t = _r['tab'] if hasattr(_r, 'keys') else (_r[1] if len(_r) > 1 else None)
                    except Exception:
                        k, t = None, None
                    if k and (t == 'additional'):
                        additional_keys.add(k)
            except Exception:
                pass

            # 명시적 우선 키(요청된 필드들): 추가정보와 동일하게 덮어쓰기 허용
            override_always = {
                'company_1cha','company_1cha_bizno',
                'accident_company','accident_company_bizno',
                'accident_time'
            }
            overwrite_keys = additional_keys | override_always
            
            for key, value in custom_data.items():
                # 리스트 필드 병합 우선 처리
                if is_list_field(value) or is_list_field(existing_custom_data.get(key, [])):
                    print(f"[MERGE DEBUG] {key} 리스트 필드로 감지, 병합 처리 시작")
                    
                    # 기존 데이터 파싱
                    existing_list = existing_custom_data.get(key, [])
                    if isinstance(existing_list, str) and existing_list.strip():
                        try:
                            existing_list = pyjson.loads(existing_list)
                        except:
                            existing_list = []
                    if not isinstance(existing_list, list):
                        existing_list = []
                    
                    # 새 데이터 파싱
                    new_list = []
                    if isinstance(value, list):
                        new_list = value
                    elif isinstance(value, str) and value.strip():
                        if value.startswith('[') and value.endswith(']'):
                            try:
                                new_list = pyjson.loads(value)
                                if not isinstance(new_list, list):
                                    new_list = []
                            except:
                                new_list = []
                    
                    print(f"[MERGE DEBUG] {key} - 기존: {len(existing_list)}개, 새로: {len(new_list)}개")
                    
                    # 추가정보/오버라이드 키는 우선 대체하되, 완전 빈 배열이면 기존값 보존
                    if key in overwrite_keys:
                        if len(new_list) == 0 and len(existing_list) > 0:
                            existing_custom_data[key] = existing_list
                            print(f"[MERGE DEBUG] {key} 추가정보/오버라이드 → 빈 배열 무시, 기존 유지: {len(existing_list)}개")
                        else:
                            existing_custom_data[key] = new_list
                            print(f"[MERGE DEBUG] {key} 추가정보/오버라이드 → 전체 대체: {len(new_list)}개")
                    # 그 외: 프론트에서 전체 배열을 보냈다면 그대로 사용, 아니면 병합
                    elif len(new_list) > 0 and len(existing_list) > 0:
                        # 새로운 데이터에 기존 데이터의 첫 번째 항목이 포함되어 있다면 전체 교체로 간주
                        first_existing_id = existing_list[0].get('id', '') if existing_list and isinstance(existing_list[0], dict) else ''
                        has_existing_data = any(
                            isinstance(item, dict) and item.get('id') == first_existing_id 
                            for item in new_list
                        ) if first_existing_id else False
                        
                        if has_existing_data:
                            # 전체 데이터를 보냈으므로 그대로 사용
                            existing_custom_data[key] = new_list
                            print(f"[MERGE DEBUG] {key} 전체 교체: {len(new_list)}개 항목")
                        else:
                            # 새 항목만 추가하므로 병합 처리
                            merged_list = list(existing_list)
                            existing_ids = {item.get('id', '') for item in existing_list if isinstance(item, dict)}
                            
                            for new_item in new_list:
                                if isinstance(new_item, dict) and new_item.get('id') not in existing_ids:
                                    merged_list.append(new_item)
                                    existing_ids.add(new_item.get('id'))
                            
                            existing_custom_data[key] = merged_list
                            print(f"[MERGE DEBUG] {key} 병합 완료: 기존 {len(existing_list)}개 + 새로 {len(new_list)}개 = 최종 {len(merged_list)}개 항목")
                    else:
                        # 하나가 비어있으면 비어있지 않은 것을 사용 (일반 키)
                        existing_custom_data[key] = new_list if len(new_list) > 0 else existing_list
                        print(f"[MERGE DEBUG] {key} 단순 대체: {len(existing_custom_data[key])}개 항목")
                else:
                    # 일반 필드
                    # 값이 비어있으면 공통적으로 보존
                    if _is_empty_value(value):
                        print(f"[MERGE GUARD] skip empty/blank for key: {key}")
                        continue
                    existing_custom_data[key] = value
            
            # detailed_content를 custom_data에 추가
            if final_content:
                existing_custom_data['detailed_content'] = final_content
                logging.info(f"detailed_content를 custom_data에 추가: {len(final_content)}자")
            
            # custom_data 업데이트 (JSONB 캐스팅 제거)
            cursor.execute("""
                UPDATE accidents_cache 
                SET custom_data = %s
                WHERE accident_number = %s
            """, (existing_custom_data, accident_number))
            logging.info(f"custom_data 업데이트 완료: {accident_number}")
        else:
            # custom_data를 JSON 문자열로 변환
            if not isinstance(custom_data, str):
                custom_data_str = pyjson.dumps(custom_data)
            else:
                custom_data_str = custom_data
            
            # detailed_content를 custom_data에 추가
            if final_content:
                custom_data_dict = pyjson.loads(custom_data_str) if isinstance(custom_data_str, str) else custom_data_str
                custom_data_dict['detailed_content'] = final_content
                custom_data_str = pyjson.dumps(custom_data_dict)
            
            # FormData에서 직접 받은 필드들 사용 (하드코딩 제거)
            # 새 레코드 생성 (업체 정보는 선택적)
            # 비공식/직접등록 사고
            korean_date = get_korean_time().strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT INTO accidents_cache (
                    accident_number, accident_name, custom_data, accident_date,
                    workplace, accident_grade, major_category, injury_form, 
                    injury_type, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                accident_number, 
                request.form.get('accident_name', f"사고_{accident_number}"),
                custom_data_str, 
                request.form.get('accident_date', korean_date) or None,
                request.form.get('workplace', ''),
                request.form.get('accident_grade', ''),
                request.form.get('major_category', ''),
                request.form.get('injury_form', ''),
                request.form.get('injury_type', ''),
                korean_date
            ))
            logging.info(f"새 사고 레코드 생성 (직접등록) 및 동적 컬럼 데이터 저장: {accident_number}")
        
        # 2. 사고 첨부파일 처리 - item_id 사용
        
        # 3. 삭제된 첨부파일 처리
        for attachment_id in deleted_attachments:
            cursor.execute("DELETE FROM accident_attachments WHERE id = %s", (attachment_id,))
        
        # 4. 기존 첨부파일 정보 업데이트
        for attachment in attachment_data:
            # attachment가 딕셔너리인지 확인
            if isinstance(attachment, dict):
                print(f"[ATTACH DEBUG] 처리할 첨부파일: {attachment}")
                
                # 기존 첨부파일 업데이트 (id가 있는 경우)
                if attachment.get('id') and not attachment.get('isNew'):
                    print(f"[ATTACH DEBUG] 기존 첨부파일 업데이트: ID={attachment['id']}")
                    cursor.execute("""
                        UPDATE accident_attachments 
                        SET description = %s 
                        WHERE id = %s
                    """, (attachment.get('description', ''), attachment['id']))
                
                # id가 None이지만 isNew가 False인 경우 - 기존 파일인데 ID가 없는 상황
                elif attachment.get('id') is None and not attachment.get('isNew', True):
                    print(f"[ATTACH DEBUG] ID가 None인 기존 첨부파일 - accident_number로 찾아서 업데이트")
                    # 이 사고에 속한 첨부파일 중에서 description을 업데이트
                    cursor.execute("""
                        SELECT id FROM accident_attachments 
                        WHERE accident_number = %s 
                        ORDER BY id ASC
                    """, (accident_number,))
                    existing_ids = [row[0] for row in cursor.fetchall()]
                    print(f"[ATTACH DEBUG] 기존 첨부파일 IDs: {existing_ids}")
                    
                    if existing_ids:
                        # 첫 번째 첨부파일의 description을 업데이트 (간단한 매칭)
                        cursor.execute("""
                            UPDATE accident_attachments 
                            SET description = %s 
                            WHERE id = %s
                        """, (attachment.get('description', ''), existing_ids[0]))
                        print(f"[ATTACH DEBUG] 첨부파일 {existing_ids[0]}의 설명을 '{attachment.get('description', '')}' 로 업데이트")
            else:
                logging.warning(f"attachment가 딕셔너리가 아님: {type(attachment)}")
        
        # 5. 새 파일 업로드 처리
        import os
        upload_folder = os.path.join(os.getcwd(), 'uploads')
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        # 새 파일들과 새 첨부파일 데이터 매칭
        new_attachments = [a for a in attachment_data if isinstance(a, dict) and a.get('isNew')]
        print(f"New attachments: {new_attachments}")
        
        for i, file in enumerate(files):
            if file.filename and i < len(new_attachments):
                filename = file.filename
                # 파일명에 타임스탬프 추가하여 중복 방지
                import time
                timestamp = str(int(time.time()))
                name, ext = os.path.splitext(filename)
                unique_filename = f"{name}_{timestamp}{ext}"
                file_path = os.path.join(upload_folder, unique_filename)
                
                print(f"Saving file: {filename} as {unique_filename}")
                file.save(file_path)
                
                attachment_info = new_attachments[i]
                cursor.execute("""
                    INSERT INTO accident_attachments 
                    (accident_number, file_name, file_path, file_size, description)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    accident_number,  # accident_number 저장
                    filename,  # 원본 파일명으로 저장
                    file_path,
                    os.path.getsize(file_path),
                    attachment_info.get('description', '')
                ))
                logging.info(f"첨부파일 추가: {filename} - {attachment_info.get('description', '')}")
        
        # 커밋 전 확인
        check_result = cursor.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = %s", (accident_number,)).fetchone()
        logging.info(f"커밋 전 {accident_number} 사고 첨부파일 개수: {check_result[0]}개")
        
        try:
            conn.commit()
            logging.info("데이터베이스 커밋 성공")
            
            # 커밋 후 다시 확인
            check_result2 = cursor.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = %s", (accident_number,)).fetchone()
            logging.info(f"커밋 후 {accident_number} 사고 첨부파일 개수: {check_result2[0]}개")
            
            conn.close()
            
            # 새로운 연결로 다시 확인
            logging.info("새 연결로 데이터 지속성 확인...")
            verify_conn = get_db_connection()
            verify_result = verify_conn.execute("SELECT COUNT(*) FROM accident_attachments WHERE accident_number = %s", (accident_number,)).fetchone()
            logging.info(f"새 연결 확인: {accident_number} 사고 첨부파일 개수: {verify_result[0]}개")
            verify_conn.close()
            
            from flask import jsonify
            return jsonify({"success": True})
        except Exception as commit_error:
            print(f"Commit failed: {commit_error}")
            conn.rollback()
            conn.close()
            from flask import jsonify
            return jsonify({"success": False, "message": f"Commit failed: {str(commit_error)}"})
        
    except Exception as e:
        if conn:
            try:
                conn.rollback()
                conn.close()
            except:
                pass
        from flask import jsonify
        logging.error(f"사고 업데이트 중 오류 발생: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500



@app.route("/download/<int:attachment_id>")
def download_attachment(attachment_id):
    """첨부파일 다운로드 (협력사 및 사고 통합)"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 먼저 partner_attachments에서 찾기
    attachment = conn.execute(
        "SELECT * FROM partner_attachments WHERE id = ?", 
        (attachment_id,)
    ).fetchone()
    
    # partner_attachments에 없으면 accident_attachments에서 찾기
    if not attachment:
        attachment = conn.execute(
            "SELECT * FROM accident_attachments WHERE id = ?", 
            (attachment_id,)
        ).fetchone()
    
    conn.close()
    
    if not attachment:
        return "File not found", 404
    
    from flask import send_file
    import os
    
    # DB에 저장된 file_path 사용 (실제 저장된 경로)
    stored_file_path = attachment['file_path']
    
    # 절대 경로인지 상대 경로인지 확인
    if os.path.isabs(stored_file_path):
        actual_file_path = stored_file_path
    else:
        # 상대 경로면 현재 디렉토리 기준으로 구성
        actual_file_path = os.path.join(os.getcwd(), stored_file_path.lstrip('/\\'))
    
    logging.info(f"다운로드 요청: ID={attachment_id}, 파일={attachment['file_name']}, 경로={actual_file_path}")
    
    try:
        if os.path.exists(actual_file_path):
            return send_file(
                actual_file_path,
                as_attachment=True,
                download_name=attachment['file_name']
            )
        else:
            logging.error(f"파일을 찾을 수 없습니다: {actual_file_path}")
            return "File not found on disk", 404
    except Exception as e:
        logging.error(f"파일 다운로드 중 오류: {e}")
        return f"Download error: {str(e)}", 500


@app.route("/partner-attachments/<business_number>")
def get_partner_attachments(business_number):
    """협력사 첨부파일 목록 가져오기"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    attachments = conn.execute("""
        SELECT * FROM partner_attachments 
        WHERE business_number = ? 
        ORDER BY upload_date DESC
    """, (business_number,)).fetchall()
    conn.close()
    
    # 첨부파일 목록을 딕셔너리로 변환
    result = [dict(attachment) for attachment in attachments]
    
    from flask import jsonify
    return jsonify(result)

@app.route("/api/auto-upload-partner-files", methods=['POST'])
def auto_upload_partner_files():
    """협력사 사업자번호에 대한 HTML 파일 자동 생성 및 업로드"""
    try:
        data = request.get_json()
        business_number = data.get('business_number')
        file_paths = data.get('file_paths', [])
        
        if not business_number:
            return jsonify({"error": "business_number is required"}), 400
            
        if not file_paths:
            return jsonify({"error": "file_paths is required"}), 400
        
        # 협력사 정보 확인
        partner = partner_manager.get_partner_by_business_number(business_number)
        if not partner:
            return jsonify({"error": f"Partner not found: {business_number}"}), 404
        
        # 업로드 폴더 (현재 작업 디렉토리 기준 상대경로)
        upload_folder = Path(os.getcwd()) / "uploads"
        upload_folder.mkdir(parents=True, exist_ok=True)
        
        uploaded_files = []
        skipped = []  # 업로드 실패한 파일 추적
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row  # Row 객체 사용 설정
        cursor = conn.cursor()
        
        # 자동 업로드 설명 문구 정의
        auto_upload_desc = "통합레포트 자동업로드(매월 삭제 및 최신월 레포트로 교체됩니다)"
        
        # 기존 파일들 삭제 (자동 업로드된 파일만 삭제)
        deleted_count = 0
        try:
            # 기존 자동 업로드 파일 정보 조회 (정확한 설명 문구만)
            existing_files = cursor.execute("""
                SELECT file_path FROM partner_attachments 
                WHERE business_number = ? AND description = ?
            """, (business_number, auto_upload_desc)).fetchall()
            
            # 파일 시스템에서 삭제
            for file_row in existing_files:
                old_file_path = Path(file_row['file_path'])
                if old_file_path.exists():
                    try:
                        old_file_path.unlink()
                        logging.info(f"Deleted old file: {old_file_path}")
                    except Exception as e:
                        logging.warning(f"Failed to delete old file {old_file_path}: {e}")
            
            # DB에서 삭제 (정확한 설명 문구만)
            cursor.execute("""
                DELETE FROM partner_attachments 
                WHERE business_number = ? AND description = ?
            """, (business_number, auto_upload_desc))
            conn.commit()
            deleted_count = len(existing_files)
            logging.info(f"Deleted {deleted_count} old files for {business_number}")
            
        except Exception as e:
            logging.error(f"Error deleting old files: {e}")
            # 기존 파일 삭제 실패해도 계속 진행
        
        for file_path in file_paths:
            try:
                # 절대경로로 변환
                file_path = Path(file_path).expanduser().resolve()
                if not file_path.exists():
                    logging.warning(f"File not found: {file_path}")
                    skipped.append(str(file_path))
                    continue
                
                # 파일명 안전화 (한글 유지)
                original_name = file_path.name
                # 위험한 문자만 제거, 한글은 유지
                safe_name = re.sub(r'[<>:"/\\|?*]', '_', original_name) if original_name else "file"
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_filename = f"{business_number}_{timestamp}_{safe_name}"
                dest_path = upload_folder / new_filename
                
                # 파일 복사
                shutil.copy2(file_path, dest_path)
                
                # DB에 저장 (기존 컬럼만 사용)
                # 한국 시간으로 년도와 월 정보, 회사명 가져오기
                korean_time = get_korean_time()
                year = korean_time.strftime("%Y")
                month = korean_time.strftime("%m")
                try:
                    company_name = partner['company_name'] or '협력사'
                except (KeyError, TypeError):
                    company_name = '협력사'
                
                # 표시용 한글 파일명 생성 (base64 인코딩 제거)
                korean_filename = f"{company_name}_{year}년_{month}월_통합레포트.html"
                
                cursor.execute("""
                    INSERT INTO partner_attachments
                    (business_number, file_name, file_path, file_size, upload_date, description)
                    VALUES (?, ?, ?, ?, datetime('now'), ?)
                """, (
                    business_number,
                    korean_filename,        # 한글 표시명 (인코딩 없이 그대로)
                    str(dest_path),         # file_path (실제 파일 경로)
                    dest_path.stat().st_size, # file_size
                    auto_upload_desc        # description (자동 업로드 설명)
                ))
                
                uploaded_files.append({
                    "original_path": str(file_path),
                    "uploaded_filename": new_filename,
                    "file_size": dest_path.stat().st_size
                })
                
                logging.info(f"File uploaded: {file_path.name} → {new_filename}")
  
            except Exception as e:
                logging.error(f"Error processing file {file_path}: {str(e)}")
                skipped.append(str(file_path))
                continue
        
        conn.commit()
        conn.close()
        
        # 응답 상태 코드 설정 (200: 모두 성공, 207: 일부 성공, 400: 모두 실패)
        status = 200 if uploaded_files and not skipped else (207 if uploaded_files and skipped else 400)
        
        return jsonify({
            "success": bool(uploaded_files),
            "business_number": business_number,
            "uploaded_files": uploaded_files,
            "skipped": skipped,  # 실패한 파일 목록
            "deleted_count": deleted_count,  # 삭제된 기존 파일 개수
            "total_uploaded": len(uploaded_files),
            "total_skipped": len(skipped),
            "message": f"기존 {deleted_count}개 파일 삭제 후 {len(uploaded_files)}개 새 파일 업로드"
        }), status
        
    except Exception as e:
        logging.error(f"Error in auto_upload_partner_files: {str(e)}")
        return jsonify({"error": str(e)}), 500



# ===== Phase 1: 동적 컬럼 관리 API =====

# 테스트용 간단한 라우트
@app.route("/api/test-route")
def test_route():
    return jsonify({"message": "Test route works!"})

@app.route("/api/accident-columns", methods=["GET"])
def get_accident_columns():
    """사고 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('accident', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns", methods=["POST"])
def add_accident_column():
    """사고 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('accident', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/<int:column_id>", methods=["PUT"])
def update_accident_column(column_id):
    """사고 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('accident', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/<int:column_id>", methods=["DELETE"])
def delete_accident_column(column_id):
    """사고 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('accident', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-columns/order", methods=["PUT"])
def update_accident_columns_order():
    """사고 페이지 동적 컬럼 순서 변경"""
    try:
        column_service = ColumnConfigService('accident', DB_PATH)
        result = column_service.update_columns_order(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"컬럼 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# 관리자 인증 라우트
@app.route("/admin/login", methods=["POST"])
def admin_login():
    """관리자 비밀번호 인증 처리"""
    password = request.form.get('password')
    redirect_url = request.form.get('redirect_url', '/admin/menu-settings')
    
    if password == ADMIN_PASSWORD:
        session['admin_authenticated'] = True
        return redirect(redirect_url)
    else:
        return render_template('admin-login.html', 
                             error='비밀번호가 틀렸습니다.',
                             redirect_url=redirect_url,
                             menu=MENU_CONFIG)

@app.route("/admin/logout")
def admin_logout():
    """관리자 로그아웃"""
    session.pop('admin_authenticated', None)
    return redirect(url_for('index'))

# ======================================================================
# Admin 동기화 관리 엔드포인트
# ======================================================================

@app.route('/admin/sync-now', methods=['POST'])
def admin_sync_now():
    """수동 강제 동기화 엔드포인트"""
    try:
        from database_config import maybe_daily_sync_master, maybe_one_time_sync_content
        
        sync_type = request.json.get('type', 'all')
        
        if sync_type == 'master' or sync_type == 'all':
            maybe_daily_sync_master(force=True)
        
        if sync_type == 'content' or sync_type == 'all':
            maybe_one_time_sync_content(force=True)
            
        return jsonify({'success': True, 'message': f'Sync completed ({sync_type})'})
    except Exception as e:
        logging.error(f"Manual sync failed: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/admin/cache-counts', methods=['GET'])
def admin_cache_counts():
    """캐시 테이블 레코드 수 확인 엔드포인트"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        tables = ['partners_cache','accidents_cache','safety_instructions_cache',
                 'departments_cache','buildings_cache','contractors_cache','employees_cache']
        counts = {}
        for t in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                counts[t] = cur.fetchone()[0]
            except Exception:
                counts[t] = 'table not found'
        conn.close()
        return jsonify({'success': True, 'counts': counts})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 이 라우트는 아래에 더 완전한 버전이 있으므로 제거됨

@app.route("/admin/accident-columns")
@require_admin_auth
def admin_accident_columns():
    """사고 컬럼 관리 페이지 (표준 경로) - simplified 템플릿 사용"""
    # 기존 simplified 구현을 표준 경로에서 사용
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    _wa = sql_is_active_true('is_active', conn)
    _wd = sql_is_deleted_false('is_deleted', conn)
    sections = conn.execute(
        f"SELECT * FROM section_config WHERE board_type = 'accident' AND {_wa} AND {_wd} ORDER BY section_order"
    ).fetchall()
    sections = [dict(row) for row in sections]
    # 컬럼 관리 페이지에서는 사고 데이터 매핑이 필요 없음 (불필요 코드 제거)
    conn.close()
    return render_template('admin-accident-columns-simplified.html', sections=sections, menu=MENU_CONFIG)

@app.route("/admin/accident-columns-simplified")
@require_admin_auth
def admin_accident_columns_simplified():
    """구 경로 호환: 표준 경로로 리다이렉트"""
    return redirect(url_for('admin_accident_columns'))

@app.route("/admin/accident-basic-codes")
@require_admin_auth
def admin_accident_basic_codes():
    """사고 기본정보 코드 관리 페이지"""
    return render_template('admin-accident-basic-codes.html', menu=MENU_CONFIG)

@app.route("/admin/accident-codes")
@require_admin_auth
def admin_accident_codes():
    """사고 코드 관리 임베디드 페이지"""
    column_key = request.args.get('column_key', '')
    embedded = request.args.get('embedded', 'false') == 'true'
    
    return render_template('admin-accident-codes.html', 
                         column_key=column_key,
                         embedded=embedded,
                         menu=MENU_CONFIG)

# ===== 사고 데이터 캐시 이관 (accidents -> accidents_cache) =====
@app.route('/admin/migrate-accidents-to-cache', methods=['POST'])
@require_admin_auth
def migrate_accidents_to_cache():
    """외부 accidents 테이블 데이터를 accidents_cache로 일괄 업서트 이관

    - 기준: accident_number(UNIQUE)
    - 이미 존재하면 업데이트, 없으면 신규 생성
    - 소스의 잔여 필드는 custom_data로 병합
    """
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        # accidents 테이블 존재 여부 확인
        try:
            cur.execute("PRAGMA table_info(accidents)")
            cols = cur.fetchall()
            if not cols:
                return jsonify({'success': False, 'message': 'accidents 테이블이 없습니다.'}), 404
            acc_columns = [c[1] for c in cols]
        except Exception:
            try:
                cur.execute(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
                    ('accidents',)
                )
                acc_columns = [r[0] if not isinstance(r, dict) else r['column_name'] for r in cur.fetchall()]
                if not acc_columns:
                    return jsonify({'success': False, 'message': 'accidents 테이블이 없습니다.'}), 404
            except Exception:
                return jsonify({'success': False, 'message': 'accidents 테이블 확인 실패'}), 500

        # cache 필수 컬럼 보강
        try:
            cur.execute("PRAGMA table_info(accidents_cache)")
            cache_cols = [c[1] for c in cur.fetchall()]
            ensure_cols = [
                ('accident_number','TEXT'),('accident_name','TEXT'),('workplace','TEXT'),
                ('accident_grade','TEXT'),('major_category','TEXT'),('injury_form','TEXT'),('injury_type','TEXT'),
                ('accident_date','TEXT'),('day_of_week','TEXT'),('report_date','TEXT'),('created_at','TEXT'),
                ('building','TEXT'),('floor','TEXT'),('location_category','TEXT'),('location_detail','TEXT'),
                ('custom_data','TEXT'),('is_deleted','INTEGER')
            ]
            for cn, ct in ensure_cols:
                if cn not in cache_cols:
                    try:
                        cur.execute(f"ALTER TABLE accidents_cache ADD COLUMN {cn} {ct}")
                    except Exception:
                        pass
        except Exception:
            pass

        # 소스 데이터 조회 (삭제 제외)
        where_notdel = sql_is_deleted_false('is_deleted', conn) if 'is_deleted' in acc_columns else '1=1'
        src_rows = conn.execute(f"SELECT * FROM accidents WHERE {where_notdel}").fetchall()

        migrated = 0
        updated = 0
        skipped = 0

        from db.upsert import safe_upsert
        for r in src_rows:
            row = dict(r)
            acc_no = row.get('accident_number')
            if not acc_no:
                skipped += 1
                continue

            top_keys = ['accident_number','accident_name','workplace','accident_grade','major_category',
                        'injury_form','injury_type','accident_date','day_of_week','report_date','created_at',
                        'building','floor','location_category','location_detail']
            data = {k: row.get(k) for k in top_keys if k in row}
            for dk in ('accident_date','report_date','created_at'):
                if dk in data and data[dk] is not None:
                    data[dk] = str(data[dk])

            # custom_data 병합
            src_cd = row.get('custom_data')
            if isinstance(src_cd, str):
                try:
                    import json as _json
                    src_cd = _json.loads(src_cd) if src_cd else {}
                except Exception:
                    src_cd = {}
            elif not isinstance(src_cd, dict):
                src_cd = {}
            leftovers = {k: v for k, v in row.items() if (k not in data and k not in ('custom_data','id','is_deleted'))}
            merged_cd = {}
            merged_cd.update(src_cd)
            merged_cd.update(leftovers)
            data['custom_data'] = merged_cd
            if 'is_deleted' in row:
                data['is_deleted'] = row['is_deleted']

            try:
                exist = conn.execute("SELECT 1 FROM accidents_cache WHERE accident_number = ?", (acc_no,)).fetchone()
                safe_upsert(conn, 'accidents_cache', data, conflict_cols=['accident_number'])
                if exist:
                    updated += 1
                else:
                    migrated += 1
            except Exception as _e:
                logging.error(f"업서트 실패: {acc_no}: {_e}")
                skipped += 1

        conn.commit(); conn.close()
        return jsonify({'success': True, 'migrated': migrated, 'updated': updated, 'skipped': skipped, 'total_source': len(src_rows)})
    except Exception as e:
        logging.error(f"사고 캐시 이관 실패: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route("/admin/safety-instruction-codes")
@require_admin_auth
def admin_safety_instruction_codes():
    """환경안전 지시서 코드 관리 페이지"""
    return render_template('admin-safety-instruction-codes.html', menu=MENU_CONFIG)

@app.route("/admin/fullprocess-codes")
@require_admin_auth
def admin_fullprocess_codes():
    """Full Process 코드 관리 임베디드 페이지"""
    column_key = request.args.get('column_key', '')
    embedded = request.args.get('embedded', 'false') == 'true'
    
    return render_template('admin-fullprocess-codes.html', 
                         column_key=column_key,
                         embedded=embedded,
                         menu=MENU_CONFIG)

@app.route("/admin/followsop-codes")
@require_admin_auth
def admin_followsop_codes():
    """Follow SOP 코드 관리 임베디드 페이지"""
    column_key = request.args.get('column_key', '')
    embedded = request.args.get('embedded', 'false') == 'true'
    
    return render_template('admin-followsop-codes.html', 
                         column_key=column_key,
                         embedded=embedded,
                         menu=MENU_CONFIG)

@app.route("/admin/person-master")
@require_admin_auth
def admin_person_master():
    """담당자 마스터 관리 페이지"""
    return render_template('admin-person-master.html', menu=MENU_CONFIG)

# Follow SOP API 엔드포인트
@app.route("/api/follow-sop-columns", methods=["GET"])
def get_follow_sop_columns():
    """Follow SOP 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns", methods=["POST"])
def add_follow_sop_column():
    """Follow SOP 페이지 동적 컬럼 추가"""
    try:
        if not request.json:
            return jsonify({"success": False, "message": "JSON data required"}), 400
            
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["PUT"])
def update_follow_sop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["DELETE"])
def delete_follow_sop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# Full Process API 엔드포인트
@app.route("/api/full-process-columns", methods=["GET"])
def get_full_process_columns():
    """Full Process 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Full Process 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns", methods=["POST"])
def add_full_process_column():
    """Full Process 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["PUT"])
def update_full_process_column(column_id):
    """Full Process 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["DELETE"])
def delete_full_process_column(column_id):
    """Full Process 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/admin/safety-instruction-columns")
@require_admin_auth  
def admin_safety_instruction_columns():
    """환경안전 지시서 컬럼 관리 페이지"""
    # 섹션 정보 로드
    from section_service import SectionConfigService
    section_service = SectionConfigService('safety_instruction', DB_PATH)
    sections = section_service.get_sections()
    
    return render_template('admin-safety-instruction-columns.html', 
                         menu=MENU_CONFIG,
                         sections=sections)

@app.route("/admin/follow-sop-columns")
@app.route("/admin/followsop-columns")  # 두 URL 모두 지원
@require_admin_auth  
def admin_follow_sop_columns():
    """Follow SOP 컬럼 관리 페이지"""
    # 섹션 정보 로드
    from section_service import SectionConfigService
    section_service = SectionConfigService('follow_sop', DB_PATH)
    section_columns = section_service.get_sections_with_columns()
    
    return render_template('admin-followsop-columns.html', 
                         menu=MENU_CONFIG,
                         section_columns=section_columns,
                         sections=section_columns)  # 하위 호환성

@app.route("/admin/full-process-columns")
@app.route("/admin/fullprocess-columns")  # 두 URL 모두 지원
@require_admin_auth  
def admin_full_process_columns():
    """Full Process 컬럼 관리 페이지"""
    # 섹션 정보 로드
    from section_service import SectionConfigService
    section_service = SectionConfigService('full_process', DB_PATH)
    section_columns = section_service.get_sections_with_columns()
    
    return render_template('admin-fullprocess-columns.html', 
                         menu=MENU_CONFIG,
                         section_columns=section_columns,
                         sections=section_columns)  # 하위 호환성

@app.route("/admin/safety-instruction-columns-simplified")
@require_admin_auth
def admin_safety_instruction_columns_simplified():
    """환경안전 지시서 컬럼 관리 페이지 Simplified - 간소화 버전"""
    return render_template('admin-safety-instruction-columns-simplified.html', menu=MENU_CONFIG)

@app.route("/admin/change-request-columns")
@require_admin_auth
def admin_change_request_columns():
    """기준정보 변경요청 컬럼 관리 페이지"""
    return render_template('admin-change-request-columns.html', menu=MENU_CONFIG)

# 중복 라우트 제거됨 - 위에서 이미 처리

@app.route("/admin/change-request-columns-simplified")
@require_admin_auth
def admin_change_request_columns_simplified():
    """기준정보 변경요청 컬럼 관리 페이지 Simplified - 간소화 버전"""
    return render_template('admin-change-request-columns-simplified.html', menu=MENU_CONFIG)

# ===== 기준정보 변경요청 컬럼 관리 API =====

@app.route("/api/change-request/columns", methods=["GET"])
def get_change_request_columns():
    """기준정보 변경요청 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('change_request', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"변경요청 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/columns", methods=["POST"])
def add_change_request_column():
    """기준정보 변경요청 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('change_request', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"변경요청 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/columns/<int:column_id>", methods=["PUT"])
def update_change_request_column(column_id):
    """기준정보 변경요청 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('change_request', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"변경요청 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/columns/<int:column_id>", methods=["DELETE"])
def delete_change_request_column(column_id):
    """기준정보 변경요청 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('change_request', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"변경요청 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/columns/order", methods=["PUT"])
def update_change_request_columns_order():
    """변경요청 페이지 동적 컬럼 순서 변경"""
    try:
        column_service = ColumnConfigService('change_request', DB_PATH)
        result = column_service.update_columns_order(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"컬럼 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/dropdown-codes", methods=["GET"])
def get_change_request_dropdown_codes():
    column_key = request.args.get('column_key')
    if not column_key:
        return jsonify({"success": False, "message": "column_key is required"}), 400
    """특정 컬럼의 드롭다운 코드 조회 (v2 통일)"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # v2 테이블 사용
        codes = conn.execute("""
            SELECT option_code as code, option_value as value, display_order, is_active
            FROM dropdown_option_codes_v2
            WHERE board_type = 'change_request' AND column_key = ? AND is_active = 1
            ORDER BY display_order, id
        """, (column_key,)).fetchall()
        
        conn.close()
        
        return jsonify({
            "success": True,
            "codes": [dict(code) for code in codes],
            "column_key": column_key
        })
    except Exception as e:
        logging.error(f"변경요청 드롭다운 코드 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/dropdown-codes", methods=["POST"])
def save_change_request_dropdown_codes():
    """드롭다운 코드 일괄 저장"""
    try:
        column_key = request.args.get('column_key')
        codes = request.json  # 바디는 배열만
        
        if not column_key:
            return jsonify({"success": False, "message": "column_key is required"}), 400
        
        if not isinstance(codes, list):
            return jsonify({"success": False, "message": "Body must be an array"}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 기존 코드 비활성화 (v2 테이블)
        cursor.execute("""
            UPDATE dropdown_option_codes_v2
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE board_type = 'change_request' AND column_key = ?
        """, (column_key,))
        
        # 새 코드 삽입 또는 업데이트 (v2 테이블)
        for idx, code_data in enumerate(codes):
            cursor.execute("""
                INSERT INTO dropdown_option_codes_v2
                (board_type, column_key, option_code, option_value, display_order, is_active)
                VALUES ('change_request', ?, ?, ?, ?, 1)
                ON CONFLICT(board_type, column_key, option_code) DO UPDATE SET
                    option_value = excluded.option_value,
                    display_order = excluded.display_order,
                    is_active = 1,
                    updated_at = CURRENT_TIMESTAMP
            """, (column_key, code_data['code'], code_data['value'], idx))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "코드가 저장되었습니다."})
    except Exception as e:
        logging.error(f"변경요청 드롭다운 코드 저장 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request-dropdown-codes/<int:code_id>", methods=["DELETE"])
def delete_change_request_dropdown_code(code_id):
    """드롭다운 코드 삭제 (v2 통일)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dropdown_option_codes_v2
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP 
            WHERE id = ?
        """, (code_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "코드가 삭제되었습니다."})
    except Exception as e:
        logging.error(f"변경요청 드롭다운 코드 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/change-request/save", methods=["POST"])
def save_change_request():
    """변경요청 저장"""
    try:
        data = request.json
        request_number = data.get('request_number')
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 테이블이 없으면 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT UNIQUE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 동적 컬럼들을 위한 ALTER TABLE
        for key, value in data.items():
            if key != 'request_number':
                try:
                    cursor.execute(f"ALTER TABLE change_requests ADD COLUMN {key} TEXT")
                except:
                    pass  # 컬럼이 이미 존재하면 무시
        
        # 상태를 강제로 'requested'로 설정
        if 'status' in data:
            data['status'] = 'requested'  # 등록 시에는 항상 '요청' 상태
        
        # 데이터 삽입
        columns = list(data.keys())
        values = list(data.values())
        placeholders = ', '.join(['?' for _ in values])
        column_names = ', '.join(columns)
        
        cursor.execute(f"""
            INSERT INTO change_requests_cache ({column_names})
            VALUES ({placeholders})
        """, values)
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": "변경요청이 저장되었습니다."})
    except Exception as e:
        logging.error(f"변경요청 저장 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/change-request-register")
def change_request_register():
    """변경요청 등록 팝업 페이지"""
    from timezone_config import get_korean_time
    
    # 요청번호 자동 생성 (CR-YYYYMM-NN 형식으로 통일)
    today = get_korean_time()
    base_number = f"CR-{today.strftime('%Y%m')}-"
    
    conn = None
    try:
        # 오늘 날짜의 마지막 번호 찾기
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 변경요청 캐시 테이블이 없으면 생성 (미니멀 필드)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        cursor.execute("""
            SELECT MAX(CAST(SUBSTR(request_number, -2) AS INTEGER))
            FROM change_requests
            WHERE request_number LIKE ?
        """, (f"{base_number}%",))
        
        last_number = cursor.fetchone()[0]
        if last_number is None:
            last_number = 0
        
        request_number = f"{base_number}{str(last_number + 1).zfill(2)}"
        conn.commit()
        
        # 동적 컬럼 설정 가져오기 (딕셔너리로 직접 조회)
        _wa = sql_is_active_true('is_active', conn)
        _wd = sql_is_deleted_false('is_deleted', conn)
        dynamic_columns_rows = conn.execute(f"""
            SELECT 
                column_key, column_name, column_type, column_order, is_active,
                dropdown_options, tab, column_span, linked_columns
            FROM change_request_column_config 
            WHERE {_wa} AND {_wd}
            ORDER BY column_order
        """).fetchall()
        
        # 딕셔너리 형태로 변환
        dynamic_columns = []
        for row in dynamic_columns_rows:
            dynamic_columns.append({
                'column_key': row[0],
                'column_name': row[1], 
                'column_type': row[2],
                'column_order': row[3],
                'is_active': row[4],
                'dropdown_options': row[5],
                'tab': row[6],
                'column_span': row[7],
                'linked_columns': row[8]
            })
        
    except Exception as e:
        logging.error(f"요청번호 생성 중 오류: {e}")
        request_number = f"{base_number}01"  # 오류 시 기본값
        dynamic_columns = []
    finally:
        if conn:
            conn.close()
    
    # 드롭다운 컬럼에 대해 코드-값 매핑 적용 (v2 통일)
    for col in dynamic_columns:
        if col['column_type'] == 'dropdown':
            # v2 공통 헬퍼 사용
            code_options = get_dropdown_options_for_display('change_request', col['column_key'])
            
            # 프런트엔드 호환성을 위해 형식 변환
            if code_options:
                col['dropdown_options_mapped'] = [{"code": opt["code"], "value": opt["value"]} for opt in code_options]
            else:
                col['dropdown_options_mapped'] = []
    
    logging.info(f"변경요청 동적 컬럼 {len(dynamic_columns)}개 로드됨")
    
    # 팝업 모드 확인
    is_popup = request.args.get('popup', '0') == '1'
    
    return render_template('change-request-register.html', 
                         menu=MENU_CONFIG, 
                         request_number=request_number,
                         today=today,
                         is_popup=is_popup,
                         dynamic_columns=dynamic_columns)

@app.route("/admin/menu-settings")
@require_admin_auth
def admin_menu_settings():
    """메뉴 설정 페이지"""
    return render_template('admin-menu-settings.html', menu=MENU_CONFIG)

@app.route("/admin/permission-settings")
@require_admin_auth
def admin_permission_settings():
    """권한 설정 페이지"""
    return render_template('admin-permission-settings.html', menu=MENU_CONFIG)

@app.route("/admin/data-management")
@require_admin_auth
def admin_data_management():
    """데이터 관리 페이지"""
    return render_template('admin-data-management.html', menu=MENU_CONFIG)

@app.route("/api/accidents/deleted")
def get_deleted_accidents():
    """삭제된 사고 목록 API"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 삭제된 사고만 조회
    deleted_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        WHERE is_deleted = 1
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    deleted_accidents = [dict(row) for row in deleted_accidents_rows]
    conn.close()
    
    return jsonify({"success": True, "accidents": deleted_accidents})

@app.route("/api/partners/deleted")
def get_deleted_partners():
    """삭제된 협력사 목록 API"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    # 삭제된 협력사만 조회
    deleted_partners_rows = conn.execute("""
        SELECT * FROM partners_cache 
        WHERE is_deleted = 1
        ORDER BY company_name
    """).fetchall()
    
    deleted_partners = [dict(row) for row in deleted_partners_rows]
    conn.close()
    
    return jsonify({"success": True, "partners": deleted_partners})

@app.route("/api/safety-instruction/deleted")
def get_deleted_safety_instructions():
    """삭제된 안전교육 목록 API"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    deleted_items = conn.execute("""
        SELECT * FROM safety_instructions 
        WHERE is_deleted = 1
        ORDER BY created_at DESC
    """).fetchall()
    
    conn.close()
    return jsonify({"success": True, "items": [dict(row) for row in deleted_items]})


@app.route("/api/follow-sop/deleted") 
def get_deleted_follow_sop():
    """삭제된 Follow SOP 목록 API"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    deleted_items = conn.execute("""
        SELECT * FROM follow_sop 
        WHERE is_deleted = 1
        ORDER BY created_at DESC
    """).fetchall()
    
    conn.close()
    return jsonify({"success": True, "items": [dict(row) for row in deleted_items]})


@app.route("/api/full-process")
def get_full_process():
    """Full Process 목록 API (일반 데이터)"""
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # 삭제되지 않은 Full Process 목록 조회
        _wd = sql_is_deleted_false('is_deleted', conn)
        items = conn.execute(f"""
            SELECT * FROM full_process 
            WHERE {_wd}
            ORDER BY created_at DESC
        """).fetchall()
        
        conn.close()
        
        # 결과를 딕셔너리 리스트로 변환
        result = []
        for item in items:
            item_dict = dict(item)
            # custom_data를 JSON으로 파싱
            if item_dict.get('custom_data'):
                try:
                    import json
                    custom_data = json.loads(item_dict['custom_data'])
                    item_dict.update(custom_data)  # custom_data의 내용을 최상위로 병합
                except json.JSONDecodeError:
                    pass
            result.append(item_dict)
        
        return jsonify({
            "success": True,
            "data": result,
            "total": len(result)
        })
        
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process/deleted")
def get_deleted_full_process():
    """삭제된 Full Process 목록 API"""
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    
    deleted_items = conn.execute("""
        SELECT * FROM full_process 
        WHERE is_deleted = 1
        ORDER BY created_at DESC
    """).fetchall()
    
    conn.close()
    return jsonify({"success": True, "items": [dict(row) for row in deleted_items]})


@app.route("/api/safety-instruction/restore", methods=['POST'])
def restore_safety_instructions():
    """안전교육 복구 API"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item_id in ids:
            cursor.execute("UPDATE safety_instructions SET is_deleted = 0 WHERE id = ?", (item_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": f"복구 완료: {len(ids)}개 항목"})
        
    except Exception as e:
        logging.error(f"Error restoring safety instructions: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/follow-sop/restore", methods=['POST'])
def restore_follow_sop():
    """Follow SOP 복구 API"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item_id in ids:
            cursor.execute("UPDATE follow_sop SET is_deleted = 0 WHERE work_req_no = ?", (item_id,))
            # Cache table is no longer used for display, only update main table
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": f"복구 완료: {len(ids)}개 항목"})
        
    except Exception as e:
        logging.error(f"Error restoring follow SOP: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/full-process/restore", methods=['POST'])
def restore_full_process():
    """Full Process 복구 API"""
    try:
        data = request.get_json()
        ids = data.get('ids', [])
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        for item_id in ids:
            cursor.execute("UPDATE full_process SET is_deleted = 0 WHERE fullprocess_number = ?", (item_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "message": f"복구 완료: {len(ids)}개 항목"})
        
    except Exception as e:
        logging.error(f"Error restoring full process: {str(e)}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/<board_type>/delete', methods=['POST'])
def delete_items(board_type):
    """범용 소프트 삭제 API - 각 게시판의 primary key를 사용"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        # 게시판별 테이블 및 primary key 매핑
        board_config = {
            'accidents': {'table': 'accidents_cache', 'pk': 'id'},
            'safety-instructions': {'table': 'safety_instructions', 'pk': 'id'},
            'change-requests': {'table': 'change_requests_cache', 'pk': 'id'},
            'partners': {'table': 'partners_cache', 'pk': 'id'}
        }
        
        if board_type not in board_config:
            return jsonify({"success": False, "message": "잘못된 게시판 타입입니다."}), 400
        
        config = board_config[board_type]
        table_name = config['table']
        pk_column = config['pk']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 소프트 삭제 수행
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE {table_name} 
            SET is_deleted = 1 
            WHERE {pk_column} IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"{board_type} 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/accidents/delete', methods=['POST'])
def delete_accidents():
    """선택한 사고들을 소프트 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 모든 사고 삭제 가능 (ACC, K 모두)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE accidents_cache 
            SET is_deleted = 1 
            WHERE id IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/safety-instructions/delete', methods=['POST'])
def delete_safety_instructions():
    """선택한 환경안전지시서들을 소프트 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])  # 실제로는 issue_number들
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 메인 테이블에서 소프트 삭제 (issue_number 기준)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE safety_instructions 
            SET is_deleted = 1 
            WHERE issue_number IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"환경안전지시서 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/follow-sop/delete', methods=['POST'])
def delete_follow_sop():
    """선택한 Follow SOP들을 소프트 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])  # 실제로는 work_req_no들
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # follow_sop 테이블에서 소프트 삭제 (work_req_no 기준)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE follow_sop 
            SET is_deleted = 1 
            WHERE work_req_no IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"Follow SOP 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/full-process/delete', methods=['POST'])
def delete_full_process():
    """선택한 Full Process들을 소프트 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])  # 실제로는 fullprocess_number들
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # full_process 테이블에서 소프트 삭제 (fullprocess_number 기준)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE full_process 
            SET is_deleted = 1 
            WHERE fullprocess_number IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"Full Process 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/accidents/restore', methods=['POST'])
def restore_accidents():
    """삭제된 사고들을 복구"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "복구할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 선택한 사고들을 복구 (is_deleted = 0)
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE accidents_cache 
            SET is_deleted = 0 
            WHERE id IN ({placeholders})
        """, ids)
        
        restored_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "restored_count": restored_count,
            "message": f"{restored_count}건이 복구되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 복구 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/partners/restore', methods=['POST'])
def restore_partners():
    """삭제된 협력사들을 복구"""
    try:
        data = request.json
        business_numbers = data.get('business_numbers', [])
        
        if not business_numbers:
            return jsonify({"success": False, "message": "복구할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 선택한 협력사들을 복구 (is_deleted = 0)
        placeholders = ','.join('?' * len(business_numbers))
        cursor.execute(f"""
            UPDATE partners_cache 
            SET is_deleted = 0 
            WHERE business_number IN ({placeholders})
        """, business_numbers)
        
        restored_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "restored_count": restored_count,
            "message": f"{restored_count}개의 협력사가 복구되었습니다."
        })
    except Exception as e:
        logging.error(f"협력사 복구 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/buildings/search', methods=['GET'])
def search_buildings():
    """건물 검색 API"""
    try:
        search_term = request.args.get('q', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute("""
                SELECT building_code, building_name
                FROM buildings_cache
                WHERE building_name LIKE ? OR building_code LIKE ?
                ORDER BY building_name
                LIMIT 50
            """, (f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute("""
                SELECT building_code, building_name
                FROM buildings_cache
                ORDER BY building_name
                LIMIT 50
            """)
        
        buildings = []
        for row in cursor.fetchall():
            buildings.append({
                'building_code': row[0],
                'building_name': row[1]
            })
        
        conn.close()
        return jsonify({'success': True, 'buildings': buildings})
    except Exception as e:
        logging.error(f"건물 검색 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/departments/search', methods=['GET'])
def search_departments():
    """부서 검색 API"""
    try:
        search_term = request.args.get('q', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if search_term:
            cursor.execute("""
                SELECT d.dept_code, d.dept_name, 
                       p.dept_name as parent_name
                FROM departments_cache d
                LEFT JOIN departments_cache p ON d.parent_dept_code = p.dept_code
                WHERE d.dept_name LIKE ? OR d.dept_code LIKE ?
                ORDER BY d.dept_name
                LIMIT 50
            """, (f'%{search_term}%', f'%{search_term}%'))
        else:
            cursor.execute("""
                SELECT d.dept_code, d.dept_name, 
                       p.dept_name as parent_name
                FROM departments_cache d
                LEFT JOIN departments_cache p ON d.parent_dept_code = p.dept_code
                ORDER BY d.dept_name
                LIMIT 50
            """)
        
        departments = []
        for row in cursor.fetchall():
            departments.append({
                'dept_code': row[0],
                'dept_name': row[1],
                'parent_name': row[2] or '',
                'parent_dept_code': d.parent_dept_code or ''
            })
        
        conn.close()
        return jsonify({'success': True, 'departments': departments})
    except Exception as e:
        logging.error(f"부서 검색 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/search', methods=['GET'])
def api_search():
    """범용 검색 API"""
    try:
        search_type = request.args.get('type', 'person')
        search_value = request.args.get('value', 'person')
        search_term = request.args.get('q', '').strip()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        results = []
        
        if search_type == 'person':
            # 담당자 검색 (더미 데이터)
            sample_persons = [
                {'employee_id': '10001', 'name': '김철수', 'department': '안전보건팀'},
                {'employee_id': '10002', 'name': '이영희', 'department': '생산1팀'},
                {'employee_id': '10003', 'name': '박민수', 'department': '품질관리팀'},
                {'employee_id': '10004', 'name': '정수진', 'department': '인사팀'},
                {'employee_id': '10005', 'name': '최동욱', 'department': '총무팀'}
            ]
            
            if search_term:
                if search_value == 'employee_id':
                    results = [p for p in sample_persons if search_term in p['employee_id']]
                else:
                    results = [p for p in sample_persons if search_term in p['name'] or search_term in p['department']]
            else:
                results = sample_persons
                
        elif search_type == 'company':
            # 협력사 검색
            if search_term:
                if search_value == 'business_number':
                    cursor.execute("""
                        SELECT business_number, company_name, representative, 
                               business_type_major, NULL as phone
                        FROM partners_cache
                        WHERE business_number LIKE ? AND is_deleted = 0
                        LIMIT 50
                    """, (f'%{search_term}%',))
                else:
                    cursor.execute("""
                        SELECT business_number, company_name, representative, 
                               business_type_major, NULL as phone
                        FROM partners_cache
                        WHERE company_name LIKE ? AND is_deleted = 0
                        LIMIT 50
                    """, (f'%{search_term}%',))
            else:
                cursor.execute("""
                    SELECT business_number, company_name, representative, 
                           business_type_major, NULL as phone
                    FROM partners_cache
                    WHERE is_deleted = 0
                    LIMIT 50
                """)
            
            for row in cursor.fetchall():
                results.append({
                    'company_business_number': row[0],
                    'company_name': row[1],
                    'representative_name': row[2] or '',
                    'business_type': row[3] or '',
                    'company_phone': row[4] or ''
                })
                
        elif search_type == 'building':
            # 건물 검색 - 외부 DB에서 조회
            try:
                from database_config import execute_SQL
                
                # config.ini에서 BUILDING_QUERY 가져오기
                building_query = db_config.config.get('MASTER_DATA_QUERIES', 'BUILDING_QUERY')
                
                # 검색어 조건 추가
                if search_term:
                    if search_value == 'building_code':
                        building_query += f" AND building_code LIKE '%{search_term}%'"
                    else:
                        building_query += f" AND building_name LIKE '%{search_term}%'"
                
                building_query += " ORDER BY building_name LIMIT 50"
                
                # 외부 DB에서 실행
                df = execute_SQL(building_query)
                
                for _, row in df.iterrows():
                    results.append({
                        'building_code': row.get('building_code', ''),
                        'building_name': row.get('building_name', '')
                    })
                    
            except Exception as e:
                logging.warning(f"외부 DB 건물 조회 실패, 로컬 DB 사용: {e}")
                # 외부 DB 실패 시 로컬 DB 사용
                if search_term:
                    if search_value == 'building_code':
                        cursor.execute("""
                            SELECT building_code, building_name
                            FROM buildings_cache
                            WHERE building_code LIKE ?
                            ORDER BY building_name
                            LIMIT 50
                        """, (f'%{search_term}%',))
                    else:
                        cursor.execute("""
                            SELECT building_code, building_name
                            FROM buildings_cache
                            WHERE building_name LIKE ?
                            ORDER BY building_name
                            LIMIT 50
                        """, (f'%{search_term}%',))
                else:
                    cursor.execute("""
                        SELECT building_code, building_name
                        FROM buildings_cache
                        ORDER BY building_name
                        LIMIT 50
                    """)
                
                for row in cursor.fetchall():
                    results.append({
                        'building_code': row[0],
                        'building_name': row[1]
                    })
                
        elif search_type == 'department':
            # 부서 검색 - 외부 DB에서 조회
            try:
                from database_config import execute_SQL
                
                # config.ini에서 DEPARTMENT_QUERY 가져오기
                department_query = db_config.config.get('MASTER_DATA_QUERIES', 'DEPARTMENT_QUERY')
                
                # 검색어 조건 추가
                if search_term:
                    if search_value == 'dept_code':
                        department_query += f" AND dept_code LIKE '%{search_term}%'"
                    else:
                        department_query += f" AND dept_name LIKE '%{search_term}%'"
                
                department_query += " ORDER BY dept_level, dept_name LIMIT 50"
                
                # 외부 DB에서 실행
                df = execute_SQL(department_query)
                
                for _, row in df.iterrows():
                    results.append({
                        'dept_code': row.get('dept_code', ''),
                        'dept_name': row.get('dept_name', ''),
                        'parent_name': row.get('parent_dept_code', ''),  # 부모 부서코드를 이름으로 사용
                        'dept_level': row.get('dept_level', 0)
                    })
                    
            except Exception as e:
                logging.warning(f"외부 DB 부서 조회 실패, 로컬 DB 사용: {e}")
                # 외부 DB 실패 시 로컬 DB 사용
                if search_term:
                    if search_value == 'dept_code':
                        cursor.execute("""
                            SELECT d.dept_code, d.dept_name, 
                                   p.dept_name as parent_name, d.dept_level
                            FROM departments_cache d
                            LEFT JOIN departments_cache p ON d.parent_dept_code = p.dept_code
                            WHERE d.dept_code LIKE ?
                            ORDER BY d.dept_name
                            LIMIT 50
                        """, (f'%{search_term}%',))
                    else:
                        cursor.execute("""
                            SELECT d.dept_code, d.dept_name, 
                                   p.dept_name as parent_name, d.dept_level
                            FROM departments_cache d
                            LEFT JOIN departments_cache p ON d.parent_dept_code = p.dept_code
                            WHERE d.dept_name LIKE ?
                            ORDER BY d.dept_name
                            LIMIT 50
                        """, (f'%{search_term}%',))
                else:
                    cursor.execute("""
                        SELECT d.dept_code, d.dept_name, 
                               p.dept_name as parent_name, d.dept_level
                        FROM departments_cache d
                        LEFT JOIN departments_cache p ON d.parent_dept_code = p.dept_code
                        ORDER BY d.dept_name
                        LIMIT 50
                    """)
                
                for row in cursor.fetchall():
                    results.append({
                        'dept_code': row[0],
                        'dept_name': row[1],
                        'parent_name': row[2] or '',
                        'parent_dept_code': d.parent_dept_code or ''
                    })
                
        elif search_type == 'contractor':
            # 협력사 근로자 검색 - 외부 DB에서 조회
            try:
                from database_config import execute_SQL
                
                # config.ini에서 CONTRACTOR_QUERY 가져오기
                contractor_query = db_config.config.get('MASTER_DATA_QUERIES', 'CONTRACTOR_QUERY')
                
                # 검색어 조건 추가
                if search_term:
                    if search_value == 'worker_id':
                        contractor_query += f" AND worker_id LIKE '%{search_term}%'"
                    else:
                        contractor_query += f" AND worker_name LIKE '%{search_term}%'"
                
                contractor_query += " ORDER BY worker_name LIMIT 50"
                
                # 외부 DB에서 실행
                df = execute_SQL(contractor_query)
                
                for _, row in df.iterrows():
                    results.append({
                        'worker_id': row.get('worker_id', ''),
                        'worker_name': row.get('worker_name', ''),
                        'company_name': row.get('company_name', ''),
                        'business_number': row.get('business_number', '')
                    })
                    
            except Exception as e:
                logging.warning(f"외부 DB 협력사 근로자 조회 실패, 더미 데이터 사용: {e}")
                # 외부 DB 실패 시 더미 데이터 사용
                sample_contractors = [
                    {'worker_id': 'C001', 'worker_name': '김민수', 'company_name': '삼성건설', 'business_number': '1248100998'},
                    {'worker_id': 'C002', 'worker_name': '이철호', 'company_name': '대림산업', 'business_number': '1108114055'},
                    {'worker_id': 'C003', 'worker_name': '박영진', 'company_name': 'GS건설', 'business_number': '1048145271'},
                    {'worker_id': 'C004', 'worker_name': '최성훈', 'company_name': '현대건설', 'business_number': '1018116293'},
                    {'worker_id': 'C005', 'worker_name': '정미경', 'company_name': '롯데건설', 'business_number': '2148111745'},
                    {'worker_id': 'C006', 'worker_name': '홍길동', 'company_name': '포스코건설', 'business_number': '5068151224'},
                    {'worker_id': 'C007', 'worker_name': '김수연', 'company_name': 'SK건설', 'business_number': '1018143363'},
                    {'worker_id': 'C008', 'worker_name': '장민호', 'company_name': '두산건설', 'business_number': '1028144723'}
                ]
                
                if search_term:
                    if search_value == 'worker_id':  # ID로 검색
                        results = [c for c in sample_contractors if search_term.upper() in c['worker_id'].upper()]
                    else:  # name (이름으로 검색)
                        results = [c for c in sample_contractors if search_term in c['worker_name']]
                else:
                    results = sample_contractors
        
        conn.close()
        return jsonify({'success': True, 'data': results})
    except Exception as e:
        logging.error(f"검색 API 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

@app.route('/api/accidents/permanent-delete', methods=['POST'])
def permanent_delete_accidents():
    """선택한 사고들을 영구 삭제"""
    try:
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 선택한 사고들을 영구 삭제
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            DELETE FROM accidents_cache 
            WHERE id IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 영구 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"사고 영구 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/safety-instruction-columns", methods=["GET"])
def get_safety_instruction_columns():
    """환경안전 지시서 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('safety_instruction', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"환경안전 지시서 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-columns", methods=["POST"])
def add_safety_instruction_column():
    """환경안전 지시서 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('safety_instruction', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"환경안전 지시서 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-columns/<int:column_id>", methods=["PUT"])
def update_safety_instruction_column(column_id):
    """환경안전 지시서 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('safety_instruction', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"환경안전 지시서 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-columns/<int:column_id>", methods=["DELETE"])
def delete_safety_instruction_column(column_id):
    """환경안전 지시서 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('safety_instruction', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"환경안전 지시서 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ===== Admin utility: force delete safety-instruction columns by keys =====
@app.route("/admin/safety-instruction-columns/force-delete-keys", methods=["POST"])
@require_admin_auth
def admin_force_delete_si_columns():
    """강제 컬럼 삭제(soft delete). 관리자 전용.

    Request JSON: {"keys": ["attachments","notes","note"]}
    """
    try:
        data = request.get_json(force=True) or {}
        keys = data.get('keys') or []
        if not keys:
            return jsonify({"success": False, "message": "keys is required"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        placeholders = ','.join('?' * len(keys))
        cursor.execute(
            f"UPDATE safety_instruction_column_config SET is_deleted = 1 WHERE LOWER(column_key) IN ({placeholders})",
            [k.lower() for k in keys]
        )
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        return jsonify({"success": True, "deleted": affected})
    except Exception as e:
        logging.error(f"force delete si columns error: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ============= 섹션 관리 API =============
@app.route("/api/safety-instruction-sections", methods=["GET"])
def get_safety_instruction_sections():
    """환경안전 지시서 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('safety_instruction', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-sections", methods=["POST"])
def add_safety_instruction_section():
    """환경안전 지시서 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('safety_instruction', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-sections/<int:section_id>", methods=["PUT"])
def update_safety_instruction_section(section_id):
    """환경안전 지시서 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('safety_instruction', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-sections/<int:section_id>", methods=["DELETE"])
def delete_safety_instruction_section(section_id):
    """환경안전 지시서 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('safety_instruction', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/safety-instruction-sections/reorder", methods=["POST"])
def reorder_safety_instruction_sections():
    """환경안전 지시서 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('safety_instruction', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ============= Follow SOP API 엔드포인트 =============
@app.route("/api/follow-sop-columns", methods=["GET"])
def get_followsop_columns():
    """Follow SOP 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns", methods=["POST"])
def add_followsop_column():
    """Follow SOP 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["PUT"])
def update_followsop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-columns/<int:column_id>", methods=["DELETE"])
def delete_followsop_column(column_id):
    """Follow SOP 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('follow_sop', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections", methods=["GET"])
def get_followsop_sections():
    """Follow SOP 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"Follow SOP 섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections", methods=["POST"])
def add_followsop_section():
    """Follow SOP 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/<int:section_id>", methods=["PUT"])
def update_followsop_section(section_id):
    """Follow SOP 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/<int:section_id>", methods=["DELETE"])
def delete_followsop_section(section_id):
    """Follow SOP 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/follow-sop-sections/reorder", methods=["POST"])
def reorder_followsop_sections():
    """Follow SOP 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('follow_sop', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Follow SOP 섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ============= Full Process API 엔드포인트 =============
@app.route("/api/full-process-columns", methods=["GET"])
def get_fullprocess_columns():
    """Full Process 페이지 동적 컬럼 설정 조회"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        columns = column_service.list_columns()
        return jsonify(columns)
    except Exception as e:
        logging.error(f"Full Process 컬럼 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns", methods=["POST"])
def add_fullprocess_column():
    """Full Process 페이지 동적 컬럼 추가"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.add_column(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["PUT"])
def update_fullprocess_column(column_id):
    """Full Process 페이지 동적 컬럼 수정"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.update_column(column_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-columns/<int:column_id>", methods=["DELETE"])
def delete_fullprocess_column(column_id):
    """Full Process 페이지 동적 컬럼 삭제 (비활성화)"""
    try:
        column_service = ColumnConfigService('full_process', DB_PATH)
        result = column_service.delete_column(column_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 컬럼 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections", methods=["GET"])
def get_fullprocess_sections():
    """Full Process 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"Full Process 섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections", methods=["POST"])
def add_fullprocess_section():
    """Full Process 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/<int:section_id>", methods=["PUT"])
def update_fullprocess_section(section_id):
    """Full Process 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/<int:section_id>", methods=["DELETE"])
def delete_fullprocess_section(section_id):
    """Full Process 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/full-process-sections/reorder", methods=["POST"])
def reorder_fullprocess_sections():
    """Full Process 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('full_process', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"Full Process 섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ============= 사고게시판 섹션 관리 API =============
@app.route("/api/accident-sections", methods=["GET"])
def get_accident_sections():
    """사고게시판 섹션 목록 조회"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        sections = section_service.get_sections()
        return jsonify({"success": True, "sections": sections})
    except Exception as e:
        logging.error(f"사고 섹션 조회 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-sections", methods=["POST"])
def add_accident_section():
    """사고게시판 섹션 추가"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        result = section_service.add_section(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"사고 섹션 추가 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-sections/<int:section_id>", methods=["PUT"])
def update_accident_section(section_id):
    """사고게시판 섹션 수정"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        result = section_service.update_section(section_id, request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"사고 섹션 수정 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-sections/<int:section_id>", methods=["DELETE"])
def delete_accident_section(section_id):
    """사고게시판 섹션 삭제"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        result = section_service.delete_section(section_id)
        return jsonify(result)
    except Exception as e:
        logging.error(f"사고 섹션 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/api/accident-sections/reorder", methods=["POST"])
def reorder_accident_sections():
    """사고게시판 섹션 순서 변경"""
    try:
        from section_service import SectionConfigService
        section_service = SectionConfigService('accident', DB_PATH)
        result = section_service.reorder_sections(request.json)
        return jsonify(result)
    except Exception as e:
        logging.error(f"사고 섹션 순서 변경 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/api/accident-export")
def export_accidents_excel():
    """사고 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from datetime import datetime
        import io
        
        # 검색 조건 가져오기
        company_name = request.args.get('company_name', '')
        business_number = request.args.get('business_number', '')
        accident_date_start = request.args.get('accident_date_start', '')
        accident_date_end = request.args.get('accident_date_end', '')
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # 동적 컬럼 정보 가져오기 (활성+미삭제, 섹션도 활성인 것만)
        where_c_active = sql_is_active_true('c.is_active', conn)
        where_c_notdel = sql_is_deleted_false('c.is_deleted', conn)
        where_s_active = sql_is_active_true('s.is_active', conn)
        where_s_notdel = sql_is_deleted_false('s.is_deleted', conn)
        dyn_sql = f"""
            SELECT c.* FROM accident_column_config c
            LEFT JOIN section_config s ON s.board_type = 'accident' AND s.section_key = c.tab
            WHERE {where_c_active}
              AND {where_c_notdel}
              AND ({where_s_active} OR s.section_key IS NULL)
              AND ({where_s_notdel} OR s.section_key IS NULL)
            ORDER BY c.column_order
        """
        dynamic_columns_rows = conn.execute(dyn_sql).fetchall()
        dynamic_columns = [dict(row) for row in dynamic_columns_rows]
        
        # 사고 데이터 조회 (partner_accident 함수와 동일한 로직)
        # 삭제되지 않은 데이터만 조회
        query = f"""
            SELECT * FROM accidents_cache 
            WHERE {sql_is_deleted_false('is_deleted', conn)}
        """
        params = []
        
        # company_name과 business_number 필터링은 제거 (responsible_company 관련)
        
        if accident_date_start:
            query += " AND accident_date >= ?"
            params.append(accident_date_start)
        
        if accident_date_end:
            query += " AND accident_date <= ?"
            params.append(accident_date_end)
        
        # 등록일 기준 최신순 정렬 (시분초까지 정확히 정렬됨)
        query += " ORDER BY created_at DESC, accident_number DESC"
        
        accidents = conn.execute(query, params).fetchall()
        
        # 디버그: 첫 번째 사고 데이터 로깅
        if accidents:
            first_accident = dict(accidents[0])
            logging.info(f"First accident data: {first_accident}")
            if first_accident.get('custom_data'):
                logging.info(f"Custom data: {first_accident['custom_data']}")
        
        # 디버그: 동적 컬럼 정보 로깅  
        logging.info(f"Dynamic columns count: {len(dynamic_columns)}")
        for col in dynamic_columns[:3]:  # 처음 3개만
            logging.info(f"Column: {col['column_key']} - {col['column_name']} ({col['column_type']})")
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "사고 현황"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 헤더 작성 (ACCIDENTS_QUERY와 동일한 14개 필드)
        headers = [
            '사고번호', '사고명', '사업장', '사고등급', '대분류',
            '재해형태', '재해유형', '재해날짜', '요일', '등록일',
            '건물', '층', '장소구분', '세부위치'
        ]
        
        # 기본 컬럼과 중복되지 않는 커스텀 동적 컬럼만 추가
        basic_column_keys = [
            'accident_number', 'accident_name', 'workplace', 'accident_grade', 'major_category',
            'injury_form', 'injury_type', 'accident_date', 'day_of_week', 'created_at',
            'building', 'floor', 'location_category', 'location_detail'
        ]
        
        custom_columns = [col for col in dynamic_columns if col['column_key'] not in basic_column_keys]
        for col in custom_columns:
            headers.append(col['column_name'])
        
        # 헤더 쓰기
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        
        # 드롭다운 코드-값 매핑 함수
        def get_display_value(column_key, code_value):
            if not code_value or code_value == '':
                return ''
            try:
                options = get_dropdown_options_for_display('accident', column_key)
                if options:
                    # 리스트 형태의 옵션에서 코드에 해당하는 값 찾기
                    for option in options:
                        if option['code'] == code_value:
                            return option['value']
                return code_value
            except:
                return code_value
        
        # 날짜 형식 정리 함수 (시분초 제거)
        def format_date(date_value):
            if not date_value:
                return ''
            date_str = str(date_value)
            if ' ' in date_str:
                return date_str.split(' ')[0]  # 2025-09-07 0:00:00 → 2025-09-07
            return date_str
        
        # 데이터 쓰기
        for row_idx, accident_row in enumerate(accidents, 2):
            accident = dict(accident_row)
            
            # 기본 필드 쓰기 (드롭다운 코드는 실제 값으로 변환, 날짜는 시분초 제거)
            ws.cell(row=row_idx, column=1, value=accident.get('accident_number', ''))
            ws.cell(row=row_idx, column=2, value=accident.get('accident_name', ''))
            ws.cell(row=row_idx, column=3, value=get_display_value('workplace', accident.get('workplace', '')))
            ws.cell(row=row_idx, column=4, value=get_display_value('accident_grade', accident.get('accident_grade', '')))
            ws.cell(row=row_idx, column=5, value=get_display_value('major_category', accident.get('major_category', '')))
            ws.cell(row=row_idx, column=6, value=get_display_value('injury_form', accident.get('injury_form', '')))
            ws.cell(row=row_idx, column=7, value=get_display_value('injury_type', accident.get('injury_type', '')))
            ws.cell(row=row_idx, column=8, value=format_date(accident.get('accident_date', '')))
            ws.cell(row=row_idx, column=9, value=accident.get('day_of_week', ''))
            ws.cell(row=row_idx, column=10, value=format_date(accident.get('created_at', '')))
            ws.cell(row=row_idx, column=11, value=get_display_value('building', accident.get('building', '')))
            ws.cell(row=row_idx, column=12, value=accident.get('floor', ''))
            ws.cell(row=row_idx, column=13, value=get_display_value('location_category', accident.get('location_category', '')))
            ws.cell(row=row_idx, column=14, value=accident.get('location_detail', ''))
            
            # 동적 컬럼 데이터 쓰기
            custom_data = {}
            if accident.get('custom_data'):
                try:
                    if isinstance(accident['custom_data'], str):
                        custom_data = pyjson.loads(accident['custom_data'])
                    else:
                        custom_data = accident['custom_data']  # PostgreSQL JSONB
                except:
                    custom_data = {}
            
            for col_idx, col in enumerate(custom_columns, 15):
                value = custom_data.get(col['column_key'], '')
                
                # list 타입 데이터 처리 (재해자 정보) - 전체 데이터 표시
                if col['column_type'] == 'list' and isinstance(value, list):
                    # 엑셀에서는 전체 재해자 정보를 JSON 형태로 표시 (빈 리스트는 빈 문자열)
                    try:
                        value = pyjson.dumps(value, ensure_ascii=False) if value else ''
                    except:
                        value = str(value) if value else ''
                
                # popup 타입 데이터 처리
                elif isinstance(value, dict):
                    if 'name' in value:
                        value = value['name']
                    else:
                        value = str(value)
                
                # 드롭다운 타입인 경우 코드를 실제 값으로 변환
                elif col['column_type'] == 'dropdown' and value:
                    value = get_display_value(col['column_key'], value)
                
                # 날짜 타입인 경우 시분초 제거
                elif col['column_type'] in ['date', 'datetime'] and value:
                    value = format_date(value)
                
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 파일을 메모리에 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        conn.close()
        
        # 파일명 생성
        filename = f"accident_list_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        # 다운로드 응답
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"엑셀 다운로드 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 엑셀 임포트 API =====
@app.route('/api/accident-import', methods=['POST'])
def import_accidents():
    try:
        import openpyxl
        # json already imported globally
        from datetime import datetime
        import re
        
        # 파일 확인
        if 'file' not in request.files:
            return jsonify({"success": False, "message": "파일이 없습니다."}), 400
            
        file = request.files['file']
        if file.filename == '':
            return jsonify({"success": False, "message": "파일이 선택되지 않았습니다."}), 400
            
        if not file.filename.lower().endswith(('.xlsx', '.xls')):
            return jsonify({"success": False, "message": "엑셀 파일만 업로드 가능합니다."}), 400
        
        # 옵션 확인
        skip_duplicates = request.form.get('skip_duplicates') == 'on'
        validate_data = request.form.get('validate_data') == 'on'
        
        # 엑셀 파일 읽기
        wb = openpyxl.load_workbook(file, data_only=True)
        ws = wb.active
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # accident_columns 테이블 확인 및 생성
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='accident_column_config'
        """)
        if not cursor.fetchone():
            # 테이블이 없으면 빈 리스트로 처리
            dynamic_columns = []
            logging.info("accident_columns 테이블이 없어서 동적 컬럼 없이 처리합니다.")
        else:
            # 동적 컬럼 조회
            _wa = sql_is_active_true('is_active', conn)
            _wd = sql_is_deleted_false('is_deleted', conn)
            cursor.execute(f"""
                SELECT column_key, column_name, column_type, dropdown_options
                FROM accident_column_config 
                WHERE {_wa} AND {_wd}
                ORDER BY column_order
            """)
            dynamic_columns = cursor.fetchall()
        
        # 헤더 매핑 (한글 헤더명 -> DB 컬럼명)
        # 주의: 사고번호는 자동 생성하므로 매핑에서 제외
        header_mapping = {
            '사고명': 'accident_name', 
            '재해날짜': 'accident_date',
            '시간': 'accident_time',
            '사고등급': 'accident_level',
            '사고분류': 'accident_classification',
            '재해유형': 'disaster_type',
            '재해형태': 'disaster_form',
            '사업장': 'workplace',
            '건물': 'building',
            '층': 'floor',
            '세부위치': 'location_detail',
            '요일': 'day_of_week',
            '처리상태': 'processing_status',
            '조치사항': 'measures',
            '재발방지대책': 'prevention_measures',
            '담당부서': 'department',
            '담당자': 'manager',
            '완료예정일': 'completion_date',
            '원인분석': 'cause_analysis',
            '첨부문서': 'attachment',
            '발생위치': 'occurrence_location'
        }
        
        # 동적 컬럼 매핑 추가
        for col in dynamic_columns:
            header_mapping[col['column_name']] = col['column_key']
        
        # 첫 번째 행에서 헤더 읽기
        headers = []
        for cell in ws[1]:
            headers.append(cell.value if cell.value else '')
        
        success_count = 0
        error_count = 0
        errors = []
        
        # 헤더 정보 로그
        logging.info(f"엑셀 헤더: {headers}")
        logging.info(f"헤더 매핑: {header_mapping}")
        
        # 데이터 행 처리 (2행부터)
        for row_idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), 2):
            try:
                # 빈 행 건너뛰기
                if not any(row):
                    continue
                
                logging.info(f"처리 중인 행 {row_idx}: {row}")
                
                # 데이터 매핑
                data = {}
                custom_data = {}
                
                for col_idx, cell_value in enumerate(row):
                    if col_idx >= len(headers):
                        break
                        
                    header = headers[col_idx]
                    if not header or not cell_value:
                        continue
                        
                    # 문자열로 변환
                    str_value = str(cell_value).strip()
                    if not str_value:
                        continue
                    
                    # 헤더 매핑
                    if header in header_mapping:
                        db_column = header_mapping[header]
                        
                        # 기본 컬럼인지 동적 컬럼인지 확인 (accident_number는 자동 생성하므로 제외)
                        if db_column in ['accident_name', 'accident_date', 'accident_time', 
                                       'accident_level', 'accident_classification', 'disaster_type', 'disaster_form',
                                       'workplace', 'building', 'floor', 'location_detail', 'day_of_week',
                                       'processing_status', 'measures', 
                                       'prevention_measures', 'department', 'manager', 'completion_date',
                                       'cause_analysis', 'attachment', 'occurrence_location']:
                            data[db_column] = str_value
                        else:
                            # 동적 컬럼
                            custom_data[db_column] = str_value
                
                # 사고번호는 항상 자동 생성 (사용자 입력 무시)
                if data.get('accident_date'):
                    # 재해날짜를 기준으로 ACCYYMMDD 형식으로 생성
                    try:
                        accident_date = data['accident_date']
                        if isinstance(accident_date, str):
                            # 날짜 문자열을 파싱
                            for fmt in ['%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d']:
                                try:
                                    dt = datetime.strptime(accident_date, fmt)
                                    break
                                except ValueError:
                                    continue
                            else:
                                # 파싱 실패시 현재 날짜 사용
                                dt = get_korean_time()
                        else:
                            dt = datetime.now()
                        
                        # ACCYYMMDD 기본 형식으로 생성
                        base_number = dt.strftime('ACC%y%m%d')
                        
                        # 같은 날짜에 이미 있는 사고 수 확인 (cache 기준)
                        cursor.execute("""
                            SELECT COUNT(*) FROM accidents_cache 
                            WHERE accident_number LIKE ?
                        """, (base_number + '%',))
                        count = cursor.fetchone()[0]
                        
                        # 일련번호 추가 (01, 02, 03...)
                        sequence = str(count + 1).zfill(2)
                        data['accident_number'] = base_number + sequence
                        
                    except Exception as e:
                        # 오류 발생시 기본 자동 생성 방식 사용
                        data['accident_number'] = generate_manual_accident_number(cursor)
                else:
                    # 재해날짜가 없으면 기본 자동 생성 방식 사용
                    data['accident_number'] = generate_manual_accident_number(cursor)
                
                # 중복 확인 (cache 기준)
                if skip_duplicates and data.get('accident_number'):
                    try:
                        cursor.execute("SELECT COUNT(*) FROM accidents_cache WHERE accident_number = ?", (data['accident_number'],))
                        if (cursor.fetchone() or [0])[0] > 0:
                            continue
                    except Exception:
                        pass
                
                # 날짜 형식 처리 - 간단화
                if data.get('accident_date'):
                    date_str = str(data['accident_date']).strip()
                    if date_str and date_str != 'None':
                        data['accident_date'] = date_str
                    else:
                        # 날짜가 없으면 오늘 날짜로 설정
                        data['accident_date'] = get_korean_time().strftime('%Y-%m-%d')
                
                logging.info(f"매핑된 데이터: {data}")
                logging.info(f"동적 컬럼 데이터: {custom_data}")
                
                # 최소 필수 데이터 확인
                if not data.get('accident_number'):
                    logging.error(f"행 {row_idx}: 사고번호가 생성되지 않음")
                    continue
                
                # DB 저장 - SOT: accidents_cache
                try:
                    # 표준 키 정규화
                    accident_grade = data.pop('accident_level', None)
                    major_category = data.pop('accident_classification', None)
                    injury_type = data.pop('disaster_type', None)
                    injury_form = data.pop('disaster_form', None)

                    top = {
                        'accident_number': data.get('accident_number'),
                        'accident_name': data.get('accident_name', ''),
                        'workplace': data.get('workplace', ''),
                        'accident_grade': accident_grade or data.get('accident_grade', ''),
                        'major_category': major_category or data.get('major_category', ''),
                        'injury_form': injury_form or data.get('injury_form', ''),
                        'injury_type': injury_type or data.get('injury_type', ''),
                        'accident_date': data.get('accident_date', get_korean_time().strftime('%Y-%m-%d')),
                        'day_of_week': data.get('day_of_week', ''),
                        'report_date': data.get('accident_date', get_korean_time().strftime('%Y-%m-%d')),
                        'created_at': get_korean_time().strftime('%Y-%m-%d'),
                        'building': data.get('building', ''),
                        'floor': data.get('floor', ''),
                        'location_category': data.get('location_category', ''),
                        'location_detail': data.get('location_detail', ''),
                    }

                    # 나머지 키는 custom_data에 병합
                    extra = {k: v for k, v in data.items() if k not in top}
                    # 기존 dynamic custom_data와 합치기
                    full_custom = {}
                    full_custom.update(extra)
                    full_custom.update(custom_data)

                    cursor.execute(
                        """
                        INSERT INTO accidents_cache (
                            accident_number,
                            accident_name,
                            workplace,
                            accident_grade,
                            major_category,
                            injury_form,
                            injury_type,
                            accident_date,
                            day_of_week,
                            report_date,
                            created_at,
                            building,
                            floor,
                            location_category,
                            location_detail,
                            custom_data
                        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        (
                            top['accident_number'],
                            top['accident_name'],
                            top['workplace'],
                            top['accident_grade'],
                            top['major_category'],
                            top['injury_form'],
                            top['injury_type'],
                            top['accident_date'],
                            top['day_of_week'],
                            top['report_date'],
                            top['created_at'],
                            top['building'],
                            top['floor'],
                            top['location_category'],
                            top['location_detail'],
                            full_custom,
                        )
                    )

                except Exception as sql_error:
                    logging.error(f"accidents_cache INSERT 오류: {sql_error}")
                    raise sql_error
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                errors.append(f"행 {row_idx}: {str(e)}")
                continue
        
        conn.commit()
        conn.close()
        
        result = {
            "success": True,
            "success_count": success_count,
            "error_count": error_count
        }
        
        if errors:
            result["errors"] = errors[:10]  # 최대 10개 오류만 반환
            
        return jsonify(result)
        
    except Exception as e:
        logging.error(f"엑셀 임포트 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== Follow SOP 엑셀 다운로드 API =====
@app.route('/api/follow-sop-export')
def export_follow_sop_excel():
    """Follow SOP 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        import io
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 동적 컬럼 정보 (활성+미삭제, 섹션도 활성)
        where_c_active = sql_is_active_true('c.is_active', conn)
        where_c_notdel = sql_is_deleted_false('c.is_deleted', conn)
        where_s_active = sql_is_active_true('s.is_active', conn)
        where_s_notdel = sql_is_deleted_false('s.is_deleted', conn)
        dyn_sql = f"""
            SELECT c.* FROM follow_sop_column_config c
            LEFT JOIN follow_sop_sections s ON s.section_key = c.tab
            WHERE {where_c_active}
              AND {where_c_notdel}
              AND ({where_s_active} OR s.section_key IS NULL)
              AND ({where_s_notdel} OR s.section_key IS NULL)
            ORDER BY c.column_order
        """
        cursor.execute(dyn_sql)
        dynamic_columns = cursor.fetchall()
        
        # Follow SOP 데이터 조회
        data_sql = f"""
            SELECT * FROM follow_sop 
            WHERE {sql_is_deleted_false('is_deleted', conn)}
            ORDER BY created_at DESC
        """
        cursor.execute(data_sql)
        data = cursor.fetchall()
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "Follow SOP"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 헤더 작성
        col_idx = 1
        
        # 기본 필드 (follow_sop 테이블에 맞게)
        basic_headers = ['점검번호', '등록일', '작성자']
        for header in basic_headers:
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            col_idx += 1
        
        # 채점 항목을 개별 컬럼으로 확장한 목록 구성
        def _expand_scoring_columns(_cols):
            out = []
            import json as _json
            for c in _cols:
                if c.get('column_type') == 'scoring':
                    sc = c.get('scoring_config')
                    if sc and isinstance(sc, str):
                        try: sc = _json.loads(sc)
                        except Exception: sc = {}
                    items = (sc or {}).get('items') or []
                    for it in items:
                        iid = it.get('id')
                        label = it.get('label') or iid
                        if not iid:
                            continue
                        out.append({
                            'column_key': f"{c['column_key']}__{iid}",
                            'column_name': f"{c.get('column_name', c.get('column_key'))} - {label}",
                            'column_type': 'number',
                            '_virtual': 1,
                            '_source_scoring_key': c['column_key'],
                            '_source_item_id': iid
                        })
                else:
                    out.append(dict(c))
            return out

        dyn_cols_list = [dict(x) for x in dynamic_columns]
        expanded_columns = _expand_scoring_columns(dyn_cols_list)

        # 스코어 총점 계산 준비
        import json as _json
        scoring_cols = [dict(c) for c in dyn_cols_list if dict(c).get('column_type') == 'scoring']
        score_total_cols = [dict(c) for c in dyn_cols_list if dict(c).get('column_type') == 'score_total']

        # 동적 컬럼 헤더
        for col in expanded_columns:
            cell = ws.cell(row=1, column=col_idx, value=col['column_name'])
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            col_idx += 1
        
        # 데이터 작성
        for row_idx, row in enumerate(data, 2):
            # 먼저 row를 dict로 변환
            row_dict = dict(row)
            col_idx = 1
            
            # 기본 필드 - 실제 컬럼명 사용
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('work_req_no', ''))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('created_at', ''))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('created_by', ''))
            col_idx += 1
            
            # custom_data 파싱
            custom_data = {}
            if row_dict.get('custom_data'):
                try:
                    custom_data = json.loads(row_dict.get('custom_data', '{}'))
                except:
                    custom_data = {}
            
            # 동적 컬럼 데이터 - 드롭다운/가상 채점 항목 포함
            # 드롭다운 매핑 지원
            def _map_value(col, value):
                # 팝업형 값(dict) → name
                if isinstance(value, dict):
                    return value.get('name', str(value))
                # 리스트 ⇒ JSON 문자열
                if col['column_type'] == 'list' and isinstance(value, list):
                    try:
                        return json.dumps(value, ensure_ascii=False)
                    except Exception:
                        return str(value)
                # 드롭다운 코드 → 표시값
                if col['column_type'] == 'dropdown' and value:
                    opts = get_dropdown_options_for_display('follow_sop', col['column_key'])
                    if opts:
                        for opt in opts:
                            if opt['code'] == value:
                                return opt['value']
                return value

            for col in expanded_columns:
                if col.get('_virtual') == 1:
                    src = col.get('_source_scoring_key')
                    iid = col.get('_source_item_id')
                    group_obj = custom_data.get(src, {})
                    if isinstance(group_obj, str):
                        try:
                            group_obj = json.loads(group_obj)
                        except Exception:
                            group_obj = {}
                    v = 0
                    if isinstance(group_obj, dict):
                        v = group_obj.get(iid, 0)
                    ws.cell(row=row_idx, column=col_idx, value=v)
                else:
                    if col.get('column_type') == 'score_total':
                        # 총점 계산 (total_key 기준)
                        try:
                            stc = col
                            conf = stc.get('scoring_config')
                            if conf and isinstance(conf, str):
                                try: conf = _json.loads(conf)
                                except Exception: conf = {}
                            total_key = (conf or {}).get('total_key') or 'default'
                            base = (conf or {}).get('base_score', 100)
                            total = base
                            for sc_col in scoring_cols:
                                sconf = sc_col.get('scoring_config')
                                if sconf and isinstance(sconf, str):
                                    try: sconf = _json.loads(sconf)
                                    except Exception: sconf = {}
                                if ((sconf or {}).get('total_key') or 'default') != total_key:
                                    continue
                                items_cfg = (sconf or {}).get('items') or []
                                group_obj = custom_data.get(sc_col.get('column_key'), {})
                                if isinstance(group_obj, str):
                                    try: group_obj = _json.loads(group_obj)
                                    except Exception: group_obj = {}
                                for it in items_cfg:
                                    iid = it.get('id')
                                    delta = float(it.get('per_unit_delta') or 0)
                                    cnt = 0
                                    if isinstance(group_obj, dict) and iid in group_obj:
                                        try: cnt = int(group_obj.get(iid) or 0)
                                        except Exception: cnt = 0
                                    total += cnt * delta
                            ws.cell(row=row_idx, column=col_idx, value=total)
                        except Exception:
                            ws.cell(row=row_idx, column=col_idx, value='')
                    else:
                        v = custom_data.get(col['column_key'], '')
                        ws.cell(row=row_idx, column=col_idx, value=_map_value(col, v))
                col_idx += 1
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 파일 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"follow_sop_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        conn.close()
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        )
        
    except Exception as e:
        import traceback
        logging.error(f"Follow SOP 엑셀 다운로드 중 오류: {e}")
        logging.error(traceback.format_exc())
        if conn:
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== Full Process 엑셀 다운로드 API =====
@app.route('/api/full-process-export')
def export_full_process_excel():
    """Full Process 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        import io
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 동적 컬럼 정보 (활성+미삭제, 섹션도 활성)
        where_c_active = sql_is_active_true('c.is_active', conn)
        where_c_notdel = sql_is_deleted_false('c.is_deleted', conn)
        where_s_active = sql_is_active_true('s.is_active', conn)
        where_s_notdel = sql_is_deleted_false('s.is_deleted', conn)
        dyn_sql = f"""
            SELECT c.* FROM full_process_column_config c
            LEFT JOIN full_process_sections s ON s.section_key = c.tab
            WHERE {where_c_active}
              AND {where_c_notdel}
              AND ({where_s_active} OR s.section_key IS NULL)
              AND ({where_s_notdel} OR s.section_key IS NULL)
            ORDER BY c.column_order
        """
        cursor.execute(dyn_sql)
        dynamic_columns = cursor.fetchall()
        
        # Full Process 데이터 조회
        data_sql = f"""
            SELECT * FROM full_process 
            WHERE {sql_is_deleted_false('is_deleted', conn)}
            ORDER BY created_at DESC
        """
        cursor.execute(data_sql)
        data = cursor.fetchall()
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "Full Process"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 헤더 작성
        col_idx = 1
        
        # 기본 필드 (full_process 테이블에 맞게)
        basic_headers = ['프로세스 번호', '작성일', '작성자']
        for header in basic_headers:
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            col_idx += 1
        
        # 동적 컬럼 - 삭제되지 않은 것만
        for col in dynamic_columns:
            cell = ws.cell(row=1, column=col_idx, value=col['column_name'])
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            col_idx += 1
        
        # 데이터 작성
        for row_idx, row in enumerate(data, 2):
            # 먼저 row를 dict로 변환
            row_dict = dict(row)
            col_idx = 1
            
            # 기본 필드 - 실제 컬럼명 사용
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('fullprocess_number', ''))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('created_at', ''))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('created_by', ''))
            col_idx += 1
            
            # custom_data 파싱
            custom_data = {}
            if row_dict.get('custom_data'):
                try:
                    custom_data = json.loads(row_dict.get('custom_data', '{}'))
                except:
                    custom_data = {}
            
            # 동적 컬럼 데이터 - 활성화되고 삭제되지 않은 컬럼만
            # 드롭다운 매핑 지원
            def _map_value(col, value):
                if isinstance(value, dict):
                    return value.get('name', str(value))
                if col['column_type'] == 'list' and isinstance(value, list):
                    try:
                        return json.dumps(value, ensure_ascii=False)
                    except Exception:
                        return str(value)
                if col['column_type'] == 'dropdown' and value:
                    opts = get_dropdown_options_for_display('full_process', col['column_key'])
                    if opts:
                        for opt in opts:
                            if opt['code'] == value:
                                return opt['value']
                return value

            for col in dynamic_columns:
                v = custom_data.get(col['column_key'], '')
                ws.cell(row=row_idx, column=col_idx, value=_map_value(col, v))
                col_idx += 1
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 파일 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"full_process_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        conn.close()
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        )
        
    except Exception as e:
        import traceback
        logging.error(f"Full Process 엑셀 다운로드 중 오류: {e}")
        logging.error(traceback.format_exc())
        if conn:
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== Safety Instruction 엑셀 다운로드 API =====
@app.route('/api/safety-instruction-export')
def export_safety_instruction_excel():
    """Safety Instruction 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        import io
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # 동적 컬럼 정보 (활성+미삭제, 섹션도 활성)
        where_c_active = sql_is_active_true('c.is_active', conn)
        where_c_notdel = sql_is_deleted_false('c.is_deleted', conn)
        where_s_active = sql_is_active_true('s.is_active', conn)
        dyn_sql = f"""
            SELECT c.* FROM safety_instruction_column_config c
            INNER JOIN section_config s 
              ON s.board_type = 'safety_instruction' AND s.section_key = c.tab AND {where_s_active}
            WHERE {where_c_active}
              AND {where_c_notdel}
            ORDER BY c.column_order
        """
        cursor.execute(dyn_sql)
        dynamic_columns = cursor.fetchall()
        
        # Safety Instruction 데이터 조회 - 메인 테이블 사용
        data_sql = f"""
            SELECT * FROM safety_instructions 
            WHERE {sql_is_deleted_false('is_deleted', conn)}
            ORDER BY created_at DESC, issue_number DESC
        """
        cursor.execute(data_sql)
        data = cursor.fetchall()
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "Safety Instructions"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 헤더 작성
        col_idx = 1
        
        # 기본 필드 (safety_instructions_cache 테이블의 주요 컬럼)
        basic_headers = ['발부번호', '발부자', '위반일자', '징계일자', '피징계자']
        for header in basic_headers:
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
            col_idx += 1
        
        # 동적 컬럼 - 삭제되지 않은 것만 (기본 필드 제외)
        basic_column_keys = ['issue_number', 'issuer', 'violation_date', 'discipline_date', 'disciplined_person']
        for col in dynamic_columns:
            if col['column_key'] not in basic_column_keys:
                cell = ws.cell(row=1, column=col_idx, value=col['column_name'])
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
                col_idx += 1
        
        # 데이터 작성
        for row_idx, row in enumerate(data, 2):
            # 먼저 row를 dict로 변환
            row_dict = dict(row)
            col_idx = 1

            # custom_data 파싱 (먼저 파싱하여 기본 필드 보완)
            custom_data = {}
            if row_dict.get('custom_data'):
                try:
                    custom_data = json.loads(row_dict.get('custom_data', '{}'))
                except Exception:
                    custom_data = {}

            # 기본 필드 - issue_number는 실제 컬럼, 나머지는 custom_data 우선
            ws.cell(row=row_idx, column=col_idx, value=row_dict.get('issue_number', ''))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=(custom_data.get('issuer') or row_dict.get('issuer', '')))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=(custom_data.get('violation_date') or row_dict.get('violation_date', '')))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=(custom_data.get('discipline_date') or row_dict.get('discipline_date', '')))
            col_idx += 1
            ws.cell(row=row_idx, column=col_idx, value=(custom_data.get('disciplined_person') or row_dict.get('disciplined_person', '')))
            col_idx += 1

            # 동적 컬럼 데이터 - 기본 필드 제외하고 처리
            basic_column_keys = ['issue_number', 'issuer', 'violation_date', 'discipline_date', 'disciplined_person']
            def _map_value(col, value):
                if isinstance(value, dict):
                    return value.get('name', str(value))
                if col['column_type'] == 'list' and isinstance(value, list):
                    try:
                        return json.dumps(value, ensure_ascii=False)
                    except Exception:
                        return str(value)
                if col['column_type'] == 'dropdown' and value:
                    opts = get_dropdown_options_for_display('safety_instruction', col['column_key'])
                    if opts:
                        for opt in opts:
                            if opt['code'] == value:
                                return opt['value']
                return value

            for col in dynamic_columns:
                if col['column_key'] not in basic_column_keys:
                    col_key = col['column_key']
                    v = row_dict.get(col_key, '') or (custom_data.get(col_key, '') if custom_data else '')
                    ws.cell(row=row_idx, column=col_idx, value=_map_value(col, v))
                    col_idx += 1
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min((max_length + 2) * 1.2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 파일 저장
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        filename = f"safety_instruction_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        conn.close()
        
        return Response(
            output.getvalue(),
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            headers={
                'Content-Disposition': f'attachment; filename={filename}',
                'Content-Type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            }
        )
        
    except Exception as e:
        import traceback
        logging.error(f"Safety Instruction 엑셀 다운로드 중 오류: {e}")
        logging.error(traceback.format_exc())
        if conn:
            conn.close()
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 기준정보 변경요청 엑셀 다운로드 API =====
@app.route('/api/change-requests/export')
def export_change_requests_excel():
    """기준정보 변경요청 데이터 엑셀 다운로드"""
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from datetime import datetime
        import io
        
        # 검색 조건 가져오기
        company_name = request.args.get('company_name', '')
        business_number = request.args.get('business_number', '')
        status = request.args.get('status', '')
        created_date_start = request.args.get('created_date_start', '')
        created_date_end = request.args.get('created_date_end', '')
        
        # DB 연결
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        
        # 동적 컬럼 정보 (활성+미삭제, 섹션도 활성)
        where_c_active = sql_is_active_true('c.is_active', conn)
        where_c_notdel = sql_is_deleted_false('c.is_deleted', conn)
        where_s_active = sql_is_active_true('s.is_active', conn)
        where_s_notdel = sql_is_deleted_false('s.is_deleted', conn)
        dyn_sql = f"""
            SELECT c.* FROM change_request_column_config c
            LEFT JOIN section_config s ON s.board_type = 'change_request' AND s.section_key = c.tab
            WHERE {where_c_active}
              AND {where_c_notdel}
              AND ({where_s_active} OR s.section_key IS NULL)
              AND ({where_s_notdel} OR s.section_key IS NULL)
            ORDER BY c.column_order
        """
        dynamic_columns_rows = conn.execute(dyn_sql).fetchall()
        dynamic_columns = [dict(row) for row in dynamic_columns_rows]
        
        # 변경요청 데이터 조회
        query = f"""
            SELECT * FROM partner_change_requests 
            WHERE {sql_is_deleted_false('is_deleted', conn)}
        """
        params = []
        
        if company_name:
            query += " AND company_name LIKE ?"
            params.append(f"%{company_name}%")
        
        if business_number:
            query += " AND business_number LIKE ?"
            params.append(f"%{business_number}%")
            
        if status:
            query += " AND status = ?"
            params.append(status)
        
        if created_date_start:
            query += " AND DATE(created_at) >= ?"
            params.append(created_date_start)
        
        if created_date_end:
            query += " AND DATE(created_at) <= ?"
            params.append(created_date_end)
        
        # 등록일 기준 최신순 정렬
        query += " ORDER BY created_at DESC, id DESC"
        
        change_requests = conn.execute(query, params).fetchall()
        
        # 드롭다운 코드-값 매핑 함수
        def get_display_value(column_key, code_value):
            if not code_value or code_value == '':
                return ''
            try:
                options = get_dropdown_options_for_display('change_request', column_key)
                if options:
                    # 리스트 형태의 옵션에서 코드에 해당하는 값 찾기
                    for option in options:
                        if option['code'] == code_value:
                            return option['value']
                return code_value
            except:
                return code_value
        
        # 날짜 형식 정리 함수 (시분초 제거)
        def format_date(date_value):
            if not date_value:
                return ''
            date_str = str(date_value)
            if ' ' in date_str:
                return date_str.split(' ')[0]  # 2025-09-07 0:00:00 → 2025-09-07
            return date_str
        
        # 엑셀 워크북 생성
        wb = Workbook()
        ws = wb.active
        ws.title = "기준정보 변경요청"
        
        # 헤더 스타일 설정
        header_font = Font(bold=True, color="FFFFFF")
        header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
        header_align = Alignment(horizontal="center", vertical="center")
        
        # 기본 헤더
        headers = [
            '요청번호', '회사명', '사업자번호', '상태', '등록일', '수정일'
        ]
        
        # 동적 컬럼 헤더 추가
        for col in dynamic_columns:
            headers.append(col['column_name'])
        
        # 헤더 쓰기
        for col_idx, header in enumerate(headers, 1):
            cell = ws.cell(row=1, column=col_idx, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_align
        
        # 데이터 쓰기
        for row_idx, request_row in enumerate(change_requests, 2):
            request_data = dict(request_row)
            
            # 기본 필드 쓰기
            ws.cell(row=row_idx, column=1, value=request_data.get('request_number', ''))
            ws.cell(row=row_idx, column=2, value=request_data.get('company_name', ''))
            ws.cell(row=row_idx, column=3, value=request_data.get('business_number', ''))
            
            # 상태 코드를 실제 값으로 변환
            status_value = request_data.get('status', '')
            status_display = get_display_value('status', status_value) if status_value else ''
            ws.cell(row=row_idx, column=4, value=status_display)
            
            ws.cell(row=row_idx, column=5, value=format_date(request_data.get('created_at', '')))
            ws.cell(row=row_idx, column=6, value=format_date(request_data.get('updated_at', '')))
            
            # 동적 컬럼 데이터 쓰기
            custom_data = {}
            if request_data.get('custom_data'):
                try:
                    if isinstance(request_data['custom_data'], str):
                        custom_data = pyjson.loads(request_data['custom_data'])
                    else:
                        custom_data = request_data['custom_data']  # PostgreSQL JSONB
                except:
                    custom_data = {}
            
            for col_idx, col in enumerate(dynamic_columns, 7):  # 7번째 컬럼부터
                value = custom_data.get(col['column_key'], '')
                
                # popup 타입 데이터 처리
                if isinstance(value, dict):
                    if 'name' in value:
                        value = value['name']
                    else:
                        value = str(value)
                
                # 드롭다운 타입인 경우 코드를 실제 값으로 변환
                if col['column_type'] == 'dropdown' and value:
                    value = get_display_value(col['column_key'], value)
                
                # 날짜 타입인 경우 시분초 제거
                elif col['column_type'] in ['date', 'datetime'] and value:
                    value = format_date(value)
                
                ws.cell(row=row_idx, column=col_idx, value=value)
        
        # 컬럼 너비 자동 조정
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # 메모리에서 엑셀 파일 생성
        output = io.BytesIO()
        wb.save(output)
        output.seek(0)
        
        # 파일명 생성 (한국시간 기준)
        korean_time = get_korean_time()
        filename = f"기준정보_변경요청_{korean_time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        conn.close()
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        logging.error(f"변경요청 엑셀 다운로드 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 협력사 엑셀 다운로드 API =====
@app.route('/api/partners/export')
def export_partners_to_excel():
    try:
        import openpyxl
        from openpyxl import Workbook
        from openpyxl.styles import Font, Alignment, PatternFill
        from datetime import datetime
        import io
        
        # 검색 조건 가져오기
        company_name = request.args.get('company_name', '')
        business_number = request.args.get('business_number', '')
        business_type_major = request.args.get('business_type_major', '')
        business_type_minor = request.args.get('business_type_minor', '')
        workers_min = request.args.get('workers_min', '')
        workers_max = request.args.get('workers_max', '')
        
        # 협력사 데이터 조회 (partner_standards 함수와 동일한 로직)
        try:
            conn = get_db_connection()
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # 쿼리 구성 (삭제되지 않은 데이터만)
            query = f"SELECT * FROM partners_cache WHERE {sql_is_deleted_false('is_deleted', conn)}"
            params = []
            
            if company_name:
                query += " AND company_name LIKE ?"
                params.append(f'%{company_name}%')
            
            if business_number:
                query += " AND business_number LIKE ?"
                params.append(f'%{business_number}%')
                
            if business_type_major:
                query += " AND business_type_major = ?"
                params.append(business_type_major)
                
            if business_type_minor:
                query += " AND business_type_minor = ?"
                params.append(business_type_minor)
                
            if workers_min:
                try:
                    min_val = int(workers_min)
                    query += " AND permanent_workers >= ?"
                    params.append(min_val)
                except ValueError:
                    pass
                    
            if workers_max:
                try:
                    max_val = int(workers_max)
                    query += " AND permanent_workers <= ?"
                    params.append(max_val)
                except ValueError:
                    pass
            
            query += " ORDER BY company_name"
            
            partners = cursor.execute(query, params).fetchall()
            
            # 엑셀 워크북 생성
            wb = Workbook()
            ws = wb.active
            ws.title = "협력사 기준정보"
            
            # 헤더 스타일 설정
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            
            # 헤더 작성
            headers = [
                '협력사명', '사업자번호', 'Class', '업종(대분류)', '업종(소분류)',
                '위험작업여부', '대표자성명', '주소', '평균연령', '매출액', 
                '거래차수', '상시근로자'
            ]
            
            # 헤더 쓰기
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            
            # 데이터 쓰기
            for row_idx, partner_row in enumerate(partners, 2):
                partner = dict(partner_row)
                
                ws.cell(row=row_idx, column=1, value=partner.get('company_name', ''))
                ws.cell(row=row_idx, column=2, value=partner.get('business_number', ''))
                ws.cell(row=row_idx, column=3, value=partner.get('partner_class', ''))
                ws.cell(row=row_idx, column=4, value=partner.get('business_type_major', ''))
                ws.cell(row=row_idx, column=5, value=partner.get('business_type_minor', ''))
                
                # 위험작업여부 처리
                hazard_work = partner.get('hazard_work_flag', '')
                hazard_text = '예' if hazard_work == 'O' else '아니오' if hazard_work == 'X' else ''
                ws.cell(row=row_idx, column=6, value=hazard_text)
                
                ws.cell(row=row_idx, column=7, value=partner.get('representative', ''))
                ws.cell(row=row_idx, column=8, value=partner.get('address', ''))
                ws.cell(row=row_idx, column=9, value=partner.get('average_age', ''))
                
                # 매출액 처리 (억원 단위)
                revenue = partner.get('annual_revenue')
                if revenue:
                    revenue_text = f"{revenue // 100000000}억원"
                else:
                    revenue_text = ''
                ws.cell(row=row_idx, column=10, value=revenue_text)
                
                ws.cell(row=row_idx, column=11, value=partner.get('transaction_count', ''))
                
                # 상시근로자 처리
                workers = partner.get('permanent_workers')
                workers_text = f"{workers}명" if workers else ''
                ws.cell(row=row_idx, column=12, value=workers_text)
            
            # 컬럼 너비 자동 조정
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # 파일을 메모리에 저장
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            conn.close()
            
            # 파일명 생성
            filename = f"partners_list_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            # 다운로드 응답
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
            
        except Exception as db_error:
            logging.error(f"협력사 데이터 조회 중 오류: {db_error}")
            # 더미 데이터로 대체
            wb = Workbook()
            ws = wb.active
            ws.title = "협력사 기준정보"
            
            # 헤더만 있는 빈 파일 생성
            headers = [
                '협력사명', '사업자번호', 'Class', '업종(대분류)', '업종(소분류)',
                '위험작업여부', '대표자성명', '주소', '평균연령', '매출액', 
                '거래차수', '상시근로자'
            ]
            
            header_font = Font(bold=True, color="FFFFFF")
            header_fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
            header_align = Alignment(horizontal="center", vertical="center")
            
            for col_idx, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col_idx, value=header)
                cell.font = header_font
                cell.fill = header_fill
                cell.alignment = header_align
            
            # 샘플 데이터 1행 추가
            sample_data = [
                '샘플 협력사', '123-45-67890', 'A', '제조업', '전자제품',
                '예', '김대표', '서울시 강남구', '35', '100억원', '5', '50명'
            ]
            for col_idx, value in enumerate(sample_data, 1):
                ws.cell(row=2, column=col_idx, value=value)
            
            # 컬럼 너비 조정
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 30)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            output = io.BytesIO()
            wb.save(output)
            output.seek(0)
            
            filename = f"partners_list_{get_korean_time().strftime('%Y%m%d_%H%M%S')}.xlsx"
            
            return send_file(
                output,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                as_attachment=True,
                download_name=filename
            )
    
    except Exception as e:
        logging.error(f"협력사 엑셀 다운로드 중 오류: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return jsonify({"success": False, "message": str(e)}), 500

# ===== 협력사 삭제 API =====
@app.route('/api/partners/delete', methods=['POST'])
def delete_partners():
    try:
        data = request.get_json()
        business_numbers = data.get('business_numbers', [])
        
        if not business_numbers:
            return jsonify({"success": False, "message": "삭제할 협력사가 선택되지 않았습니다."}), 400
        
        # DB 연결
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Soft delete (is_deleted = 1로 설정)
        placeholders = ','.join('?' * len(business_numbers))
        cursor.execute(f"""
            UPDATE partners_cache 
            SET is_deleted = 1 
            WHERE business_number IN ({placeholders})
        """, business_numbers)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}개의 협력사가 삭제되었습니다.",
            "reload": True  # 페이지 새로고침 필요 플래그 추가
        })
        
    except Exception as e:
        logging.error(f"협력사 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

# 새로운 메뉴들의 라우트
@app.route('/work-safety')
def work_safety():
    """작업안전 현황 페이지"""
    return render_template('work-safety.html', menu=menu)

@app.route('/risk-assessment')
def risk_assessment():
    """위험성평가 현황 페이지"""
    return render_template('risk-assessment.html', menu=menu)

@app.route('/qualification-assessment')
def qualification_assessment():
    """적격성평가 현황 페이지"""
    return render_template('qualification-assessment.html', menu=menu)

@app.route('/safety-culture')
def safety_culture():
    """안전문화 현황 페이지"""
    return render_template('safety-culture.html', menu=menu)

@app.after_request
def add_header(response):
    """응답 헤더 추가 - 캐시 무효화"""
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response


@app.route('/api/partner-change-request', methods=['POST'])
def create_partner_change_request():
    """기준정보 변경요청 등록 API"""
    try:
        data = request.get_json()
        
        # 필수 필드 검증
        required_fields = ['requester_name', 'requester_department', 'company_name', 
                          'business_number', 'change_type', 'current_value', 'new_value', 'change_reason']
        
        for field in required_fields:
            if not data.get(field):
                return jsonify({"success": False, "message": f"{field} 필드가 필요합니다."}), 400
        
        # DB 연결 및 테이블 생성
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 변경요청 테이블 생성 (없을 경우)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS partner_change_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_number TEXT UNIQUE,
                requester_name TEXT NOT NULL,
                requester_department TEXT NOT NULL,
                company_name TEXT NOT NULL,
                business_number TEXT NOT NULL,
                change_type TEXT NOT NULL,
                current_value TEXT NOT NULL,
                new_value TEXT NOT NULL,
                change_reason TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                custom_data TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        
        # 기존 테이블에 request_number 컬럼이 없으면 추가
        cursor.execute("PRAGMA table_info(partner_change_requests)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'request_number' not in columns:
            cursor.execute("ALTER TABLE partner_change_requests ADD COLUMN request_number TEXT UNIQUE")
            logging.info("request_number 컬럼 추가됨")
        if 'custom_data' not in columns:
            cursor.execute("ALTER TABLE partner_change_requests ADD COLUMN custom_data TEXT")
            logging.info("custom_data 컬럼 추가됨")
        if 'is_deleted' not in columns:
            cursor.execute("ALTER TABLE partner_change_requests ADD COLUMN is_deleted INTEGER DEFAULT 0")
            logging.info("is_deleted 컬럼 추가됨")
        
        # request_number 생성 (CR-YYYYMM-SEQ 형식)
        current_month = get_korean_time().strftime('%Y%m')
        
        # 이번 달 최대 시퀀스 번호 조회
        cursor.execute("""
            SELECT MAX(CAST(SUBSTR(request_number, -2) AS INTEGER)) as max_seq
            FROM partner_change_requests
            WHERE request_number LIKE ?
        """, (f'CR-{current_month}-%',))
        
        result = cursor.fetchone()
        max_seq = result[0] if result[0] else 0
        new_seq = max_seq + 1
        request_number = f'CR-{current_month}-{new_seq:02d}'
        
        # status 값 결정 (requested로 설정)
        status = data.get('status', 'requested')
        
        # 변경요청 데이터 삽입 (request_number, custom_data, status 포함)
        cursor.execute_with_returning_id("""
            INSERT INTO partner_change_requests 
            (request_number, requester_name, requester_department, company_name, business_number, 
             change_type, current_value, new_value, change_reason, custom_data, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            request_number,  # 자동 생성된 request_number
            data['requester_name'],
            data['requester_department'],
            data['company_name'],
            data['business_number'],
            data['change_type'],
            data['current_value'],
            data['new_value'],
            data['change_reason'],
            pyjson.dumps(data.get('custom_data', {})),  # custom_data 추가
            status  # status 추가
        ))
        
        request_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "request_id": request_id,
            "message": "변경요청이 성공적으로 등록되었습니다.",
            "reload": True
        })
        
    except Exception as e:
        logging.error(f"변경요청 등록 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/change-requests/delete', methods=['POST'])
def delete_change_requests():
    """선택한 변경요청들을 소프트 삭제 (공통 서비스 활용)"""
    try:
        from board_services import ItemService
        
        data = request.json
        ids = data.get('ids', [])
        
        if not ids:
            return jsonify({"success": False, "message": "삭제할 항목이 없습니다."}), 400
        
        # partner_change_requests 테이블에 is_deleted 컬럼 추가 (없으면)
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            PRAGMA table_info(partner_change_requests)
        """)
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_deleted' not in columns:
            cursor.execute("""
                ALTER TABLE partner_change_requests 
                ADD COLUMN is_deleted INTEGER DEFAULT 0
            """)
            conn.commit()
        
        # 소프트 삭제 실행
        placeholders = ','.join('?' * len(ids))
        cursor.execute(f"""
            UPDATE partner_change_requests 
            SET is_deleted = 1 
            WHERE id IN ({placeholders})
        """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        conn.close()
        
        return jsonify({
            "success": True,
            "deleted_count": deleted_count,
            "message": f"{deleted_count}건이 삭제되었습니다."
        })
    except Exception as e:
        logging.error(f"변경요청 삭제 중 오류: {e}")
        return jsonify({"success": False, "message": str(e)}), 500


@app.route('/api/partner-change-requests', methods=['GET'])
def get_partner_change_requests():
    """기준정보 변경요청 목록 조회 API"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, requester_name, requester_department, company_name, business_number,
                   change_type, current_value, new_value, change_reason, status, created_at
            FROM partner_change_requests
            ORDER BY created_at DESC
        """)
        
        requests = []
        for row in cursor.fetchall():
            requests.append({
                'id': row[0],
                'requester_name': row[1],
                'requester_department': row[2],
                'company_name': row[3],
                'business_number': row[4],
                'change_type': row[5],
                'current_value': row[6],
                'new_value': row[7],
                'change_reason': row[8],
                'status': row[9],
                'created_at': row[10]
            })
        
        conn.close()
        return jsonify({'success': True, 'requests': requests})
        
    except Exception as e:
        logging.error(f"변경요청 목록 조회 중 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# 변경요청 컬럼 관리 API

@app.route('/api/person-master', methods=['GET'])
def api_get_person_master():
    """담당자 마스터 목록 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, department, position, company_name, phone, email, is_active
            FROM person_master
            WHERE is_active = 1
            ORDER BY name
        """)
        
        persons = []
        for row in cursor.fetchall():
            persons.append({
                'id': row[0],
                'name': row[1],
                'department': row[2],
                'position': row[3],
                'company_name': row[4],
                'phone': row[5],
                'email': row[6],
                'is_active': row[7]
            })
        
        conn.close()
        return jsonify({'success': True, 'persons': persons})
        
    except Exception as e:
        logging.error(f"담당자 마스터 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/person-master/<int:person_id>', methods=['GET'])
def api_get_person_detail(person_id):
    """담당자 상세 정보 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, name, department, position, company_name, phone, email
            FROM person_master
            WHERE id = ? AND is_active = 1
        """, (person_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            person = {
                'id': row[0],
                'name': row[1],
                'department': row[2],
                'position': row[3],
                'company_name': row[4],
                'phone': row[5],
                'email': row[6]
            }
            return jsonify({'success': True, 'person': person})
        else:
            return jsonify({'success': False, 'message': '담당자를 찾을 수 없습니다.'}), 404
            
    except Exception as e:
        logging.error(f"담당자 상세 조회 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/person-master', methods=['POST'])
@require_admin_auth
def api_create_person():
    """담당자 추가"""
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'success': False, 'message': '이름은 필수 입력 항목입니다.'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute_with_returning_id("""
            INSERT INTO person_master (name, department, position, company_name, phone, email)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            data.get('name'),
            data.get('department', ''),
            data.get('position', ''),
            data.get('company_name', ''),
            data.get('phone', ''),
            data.get('email', '')
        ))
        
        person_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'person_id': person_id, 'message': '담당자가 추가되었습니다.'})
        
    except Exception as e:
        logging.error(f"담당자 추가 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/person-master/<int:person_id>', methods=['PUT'])
@require_admin_auth
def api_update_person(person_id):
    """담당자 수정"""
    try:
        data = request.get_json()
        
        if not data.get('name'):
            return jsonify({'success': False, 'message': '이름은 필수 입력 항목입니다.'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE person_master 
            SET name = ?, department = ?, position = ?, company_name = ?, phone = ?, email = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
        """, (
            data.get('name'),
            data.get('department', ''),
            data.get('position', ''),
            data.get('company_name', ''),
            data.get('phone', ''),
            data.get('email', ''),
            person_id
        ))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'message': '담당자를 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '담당자가 수정되었습니다.'})
        
    except Exception as e:
        logging.error(f"담당자 수정 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/person-master/<int:person_id>', methods=['DELETE'])
@require_admin_auth
def api_delete_person(person_id):
    """담당자 삭제 (소프트 삭제)"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE person_master 
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE id = ? AND is_active = 1
        """, (person_id,))
        
        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'success': False, 'message': '담당자를 찾을 수 없습니다.'}), 404
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True, 'message': '담당자가 삭제되었습니다.'})
        
    except Exception as e:
        logging.error(f"담당자 삭제 오류: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


# ============================================================================
# 표준화된 API 엔드포인트 (/api/<board>/...)
# ============================================================================

@app.route("/api/<board>/columns", methods=["GET", "POST"])
def board_columns_api(board):
    """보드별 컬럼 관리 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ColumnService(board_type, DB_PATH)
        
        if request.method == "GET":
            columns = service.list()
            return jsonify(columns)
        
        elif request.method == "POST":
            data = request.json
            column_id = service.add(data)
            return jsonify({"success": True, "id": column_id})
            
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board columns API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/columns/<int:column_id>", methods=["PUT", "DELETE"])
def board_column_api(board, column_id):
    """보드별 개별 컬럼 관리 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ColumnService(board_type, DB_PATH)
        
        if request.method == "PUT":
            data = request.json
            service.update(column_id, data)
            return jsonify({"success": True})
        
        elif request.method == "DELETE":
            service.delete(column_id)
            return jsonify({"success": True})
            
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board column API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/columns/order", methods=["PUT"])
def board_columns_order_api(board):
    """보드별 컬럼 순서 변경 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ColumnService(board_type, DB_PATH)
        items = request.json
        service.reorder(items)
        return jsonify({"success": True})
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board columns order API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/dropdown-codes", methods=["GET", "POST"])
def board_dropdown_codes_api(board):
    """보드별 드롭다운 코드 관리 API"""
    board_type = board.replace('-', '_')
    column_key = request.args.get('column_key')
    
    if not column_key:
        return jsonify({"error": "column_key is required"}), 400
    
    try:
        service = CodeService(board_type, DB_PATH)
        
        if request.method == "GET":
            codes = service.list(column_key)
            return jsonify(codes)
        
        elif request.method == "POST":
            codes = request.json
            service.save(column_key, codes)
            return jsonify({"success": True})
            
    except Exception as e:
        logging.error(f"Board dropdown codes API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/dropdown-codes/<int:code_id>", methods=["DELETE"])
def board_dropdown_code_api(board, code_id):
    """보드별 개별 드롭다운 코드 삭제 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = CodeService(board_type, DB_PATH)
        service.delete(code_id)
        return jsonify({"success": True})
        
    except Exception as e:
        logging.error(f"Board dropdown code API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/dropdown-codes/history", methods=["GET"])
def board_dropdown_history(board):
    """보드별 드롭다운 코드 변경 이력 (컬럼 기준)"""
    board_type = board.replace('-', '_')
    column_key = request.args.get('column_key')
    if not column_key:
        return jsonify({"error": "column_key is required"}), 400
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        # board_type 컬럼 존재 여부 확인
        cur.execute("PRAGMA table_info(dropdown_code_audit)")
        cols = [r[1] for r in cur.fetchall()]
        if 'board_type' in cols:
            history = conn.execute(
                """
                SELECT * FROM dropdown_code_audit
                WHERE board_type = ? AND column_key = ?
                ORDER BY changed_at DESC, id DESC
                """,
                (board_type, column_key),
            ).fetchall()
        else:
            history = conn.execute(
                """
                SELECT * FROM dropdown_code_audit
                WHERE column_key = ?
                ORDER BY changed_at DESC, id DESC
                """,
                (column_key,),
            ).fetchall()
        conn.close()
        return jsonify({"history": [dict(h) for h in history]})
    except Exception as e:
        logging.error(f"Board dropdown history error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/dropdown-codes/audit-summary", methods=["GET"])
def board_dropdown_audit_summary(board):
    """보드별 드롭다운 감사 요약"""
    board_type = board.replace('-', '_')
    try:
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(dropdown_code_audit)")
        cols = [r[1] for r in cur.fetchall()]
        if 'board_type' in cols:
            recent = conn.execute(
                """
                SELECT DATE(changed_at) as date,
                       COUNT(*) as total_changes,
                       COUNT(DISTINCT column_key) as columns_changed
                FROM dropdown_code_audit
                WHERE board_type = ? AND changed_at >= datetime('now','-7 days')
                GROUP BY DATE(changed_at)
                ORDER BY date DESC
                """,
                (board_type,),
            ).fetchall()
            most = conn.execute(
                """
                SELECT column_key, COUNT(*) as change_count, MAX(changed_at) as last_changed
                FROM dropdown_code_audit
                WHERE board_type = ?
                GROUP BY column_key
                ORDER BY change_count DESC
                LIMIT 5
                """,
                (board_type,),
            ).fetchall()
        else:
            # board_type 미도입 환경: 전역 기준 요약
            recent = conn.execute(
                """
                SELECT DATE(changed_at) as date,
                       COUNT(*) as total_changes,
                       COUNT(DISTINCT column_key) as columns_changed
                FROM dropdown_code_audit
                WHERE changed_at >= datetime('now','-7 days')
                GROUP BY DATE(changed_at)
                ORDER BY date DESC
                """,
            ).fetchall()
            most = conn.execute(
                """
                SELECT column_key, COUNT(*) as change_count, MAX(changed_at) as last_changed
                FROM dropdown_code_audit
                GROUP BY column_key
                ORDER BY change_count DESC
                LIMIT 5
                """,
            ).fetchall()
        conn.close()
        return jsonify({
            "recent_changes": [dict(r) for r in recent],
            "most_changed_columns": [dict(m) for m in most],
        })
    except Exception as e:
        logging.error(f"Board audit summary error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/items", methods=["GET"])
def board_items_api(board):
    """보드별 아이템 목록 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ItemService(board_type, DB_PATH)
        
        filters = {
            'company_name': request.args.get('company_name'),
            'business_number': request.args.get('business_number'),
            'date_start': request.args.get('date_start'),
            'date_end': request.args.get('date_end'),
        }
        
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        result = service.list(filters, page, per_page)
        return jsonify(result)
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board items API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/items/<int:item_id>", methods=["GET"])
def board_item_detail_api(board, item_id):
    """보드별 아이템 상세 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ItemService(board_type, DB_PATH)
        item = service.detail(item_id)
        
        if item:
            return jsonify(item)
        else:
            return jsonify({"error": "Item not found"}), 404
            
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board item detail API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/items/register", methods=["POST"])
def board_item_register_api(board):
    """보드별 아이템 등록 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ItemService(board_type, DB_PATH)
        data = request.json
        result = service.register(data)
        return jsonify({"success": True, **result})
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board item register API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/items/update/<int:item_id>", methods=["POST"])
def board_item_update_api(board, item_id):
    """보드별 아이템 수정 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ItemService(board_type, DB_PATH)
        data = request.json
        service.update(item_id, data)
        return jsonify({"success": True})
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board item update API error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/<board>/items/delete", methods=["POST"])
def board_items_delete_api(board):
    """보드별 아이템 삭제 API"""
    board_type = board.replace('-', '_')
    
    try:
        service = ItemService(board_type, DB_PATH)
        item_ids = request.json.get('ids', [])
        hard_delete = request.json.get('hard_delete', False)
        service.delete(item_ids, hard_delete)
        return jsonify({"success": True})
        
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except Exception as e:
        logging.error(f"Board items delete API error: {e}")
        return jsonify({"error": str(e)}), 500


# ============= Follow SOP & Full Process 페이지 라우트 =============
"""
리팩토링 이후 CWD가 달라질 때 exec로 라우트를 읽지 못해
엔드포인트가 등록되지 않는 문제가 발생할 수 있음.
add_page_routes.py는 app 모듈의 globals()를 필요로 하므로
import 대신 안전한 절대 경로 exec로 로드한다.
"""
try:
    routes_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'add_page_routes.py')
    with open(routes_path, encoding='utf-8') as f:
        code = compile(f.read(), routes_path, 'exec')
        exec(code, globals())
    print("추가 라우트 로드 완료: follow-sop, full-process 등", flush=True)
except Exception as e:
    # 콘솔과 로거 모두에 남겨 원인 파악을 돕는다
    msg = f"추가 라우트 로드 실패: {e}"
    print(msg, flush=True)
    import traceback
    traceback.print_exc()
    try:
        import logging as _logging
        _logging.error(msg)
    except Exception:
        pass

# ============= CMS Catch-all Route (모든 라우트 후에 배치) =============
@app.route("/<path:url>")
def page_view(url):
    """일반 페이지 체크 (catch-all 라우트) - 모든 다른 라우트 후에 실행"""
    # 실제 라우트로 리다이렉트
    route_map = {
        'accident': 'accident_route',
        # 구경로 호환: partner-accident는 accident로 리다이렉트
        'partner-accident': 'accident_route',
        'safety-instruction': 'safety_instruction_route',
        'follow-sop': 'follow_sop_route',
        'full-process': 'full_process_route',
        'partner-standards': 'partner_standards_route',
        # 구 라우트 호환: /change-request -> /partner-change-request
        'change-request': 'partner_change_request_route',
    }
    
    if url in route_map:
        endpoint = route_map[url]
        if endpoint != 'page_view':
            # 엔드포인트가 미등록이면 BuildError를 유발하지 않도록 가드
            if endpoint in app.view_functions:
                return redirect(url_for(endpoint))
            else:
                try:
                    import logging as _logging
                    _logging.error(f"[page_view] 미등록 엔드포인트: {endpoint} (url={url})")
                except Exception:
                    pass
                # 미등록이면 CMS 페이지 탐색으로 폴백 (아래 로직 수행)
    
    conn = get_db_connection()
    # Ensure pages table exists even if init hook didn't run yet
    try:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT
            )
        ''')
    except Exception as _e:
        try:
            import logging as _logging
            _logging.debug(f"pages ensure failed: {_e}")
        except Exception:
            pass
    page = conn.execute("SELECT * FROM pages WHERE url = ?", (url,)).fetchone()
    conn.close()
    
    if not page:
        return "Page not found", 404
    
    return render_template("page.html", 
                         page={'url': page[1], 'title': page[2], 'content': page[3]},
                         menu=MENU_CONFIG)


if __name__ == "__main__":
    print("Flask 앱 시작 중...", flush=True)
    
    # 데이터베이스 초기화 및 동기화 (서버 시작 시 한 번만 실행)
    print("데이터베이스 초기화 중...", flush=True)
    init_db()
    
    # 일일 동기화 체크 (24시간 경과 시만 동기화)
    from database_config import maybe_daily_sync
    if db_config.external_db_enabled:
        try:
            print("일일 동기화 체크 중...", flush=True)
            maybe_daily_sync()
        except Exception as e:
            print(f"일일 동기화 체크 중 오류: {e}", flush=True)
    
    # JSON 컬럼 설정 동기화 (조건부 - GPT 제안대로 단순화)
    if db_config.config.getboolean('COLUMNS', 'SYNC_ON_STARTUP', fallback=False):
        try:
            print("JSON 컬럼 설정 동기화 시작... (config: SYNC_ON_STARTUP=true)", flush=True)
            sync_service = ColumnSyncService(DB_PATH, 'columns')
            sync_results = sync_service.sync_all_boards()
            
            for board, count in sync_results.items():
                if count >= 0:
                    print(f"  - {board}: {count}개 컬럼 동기화 완료", flush=True)
                else:
                    print(f"  - {board}: 동기화 실패", flush=True)
                    
            print("JSON 컬럼 설정 동기화 완료!", flush=True)
        except Exception as e:
            print(f"컬럼 동기화 중 오류 발생: {e}", flush=True)
            # 동기화 실패해도 앱은 실행되도록 함
    else:
        print("JSON 동기화 건너뜀 (config: SYNC_ON_STARTUP=false)", flush=True)
        print("DB의 컬럼 설정을 그대로 사용합니다.", flush=True)
    
    # 스케줄러는 실제 메인 프로세스에서만 시작(리로더 중복 방지)
    if os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        # 스케줄 등록: 매일 07:00에 maybe_daily_sync() 호출
        schedule.clear()  # 혹시 있을지 모르는 기존 잡 제거
        schedule.every().day.at("07:00").do(maybe_daily_sync)
        
        scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
        scheduler_thread.start()
        
        logging.info("=" * 50)
        logging.info("자동 동기화 스케줄러 시작")
        logging.info("매일 오전 7시에 자동으로 데이터를 동기화합니다.")
        logging.info("=" * 50)
    
    print(f"partner-accident 라우트 등록됨: {'/partner-accident' in [rule.rule for rule in app.url_map.iter_rules()]}", flush=True)
    app.run(host="0.0.0.0", port=5000, debug=app.debug)
@app.route('/upload-inline-image', methods=['POST'])
def upload_inline_image():
    try:
        file = request.files.get('upload') or request.files.get('file')
        if not file or not file.filename:
            return jsonify({ 'error': { 'message': 'No file uploaded' } }), 400

        # 확장자/크기 검증
        allowed = {'png','jpg','jpeg','gif','webp','bmp'}
        ext = os.path.splitext(file.filename)[1].lower().lstrip('.')
        if ext not in allowed:
            return jsonify({ 'error': { 'message': 'Unsupported file type' } }), 400
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)
        if size > 10 * 1024 * 1024:  # 10MB
            return jsonify({ 'error': { 'message': 'File too large' } }), 400

        # 저장 경로
        upload_dir = os.path.join('uploads', 'content')
        os.makedirs(upload_dir, exist_ok=True)

        # 안전한 파일명
        import time
        basename = secure_filename(file.filename)
        fname = f"{int(time.time())}_{basename}"
        path = os.path.join(upload_dir, fname)
        file.save(path)

        url = f"/uploads/content/{fname}"
        return jsonify({ 'url': url })
    except Exception as e:
        logging.error(f"Inline image upload failed: {e}")
        return jsonify({ 'error': { 'message': 'Upload failed' } }), 500


@app.route('/uploads/content/<path:filename>')
def serve_uploaded_content(filename):
    directory = os.path.join('uploads', 'content')
    return send_from_directory(directory, filename)
