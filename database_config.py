import configparser
import os
import sqlite3
import logging
import sys
import traceback
import pandas as pd
from datetime import datetime, timedelta, date
from decimal import Decimal
import numpy as np
import json
import re
from db_connection import get_db_connection, get_postgres_dsn
from db.upsert import safe_upsert

# 설정 파일 로드
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(__file__), 'config.ini')

# config.ini 파일에서 module_folder 경로 가져오기
config.read(config_path, encoding='utf-8')
module_folder = config.get('DATABASE', 'IQADB_MODULE_PATH')

# IQADB_CONNECT310 모듈 로드
try:
    sys.path.insert(0, os.path.abspath(module_folder))
    from IQADB_CONNECT310 import *
    IQADB_AVAILABLE = True
    print(f"[SUCCESS] IQADB_CONNECT310 모듈 로드 성공: {module_folder}")
except ImportError as e:
    IQADB_AVAILABLE = False
    print(f"[WARNING] IQADB_CONNECT310 모듈을 가져올 수 없습니다: {e}")
except Exception as e:
    IQADB_AVAILABLE = False
    print(f"[ERROR] IQADB 모듈 로드 중 오류 발생: {e}")

def _normalize_df(df):
    """DataFrame 컬럼명 정규화 - 소문자화 & 공백 제거"""
    df.columns = [str(c).strip().lower() for c in df.columns]
    return df

def _to_sqlite_safe(v):
    """SQLite에 안전하게 저장하기 위한 타입 변환"""
    if pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime, date)):
        return str(v)[:19]  # 'YYYY-MM-DD HH:MM:SS'
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (np.integer, )):
        return int(v)
    if isinstance(v, (np.floating, )):
        return float(v)
    return v

def execute_SQL(query):
    """
    기존 성공 방식: IQADB_CONNECT310을 사용한 데이터베이스 조회
    """
    if not IQADB_AVAILABLE:
        raise Exception("IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
    
    conn = iqadb1()
    try:
        with conn.cursor() as cur:
            cur.execute(query)
            data = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]
            df = pd.DataFrame(data, columns=col_names)
            return df
    except Exception as e:
        print(f"[ERROR] execute_SQL 실행 중 오류: {e}")
        traceback.print_exc()
        raise e
    finally:
        conn.close()

# config는 이미 위에서 로드되었음 - 중복 제거
# 설정 파일 로드 성공 메시지는 이미 위에서 출력됨

