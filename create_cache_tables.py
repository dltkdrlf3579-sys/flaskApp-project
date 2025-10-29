#!/usr/bin/env python3
"""
모든 _cache 테이블 생성 스크립트
"""
import psycopg
import configparser
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        logging.error(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
        return None
    
    user, password, host, port, database = match.groups()
    
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=database,
            user=user,
            password=password
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logging.error(f"PostgreSQL 연결 실패: {e}")
        return None

def create_cache_tables(conn):
    """모든 _cache 테이블 생성"""
    cursor = conn.cursor()
    
    cache_tables = {
        'safety_instructions_cache': """
            CREATE TABLE IF NOT EXISTS safety_instructions_cache (
                id SERIAL PRIMARY KEY,
                issue_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """,
        'follow_sop_cache': """
            CREATE TABLE IF NOT EXISTS follow_sop_cache (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """,
        'full_process_cache': """
            CREATE TABLE IF NOT EXISTS full_process_cache (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """,
        'change_requests_cache': """
            CREATE TABLE IF NOT EXISTS change_requests_cache (
                id SERIAL PRIMARY KEY,
                request_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """,
        'partner_standards_cache': """
            CREATE TABLE IF NOT EXISTS partner_standards_cache (
                id SERIAL PRIMARY KEY,
                standard_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        """
    }
    
    for table_name, create_sql in cache_tables.items():
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            
            exists = cursor.fetchone()[0]
            
            if not exists:
                cursor.execute(create_sql)
                logging.info(f"[생성] {table_name} 테이블 생성됨")
            else:
                logging.info(f"[확인] {table_name} 테이블 이미 존재")
                
            # custom_data 컬럼 타입 확인 및 수정
            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'custom_data'
            """, (table_name,))
            
            result = cursor.fetchone()
            if result:
                data_type = result[0]
                if data_type == 'text':
                    # TEXT를 JSONB로 변환
                    logging.info(f"  -> {table_name}.custom_data를 TEXT에서 JSONB로 변환")
                    cursor.execute(f"""
                        ALTER TABLE {table_name} 
                        ALTER COLUMN custom_data TYPE JSONB 
                        USING custom_data::JSONB
                    """)
                    
        except Exception as e:
            logging.error(f"[오류] {table_name}: {e}")

def verify_tables(conn):
    """테이블 확인"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("테이블 상태 확인")
    print("="*60)
    
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache',
        'partner_standards_cache'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'custom_data'
            """, (table,))
            
            result = cursor.fetchone()
            data_type = result[0] if result else "없음"
            
            print(f"[OK] {table}: {count}개 레코드, custom_data 타입: {data_type}")
            
        except Exception as e:
            print(f"[ERROR] {table}: {e}")

def main():
    """메인 실행"""
    print("="*60)
    print("_cache 테이블 생성 및 확인")
    print("="*60)
    
    conn = get_pg_connection()
    if not conn:
        return
    
    try:
        # 1. 테이블 생성
        print("\n1. _cache 테이블 생성")
        create_cache_tables(conn)
        
        # 2. 확인
        verify_tables(conn)
        
        print("\n[완료] 모든 _cache 테이블이 준비되었습니다!")
        
    except Exception as e:
        print(f"\n[ERROR] 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()
