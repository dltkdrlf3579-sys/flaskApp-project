import configparser
import os
import sqlite3
import logging
import sys
import traceback
import pandas as pd
from datetime import datetime, timedelta

# 기존 성공 방식: IQADB_CONNECT310 모듈 로드
try:
    module_folder = 'C:/Users/user/AppData/Local/aipforge/pkgs/dist/obf/PY310'
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

# 설정 파일 로드 (절대 경로 사용)
config = configparser.ConfigParser()
config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

# 설정 파일 존재 확인 및 로드
if not os.path.exists(config_path):
    print(f"[ERROR] 설정 파일을 찾을 수 없습니다: {config_path}")
    print("config_template.ini를 config.ini로 복사하세요.")
    exit(1)

try:
    config.read(config_path, encoding='utf-8')
    if not config.has_section('DATABASE'):
        print(f"[ERROR] config.ini에 [DATABASE] 섹션이 없습니다.")
        print("config_template.ini를 참고하여 설정을 확인하세요.")
        exit(1)
    print(f"[SUCCESS] 설정 파일 로드 성공: {config_path}")
except Exception as e:
    print(f"[ERROR] 설정 파일 로드 실패: {e}")
    exit(1)

class DatabaseConfig:
    def __init__(self):
        self.config = config
        self.local_db_path = config.get('DATABASE', 'LOCAL_DB_PATH')
        self.external_db_enabled = config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED')
        
        # PostgreSQL 설정 (외부 DB)
        if self.external_db_enabled:
            self.pg_host = config.get('DATABASE', 'EXTERNAL_DB_HOST')
            self.pg_port = config.getint('DATABASE', 'EXTERNAL_DB_PORT')
            self.pg_database = config.get('DATABASE', 'EXTERNAL_DB_NAME')
            self.pg_user = config.get('DATABASE', 'EXTERNAL_DB_USER')
            self.pg_password = config.get('DATABASE', 'EXTERNAL_DB_PASSWORD')
            self.pg_schema = config.get('DATABASE', 'EXTERNAL_DB_SCHEMA')
            self.pg_table = config.get('DATABASE', 'EXTERNAL_DB_TABLE')
    
    def get_sqlite_connection(self):
        """SQLite 연결 (로컬 업무 데이터용)"""
        return sqlite3.connect(self.local_db_path)
    
    def should_sync(self):
        """동기화가 필요한지 확인"""
        if not self.external_db_enabled:
            return False
            
        if not config.getboolean('SYNC', 'AUTO_SYNC_ENABLED'):
            return False
            
        last_sync_file = config.get('SYNC', 'LAST_SYNC_FILE')
        if not os.path.exists(last_sync_file):
            return True
            
        try:
            with open(last_sync_file, 'r') as f:
                last_sync_str = f.read().strip()
                last_sync = datetime.fromisoformat(last_sync_str)
                
            sync_interval = config.getint('SYNC', 'SYNC_INTERVAL_MINUTES')
            next_sync = last_sync + timedelta(minutes=sync_interval)
            
            return datetime.now() >= next_sync
        except:
            return True
    
    def update_last_sync(self):
        """마지막 동기화 시간 업데이트"""
        last_sync_file = config.get('SYNC', 'LAST_SYNC_FILE')
        with open(last_sync_file, 'w') as f:
            f.write(datetime.now().isoformat())

class PartnerDataManager:
    def __init__(self):
        self.db_config = DatabaseConfig()
        self.init_local_tables()
    
    def should_sync(self):
        """동기화가 필요한지 확인 - DatabaseConfig의 메서드 호출"""
        return self.db_config.should_sync()
    
    def update_last_sync(self):
        """마지막 동기화 시간 업데이트 - DatabaseConfig의 메서드 호출"""
        return self.db_config.update_last_sync()
    
    def init_local_tables(self):
        """로컬 SQLite 테이블 초기화"""
        conn = self.db_config.get_sqlite_connection()
        cursor = conn.cursor()
        
        # 협력사 마스터 데이터 캐시 테이블 (11개 컬럼)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partners_cache (
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
                transaction_count INTEGER,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
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
        
        conn.commit()
        conn.close()
    
    def sync_partners_from_external_db(self):
        """외부 DB에서 협력사 마스터 데이터 동기화 (기존 성공 방식)"""
        if not self.db_config.external_db_enabled:
            logging.info("외부 DB가 비활성화되어 있어 동기화를 건너뜁니다.")
            return False
        
        if not IQADB_AVAILABLE:
            logging.error("IQADB_CONNECT310 모듈을 사용할 수 없습니다.")
            return False
        
        try:
            # config.ini에서 PARTNERS_QUERY 가져오기
            query_template = self.db_config.config.get('SQL_QUERIES', 'PARTNERS_QUERY')
            query = query_template.format(
                schema=self.db_config.pg_schema,
                table=self.db_config.pg_table
            )
            
            # ✨ 기존 성공 방식으로 데이터 조회
            logging.info("IQADB_CONNECT310을 사용하여 데이터 조회 시작...")
            df = execute_SQL(query)
            logging.info(f"데이터 조회 완료: {len(df)} 건")
            
            if df.empty:
                logging.warning("조회된 데이터가 없습니다.")
                return False
            
            # DataFrame을 SQLite에 저장
            sqlite_conn = self.db_config.get_sqlite_connection()
            sqlite_cursor = sqlite_conn.cursor()
            
            # 기존 캐시 데이터 삭제
            sqlite_cursor.execute("DELETE FROM partners_cache")
            
            # DataFrame을 레코드 배열로 변환하여 SQLite에 삽입
            for _, row in df.iterrows():
                sqlite_cursor.execute('''
                    INSERT INTO partners_cache (
                        business_number, company_name, partner_class, business_type_major,
                        business_type_minor, hazard_work_flag, representative, address,
                        average_age, annual_revenue, transaction_count
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    row.get('business_number', ''),
                    row.get('company_name', ''),
                    row.get('partner_class', ''),
                    row.get('business_type_major', ''),
                    row.get('business_type_minor', ''),
                    row.get('hazard_work_flag', ''),
                    row.get('representative', ''),
                    row.get('address', ''),
                    row.get('average_age', None),
                    row.get('annual_revenue', None),
                    row.get('transaction_count', None)
                ))
            
            sqlite_conn.commit()
            sqlite_conn.close()
            
            self.db_config.update_last_sync()
            logging.info(f"✅ 협력사 데이터 {len(df)}건 동기화 완료")
            return True
            
        except Exception as e:
            logging.error(f"❌ 데이터 동기화 실패: {e}")
            traceback.print_exc()
            return False
    
    def get_partner_by_business_number(self, business_number):
        """사업자번호로 협력사 정보 조회 (캐시 + 상세정보 조인)"""
        conn = self.db_config.get_sqlite_connection()
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
        conn = self.db_config.get_sqlite_connection()
        conn.row_factory = sqlite3.Row
        
        # 기본 쿼리
        query = "SELECT * FROM partners_cache WHERE 1=1"
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
        
        # 전체 개수 조회
        count_query = query.replace("SELECT *", "SELECT COUNT(*)")
        total_count = conn.execute(count_query, params).fetchone()[0]
        
        # 페이징 적용
        query += " ORDER BY company_name LIMIT ? OFFSET ?"
        params.extend([per_page, (page - 1) * per_page])
        
        partners = conn.execute(query, params).fetchall()
        conn.close()
        
        return partners, total_count

# 전역 인스턴스
db_config = DatabaseConfig()
partner_manager = PartnerDataManager()