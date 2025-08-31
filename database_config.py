import configparser
import os
import sqlite3
import logging
import sys
import traceback
import pandas as pd
from datetime import datetime, timedelta

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
        conn = sqlite3.connect(self.local_db_path)
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
        
        # 테이블이 없거나 구조가 다르면 재생성
        if not existing_columns or set(existing_columns.keys()) != set(required_columns.keys()):
            print("[INFO] partners_cache 테이블 구조가 변경되어 재생성합니다.")
            cursor.execute("DROP TABLE IF EXISTS partners_cache")
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
            print("[SUCCESS] partners_cache 테이블 재생성 완료")
        else:
            print("[INFO] partners_cache 테이블 구조가 정상입니다.")
        
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
                is_active BOOLEAN DEFAULT 1,
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
        
        # 기존 테이블에 permanent_workers 컬럼이 없으면 추가
        try:
            cursor.execute("ALTER TABLE partners_cache ADD COLUMN permanent_workers INTEGER")
            logging.info("partners_cache 테이블에 permanent_workers 컬럼 추가 완료")
        except Exception as e:
            if "duplicate column name" in str(e).lower() or "already exists" in str(e).lower():
                logging.info("permanent_workers 컬럼이 이미 존재합니다")
            else:
                logging.warning(f"permanent_workers 컬럼 추가 중 오류: {e}")
        
        # 건물 마스터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS building_master (
                building_code TEXT PRIMARY KEY,
                building_name TEXT NOT NULL,
                SITE TEXT,
                SITE_TYPE TEXT
            )
        ''')
        
        # 부서 마스터 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS department_master (
                dept_code TEXT PRIMARY KEY,
                dept_name TEXT NOT NULL,
                parent_dept_code TEXT,
                dept_level INTEGER
            )
        ''')
        
        # 더미 데이터 삽입 (건물)
        cursor.execute("SELECT COUNT(*) FROM building_master")
        if cursor.fetchone()[0] == 0:
            buildings = [
                ('BLD001', '본관', '서울시 강남구 테헤란로 123', '사무실'),
                ('BLD002', '신관', '서울시 강남구 테헤란로 124', '사무실'),
                ('BLD003', '연구동', '서울시 강남구 테헤란로 125', '연구소'),
                ('BLD004', '공장 A동', '경기도 수원시 영통구 광교로 100', '생산시설'),
                ('BLD005', '공장 B동', '경기도 수원시 영통구 광교로 101', '생산시설'),
                ('BLD006', '물류센터', '경기도 용인시 기흥구 동백중앙로 200', '물류시설'),
                ('BLD007', '연수원', '경기도 이천시 부발읍 신하리 100', '교육시설'),
                ('BLD008', '기숙사 A동', '서울시 강남구 테헤란로 126', '주거시설'),
                ('BLD009', '기숙사 B동', '서울시 강남구 테헤란로 127', '주거시설'),
                ('BLD010', '체육관', '서울시 강남구 테헤란로 128', '체육시설')
            ]
            cursor.executemany('INSERT INTO building_master VALUES (?, ?, ?, ?)', buildings)
        
        # 더미 데이터 삽입 (부서)
        cursor.execute("SELECT COUNT(*) FROM department_master")
        if cursor.fetchone()[0] == 0:
            departments = [
                ('DEPT001', '경영지원본부', None, 1),
                ('DEPT002', '인사팀', 'DEPT001', 2),
                ('DEPT003', '총무팀', 'DEPT001', 2),
                ('DEPT004', '재무팀', 'DEPT001', 2),
                ('DEPT005', '영업본부', None, 1),
                ('DEPT006', '국내영업팀', 'DEPT005', 2),
                ('DEPT007', '해외영업팀', 'DEPT005', 2),
                ('DEPT008', '마케팅팀', 'DEPT005', 2),
                ('DEPT009', '생산본부', None, 1),
                ('DEPT010', '생산1팀', 'DEPT009', 2),
                ('DEPT011', '생산2팀', 'DEPT009', 2),
                ('DEPT012', '품질관리팀', 'DEPT009', 2),
                ('DEPT013', '연구개발본부', None, 1),
                ('DEPT014', 'SW개발팀', 'DEPT013', 2),
                ('DEPT015', 'HW개발팀', 'DEPT013', 2),
                ('DEPT016', '신기술연구팀', 'DEPT013', 2),
                ('DEPT017', '안전보건팀', None, 1),
                ('DEPT018', '환경안전파트', 'DEPT017', 2),
                ('DEPT019', '산업보건파트', 'DEPT017', 2),
                ('DEPT020', '시설관리팀', None, 1)
            ]
            cursor.executemany('INSERT INTO department_master VALUES (?, ?, ?, ?)', departments)
        
        conn.commit()
        conn.close()
    
    def sync_partners_from_external_db(self):
        """외부 DB에서 협력사 마스터 데이터 동기화 (기존 성공 방식)"""
        if not IQADB_AVAILABLE:
            logging.error("IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 PARTNERS_QUERY 가져오기 (간단!)
            query = self.config.get('SQL_QUERIES', 'PARTNERS_QUERY')
            print(f"[INFO] 실행할 쿼리: {query[:100]}...")
            
            # ✨ 기존 성공 방식으로 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            
            # 기존 is_deleted 값을 보존하기 위해 먼저 백업
            cursor.execute("SELECT business_number, is_deleted FROM partners_cache WHERE is_deleted = 1")
            deleted_partners = {row[0]: row[1] for row in cursor.fetchall()}
            
            # 기존 캐시 데이터 삭제
            cursor.execute("DELETE FROM partners_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                business_number = row.get('business_number', '')
                # 이전에 삭제된 협력사면 is_deleted = 1 유지, 아니면 0
                is_deleted_value = deleted_partners.get(business_number, 0)
                
                cursor.execute('''
                    INSERT INTO partners_cache (
                        business_number, company_name, partner_class, business_type_major,
                        business_type_minor, hazard_work_flag, representative, address,
                        average_age, annual_revenue, transaction_count, permanent_workers, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
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
                    row.get('transaction_count', ''),  # TEXT로 변경
                    row.get('permanent_workers', None),  # 추가
                    is_deleted_value  # 기존 삭제 상태 유지
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 협력사 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            print(f"[ERROR] ❌ 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def sync_accidents_from_external_db(self):
        """외부 DB에서 사고 데이터 동기화 (기존 성공 방식)"""
        if not IQADB_AVAILABLE:
            print("[ERROR] IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 ACCIDENTS_QUERY 가져오기 (간단!)
            query = self.config.get('SQL_QUERIES', 'ACCIDENTS_QUERY')
            print(f"[INFO] 실행할 사고 쿼리: {query[:100]}...")
            
            # ✨ 기존 성공 방식으로 데이터 조회
            print("[INFO] IQADB_CONNECT310을 사용하여 사고 데이터 조회 시작...")
            df = execute_SQL(query)
            print(f"[INFO] 사고 데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                print("[WARNING] 조회된 사고 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            
            # 디버그: DataFrame의 실제 컬럼명 확인
            print(f"[DEBUG] DataFrame 컬럼명: {list(df.columns)}")
            if not df.empty:
                print(f"[DEBUG] 첫 번째 행 전체 데이터:")
                first_row = df.iloc[0]
                for col in df.columns:
                    print(f"  - {col}: {first_row[col]}")
                print(f"\n[DEBUG] row.get으로 접근 테스트:")
                row_dict = first_row.to_dict()
                print(f"  - accident_number: {row_dict.get('accident_number', 'NOT FOUND')}")
                print(f"  - accident_name: {row_dict.get('accident_name', 'NOT FOUND')}")
                print(f"  - accident_date: {row_dict.get('accident_date', 'NOT FOUND')}")
            
            # 기존 사고 캐시 데이터 삭제
            cursor.execute("DELETE FROM accidents_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            # config.ini의 ACCIDENTS_QUERY 컬럼에 맞게 매핑 (14개 필드)
            for _, row in df.iterrows():
                cursor.execute('''
                    INSERT INTO accidents_cache (
                        accident_number, accident_name, workplace,
                        accident_grade, major_category, injury_form, injury_type,
                        accident_date, day_of_week, report_date, building, floor,
                        location_category, location_detail
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get('accident_number', ''),
                    row.get('accident_name', ''),
                    row.get('workplace', ''),
                    row.get('accident_grade', ''),
                    row.get('major_category', ''),
                    row.get('injury_form', ''),
                    row.get('injury_type', ''),
                    row.get('accident_date', ''),
                    row.get('day_of_week', ''),
                    row.get('report_date', ''),
                    row.get('building', ''),
                    row.get('floor', ''),
                    row.get('location_category', ''),
                    row.get('location_detail', '')
                ))
            
            conn.commit()
            conn.close()
            
            print(f"[SUCCESS] ✅ 사고 데이터 {len(df)}건 동기화 완료")
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
            # config.ini에서 EMPLOYEE_QUERY 가져오기
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
            conn = sqlite3.connect(self.local_db_path)
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
            # config.ini에서 DEPARTMENT_QUERY 가져오기
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
            conn = sqlite3.connect(self.local_db_path)
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
                    row.get('parent_dept_code', '')
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
            # config.ini에서 BUILDING_QUERY 가져오기
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
            conn = sqlite3.connect(self.local_db_path)
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
            # config.ini에서 CONTRACTOR_QUERY 가져오기
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
            conn = sqlite3.connect(self.local_db_path)
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
    
    def get_partner_by_business_number(self, business_number):
        """사업자번호로 협력사 정보 조회 (캐시 + 상세정보 조인)"""
        conn = sqlite3.connect(self.local_db_path)
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
        conn = sqlite3.connect(self.local_db_path)
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
        
        # 페이징 적용 - 상시근로자 수 큰 순으로 정렬
        query += " ORDER BY permanent_workers DESC NULLS LAST, company_name LIMIT ? OFFSET ?"
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
    
    def get_sqlite_connection(self):
        """SQLite 연결 반환"""
        return sqlite3.connect(self.local_db_path)

# 전역 인스턴스
db_config = DatabaseConfig()
partner_manager = PartnerDataManager()
partner_manager.db_config = db_config  # 순환 참조 해결