class PartnerDataManager:
    def __init__(self):
        self.config = config
        self.local_db_path = config.get('DATABASE', 'LOCAL_DB_PATH', fallback='portal.db')
        self.db_config = None  # 나중에 설정됨
        self.init_local_tables()
    
    def init_local_tables(self):
        """로컬 SQLite 테이블 초기화"""
        conn = get_db_connection(self.local_db_path)
        cursor = conn.cursor()
        
        # 기존 partners_cache 테이블의 구조 확인
        # PostgreSQL: information_schema를 통해 컬럼 정보 조회
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'partners_cache'
        """)
        existing_columns = {col[0]: col[1] for col in cursor.fetchall()}
        
        # 필요한 컬럼 정의
        required_columns = {
            'business_number': 'TEXT PRIMARY KEY',
            'company_name': 'TEXT NOT NULL',
            'partner_class': 'TEXT',
            'business_type_major': 'TEXT',
            'business_type_minor': 'TEXT',
            'hazard_work_flag': 'TEXT',
            'representative': 'TEXT',
            'address': 'TEXT',
            'average_age': 'INTEGER',
            'annual_revenue': 'BIGINT',
            'transaction_count': 'TEXT',
            'permanent_workers': 'INTEGER',
            'synced_at': 'DATETIME DEFAULT CURRENT_TIMESTAMP',
            'is_deleted': 'INTEGER DEFAULT 0'
        }
        
        # 테이블이 없으면 생성, 있으면 부족한 컬럼만 추가
        if not existing_columns:
            print("[INFO] partners_cache 테이블이 없어 새로 생성합니다.")
            cursor.execute('''
                CREATE TABLE partners_cache (
                    business_number TEXT PRIMARY KEY,
                    company_name TEXT NOT NULL,
                    partner_class TEXT,
                    business_type_major TEXT,
                    business_type_minor TEXT,
                    hazard_work_flag TEXT,
                    representative TEXT,
                    address TEXT,
                    average_age INTEGER,
                    annual_revenue BIGINT,
                    transaction_count TEXT,
                    permanent_workers INTEGER,
                    synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0
                )
            ''')
            print("[SUCCESS] partners_cache 테이블 생성 완료")
        else:
            # 부족한 컬럼만 ALTER로 추가
            for col, ctype in required_columns.items():
                if col not in existing_columns:
                    # PRIMARY KEY나 NOT NULL은 ALTER로 추가할 수 없으므로 기본값 처리
                    if 'PRIMARY KEY' in ctype or 'NOT NULL' in ctype:
                        ctype = ctype.replace('PRIMARY KEY', '').replace('NOT NULL', '').strip()
                    print(f"[INFO] partners_cache 테이블에 {col} 컬럼 추가")
                    cursor.execute(f"ALTER TABLE partners_cache ADD COLUMN {col} {ctype}")
            print("[INFO] partners_cache 테이블 구조 확인 완료")
        
        # 협력사 상세내용 테이블 (로컬 전용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partner_details (
                business_number TEXT PRIMARY KEY,
                detailed_content TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        ''')
        
        # 첨부파일 테이블 (로컬 전용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partner_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_number TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                uploaded_by TEXT
            )
        ''')
        
        # 사고 상세내용 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accident_details (
                accident_number TEXT PRIMARY KEY,
                detailed_content TEXT DEFAULT '',
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_by TEXT
            )
        ''')
        
        # 사고 첨부파일 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accident_attachments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accident_number TEXT NOT NULL,
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                description TEXT,
                uploaded_by TEXT
            )
        ''')
        
        # Phase 1: 사고 컬럼 설정 테이블 (동적 컬럼 관리용)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accident_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key VARCHAR(50) UNIQUE NOT NULL,
                column_name VARCHAR(100) NOT NULL,
                column_type VARCHAR(20) DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                dropdown_options TEXT,
                tab TEXT,
                column_span INTEGER DEFAULT 1,
                linked_columns TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 임직원 캐시 테이블 (기존 person_master 대체)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees_cache (
                employee_id TEXT PRIMARY KEY,
                employee_name TEXT,
                department_name TEXT
            )
        ''')
        
        # 부서 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS departments_cache (
                dept_code TEXT PRIMARY KEY,
                dept_name TEXT,
                parent_dept_code TEXT
            )
        ''')
        
        # 건물 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS buildings_cache (
                building_code TEXT PRIMARY KEY,
                building_name TEXT,
                SITE TEXT,
                SITE_TYPE TEXT
            )
        ''')
        
        # 협력사 근로자 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS contractors_cache (
                worker_id TEXT PRIMARY KEY,
                worker_name TEXT,
                company_name TEXT,
                business_number TEXT
            )
        ''')
        
        # 협력사 사고 정보 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accidents_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                accident_number TEXT,
                accident_name TEXT,
                workplace TEXT,
                accident_grade TEXT,
                major_category TEXT,
                injury_form TEXT,
                injury_type TEXT,
                accident_date TEXT,
                day_of_week TEXT,
                created_at TEXT,
                report_date TEXT,
                building TEXT,
                floor TEXT,
                location_category TEXT,
                location_detail TEXT,
                custom_data TEXT DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # 누락 컬럼 보강 (report_date)
        try:
            # PostgreSQL: information_schema를 통해 컬럼 정보 조회
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'accidents_cache'
            """)
            cols_ac = [c[0] for c in cursor.fetchall()]
            if 'report_date' not in cols_ac:
                cursor.execute("ALTER TABLE accidents_cache ADD COLUMN report_date TEXT")
        except Exception:
            pass

        # 인덱스 보강 (중복 방지 및 조회 성능)
        try:
            cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_accidents_cache_number ON accidents_cache(accident_number)")
        except Exception:
            pass
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_accidents_cache_created_at ON accidents_cache(created_at)")
        except Exception:
            pass
        try:
            # report_date가 없을 수도 있으므로 실패해도 무시
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_accidents_cache_report_date ON accidents_cache(report_date)")
        except Exception:
            pass
        
        # 안전지시서 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_instructions_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                issue_number TEXT UNIQUE,
                created_at DATETIME,
                custom_data TEXT DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # permanent_workers 컬럼은 위에서 이미 처리됨 (중복 제거)
        
        # 마스터 테이블은 더 이상 사용하지 않음 (캐시 테이블만 사용)
        # building_master, department_master 테이블 및 더미 데이터 제거
        
        conn.commit()
        conn.close()
    
    def sync_partners_from_external_db(self):
        """외부 DB에서 협력사 마스터 데이터 동기화"""
        if not IQADB_AVAILABLE:
            logging.error("IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 PARTNERS_QUERY 가져오기
            query = self.config.get('MASTER_DATA_QUERIES', 'PARTNERS_QUERY')
            print(f"[INFO] 실행할 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 데이터 조회 시작...")
            df = execute_SQL(query)
            # 외부 DB 컬럼명이 대문자/혼합/한글일 수 있어 표준화 필요
            df = _normalize_df(df)
            df = df.replace({'None': None, 'null': None, 'NULL': None})
            print(f"[INFO] 데이터 조회 완료: {len(df)} 건")
            try:
                print(f"[DEBUG] Partners DataFrame columns: {list(df.columns)}")
            except Exception:
                pass
            
            if df.empty:
                print("[WARNING] 조회된 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # PRAGMA settings removed for PostgreSQL compatibility
            # cursor.execute("PRAGMA journal_mode=WAL")
            # cursor.execute("PRAGMA busy_timeout=5000")
            # cursor.execute("PRAGMA synchronous=NORMAL")
            
            # 트랜잭션 시작
            cursor.execute("BEGIN")
            
            # 기존 is_deleted 보존을 위해 백업 (custom_data는 없음)
            cursor.execute("""
                CREATE TEMP TABLE partners_backup AS 
                SELECT business_number, is_deleted 
                FROM partners_cache
            """)
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM partners_cache")
            
            # 배치 삽입을 위한 데이터 준비
            rows = []
            _skipped_missing_bn = 0
            for _, row in df.iterrows():
                # 필수 키 누락(빈 문자열 포함) 행은 스킵하여 UNIQUE 충돌과 파이프라인 중단을 방지
                business_number = str(row.get('business_number') or '').strip()
                if not business_number:
                    _skipped_missing_bn += 1
                    continue

                # 숫자/금액/카운트 안전 변환
                def _to_int_safe(v):
                    try:
                        if v is None or (hasattr(pd, 'isna') and pd.isna(v)):
                            return None
                        if isinstance(v, (int, np.integer)):
                            return int(v)
                        if isinstance(v, (float, np.floating)):
                            return int(v)
                        s = str(v).strip()
                        if s == '':
                            return None
                        s = re.sub(r"[^0-9-]", "", s)
                        if s in ('', '-'):
                            return None
                        return int(s)
                    except Exception:
                        return None

                def _to_float_safe(v):
                    try:
                        if v is None or (hasattr(pd, 'isna') and pd.isna(v)):
                            return None
                        if isinstance(v, (int, np.integer, float, np.floating)):
                            return float(v)
                        s = str(v).strip()
                        if s == '':
                            return None
                        s = s.replace(',', '')
                        s = re.sub(r"[^0-9+\-\.eE]", "", s)
                        return float(s)
                    except Exception:
                        return None

                avg_age = _to_float_safe(row.get('average_age', None))
                revenue = _to_float_safe(row.get('annual_revenue', None))
                trx_cnt = _to_int_safe(row.get('transaction_count', None))
                perm_workers = _to_int_safe(row.get('permanent_workers', None))
                hazard_flag = row.get('hazard_work_flag', row.get('hazard_work_fla', ''))

                rows.append((
                    business_number,
                    row.get('company_name', ''),
                    row.get('partner_class', ''),
                    row.get('business_type_major', ''),
                    row.get('business_type_minor', ''),
                    hazard_flag,
                    row.get('representative', ''),
                    row.get('address', ''),
                    avg_age,
                    revenue,
                    trx_cnt,
                    perm_workers
                ))
            
            # 배치 삽입 (중복 키는 업서트)
            try:
                cursor.executemany('''
                    INSERT INTO partners_cache (
                        business_number, company_name, partner_class, business_type_major,
                        business_type_minor, hazard_work_flag, representative, address,
                        average_age, annual_revenue, transaction_count, permanent_workers,
                        is_deleted
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                    ON CONFLICT (business_number)
                    DO UPDATE SET
                        company_name = EXCLUDED.company_name,
                        partner_class = EXCLUDED.partner_class,
                        business_type_major = EXCLUDED.business_type_major,
                        business_type_minor = EXCLUDED.business_type_minor,
                        hazard_work_flag = EXCLUDED.hazard_work_flag,
                        representative = EXCLUDED.representative,
                        address = EXCLUDED.address,
                        average_age = EXCLUDED.average_age,
                        annual_revenue = EXCLUDED.annual_revenue,
                        transaction_count = EXCLUDED.transaction_count,
                        permanent_workers = EXCLUDED.permanent_workers,
                        updated_at = CURRENT_TIMESTAMP
                ''', rows)
            except Exception as _bulk_err:
                # Fallback: per-row insert with savepoints to skip bad rows
                print(f"[WARN] bulk insert failed: {_bulk_err}. Fallback to per-row inserts.")
                ok, bad = 0, 0
                for vals in rows:
                    try:
                        cursor.execute("SAVEPOINT sp_row")
                        cursor.execute('''
                            INSERT INTO partners_cache (
                                business_number, company_name, partner_class, business_type_major,
                                business_type_minor, hazard_work_flag, representative, address,
                                average_age, annual_revenue, transaction_count, permanent_workers,
                                is_deleted
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                            ON CONFLICT (business_number)
                            DO UPDATE SET
                                company_name = EXCLUDED.company_name,
                                partner_class = EXCLUDED.partner_class,
                                business_type_major = EXCLUDED.business_type_major,
                                business_type_minor = EXCLUDED.business_type_minor,
                                hazard_work_flag = EXCLUDED.hazard_work_flag,
                                representative = EXCLUDED.representative,
                                address = EXCLUDED.address,
                                average_age = EXCLUDED.average_age,
                                annual_revenue = EXCLUDED.annual_revenue,
                                transaction_count = EXCLUDED.transaction_count,
                                permanent_workers = EXCLUDED.permanent_workers,
                                updated_at = CURRENT_TIMESTAMP
                        ''', vals)
                        cursor.execute("RELEASE SAVEPOINT sp_row")
                        ok += 1
                    except Exception as _row_err:
                        try:
                            cursor.execute("ROLLBACK TO SAVEPOINT sp_row")
                        except Exception:
                            pass
                        bad += 1
                print(f"[INFO] per-row insert: ok={ok}, skipped={bad}")
            
            # 기존 is_deleted 복원
            cursor.execute("""
                UPDATE partners_cache 
                SET is_deleted = COALESCE(
                    (SELECT is_deleted FROM partners_backup 
                     WHERE partners_backup.business_number = partners_cache.business_number),
                    0
                )
            """)
            
            # 임시 테이블 삭제
            cursor.execute("DROP TABLE partners_backup")
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 협력사 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_accidents_from_external_db(self):
        """외부 DB에서 사고 데이터 동기화 (안전 업서트, 기존값 보존)

        - 전량 삭제 금지, UPSERT 기반
        - created_at/custom_data/is_deleted 보존 (UPDATE 시 미갱신)
        - 단일 백엔드(get_db_connection) 사용으로 운영/개발 일관성 보장
        """
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False

        try:
            query = self.config.get('MASTER_DATA_QUERIES', 'ACCIDENTS_QUERY')
            print(f"[INFO] 실행할 사고 쿼리: {query[:100]}...")

            print("[INFO] IQADB_CONNECT310을 사용하여 사고 데이터 조회 시작...")
            df = execute_SQL(query)
            df = _normalize_df(df)
            print(f"[INFO] 사고 데이터 조회 완료: {len(df)} 건")

            if df.empty:
                print("[WARNING] 조회된 사고 데이터가 없습니다.")
                return False

            conn = get_db_connection(timeout=30.0)
            cursor = conn.cursor()
            try:
                cursor.execute("BEGIN")
            except Exception:
                pass

            from db.upsert import safe_upsert
            from timezone_config import get_korean_time

            processed = 0
            for _, row in df.iterrows():
                acc_no = str(row.get('accident_number') or '').strip()
                if not acc_no:
                    continue

                def g(k, alt=''):
                    return _to_sqlite_safe(row.get(k, alt))

                created_val = row.get('created_at')
                if not created_val:
                    created_val = get_korean_time().strftime('%Y-%m-%d %H:%M:%S')

                data = {
                    'accident_number': acc_no,
                    'accident_name': g('accident_name'),
                    'workplace': g('workplace'),
                    'accident_grade': g('accident_grade'),
                    'major_category': g('major_category'),
                    'injury_form': g('injury_form') or g('unjury_form'),
                    'injury_type': g('injury_type'),
                    'accident_date': g('accident_date'),
                    'day_of_week': g('day_of_week'),
                    'report_date': g('report_date'),
                    'building': g('building'),
                    'floor': g('floor'),
                    'location_category': g('location_category'),
                    'location_detail': g('location_detail'),
                    'custom_data': '{}',
                    'is_deleted': 0,
                    'created_at': created_val
                }

                update_cols = [
                    'accident_name','workplace','accident_grade','major_category',
                    'injury_form','injury_type','accident_date','day_of_week','report_date',
                    'building','floor','location_category','location_detail'
                ]

                safe_upsert(conn, 'accidents_cache', data, conflict_cols=['accident_number'], update_cols=update_cols)
                processed += 1

            try:
                conn.commit()
            except Exception:
                pass
            conn.close()

            print(f"[SUCCESS] ✅ 사고 데이터 {processed}건 업서트 완료 (기존값 보존)")
            return True

        except Exception as e:
            print(f"[ERROR] ❌ 사고 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_employees_from_external_db(self):
        """외부 DB에서 임직원 데이터 동기화"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 EMPLOYEE_EXTERNAL_QUERY 가져오기 (외부 DB용)
            query = self.config.get('MASTER_DATA_QUERIES', 'EMPLOYEE_QUERY')
            print(f"[INFO] 실행할 임직원 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 임직원 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 임직원 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 임직원 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path)
            cursor = conn.cursor()
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM employees_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO employees_cache (
                        employee_id, employee_name, department_name
                    ) VALUES (%s, %s, %s)
                ''', (
                    row.get('employee_id', ''),
                    row.get('employee_name', ''),
                    row.get('department_name', '')
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 임직원 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 임직원 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_departments_from_external_db(self):
        """외부 DB에서 부서 데이터 동기화"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 DEPARTMENT_EXTERNAL_QUERY 가져오기 (외부 DB용)
            query = self.config.get('MASTER_DATA_QUERIES', 'DEPARTMENT_QUERY')
            print(f"[INFO] 실행할 부서 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 부서 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 부서 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 부서 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path)
            cursor = conn.cursor()
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM departments_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO departments_cache (
                        dept_code, dept_name, parent_dept_code
                    ) VALUES (%s, %s, %s)
                ''', (
                    row.get('dept_code', ''),
                    row.get('dept_name', ''),
                    row.get('parent_dept_code', ''),
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 부서 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 부서 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_buildings_from_external_db(self):
        """외부 DB에서 건물 데이터 동기화"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 BUILDING_EXTERNAL_QUERY 가져오기 (외부 DB용)
            query = self.config.get('MASTER_DATA_QUERIES', 'BUILDING_QUERY')
            print(f"[INFO] 실행할 건물 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 건물 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 건물 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 건물 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path)
            cursor = conn.cursor()
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM buildings_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO buildings_cache (
                        building_code, building_name, SITE, SITE_TYPE
                    ) VALUES (%s, %s, %s, %s)
                ''', (
                    row.get('building_code', ''),
                    row.get('building_name', ''),
                    row.get('site', row.get('SITE', '')),  # 대소문자 모두 처리
                    row.get('site_type', row.get('SITE_TYPE', ''))  # 대소문자 모두 처리
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 건물 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 건물 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_contractors_from_external_db(self):
        """외부 DB에서 협력사 근로자 데이터 동기화"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 CONTRACTOR_EXTERNAL_QUERY 가져오기 (외부 DB용)
            query = self.config.get('MASTER_DATA_QUERIES', 'CONTRACTOR_QUERY')
            print(f"[INFO] 실행할 협력사 근로자 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 협력사 근로자 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 협력사 근로자 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 협력사 근로자 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path)
            cursor = conn.cursor()
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM contractors_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO contractors_cache (
                        worker_id, worker_name, company_name, business_number
                    ) VALUES (%s, %s, %s, %s)
                ''', (
                    row.get('worker_id', ''),
                    row.get('worker_name', ''),
                    row.get('company_name', ''),
                    row.get('business_number', '')
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 협력사 근로자 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 협력사 근로자 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_safety_instructions_from_external_db(self):
        """외부 DB에서 안전지시서 데이터 동기화"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 외부 DB용 쿼리 가져오기
            query = self.config.get('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY') \
                if self.config.has_option('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY') \
                else self.config.get('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
            print(f"[INFO] 실행할 안전지시서 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 안전지시서 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 안전지시서 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 안전지시서 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            
            # 트랜잭션 시작 (캐시 없이 직접 처리)
            cursor.execute("BEGIN")

            # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
            rows = []
            for _, row in df.iterrows():
                # 모든 데이터를 custom_data에 JSON으로 저장
                row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                # 날짜 타입들을 안전하게 문자열로 변환 (GPT 지침에 따른 정확한 numpy 감지)
                for k, v in row_dict.items():
                    if isinstance(v, (pd.Timestamp, datetime, date)) or str(type(v)).endswith(("numpy.datetime64'>", "numpy.timedelta64'>")):
                        row_dict[k] = str(v)
                    elif pd.isna(v):
                        row_dict[k] = None

                # 원본 데이터 그대로 저장 (수동 업데이트로 변경)
                custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)
                
                # issue_number 추출
                issue_number = (row.get('issue_number') or row.get('발부번호') or '').strip()
                if not issue_number:
                    # UNIQUE 키가 비어 있으면 스킵
                    continue

                # 외부 created_at 추출 (Full Process처럼)
                created_at_str = (row.get('created_at', '') or
                                row.get('CREATED_AT', '') or
                                row.get('발부일', '') or
                                row.get('작성일', '') or
                                row.get('issue_date', '') or
                                row.get('ISSUE_DATE', '') or
                                row.get('등록일', '') or
                                row.get('REG_DATE', '') or
                                row.get('reg_date', ''))

                # 날짜 파싱
                created_dt = None
                if created_at_str:
                    # 다양한 날짜 형식 파싱 시도
                    for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%b-%y', '%d/%m/%Y']:
                        try:
                            created_dt = datetime.strptime(str(created_at_str).split('.')[0], fmt)
                            break
                        except:
                            continue
                if not created_dt:
                    created_dt = datetime.now()

                # created_dt를 문자열로 변환
                created_at_iso = created_dt.strftime('%Y-%m-%d %H:%M:%S') if created_dt else None

                rows.append((
                    issue_number,
                    custom_data,
                    created_at_iso,
                    0  # is_deleted = 0
                ))
            
            # 캐시 없이 직접 메인 테이블에 삽입 (PostgreSQL만 사용)
            for issue_number, custom_data, created_at_iso, is_deleted in rows:
                cursor.execute('''
                    INSERT INTO safety_instructions (issue_number, custom_data, created_at, is_deleted)
                    VALUES (%s, %s, %s::timestamp, %s)
                    ON CONFLICT (issue_number)
                    DO UPDATE SET
                        custom_data = EXCLUDED.custom_data,
                        created_at = EXCLUDED.created_at,
                        is_deleted = EXCLUDED.is_deleted,
                        updated_at = CURRENT_TIMESTAMP
                ''', (issue_number, custom_data, created_at_iso, is_deleted))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 안전지시서 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 안전지시서 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_followsop_from_external_db(self):
        """외부 DB에서 FollowSOP 데이터 동기화 (동적 컬럼 방식)"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 외부 DB용 쿼리 가져오기
            if self.config.has_option('CONTENT_DATA_QUERIES', 'FOLLOWSOP_QUERY'):
                query = self.config.get('CONTENT_DATA_QUERIES', 'FOLLOWSOP_QUERY')
            elif self.config.has_option('MASTER_DATA_QUERIES', 'FOLLOWSOP_QUERY'):
                query = self.config.get('MASTER_DATA_QUERIES', 'FOLLOWSOP_QUERY')
            else:
                print("[WARNING] FOLLOWSOP_QUERY가 config.ini에 정의되지 않았습니다.")
                return False
                
            print(f"[INFO] 실행할 FollowSOP 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 FollowSOP 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] FollowSOP 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 FollowSOP 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            
            # 트랜잭션 시작 (캐시 없이 직접 처리)
            cursor.execute("BEGIN")
            
            # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
            print(f"[DEBUG] FollowSOP DataFrame 컬럼: {list(df.columns)}")
            rows = []
            date_counters = {}  # Track counters for each date within this batch
            for idx, row in df.iterrows():
                # 모든 데이터를 custom_data에 JSON으로 저장
                row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                # 날짜 타입들을 안전하게 문자열로 변환 (GPT 지침에 따른 정확한 numpy 감지)
                for k, v in row_dict.items():
                    if isinstance(v, (pd.Timestamp, datetime, date)) or str(type(v)).endswith(("numpy.datetime64'>", "numpy.timedelta64'>")):
                        row_dict[k] = str(v)
                    elif pd.isna(v):
                        row_dict[k] = None
                custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)
                
                # created_at 또는 작업일자 추출하여 FS 형식 번호 생성
                # 외부 DB의 다양한 날짜 필드 확인
                created_at_str = (row.get('created_at', '') or
                                row.get('CREATED_AT', '') or
                                row.get('작업일자', '') or
                                row.get('work_date', '') or
                                row.get('WORK_DATE', '') or
                                row.get('등록일', '') or
                                row.get('REG_DATE', '') or
                                row.get('reg_date', ''))

                # 날짜 파싱 시도
                created_dt = None
                try:
                    if created_at_str:
                        # 다양한 날짜 형식 파싱 시도
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%b-%y', '%d/%m/%Y']:
                            try:
                                created_dt = datetime.strptime(str(created_at_str).split('.')[0], fmt)
                                break
                            except:
                                continue
                        else:
                            # 파싱 실패시 현재 시간 사용
                            print(f"[WARNING] 날짜 파싱 실패: {created_at_str}, 현재 시간 사용")
                            created_dt = datetime.now()
                    else:
                        # 날짜 필드가 없으면 현재 시간 사용
                        print(f"[WARNING] 날짜 필드 없음, 현재 시간 사용")
                        created_dt = datetime.now()

                    # FS 형식 번호 생성 - PostgreSQL에서 직접 조회
                    date_str = created_dt.strftime('%y%m%d')

                    # Check if we already have a counter for this date in current batch
                    if date_str in date_counters:
                        # Use the next counter from our batch tracking
                        new_counter = date_counters[date_str] + 1
                    else:
                        # First time seeing this date in batch, query DB for last number
                        pattern = f'FS{date_str}%'
                        cursor.execute('''
                            SELECT work_req_no FROM follow_sop
                            WHERE work_req_no LIKE %s
                            ORDER BY work_req_no DESC
                            LIMIT 1
                        ''', (pattern,))

                        last_result = cursor.fetchone()
                        if last_result and len(last_result[0]) == 12:  # FS(2) + YYMMDD(6) + NNNN(4) = 12
                            try:
                                last_counter = int(last_result[0][8:12])  # Extract exactly 4 digits
                                new_counter = last_counter + 1
                            except ValueError:
                                new_counter = 1  # Start from 1 if parsing fails
                        else:
                            new_counter = 1  # Start from 1 for new date

                    # Update counter for this date
                    date_counters[date_str] = new_counter
                    work_req_no = f'FS{date_str}{new_counter:04d}'
                except Exception as e:
                    # 번호 생성 실패시 원본 사용 또는 새 형식으로 생성
                    work_req_no = (row.get('work_req_no', '') or
                                  row.get('작업요청번호', '') or
                                  row.get('work_request_number', ''))
                    if not work_req_no:
                        # 새 형식으로 fallback: FSYYMMDDNNNN
                        # idx가 크면 모듈로 연산으로 제한
                        created_dt = datetime.now()
                        date_str = created_dt.strftime('%y%m%d')
                        safe_counter = (idx % 9999) + 1  # 1-9999 범위로 제한
                        work_req_no = f'FS{date_str}{safe_counter:04d}'
                    else:
                        created_dt = datetime.now()

                if idx == 0:  # 첫 번째 행만 디버깅
                    print(f"[DEBUG] work_req_no: {work_req_no}")
                    print(f"[DEBUG] custom_data 길이: {len(custom_data)}")
                    print(f"[DEBUG] created_dt: {created_dt}")

                # created_dt를 문자열로 변환하여 저장
                created_at_iso = created_dt.strftime('%Y-%m-%d %H:%M:%S') if created_dt else None
                rows.append((work_req_no, custom_data, created_at_iso))
            
            # 캐시 없이 직접 메인 테이블에 삽입 (PostgreSQL만 사용)
            for work_req_no, custom_data, created_at_iso in rows:
                cursor.execute('''
                    INSERT INTO follow_sop (work_req_no, custom_data, created_at, is_deleted)
                    VALUES (%s, %s, %s::timestamp, 0)
                    ON CONFLICT (work_req_no) DO NOTHING
                ''', (work_req_no, custom_data, created_at_iso))
            
            # 동기화된 데이터 활성화 (삭제 상태 해제)
            for work_req_no, _, _ in rows:
                cursor.execute('''
                    UPDATE follow_sop SET is_deleted = 0
                    WHERE work_req_no = %s
                ''', (work_req_no,))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ FollowSOP 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ FollowSOP 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_fullprocess_from_external_db(self):
        """외부 DB에서 FullProcess 데이터 동기화 (동적 컬럼 방식)"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 외부 DB용 쿼리 가져오기
            if self.config.has_option('CONTENT_DATA_QUERIES', 'FULLPROCESS_QUERY'):
                query = self.config.get('CONTENT_DATA_QUERIES', 'FULLPROCESS_QUERY')
            elif self.config.has_option('MASTER_DATA_QUERIES', 'FULLPROCESS_QUERY'):
                query = self.config.get('MASTER_DATA_QUERIES', 'FULLPROCESS_QUERY')
            else:
                print("[WARNING] FULLPROCESS_QUERY가 config.ini에 정의되지 않았습니다.")
                return False
                
            print(f"[INFO] 실행할 FullProcess 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 FullProcess 데이터 조회 시작...")
            df = execute_SQL(query)
            df = _normalize_df(df)
            df = df.replace({'None': None, 'null': None, 'NULL': None})
            print(f"[INFO] FullProcess 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 FullProcess 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            
            # 트랜잭션 시작 (캐시 없이 직접 처리)
            cursor.execute("BEGIN")
            
            # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
            print(f"[DEBUG] FullProcess DataFrame 컬럼: {list(df.columns)}")
            rows = []
            date_counters = {}  # Track counters for each date within this batch
            for idx, row in df.iterrows():
                # 모든 데이터를 custom_data에 JSON으로 저장
                row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                # 날짜 타입들을 안전하게 문자열로 변환 (GPT 지침에 따른 정확한 numpy 감지)
                for k, v in row_dict.items():
                    if isinstance(v, (pd.Timestamp, datetime, date)) or str(type(v)).endswith(("numpy.datetime64'>", "numpy.timedelta64'>")):
                        row_dict[k] = str(v)
                    elif pd.isna(v):
                        row_dict[k] = None

                # 원본 데이터 그대로 저장 (수동 업데이트로 변경)
                custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)
                
                # created_at 또는 평가일자 추출하여 FP 형식 번호 생성
                # 외부 DB의 다양한 날짜 필드 확인
                created_at_str = (row.get('created_at', '') or
                                row.get('CREATED_AT', '') or
                                row.get('평가일자', '') or
                                row.get('process_date', '') or
                                row.get('PROCESS_DATE', '') or
                                row.get('등록일', '') or
                                row.get('REG_DATE', '') or
                                row.get('reg_date', ''))

                # 날짜 파싱 시도
                try:
                    if created_at_str:
                        # 다양한 날짜 형식 파싱 시도
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%b-%y', '%d/%m/%Y']:
                            try:
                                created_dt = datetime.strptime(str(created_at_str).split('.')[0], fmt)
                                break
                            except:
                                continue
                        else:
                            # 파싱 실패시 현재 시간 사용
                            print(f"[WARNING] 날짜 파싱 실패: {created_at_str}, 현재 시간 사용")
                            created_dt = datetime.now()
                    else:
                        # 날짜 필드가 없으면 현재 시간 사용
                        print(f"[WARNING] 날짜 필드 없음, 현재 시간 사용")
                        created_dt = datetime.now()

                    # FP 형식 번호 생성 - PostgreSQL에서 직접 조회
                    date_str = created_dt.strftime('%y%m%d')

                    # Check if we already have a counter for this date in current batch
                    if date_str in date_counters:
                        # Use the next counter from our batch tracking
                        new_counter = date_counters[date_str] + 1
                    else:
                        # First time seeing this date in batch, query DB for last number
                        pattern = f'FP{date_str}%'
                        cursor.execute('''
                            SELECT fullprocess_number FROM full_process
                            WHERE fullprocess_number LIKE %s
                            ORDER BY fullprocess_number DESC
                            LIMIT 1
                        ''', (pattern,))

                        last_result = cursor.fetchone()
                        if last_result and len(last_result[0]) == 13:  # FP(2) + YYMMDD(6) + NNNNN(5) = 13
                            try:
                                last_counter = int(last_result[0][8:13])  # Extract exactly 5 digits
                                new_counter = last_counter + 1
                            except ValueError:
                                new_counter = 1  # Start from 1 if parsing fails
                        else:
                            new_counter = 1  # Start from 1 for new date

                    # Update counter for this date
                    date_counters[date_str] = new_counter
                    fullprocess_number = f'FP{date_str}{new_counter:05d}'
                except Exception as e:
                    # 번호 생성 실패시 원본 사용 또는 새 형식으로 생성
                    fullprocess_number = (row.get('fullprocess_number', '') or
                                         row.get('프로세스번호', '') or
                                         row.get('process_number', ''))
                    if not fullprocess_number:
                        # 새 형식으로 fallback: FPYYMMDDNNNNN
                        # idx가 크면 모듈로 연산으로 제한
                        created_dt = datetime.now()
                        date_str = created_dt.strftime('%y%m%d')
                        safe_counter = (idx % 99999) + 1  # 1-99999 범위로 제한
                        fullprocess_number = f'FP{date_str}{safe_counter:05d}'
                
                if idx == 0:  # 첫 번째 행만 디버깅
                    print(f"[DEBUG] fullprocess_number: {fullprocess_number}")
                    print(f"[DEBUG] custom_data 길이: {len(custom_data)}")
                
                # created_dt를 문자열로 변환하여 저장
                created_at_iso = created_dt.strftime('%Y-%m-%d %H:%M:%S') if created_dt else None
                rows.append((fullprocess_number, custom_data, created_at_iso))
            
            # 캐시 없이 직접 메인 테이블에 삽입 (PostgreSQL만 사용)
            for idx, (fullprocess_number, custom_data, created_at_iso) in enumerate(rows):
                # 중복 체크: 이미 존재하는 번호면 새로 생성
                cursor.execute('''
                    SELECT 1 FROM full_process WHERE fullprocess_number = %s
                ''', (fullprocess_number,))

                if cursor.fetchone():
                    # 중복이면 새 번호 생성 (날짜 + 인덱스 기반)
                    from id_generator import generate_fullprocess_number
                    if created_at_iso:
                        created_dt = datetime.strptime(created_at_iso, '%Y-%m-%d %H:%M:%S')
                    else:
                        created_dt = datetime.now()

                    # PostgreSQL에서 마지막 번호 조회
                    date_str = created_dt.strftime('%y%m%d')
                    pattern = f'FP{date_str}%'
                    cursor.execute('''
                        SELECT fullprocess_number FROM full_process
                        WHERE fullprocess_number LIKE %s
                        ORDER BY fullprocess_number DESC
                        LIMIT 1
                    ''', (pattern,))

                    last_result = cursor.fetchone()
                    if last_result and len(last_result[0]) >= 13:  # FPYYMMDDNNNNN 최소 13자리
                        try:
                            last_counter = int(last_result[0][8:13])  # FP(2) + YYMMDD(6) 이후 5자리만
                            new_counter = last_counter + 1
                        except ValueError:
                            new_counter = 1
                    else:
                        new_counter = 1

                    fullprocess_number = f'FP{date_str}{new_counter:05d}'

                # INSERT (중복 체크 완료)
                cursor.execute('''
                    INSERT INTO full_process (fullprocess_number, custom_data, created_at, is_deleted)
                    VALUES (%s, %s, %s::timestamp, 0)
                ''', (fullprocess_number, custom_data, created_at_iso))
            
            # 동기화된 데이터 활성화 (삭제 상태 해제)
            for fullprocess_number, _, _ in rows:
                cursor.execute('''
                    UPDATE full_process SET is_deleted = 0
                    WHERE fullprocess_number = %s
                ''', (fullprocess_number,))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ FullProcess 데이터 {len(df)}건 동기화 완료")
            return True

        except Exception as e:
            print(f"[ERROR] ❌ FullProcess 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False

    def sync_partner_change_requests_from_external_db(self):
        """외부 DB에서 Partner Change Requests 데이터 동기화 (동적 컬럼 방식)"""
        print("\n" + "="*80)
        print("[DEBUG] Partner Change Requests 동기화 시작")
        print("="*80)

        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False

        try:
            # config.ini에서 외부 DB용 쿼리 가져오기
            print("[DEBUG-1] config.ini에서 쿼리 찾기...")
            if self.config.has_option('CONTENT_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY'):
                query = self.config.get('CONTENT_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY')
                print("[DEBUG-1] CONTENT_DATA_QUERIES 섹션에서 쿼리 발견")
            elif self.config.has_option('MASTER_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY'):
                query = self.config.get('MASTER_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY')
                print("[DEBUG-1] MASTER_DATA_QUERIES 섹션에서 쿼리 발견")
            else:
                print("[WARNING] PARTNER_CHANGE_REQUESTS_QUERY가 config.ini에 정의되지 않았습니다.")
                return False

            print(f"[DEBUG-2] 실행할 쿼리: {query}")

            # 외부 DB에서 데이터 조회
            print("[DEBUG-3] 외부 DB 연결 시도...")
            try:
                df = execute_SQL(query)
                print(f"[DEBUG-3] 외부 DB 조회 성공: {len(df)} 건")
            except Exception as db_error:
                print(f"[ERROR] 외부 DB 조회 실패: {db_error}")
                print(f"[ERROR] 쿼리 구문: {query}")
                traceback.print_exc()
                return False

            if df.empty:
                print("[WARNING] 조회된 Partner Change Requests 데이터가 없습니다.")
                return False

            # DataFrame 컬럼 상세 분석
            print(f"[DEBUG-4] DataFrame 컬럼 목록: {list(df.columns)}")
            print(f"[DEBUG-4] DataFrame 샘플 (첫 2행):")
            for idx, row in df.head(2).iterrows():
                print(f"  Row {idx}:")
                for col in df.columns:
                    val = row[col]
                    print(f"    {col}: {val} (type: {type(val).__name__})")

            # PostgreSQL 연결
            print("[DEBUG-5] PostgreSQL 연결 시도...")
            conn = None
            cursor = None
            try:
                conn = get_db_connection()
                cursor = conn.cursor()
                print("[DEBUG-5] PostgreSQL 연결 성공")
            except Exception as pg_error:
                print(f"[ERROR] PostgreSQL 연결 실패: {pg_error}")
                traceback.print_exc()
                return False

            try:
                # partner_change_requests 본 테이블이 이미 있으면 스킵
                print("[DEBUG-6] 테이블 존재 확인...")
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'partner_change_requests'
                    )
                """)
                table_exists = cursor.fetchone()[0]
                print(f"[DEBUG-6] 테이블 존재 여부: {table_exists}")

                if table_exists:
                    # 테이블이 이미 있으면 NOT NULL 제약 조건 제거
                    print("[DEBUG-6.5] 기존 테이블의 NOT NULL 제약 조건 제거 중...")
                    try:
                        # 모든 텍스트 컬럼의 NOT NULL 제거 (NULL 허용)
                        alter_statements = [
                            "ALTER TABLE partner_change_requests ALTER COLUMN requester_name DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN requester_department DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN company_name DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN business_number DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN change_type DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN current_value DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN new_value DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN change_reason DROP NOT NULL",
                            "ALTER TABLE partner_change_requests ALTER COLUMN other_info DROP NOT NULL"
                        ]
                        for stmt in alter_statements:
                            try:
                                cursor.execute(stmt)
                                print(f"  ✓ {stmt.split('COLUMN')[1].split('DROP')[0].strip()} NULL 허용")
                            except Exception as alter_err:
                                # 이미 NULL 허용인 경우 무시
                                pass
                        conn.commit()
                        print("[DEBUG-6.5] NOT NULL 제약 조건 제거 완료")
                    except Exception as alter_error:
                        print(f"[WARNING] ALTER 실행 중 오류 (무시): {alter_error}")
                        conn.rollback()

                if not table_exists:
                    print("[DEBUG-7] 테이블 생성 시작...")
                    try:
                        cursor.execute('''
                            CREATE TABLE partner_change_requests (
                                id SERIAL PRIMARY KEY,
                                request_number TEXT UNIQUE,
                                requester_name TEXT,
                                requester_department TEXT,
                                company_name TEXT,
                                business_number TEXT,
                                change_type TEXT,
                                current_value TEXT,
                                new_value TEXT,
                                change_reason TEXT,
                                status TEXT DEFAULT 'pending',
                                custom_data JSONB DEFAULT '{}',
                                other_info TEXT,
                                final_check_date DATE,
                                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                is_deleted INTEGER DEFAULT 0
                            )
                        ''')
                        conn.commit()
                        print("[DEBUG-7] 테이블 생성 성공")
                    except Exception as create_error:
                        print(f"[ERROR] 테이블 생성 실패: {create_error}")
                        traceback.print_exc()
                        conn.rollback()
                        return False

                # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
                print(f"[DEBUG-8] 데이터 준비 시작...")
                print(f"[DEBUG-8] 총 처리할 행 수: {len(df)}")

                # DataFrame을 created_at 기준으로 오름차순 정렬 (오래된 것부터)
                # 먼저 created_at 컬럼 찾기
                date_col = None
                for col in ['created_at', 'CREATED_AT', '등록일', 'REG_DATE', 'reg_date']:
                    if col in df.columns:
                        date_col = col
                        break

                if date_col:
                    df_sorted = df.sort_values(by=date_col, ascending=True).reset_index(drop=True)
                    print(f"[DEBUG-8] DataFrame을 {date_col} 기준으로 오름차순 정렬")
                else:
                    df_sorted = df
                    print("[DEBUG-8] 날짜 컬럼을 찾을 수 없어 원본 순서 유지")

                rows = []
                for idx, row in df_sorted.iterrows():
                    if idx == 0:
                        print(f"\n[DEBUG-9] 첫 번째 행 상세 분석:")
                    # 모든 데이터를 custom_data에 JSON으로 저장
                    row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                    # 날짜 타입들을 안전하게 문자열로 변환
                    for k, v in row_dict.items():
                        if isinstance(v, (pd.Timestamp, datetime, date)) or str(type(v)).endswith(("numpy.datetime64'>", "numpy.timedelta64'>")):
                            row_dict[k] = str(v)
                        elif pd.isna(v):
                            row_dict[k] = None
                    # detailed_content 분리 (full_process 방식)
                    detailed_content = row_dict.pop('detailed_content', '') if 'detailed_content' in row_dict else ''

                    # custom_data는 detailed_content 제외한 나머지만 저장
                    custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)

                    # 외부 created_at 추출 (Full Process처럼)
                    created_at_str = (row.get('created_at', '') or
                                    row.get('CREATED_AT', '') or
                                    row.get('등록일', '') or
                                    row.get('REG_DATE', '') or
                                    row.get('reg_date', ''))

                    # 날짜 파싱
                    created_dt = None
                    if created_at_str:
                        # 다양한 날짜 형식 파싱 시도
                        for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d', '%d-%b-%y', '%d/%m/%Y']:
                            try:
                                created_dt = datetime.strptime(str(created_at_str).split('.')[0], fmt)
                                break
                            except:
                                continue
                    if not created_dt:
                        created_dt = datetime.now()

                    # request_number 생성: CRYYMMNNN 형식 (외부 created_at 기준!)
                    yymm = created_dt.strftime('%y%m')  # 외부 날짜 기준!

                    # 원본에 request_number가 있으면 그대로 사용
                    if row.get('request_number'):
                        request_number = row.get('request_number')
                    else:
                        # 해당 월의 마지막 번호 찾기 (현재 row까지만 고려)
                        month_count = 0
                        for prev_idx in range(idx):
                            prev_row = df_sorted.iloc[prev_idx]
                            prev_created = prev_row.get('created_at', '') or prev_row.get('CREATED_AT', '') or prev_row.get('등록일', '')
                            if prev_created:
                                try:
                                    prev_dt = datetime.strptime(str(prev_created).split('.')[0], '%Y-%m-%d %H:%M:%S')
                                    if prev_dt.strftime('%y%m') == yymm:
                                        month_count += 1
                                except:
                                    pass

                        # DB에서도 확인 (이미 존재하는 번호)
                        cursor.execute("""
                            SELECT request_number
                            FROM partner_change_requests
                            WHERE request_number LIKE %s
                            ORDER BY request_number DESC
                            LIMIT 1
                        """, (f"CR{yymm}%",))
                        last_num = cursor.fetchone()

                        db_last_seq = 0
                        if last_num:
                            try:
                                db_last_seq = int(last_num[0][6:9])  # CR2412001 -> 001
                            except:
                                pass

                        # 더 큰 값 사용 (DB 또는 현재 카운트)
                        next_seq = max(db_last_seq, month_count) + 1
                        request_number = f"CR{yymm}{next_seq:03d}"
                    requester_name = row.get('requester_name', '')
                    requester_department = row.get('requester_department', '')
                    company_name = row.get('company_name', '')
                    business_number = row.get('business_number', '')
                    change_type = row.get('change_type', '')
                    current_value = row.get('current_value', '')
                    new_value = row.get('new_value', '')
                    change_reason = row.get('change_reason', '')
                    status = row.get('status', 'pending')
                    other_info = row.get('other_info', '')
                    final_check_date = row.get('final_check_date', None)
                    if idx == 0:
                        print(f"[DEBUG-10] final_check_date 원본: {final_check_date} (type: {type(final_check_date).__name__})")

                    if final_check_date and pd.notna(final_check_date):
                        try:
                            # 문자열을 date 객체로 변환
                            final_check_date = pd.to_datetime(final_check_date).date()
                            if idx == 0:
                                print(f"[DEBUG-10] final_check_date 변환 성공: {final_check_date} (type: {type(final_check_date).__name__})")
                        except Exception as date_error:
                            if idx == 0:
                                print(f"[DEBUG-10] final_check_date 변환 실패: {date_error}")
                            final_check_date = None

                    # created_dt를 문자열로 변환 (디버깅 전에 먼저 정의!)
                    created_at_iso = created_dt.strftime('%Y-%m-%d %H:%M:%S') if created_dt else None

                    if idx == 0:  # 첫 번째 행만 디버깅
                        print(f"[DEBUG-11] 생성된 데이터:")
                        print(f"  request_number: {request_number}")
                        print(f"  requester_name: {requester_name}")
                        print(f"  requester_department: {requester_department}")
                        print(f"  company_name: {company_name}")
                        print(f"  business_number: {business_number}")
                        print(f"  change_type: {change_type}")
                        print(f"  current_value: {current_value[:50] if current_value else 'None'}...")
                        print(f"  new_value: {new_value[:50] if new_value else 'None'}...")
                        print(f"  change_reason: {change_reason[:50] if change_reason else 'None'}...")
                        print(f"  status: {status}")
                        print(f"  other_info: {other_info[:50] if other_info else 'None'}...")
                        print(f"  final_check_date: {final_check_date}")
                        print(f"  custom_data 길이: {len(custom_data)}")
                        print(f"  created_at_iso: {created_at_iso}")

                    rows.append((
                        request_number, requester_name, requester_department,
                        company_name, business_number, change_type,
                        current_value, new_value, change_reason,
                        status, other_info, final_check_date, custom_data,
                        created_at_iso  # created_at 추가!
                    ))

                # 각 row를 개별적으로 삽입하여 에러 확인
                print(f"\n[DEBUG-12] 데이터 삽입 시작...")
                print(f"[DEBUG-12] 총 {len(rows)}개 레코드 삽입 예정")
                success_count = 0
                error_count = 0

                # 트랜잭션 상태 확인
                try:
                    cursor.execute("SELECT 1")
                    cursor.fetchone()
                    print("[DEBUG-13] 트랜잭션 상태: 정상")
                except Exception as tx_check:
                    print(f"[ERROR] 트랜잭션 상태 이상: {tx_check}")
                    conn.rollback()
                    conn = get_db_connection()
                    cursor = conn.cursor()
                    print("[DEBUG-13] 트랜잭션 재시작")

                for row_idx, row_data in enumerate(rows):
                    if row_idx == 0:
                        print(f"\n[DEBUG-14] 첫 번째 INSERT 시도:")
                        print(f"  row_data 개수: {len(row_data)}")
                        print(f"  request_number: {row_data[0]}")
                        print(f"  final_check_date: {row_data[11]} (type: {type(row_data[11]).__name__})")
                        print(f"  created_at: {row_data[13]} (type: {type(row_data[13]).__name__})")

                    try:
                        cursor.execute('''
                                INSERT INTO partner_change_requests
                                (request_number, requester_name, requester_department,
                                 company_name, business_number, change_type,
                                 current_value, new_value, change_reason,
                                 status, other_info, final_check_date, custom_data, created_at, is_deleted)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::timestamp, 0)
                            ON CONFLICT(request_number) DO UPDATE SET
                                requester_name = EXCLUDED.requester_name,
                                requester_department = EXCLUDED.requester_department,
                                company_name = EXCLUDED.company_name,
                                business_number = EXCLUDED.business_number,
                                change_type = EXCLUDED.change_type,
                                current_value = EXCLUDED.current_value,
                                new_value = EXCLUDED.new_value,
                                change_reason = EXCLUDED.change_reason,
                                status = EXCLUDED.status,
                                other_info = EXCLUDED.other_info,
                                final_check_date = EXCLUDED.final_check_date,
                                custom_data = EXCLUDED.custom_data,
                                created_at = EXCLUDED.created_at,
                                is_deleted = 0,
                                updated_at = CURRENT_TIMESTAMP
                        ''', row_data)
                        success_count += 1
                        if row_idx == 0:
                            print(f"[DEBUG-14] 첫 번째 INSERT 성공!")
                    except Exception as row_error:
                        error_count += 1
                        print(f"\n[ERROR-INSERT] Row {row_idx} 삽입 실패")
                        print(f"  request_number: {row_data[0]}")
                        print(f"  에러 타입: {type(row_error).__name__}")
                        print(f"  에러 메시지: {str(row_error)}")

                        if error_count <= 3:  # 처음 3개 에러만 상세 출력
                            print(f"  전체 데이터 타입 확인:")
                            for i, val in enumerate(row_data):
                                field_names = ['request_number', 'requester_name', 'requester_department',
                                             'company_name', 'business_number', 'change_type',
                                             'current_value', 'new_value', 'change_reason',
                                             'status', 'other_info', 'final_check_date',
                                             'custom_data', 'created_at']
                                if i < len(field_names):
                                    print(f"    {field_names[i]}: {type(val).__name__} = {str(val)[:50] if val else 'None'}")

                        # 트랜잭션 상태 재확인
                        try:
                            cursor.execute("SELECT 1")
                            print(f"  트랜잭션 상태: 여전히 정상")
                        except:
                            print(f"  트랜잭션 상태: ABORTED - 재시작 필요")
                            conn.rollback()
                            conn = get_db_connection()
                            cursor = conn.cursor()

                print(f"\n[DEBUG-15] 삽입 완료")
                print(f"  성공: {success_count}개")
                print(f"  실패: {error_count}개")

                # detailed_content를 partner_change_request_details 테이블에 저장 (full_process 방식)
                if success_count > 0:
                    print("[INFO] partner_change_request_details 테이블 업데이트 시작...")
                    detail_count = 0
                    for idx, row in df.iterrows():
                        # detailed_content 추출
                        row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)
                        detailed_content = row_dict.get('detailed_content', '')

                        if detailed_content:
                            # request_number 재생성 (외부 created_at 기준으로)
                            # 외부 created_at 추출 (위와 동일)
                            created_at_str = (row.get('created_at', '') or
                                            row.get('CREATED_AT', '') or
                                            row.get('등록일', '') or
                                            row.get('REG_DATE', '') or
                                            row.get('reg_date', ''))

                            created_dt = None
                            if created_at_str:
                                for fmt in ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d', '%Y/%m/%d', '%Y%m%d']:
                                    try:
                                        created_dt = datetime.strptime(str(created_at_str).split('.')[0], fmt)
                                        break
                                    except:
                                        continue
                            if not created_dt:
                                created_dt = datetime.now()

                            yymm = created_dt.strftime('%y%m')  # 외부 날짜 기준!
                            request_number = row.get('request_number', f"CR{yymm}{idx+1:03d}")

                            try:
                                cursor.execute('''
                                    INSERT INTO partner_change_request_details
                                    (request_number, detailed_content, created_at, updated_at)
                                    VALUES (%s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                                    ON CONFLICT(request_number) DO UPDATE SET
                                        detailed_content = EXCLUDED.detailed_content,
                                        updated_at = CURRENT_TIMESTAMP
                                ''', (request_number, detailed_content))
                                detail_count += 1
                            except Exception as detail_error:
                                print(f"[WARNING] Details 저장 실패 - {request_number}: {detail_error}")

                    print(f"[INFO] partner_change_request_details: {detail_count}개 저장")

                if success_count > 0:
                    print(f"\n[DEBUG-16] 커밋 시도 (성공 {success_count}개)...")
                    try:
                        conn.commit()
                        print("[DEBUG-16] 커밋 성공!")
                    except Exception as commit_error:
                        print(f"[ERROR] 커밋 실패: {commit_error}")
                        traceback.print_exc()
                        conn.rollback()
                        return False
                else:
                    print("[DEBUG-16] 모든 삽입 실패로 롤백")
                    conn.rollback()

                conn.close()
                print("="*80)
                print(f"[FINAL] Partner Change Requests 동기화 결과:")
                print(f"  - 전체: {len(df)}건")
                print(f"  - 성공: {success_count}건")
                print(f"  - 실패: {error_count}건")
                print("="*80)
                return success_count > 0

            except Exception as e:
                print(f"\n[ERROR-MAIN] 데이터 준비 중 예외 발생")
                print(f"  에러 타입: {type(e).__name__}")
                print(f"  에러 메시지: {e}")
                traceback.print_exc()
                if conn:
                    conn.rollback()
                    conn.close()
                return False

        except Exception as e:
            print(f"\n[ERROR-OUTER] 전체 함수 레벨 예외 발생")
            print(f"  에러 타입: {type(e).__name__}")
            print(f"  에러 메시지: {e}")
            traceback.print_exc()
            return False

    def get_partner_by_business_number(self, business_number):
        """사업자번호로 협력사 정보 조회 (캐시 + 상세정보 조인)"""
        conn = get_db_connection(self.local_db_path)
        conn.row_factory = sqlite3.Row
        
        query = '''
            SELECT 
                pc.*,
                pd.detailed_content AS detailed_content,
                pd.updated_at as detail_updated_at
            FROM partners_cache pc
            LEFT JOIN partner_details pd ON pc.business_number = pd.business_number
            WHERE pc.business_number = %s
        '''
        
        partner = conn.execute(query, (business_number,)).fetchone()
        conn.close()
        return partner
    
    def get_all_partners(self, page=1, per_page=10, filters=None):
        """협력사 목록 조회 (필터링 포함)"""
        conn = get_db_connection(self.local_db_path)
        conn.row_factory = sqlite3.Row
        
        # 기본 쿼리 (삭제되지 않은 데이터만)
        query = "SELECT * FROM partners_cache WHERE (is_deleted = 0 OR is_deleted IS NULL)"
        params = []
        
        # 필터 적용
        if filters:
            if filters.get('company_name'):
                query += " AND company_name LIKE %s"
                params.append(f"%{filters['company_name']}%")
            
            if filters.get('business_number'):
                query += " AND business_number LIKE %s"
                params.append(f"%{filters['business_number']}%")
            
            if filters.get('business_type_major'):
                query += " AND business_type_major = %s"
                params.append(filters['business_type_major'])
            
            if filters.get('business_type_minor'):
                query += " AND business_type_minor LIKE %s"
                params.append(f"%{filters['business_type_minor']}%")
            
            # 상시근로자 수 범위 필터
            if filters.get('workers_min'):
                query += " AND permanent_workers >= %s"
                params.append(filters['workers_min'])
            
            if filters.get('workers_max'):
                query += " AND permanent_workers <= %s"
                params.append(filters['workers_max'])
        
        # 전체 개수 조회
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total_count = conn.execute(count_query, params).fetchone()[0]
        
        # 페이징 적용 - 상시근로자 수 큰 순으로 정렬 (SQLite 호환)
        query += " ORDER BY (permanent_workers IS NULL), permanent_workers DESC, company_name LIMIT %s OFFSET %s"
        params.extend([per_page, (page - 1) * per_page])
        
        partners = conn.execute(query, params).fetchall()
        conn.close()
        
        return partners, total_count

class DatabaseConfig:
    """데이터베이스 설정 관리 클래스"""
    def __init__(self):
        self.config = config
        self.local_db_path = config.get('DATABASE', 'LOCAL_DB_PATH', fallback='portal.db')
        self.external_db_enabled = config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED', fallback=False)

    def get_connection(self, timeout: float = 10.0, *, row_factory: bool = False):
        """PostgreSQL 기본 연결을 반환한다 (레거시 호환)."""
        return get_db_connection(timeout=timeout, row_factory=row_factory)

    def get_sqlite_connection(self, timeout=10.0, row_factory: bool = False):
        """레거시 호환용 메서드: 이제 PostgreSQL 연결을 반환한다."""
        return self.get_connection(timeout=timeout, row_factory=row_factory)

    def get_postgres_dsn(self) -> str:
        """현재 설정된 PostgreSQL DSN을 반환한다."""
        return get_postgres_dsn()

# 전역 인스턴스
db_config = DatabaseConfig()
partner_manager = PartnerDataManager()

def maybe_daily_sync(force=False):
    """하루에 한 번만 동기화하는 유틸리티 함수
    
    Args:
        force: True면 무조건 동기화 실행 (최초 실행 시 사용)
    """
    conn = get_db_connection(db_config.local_db_path)
    cur = conn.cursor()
    
    # 동기화 상태 테이블 생성
    cur.execute('''
        CREATE TABLE IF NOT EXISTS sync_state (
            id INTEGER PRIMARY KEY CHECK (id=1),
            last_full_sync DATETIME
        )
    ''')
    
    # 캐시 테이블이 비어있는지 확인 (최초 실행 감지)
    cur.execute("SELECT COUNT(*) FROM partners_cache")
    partners_count = cur.fetchone()[0]
    if partners_count == 0:
        print("[INFO] 캐시 테이블이 비어있음 - 최초 실행으로 감지, 강제 동기화")
        force = True
    
    # 마지막 동기화 시간 확인
    row = cur.execute("SELECT last_full_sync FROM sync_state WHERE id=1").fetchone()
    need_sync = True
    
    if row and row[0]:
        last = pd.to_datetime(row[0])
        need_sync = (pd.Timestamp.now() - last) > pd.Timedelta(days=1)
        print(f"[INFO] 마지막 동기화: {row[0]}, 동기화 필요: {need_sync}")
    else:
        print("[INFO] 첫 동기화 수행 필요")
    
    if force or need_sync:
        print("[INFO] 일일 동기화 시작...")
        success = False
        
        # 협력사 데이터 동기화
        try:
            if partner_manager.sync_partners_from_external_db():
                success = True
                print("[SUCCESS] 협력사 데이터 동기화 완료")
        except Exception as e:
            print(f"[ERROR] 협력사 동기화 실패: {e}")
        
        # 사고 데이터 동기화
        try:
            if partner_manager.sync_accidents_from_external_db():
                success = True
                print("[SUCCESS] 사고 데이터 동기화 완료")
        except Exception as e:
            print(f"[ERROR] 사고 동기화 실패: {e}")
        
        # 다른 마스터 데이터 동기화 (외부 쿼리 존재 여부로 체크)
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'EMPLOYEE_QUERY'):
                partner_manager.sync_employees_from_external_db()
        except Exception as e:
            print(f"[ERROR] 임직원 동기화 실패: {e}")
            
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'DEPARTMENT_QUERY'):
                partner_manager.sync_departments_from_external_db()
        except Exception as e:
            print(f"[ERROR] 부서 동기화 실패: {e}")
            
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'BUILDING_QUERY'):
                partner_manager.sync_buildings_from_external_db()
        except Exception as e:
            print(f"[ERROR] 건물 동기화 실패: {e}")
            
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'CONTRACTOR_QUERY'):
                partner_manager.sync_contractors_from_external_db()
        except Exception as e:
            print(f"[ERROR] 협력사 근로자 동기화 실패: {e}")
            
        # 환경안전지시서는 최초 1회만 동기화 (이미 데이터가 있으면 절대 동기화 안 함)
        try:
            if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
                # 동기화 이력 테이블 확인/생성
                cur.execute('''
                    CREATE TABLE IF NOT EXISTS safety_instructions_sync_history (
                        id INTEGER PRIMARY KEY CHECK (id=1),
                        first_sync_done INTEGER DEFAULT 0,
                        sync_date DATETIME,
                        record_count INTEGER
                    )
                ''')
                
                # 동기화 이력 확인
                cur.execute("SELECT first_sync_done FROM safety_instructions_sync_history WHERE id=1")
                sync_history = cur.fetchone()
                
                if not sync_history or sync_history[0] == 0:
                    # 최초 1회만 실행
                    print("[INFO] 환경안전지시서 최초 1회 동기화 실행")
                    partner_manager.sync_safety_instructions_from_external_db()
                    
                    # 동기화 완료 기록
                    cur.execute("SELECT COUNT(*) FROM safety_instructions_cache")
                    count = cur.fetchone()[0]
                    # safe_upsert 사용
                    sync_data = {
                        'id': 1,
                        'first_sync_done': 1,
                        'sync_date': None,  # 자동으로 처리됨
                        'record_count': count
                    }
                    safe_upsert(conn, 'safety_instructions_sync_history', sync_data)
                    conn.commit()
                    print(f"[SUCCESS] 환경안전지시서 최초 동기화 완료: {count}건")
                else:
                    cur.execute("SELECT COUNT(*) FROM safety_instructions_cache")
                    current_count = cur.fetchone()[0]
                    print(f"[INFO] 환경안전지시서 동기화 영구 스킵 (최초 동기화 완료됨, 현재 {current_count}건)")
        except Exception as e:
            print(f"[ERROR] 안전지시서 동기화 실패: {e}")
        
        # 동기화 성공 시 마지막 동기화 시간 업데이트 (safe_upsert 사용)
        if success:
            sync_data = {
                'id': 1,
                'last_full_sync': pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            safe_upsert(conn, 'sync_state', sync_data)
            conn.commit()
            print(f"[SUCCESS] 일일 동기화 완료: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("[INFO] 동기화 스킵 (24시간 미경과)")
    
    conn.close()

def _ensure_boot_sync_tables(conn):
    """
    부트 동기화 진행 여부를 기록할 테이블 보장.
    - master_sync_state: 마지막 마스터 동기화 시각
    - content_sync_state: 각 컨텐츠(안전지시서 등) 최초 동기화 여부
    """
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS master_sync_state(
          id INTEGER PRIMARY KEY CHECK(id=1),
          last_master_sync DATETIME
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS content_sync_state(
          name TEXT PRIMARY KEY,
          first_sync_done INTEGER DEFAULT 0,
          first_sync_at DATETIME
        )
    """)
    conn.commit()

def maybe_daily_sync_master(force=False):
    """
    마스터 데이터(협력사, 사고, 임직원, 부서, 건물, 협력사근로자): 매일 1회.
    - [MASTER_DATA_QUERIES]에 쿼리가 정의된 항목만 수행.
    """
    import pandas as pd
    conn = get_db_connection(db_config.local_db_path)
    _ensure_boot_sync_tables(conn)
    cur = conn.cursor()

    need = True
    if not force:
        row = cur.execute("SELECT last_master_sync FROM master_sync_state WHERE id=1").fetchone()
        if row and row[0]:
            last = pd.to_datetime(row[0])
            need = (pd.Timestamp.now() - last) > pd.Timedelta(days=1)

    if not need and not force:
        print("[INFO] Master daily sync skipped (< 24h)")
        conn.close()
        return

    print("[INFO] 마스터 데이터 동기화 시작...")
    
    # 먼저 모든 캐시 테이블 구조 확인/생성 (init_local_tables 호출)
    partner_manager.init_local_tables()
    
    # sync 파트(쿼리 존재 시에만)
    success = False
    
    # 협력사 데이터 동기화
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'PARTNERS_QUERY'):
            if partner_manager.sync_partners_from_external_db():
                success = True
                print("[SUCCESS] 협력사 데이터 동기화 완료")
        else:
            print("[INFO] PARTNERS_QUERY not found - skip")
    except Exception as e:
        print(f"[ERROR] 협력사 동기화 실패: {e}")

    # 사고 데이터 동기화
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'ACCIDENTS_QUERY'):
            if partner_manager.sync_accidents_from_external_db():
                success = True
                print("[SUCCESS] 사고 데이터 동기화 완료")
        else:
            print("[INFO] ACCIDENTS_QUERY not found - skip")
    except Exception as e:
        print(f"[ERROR] 사고 동기화 실패: {e}")

    # 다른 마스터 데이터 동기화 (외부 쿼리 존재 여부로 체크)
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'EMPLOYEE_QUERY'):
            partner_manager.sync_employees_from_external_db()
            print("[SUCCESS] 임직원 데이터 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 임직원 동기화 실패: {e}")
        
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'DEPARTMENT_QUERY'):
            partner_manager.sync_departments_from_external_db()
            print("[SUCCESS] 부서 데이터 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 부서 동기화 실패: {e}")
        
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'BUILDING_QUERY'):
            partner_manager.sync_buildings_from_external_db()
            print("[SUCCESS] 건물 데이터 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 건물 동기화 실패: {e}")
        
    try:
        if partner_manager.config.has_option('MASTER_DATA_QUERIES', 'CONTRACTOR_QUERY'):
            partner_manager.sync_contractors_from_external_db()
            print("[SUCCESS] 협력사 근로자 데이터 동기화 완료")
    except Exception as e:
        print(f"[ERROR] 협력사 근로자 동기화 실패: {e}")

    # 동기화 성공 시 마지막 동기화 시간 업데이트 (safe_upsert 사용)
    if success or force:
        sync_data = {
            'id': 1,
            'last_master_sync': None  # datetime('now') 또는 CURRENT_TIMESTAMP로 자동 처리됨
        }
        safe_upsert(conn, 'master_sync_state', sync_data)
        conn.commit()
        print(f"[SUCCESS] 마스터 데이터 동기화 완료: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}")
    else:
        print("[WARNING] 모든 동기화 실패")
    
    conn.close()

