#!/usr/bin/env python3
"""
운영 환경에서 누락된 모든 테이블 생성
check_postgres.py에서 ❌로 표시된 모든 테이블 생성

Usage:
    python fix_all_missing_tables.py
"""
import psycopg
import configparser

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def create_missing_tables():
    """누락된 모든 테이블 생성"""
    
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("누락된 테이블 생성 시작...\n")
    
    # 1. 누락된 캐시 테이블들 (이름 주의!)
    print("=== 캐시 테이블 생성 ===")
    
    # followsop_cache (언더스코어 없음!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS followsop_cache (
            id SERIAL PRIMARY KEY,
            work_req_no TEXT UNIQUE,
            custom_data JSONB DEFAULT '{}',
            sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')
    print('[OK] followsop_cache')
    
    # fullprocess_cache (언더스코어 없음!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fullprocess_cache (
            id SERIAL PRIMARY KEY,
            fullprocess_number TEXT UNIQUE,
            custom_data JSONB DEFAULT '{}',
            sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')
    print('[OK] fullprocess_cache')
    
    # change_requests_cache (s 있음!)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS change_requests_cache (
            id SERIAL PRIMARY KEY,
            request_number TEXT UNIQUE,
            primary_company TEXT,
            primary_business_number TEXT,
            subcontractor TEXT,
            subcontractor_business_number TEXT,
            custom_data JSONB DEFAULT '{}',
            sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')
    print('[OK] change_requests_cache')
    
    # partner_standards_cache (누락된 경우가 많음)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS partner_standards_cache (
            id SERIAL PRIMARY KEY,
            standard_number TEXT UNIQUE,
            primary_company TEXT,
            primary_business_number TEXT,
            subcontractor TEXT,
            subcontractor_business_number TEXT,
            custom_data JSONB DEFAULT '{}',
            sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_deleted INTEGER DEFAULT 0
        )
    ''')
    print('[OK] partner_standards_cache')
    
    print("\n=== 컬럼 설정 테이블 생성 ===")
    
    # 모든 column_config 테이블들
    config_tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_change_column_config',
        'partner_standards_column_config'  # 이것도 추가!
    ]
    
    for table in config_tables:
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                dropdown_options TEXT,
                tab TEXT,
                column_span INTEGER DEFAULT 1,
                linked_columns TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                is_list_display INTEGER DEFAULT 0,
                is_system INTEGER DEFAULT 0,
                is_required INTEGER DEFAULT 0,
                input_type TEXT DEFAULT 'text',
                table_group TEXT,
                table_type TEXT,
                table_name TEXT,
                scoring_config TEXT
            )
        ''')
        print(f'[OK] {table}')
    
    print("\n=== 섹션 테이블 생성 ===")
    
    section_tables = [
        'safety_instruction_sections',
        'accident_sections',
        'follow_sop_sections',
        'full_process_sections',
        'change_request_sections',
        'partner_change_sections',
        'partner_standards_sections'
    ]
    
    for table in section_tables:
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table} (
                id SERIAL PRIMARY KEY,
                section_key TEXT UNIQUE NOT NULL,
                section_name TEXT NOT NULL,
                section_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print(f'[OK] {table}')
    
    conn.commit()
    
    print("\n=== 생성된 테이블 확인 ===")
    
    # 생성 확인
    all_tables = (
        ['followsop_cache', 'fullprocess_cache', 'change_requests_cache', 'partner_standards_cache'] +
        config_tables + 
        section_tables
    )
    
    for table in all_tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        exists = cursor.fetchone()[0]
        status = '✅' if exists else '❌'
        print(f'{table}: {status}')
    
    cursor.close()
    conn.close()
    
    print("\n✅ 모든 누락된 테이블 생성 완료!")

if __name__ == "__main__":
    create_missing_tables()