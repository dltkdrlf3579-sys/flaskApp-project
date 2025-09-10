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
from db_connection import get_db_connection
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
        cursor.execute("PRAGMA table_info(partners_cache)")
        existing_columns = {col[1]: col[2] for col in cursor.fetchall()}
        
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
                building TEXT,
                floor TEXT,
                location_category TEXT,
                location_detail TEXT,
                custom_data TEXT DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
            print(f"[INFO] 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # PRAGMA 설정 추가
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
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
            for _, row in df.iterrows():
                business_number = row.get('business_number', '')
                
                rows.append((
                    business_number,
                    row.get('company_name', ''),
                    row.get('partner_class', ''),
                    row.get('business_type_major', ''),
                    row.get('business_type_minor', ''),
                    row.get('hazard_work_flag', ''),
                    row.get('representative', ''),
                    row.get('address', ''),
                    row.get('average_age', None),
                    row.get('annual_revenue', None),
                    row.get('transaction_count', ''),
                    row.get('permanent_workers', None)
                ))
            
            # 배치 삽입 (custom_data 컬럼 제거)
            cursor.executemany('''
                INSERT INTO partners_cache (
                    business_number, company_name, partner_class, business_type_major,
                    business_type_minor, hazard_work_flag, representative, address,
                    average_age, annual_revenue, transaction_count, permanent_workers,
                    is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            ''', rows)
            
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
        """외부 DB에서 사고 데이터 동기화 (custom_data 보존)"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 ACCIDENTS_QUERY 가져오기
            query = self.config.get('MASTER_DATA_QUERIES', 'ACCIDENTS_QUERY')
            print(f"[INFO] 실행할 사고 쿼리: {query[:100]}...")
            
            # 외부 DB에서 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 사고 데이터 조회 시작...")
            df = execute_SQL(query)
            df = _normalize_df(df)  # 컬럼명 정규화 (소문자화 & 공백 제거)
            print(f"[INFO] 사고 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 사고 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # PRAGMA 설정
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
            # 기존 custom_data와 is_deleted 보존을 위해 백업
            cursor.execute("""
                CREATE TEMP TABLE accidents_backup AS 
                SELECT accident_number, custom_data, is_deleted 
                FROM accidents_cache
                WHERE accident_number IS NOT NULL
            """)
            
            # 기존 사고 캐시 데이터 삭제
            cursor.execute("DELETE FROM accidents_cache")
            
            # 배치 삽입을 위한 데이터 준비
            rows = []
            for _, row in df.iterrows():
                rows.append(tuple(_to_sqlite_safe(dfv) for dfv in (
                    row.get('accident_number', ''),
                    row.get('accident_name', ''),
                    row.get('workplace', ''),
                    row.get('accident_grade', ''),
                    row.get('major_category', ''),
                    row.get('injury_form', ''),
                    row.get('injury_type', ''),
                    row.get('accident_date', ''),
                    row.get('day_of_week', ''),
                    row.get('created_at', ''),
                    row.get('building', ''),
                    row.get('floor', ''),
                    row.get('location_category', ''),
                    row.get('location_detail', '')
                )))
            
            # 배치 삽입
            cursor.executemany('''
                INSERT INTO accidents_cache (
                    accident_number, accident_name, workplace,
                    accident_grade, major_category, injury_form, injury_type,
                    accident_date, day_of_week, created_at, building, floor,
                    location_category, location_detail, custom_data, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, '{}', 0)
            ''', rows)
            
            # 기존 custom_data와 is_deleted 복원
            cursor.execute("""
                UPDATE accidents_cache 
                SET custom_data = COALESCE(
                    (SELECT custom_data FROM accidents_backup 
                     WHERE accidents_backup.accident_number = accidents_cache.accident_number),
                    '{}'
                ),
                is_deleted = COALESCE(
                    (SELECT is_deleted FROM accidents_backup 
                     WHERE accidents_backup.accident_number = accidents_cache.accident_number),
                    0
                )
            """)
            
            # 임시 테이블 삭제
            cursor.execute("DROP TABLE accidents_backup")
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 사고 데이터 {len(df)}건 동기화 완료 (custom_data 보존)")
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
                    ) VALUES (?, ?, ?)
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
                    ) VALUES (?, ?, ?)
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
                    ) VALUES (?, ?, ?, ?)
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
                    ) VALUES (?, ?, ?, ?)
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
            
            # PRAGMA 설정
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM safety_instructions_cache")
            
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
                custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)
                
                # issue_number와 created_at 추출 (컬럼명이 한글일 수 있음)
                issue_number = row.get('issue_number', '') or row.get('발부번호', '') or ''
                created_at = row.get('created_at', '') or row.get('작성일자', '') or row.get('등록일', '') or ''
                
                rows.append((
                    issue_number,
                    created_at,
                    custom_data,
                    0  # is_deleted = 0
                ))
            
            # 배치 삽입
            cursor.executemany('''
                INSERT INTO safety_instructions_cache (
                    issue_number, created_at, custom_data, is_deleted
                ) VALUES (?, ?, ?, ?)
            ''', rows)
            
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
            
            # PRAGMA 설정
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # followsop_cache 테이블 생성 (없으면)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS followsop_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    work_req_no TEXT UNIQUE,
                    custom_data TEXT DEFAULT '{}',
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM followsop_cache")
            
            # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
            print(f"[DEBUG] FollowSOP DataFrame 컬럼: {list(df.columns)}")
            rows = []
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
                
                # work_req_no 추출 (컬럼명이 한글일 수 있음)
                work_req_no = (row.get('work_req_no', '') or 
                              row.get('작업요청번호', '') or 
                              row.get('work_request_number', '') or 
                              str(idx))  # 없으면 인덱스 사용
                
                if idx == 0:  # 첫 번째 행만 디버깅
                    print(f"[DEBUG] work_req_no: {work_req_no}")
                    print(f"[DEBUG] custom_data 길이: {len(custom_data)}")
                
                rows.append((work_req_no, custom_data))
            
            # 배치 삽입 - PostgreSQL vs SQLite 조건부 처리
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # PostgreSQL: bulk_upsert 사용 
                from db.upsert import bulk_upsert
                data_list = [{'work_req_no': row[0], 'custom_data': row[1]} for row in rows]
                bulk_upsert(conn, 'followsop_cache', data_list)
            else:
                # SQLite: INSERT OR REPLACE
                cursor.executemany('''
                    INSERT OR REPLACE INTO followsop_cache (work_req_no, custom_data) 
                    VALUES (?, ?)
                ''', rows)
            
            # GPT 지침: 캐시→본테이블 이관 (UPSERT) - 동기화된 데이터는 무조건 활성화
            # PostgreSQL vs SQLite 조건부 처리
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # PostgreSQL: Try fast path with ON CONFLICT if a UNIQUE constraint exists.
                try:
                    # Detect UNIQUE on follow_sop(work_req_no)
                    cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.constraint_column_usage ccu
                          ON tc.constraint_name = ccu.constraint_name
                        WHERE tc.table_schema='public'
                          AND tc.table_name='follow_sop'
                          AND tc.constraint_type='UNIQUE'
                          AND ccu.column_name='work_req_no'
                        LIMIT 1
                        """
                    )
                    has_unique = cursor.fetchone() is not None
                except Exception:
                    has_unique = False

                if has_unique:
                    # Fast path: ON CONFLICT upsert
                    cursor.execute('''
                        INSERT INTO follow_sop (work_req_no, custom_data, created_at, is_deleted)
                        SELECT
                          c.work_req_no,
                          c.custom_data,
                          COALESCE(c.sync_date, CURRENT_TIMESTAMP),
                          0
                        FROM followsop_cache c
                        ON CONFLICT (work_req_no) 
                        DO UPDATE SET 
                            custom_data = EXCLUDED.custom_data,
                            is_deleted = 0,
                            updated_at = CURRENT_TIMESTAMP
                    ''')
                else:
                    # Fallback path without UNIQUE: insert missing rows, then update existing rows
                    cursor.execute('''
                        INSERT INTO follow_sop (work_req_no, custom_data, created_at, is_deleted)
                        SELECT
                          c.work_req_no,
                          c.custom_data,
                          COALESCE(c.sync_date, CURRENT_TIMESTAMP),
                          0
                        FROM followsop_cache c
                        WHERE NOT EXISTS (
                          SELECT 1 FROM follow_sop f WHERE f.work_req_no = c.work_req_no
                        )
                    ''')
                    cursor.execute('''
                        UPDATE follow_sop f
                        SET custom_data = c.custom_data,
                            is_deleted = 0,
                            updated_at = CURRENT_TIMESTAMP
                        FROM followsop_cache c
                        WHERE f.work_req_no = c.work_req_no
                    ''')
            else:
                # SQLite용 INSERT OR REPLACE
                cursor.execute('''
                    INSERT OR REPLACE INTO follow_sop (work_req_no, custom_data, created_at, is_deleted)
                    SELECT
                      c.work_req_no,
                      c.custom_data,
                      COALESCE(json_extract(c.custom_data, '$.created_at')::timestamp, c.sync_date),
                      0
                    FROM followsop_cache c
                ''')
            
            # 추가: 동기화된 데이터는 강제로 활성화 (삭제 상태 해제)
            cursor.execute('''
                UPDATE follow_sop SET is_deleted = 0 
                WHERE work_req_no IN (SELECT work_req_no FROM followsop_cache)
            ''')
            
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
            print(f"[INFO] FullProcess 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 FullProcess 데이터가 없습니다.")
                return False
            
            # SQLite에 저장
            conn = get_db_connection(self.local_db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # PRAGMA 설정
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # fullprocess_cache 테이블 생성 (없으면)
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS fullprocess_cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fullprocess_number TEXT UNIQUE,
                    custom_data TEXT DEFAULT '{}',
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 트랜잭션 시작
            cursor.execute("BEGIN IMMEDIATE")
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM fullprocess_cache")
            
            # 배치 삽입을 위한 데이터 준비 (동적 컬럼 방식)
            print(f"[DEBUG] FullProcess DataFrame 컬럼: {list(df.columns)}")
            rows = []
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
                
                # fullprocess_number 추출 (컬럼명이 한글일 수 있음)
                fullprocess_number = (row.get('fullprocess_number', '') or 
                                     row.get('프로세스번호', '') or 
                                     row.get('process_number', '') or 
                                     str(idx))  # 없으면 인덱스 사용
                
                if idx == 0:  # 첫 번째 행만 디버깅
                    print(f"[DEBUG] fullprocess_number: {fullprocess_number}")
                    print(f"[DEBUG] custom_data 길이: {len(custom_data)}")
                
                rows.append((fullprocess_number, custom_data))
            
            # 배치 삽입 - PostgreSQL vs SQLite 조건부 처리
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # PostgreSQL: bulk_upsert 사용 
                from db.upsert import bulk_upsert
                data_list = [{'fullprocess_number': row[0], 'custom_data': row[1]} for row in rows]
                bulk_upsert(conn, 'fullprocess_cache', data_list)
            else:
                # SQLite: INSERT OR REPLACE
                cursor.executemany('''
                    INSERT OR REPLACE INTO fullprocess_cache (fullprocess_number, custom_data) 
                    VALUES (?, ?)
                ''', rows)
            
            # GPT 지침: 캐시→본테이블 이관 (UPSERT) - 동기화된 데이터는 무조건 활성화
            # PostgreSQL vs SQLite 조건부 처리
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # PostgreSQL: Try fast path with ON CONFLICT if a UNIQUE exists.
                try:
                    cursor.execute(
                        """
                        SELECT 1
                        FROM information_schema.table_constraints tc
                        JOIN information_schema.constraint_column_usage ccu
                          ON tc.constraint_name = ccu.constraint_name
                        WHERE tc.table_schema='public'
                          AND tc.table_name='full_process'
                          AND tc.constraint_type='UNIQUE'
                          AND ccu.column_name='fullprocess_number'
                        LIMIT 1
                        """
                    )
                    has_unique = cursor.fetchone() is not None
                except Exception:
                    has_unique = False

                if has_unique:
                    cursor.execute('''
                        INSERT INTO full_process (fullprocess_number, custom_data, created_at, is_deleted)
                        SELECT
                          c.fullprocess_number,
                          c.custom_data,
                          COALESCE(c.sync_date, CURRENT_TIMESTAMP),
                          0
                        FROM fullprocess_cache c
                        ON CONFLICT (fullprocess_number) 
                        DO UPDATE SET 
                            custom_data = EXCLUDED.custom_data,
                            is_deleted = 0,
                            updated_at = CURRENT_TIMESTAMP
                    ''')
                else:
                    # Fallback without UNIQUE
                    cursor.execute('''
                        INSERT INTO full_process (fullprocess_number, custom_data, created_at, is_deleted)
                        SELECT
                          c.fullprocess_number,
                          c.custom_data,
                          COALESCE(c.sync_date, CURRENT_TIMESTAMP),
                          0
                        FROM fullprocess_cache c
                        WHERE NOT EXISTS (
                          SELECT 1 FROM full_process f WHERE f.fullprocess_number = c.fullprocess_number
                        )
                    ''')
                    cursor.execute('''
                        UPDATE full_process f
                        SET custom_data = c.custom_data,
                            is_deleted = 0,
                            updated_at = CURRENT_TIMESTAMP
                        FROM fullprocess_cache c
                        WHERE f.fullprocess_number = c.fullprocess_number
                    ''')
            else:
                # SQLite용 INSERT OR REPLACE
                cursor.execute('''
                    INSERT OR REPLACE INTO full_process (fullprocess_number, custom_data, created_at, is_deleted)
                    SELECT
                      c.fullprocess_number,
                      c.custom_data,
                      COALESCE(json_extract(c.custom_data, '$.created_at')::timestamp, c.sync_date),
                      0
                    FROM fullprocess_cache c
                ''')
            
            # 추가: 동기화된 데이터는 강제로 활성화 (삭제 상태 해제)
            cursor.execute('''
                UPDATE full_process SET is_deleted = 0 
                WHERE fullprocess_number IN (SELECT fullprocess_number FROM fullprocess_cache)
            ''')
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ FullProcess 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ FullProcess 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def get_partner_by_business_number(self, business_number):
        """사업자번호로 협력사 정보 조회 (캐시 + 상세정보 조인)"""
        conn = get_db_connection(self.local_db_path)
        conn.row_factory = sqlite3.Row
        
        query = '''
            SELECT 
                pc.*,
                pd.detailed_content,
                pd.updated_at as detail_updated_at
            FROM partners_cache pc
            LEFT JOIN partner_details pd ON pc.business_number = pd.business_number
            WHERE pc.business_number = ?
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
                query += " AND company_name LIKE ?"
                params.append(f"%{filters['company_name']}%")
            
            if filters.get('business_number'):
                query += " AND business_number LIKE ?"
                params.append(f"%{filters['business_number']}%")
            
            if filters.get('business_type_major'):
                query += " AND business_type_major = ?"
                params.append(filters['business_type_major'])
            
            if filters.get('business_type_minor'):
                query += " AND business_type_minor LIKE ?"
                params.append(f"%{filters['business_type_minor']}%")
            
            # 상시근로자 수 범위 필터
            if filters.get('workers_min'):
                query += " AND permanent_workers >= ?"
                params.append(filters['workers_min'])
            
            if filters.get('workers_max'):
                query += " AND permanent_workers <= ?"
                params.append(filters['workers_max'])
        
        # 전체 개수 조회
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total_count = conn.execute(count_query, params).fetchone()[0]
        
        # 페이징 적용 - 상시근로자 수 큰 순으로 정렬 (SQLite 호환)
        query += " ORDER BY (permanent_workers IS NULL), permanent_workers DESC, company_name LIMIT ? OFFSET ?"
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
    
    def get_sqlite_connection(self, timeout=10.0):
        """SQLite 연결 반환"""
        conn = get_db_connection(self.local_db_path, timeout=timeout)
        cur = conn.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA busy_timeout=5000")
        cur.execute("PRAGMA synchronous=NORMAL")
        return conn

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
        row = cur.execute("SELECT first_sync_done FROM content_sync_state WHERE name=?", (name,)).fetchone()
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

    conn.close()
partner_manager.db_config = db_config  # 순환 참조 해결