def maybe_one_time_sync_content(force=False):
    """
    컨텐츠 데이터(환경안전지시서 등): 최초 1회만. CONTENT_DATA_QUERIES 섹션 기준.
    - 안전지시서(safety_instructions_cache): 최초 1회만 채움
    - 필요 시 FOLLOWSOP/FULLPROCESS 등 확장(키 존재하면)
    """
    conn = get_db_connection(db_config.local_db_path)
    _ensure_boot_sync_tables(conn)
    cur = conn.cursor()

    def _do_once(name, runner):
        # 상태 조회
        row = cur.execute("SELECT first_sync_done FROM content_sync_state WHERE name=%s", (name,)).fetchone()
        done = (row and row[0] == 1)
        if done and not force:
            print(f"[INFO] Content '{name}' already synced (once).")
            return
        # 실행
        ok = runner()
        if ok or force:
            # safe_upsert 사용  
            sync_data = {
                'name': name,
                'first_sync_done': 1,
                'first_sync_at': None  # 자동으로 처리됨
            }
            safe_upsert(conn, 'content_sync_state', sync_data)
            conn.commit()

    # 안전지시서(쿼리 존재 시에만 수행)
    if partner_manager.config.has_section('CONTENT_DATA_QUERIES') and \
       partner_manager.config.has_option('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        def run_safety():
            try:
                return partner_manager.sync_safety_instructions_from_external_db()
            except Exception as e:
                print(f"[ERROR] SAFETY_INSTRUCTIONS sync: {e}")
                return False
        _do_once('safety_instructions', run_safety)

    # FollowSOP 동기화 (쿼리 존재 시에만 수행)
    if (partner_manager.config.has_option('CONTENT_DATA_QUERIES', 'FOLLOWSOP_QUERY') or 
        partner_manager.config.has_option('MASTER_DATA_QUERIES', 'FOLLOWSOP_QUERY')):
        def run_followsop():
            try:
                return partner_manager.sync_followsop_from_external_db()
            except Exception as e:
                print(f"[ERROR] FOLLOWSOP sync: {e}")
                return False
        _do_once('followsop', run_followsop)
    
    # FullProcess 동기화 (쿼리 존재 시에만 수행)
    if (partner_manager.config.has_option('CONTENT_DATA_QUERIES', 'FULLPROCESS_QUERY') or
        partner_manager.config.has_option('MASTER_DATA_QUERIES', 'FULLPROCESS_QUERY')):
        def run_fullprocess():
            try:
                return partner_manager.sync_fullprocess_from_external_db()
            except Exception as e:
                print(f"[ERROR] FULLPROCESS sync: {e}")
                return False
        _do_once('fullprocess', run_fullprocess)

    # Partner Change Requests 동기화 (쿼리 존재 시에만 수행)
    if (partner_manager.config.has_option('CONTENT_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY') or
        partner_manager.config.has_option('MASTER_DATA_QUERIES', 'PARTNER_CHANGE_REQUESTS_QUERY')):
        def run_partner_change_requests():
            try:
                return partner_manager.sync_partner_change_requests_from_external_db()
            except Exception as e:
                print(f"[ERROR] PARTNER_CHANGE_REQUESTS sync: {e}")
                return False
        _do_once('partner_change_requests', run_partner_change_requests)

    conn.close()
partner_manager.db_config = db_config  # 순환 참조 해결
