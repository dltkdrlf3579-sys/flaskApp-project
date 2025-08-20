import configparser
import os
import sqlite3
import logging
from datetime import datetime, timedelta

# 설정 파일 로드 (절대 경로 사용 - 보안사업장 환경 대응)
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
    
    def get_postgresql_connection(self):
        """PostgreSQL 연결 (협력사 마스터 데이터용)"""
        if not self.external_db_enabled:
            return None
            
        try:
            import psycopg2
            conn = psycopg2.connect(
                host=self.pg_host,
                port=self.pg_port,
                database=self.pg_database,
                user=self.pg_user,
                password=self.pg_password
            )
            return conn
        except ImportError:
            logging.error("psycopg2 패키지가 설치되지 않았습니다. pip install psycopg2-binary")
            return None
        except Exception as e:
            logging.error(f"PostgreSQL 연결 실패: {e}")
            return None
    
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
    
    def generate_partners_query(self):
        """컬럼 매핑을 기반으로 자동으로 협력사 쿼리 생성"""
        # COLUMN_MAPPING 섹션에서 매핑 정보 읽기
        if not self.db_config.config.has_section('COLUMN_MAPPING'):
            raise Exception("COLUMN_MAPPING 섹션이 없습니다")
            
        mapping = dict(self.db_config.config.items('COLUMN_MAPPING'))
        
        # 협력사 정보만 필터링 (사고 정보 제외)
        partner_columns = ['business_number', 'company_name', 'representative', 'regular_workers',
                          'business_type', 'business_type_major', 'business_type_minor', 
                          'establishment_date', 'capital_amount', 'annual_revenue', 'main_products',
                          'certification', 'safety_rating', 'contact_person', 'phone_number', 'email']
        
        # AS 절이 있는 SELECT 문 생성
        select_columns = []
        for portal_column in partner_columns:
            if portal_column in mapping:
                real_column = mapping[portal_column]
                select_columns.append(f"{real_column} AS {portal_column}")
        
        if not select_columns:
            raise Exception("매핑된 컬럼이 없습니다")
        
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM {self.db_config.pg_schema}.{self.db_config.pg_table}
            WHERE {mapping.get('business_number', 'business_number')} IS NOT NULL
            ORDER BY {mapping.get('company_name', 'company_name')}
        """
        
        return query
    
    def generate_accidents_query(self):
        """컬럼 매핑을 기반으로 자동으로 사고 쿼리 생성"""
        # COLUMN_MAPPING 섹션에서 매핑 정보 읽기  
        mapping = dict(self.db_config.config.items('COLUMN_MAPPING'))
        
        # 사고 관련 컬럼만 선택
        accident_columns = ['business_number', 'accident_date', 'accident_type', 'accident_location', 
                          'accident_description', 'injury_level', 'injured_count', 'cause_analysis',
                          'preventive_measures', 'report_date', 'reporter_name']
        
        select_columns = []
        for portal_column in accident_columns:
            real_column = mapping.get(portal_column, portal_column)
            select_columns.append(f"{real_column} AS {portal_column}")
        
        accidents_table = self.db_config.config.get('DATABASE', 'ACCIDENTS_DB_TABLE')
        query = f"""
            SELECT {', '.join(select_columns)}
            FROM {self.db_config.pg_schema}.{accidents_table}
            WHERE {mapping.get('business_number', 'business_number')} IS NOT NULL
              AND {mapping.get('accident_date', 'accident_date')} >= '2020-01-01'
            ORDER BY {mapping.get('accident_date', 'accident_date')} DESC
        """
        
        return query
    
    def init_local_tables(self):
        """로컬 SQLite 테이블 초기화"""
        conn = self.db_config.get_sqlite_connection()
        cursor = conn.cursor()
        
        # 협력사 마스터 데이터 캐시 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partners_cache (
                business_number TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                representative TEXT,
                regular_workers INTEGER,
                business_type TEXT,
                business_type_major TEXT,
                business_type_minor TEXT,
                establishment_date TEXT,
                capital_amount BIGINT,
                annual_revenue BIGINT,
                main_products TEXT,
                certification TEXT,
                safety_rating TEXT,
                contact_person TEXT,
                phone_number TEXT,
                email TEXT,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 협력사 사고 정보 캐시 테이블 (추가)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accidents_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                business_number TEXT NOT NULL,
                accident_date TEXT,
                accident_type TEXT,
                accident_location TEXT,
                accident_description TEXT,
                injury_level TEXT,
                injured_count INTEGER,
                cause_analysis TEXT,
                preventive_measures TEXT,
                report_date TEXT,
                reporter_name TEXT,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_number) REFERENCES partners_cache (business_number)
            )
        ''')
        
        # 업무 상세내용 테이블 (로컬 전용)
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
        
        conn.commit()
        conn.close()
    
    def sync_partners_from_postgresql(self):
        """PostgreSQL에서 협력사 마스터 데이터 동기화"""
        if not self.db_config.external_db_enabled:
            logging.info("외부 DB가 비활성화되어 있어 동기화를 건너뜁니다.")
            return False
            
        pg_conn = self.db_config.get_postgresql_connection()
        if not pg_conn:
            logging.error("PostgreSQL 연결 실패")
            return False
        
        try:
            # PostgreSQL에서 데이터 조회
            pg_cursor = pg_conn.cursor()
            # 🔧 두 가지 방법 지원: 1) 자동 생성 2) 수동 쿼리
            try:
                # 방법 1: 컬럼 매핑을 통한 자동 쿼리 생성
                query = self.generate_partners_query()
                logging.info("컬럼 매핑으로 자동 생성된 쿼리 사용")
            except Exception as mapping_error:
                logging.warning(f"컬럼 매핑 실패, 수동 쿼리 사용: {mapping_error}")
                # 방법 2: 수동 작성된 쿼리 사용 (기존 방식)
                query_template = self.db_config.config.get('SQL_QUERIES', 'PARTNERS_QUERY')
                query = query_template.format(
                    schema=self.db_config.pg_schema,
                    table=self.db_config.pg_table
                )
            pg_cursor.execute(query)
            partners_data = pg_cursor.fetchall()
            
            # SQLite에 데이터 동기화
            sqlite_conn = self.db_config.get_sqlite_connection()
            sqlite_cursor = sqlite_conn.cursor()
            
            # 기존 캐시 데이터 삭제 후 새로 삽입
            sqlite_cursor.execute("DELETE FROM partners_cache")
            
            for partner in partners_data:
                sqlite_cursor.execute('''
                    INSERT INTO partners_cache (
                        business_number, company_name, representative, regular_workers,
                        business_type, business_type_major, business_type_minor,
                        establishment_date, capital_amount, annual_revenue,
                        main_products, certification, safety_rating,
                        contact_person, phone_number, email
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', partner)
            
            sqlite_conn.commit()
            sqlite_conn.close()
            pg_conn.close()
            
            self.db_config.update_last_sync()
            logging.info(f"협력사 데이터 {len(partners_data)}건 동기화 완료")
            return True
            
        except Exception as e:
            logging.error(f"데이터 동기화 실패: {e}")
            return False
    
    def sync_accidents_from_postgresql(self):
        """PostgreSQL에서 협력사 사고 데이터 동기화"""
        if not self.db_config.external_db_enabled:
            return False
            
        if not self.db_config.config.getboolean('DATABASE', 'ACCIDENTS_DB_ENABLED'):
            logging.info("사고 데이터 동기화가 비활성화되어 있습니다.")
            return False
            
        pg_conn = self.db_config.get_postgresql_connection()
        if not pg_conn:
            logging.error("PostgreSQL 연결 실패 (사고 데이터)")
            return False
        
        try:
            # PostgreSQL에서 사고 데이터 조회
            pg_cursor = pg_conn.cursor()
            accidents_table = self.db_config.config.get('DATABASE', 'ACCIDENTS_DB_TABLE')
            
            # 🔧 두 가지 방법 지원: 1) 자동 생성 2) 수동 쿼리
            try:
                # 방법 1: 컬럼 매핑을 통한 자동 쿼리 생성
                query = self.generate_accidents_query()
                logging.info("컬럼 매핑으로 자동 생성된 사고 쿼리 사용")
            except Exception as mapping_error:
                logging.warning(f"사고 컬럼 매핑 실패, 수동 쿼리 사용: {mapping_error}")
                # 방법 2: 수동 작성된 쿼리 사용 (기존 방식)
                query_template = self.db_config.config.get('SQL_QUERIES', 'ACCIDENTS_QUERY')
                query = query_template.format(
                    schema=self.db_config.pg_schema,
                    table=accidents_table
                )
            pg_cursor.execute(query)
            accidents_data = pg_cursor.fetchall()
            
            # SQLite에 데이터 동기화
            sqlite_conn = self.db_config.get_sqlite_connection()
            sqlite_cursor = sqlite_conn.cursor()
            
            # 기존 사고 데이터 삭제 후 새로 삽입
            sqlite_cursor.execute("DELETE FROM accidents_cache")
            
            for accident in accidents_data:
                sqlite_cursor.execute('''
                    INSERT INTO accidents_cache (
                        business_number, accident_date, accident_type, accident_location,
                        accident_description, injury_level, injured_count, cause_analysis,
                        preventive_measures, report_date, reporter_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', accident)
            
            sqlite_conn.commit()
            sqlite_conn.close()
            pg_conn.close()
            
            logging.info(f"사고 데이터 {len(accidents_data)}건 동기화 완료")
            return True
            
        except Exception as e:
            logging.error(f"사고 데이터 동기화 실패: {e}")
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