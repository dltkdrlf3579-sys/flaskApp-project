#!/usr/bin/env python3
"""
운영 환경에서 누락된 테이블을 제대로 생성하는 스크립트
각 테이블마다 개별 commit하고 실제 생성 여부 확인
"""
import psycopg
import configparser

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def create_table_with_verification(cursor, conn, table_name, create_sql):
    """테이블을 생성하고 실제로 생성되었는지 확인"""
    try:
        # 1. 테이블 생성 시도
        cursor.execute(create_sql)
        
        # 2. 즉시 commit (개별 테이블마다)
        conn.commit()
        
        # 3. 실제로 생성되었는지 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        exists = cursor.fetchone()[0]
        
        if exists:
            print(f"  [SUCCESS] {table_name} - created")
            return True
        else:
            print(f"  [FAILED] {table_name} - not created despite no error")
            return False
            
    except Exception as e:
        conn.rollback()
        print(f"  [ERROR] {table_name} - {str(e)[:50]}")
        return False

def create_missing_tables():
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("="*70)
    print("Missing Tables Fix - Proper Version")
    print("="*70)
    
    success_count = 0
    fail_count = 0
    
    # 1. Cache Tables
    print("\n1. Creating Cache Tables...")
    
    cache_tables = {
        'followsop_cache': '''
            CREATE TABLE IF NOT EXISTS followsop_cache (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''',
        'fullprocess_cache': '''
            CREATE TABLE IF NOT EXISTS fullprocess_cache (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''',
        'change_requests_cache': '''
            CREATE TABLE IF NOT EXISTS change_requests_cache (
                id SERIAL PRIMARY KEY,
                request_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''',
        'partner_standards_cache': '''
            CREATE TABLE IF NOT EXISTS partner_standards_cache (
                id SERIAL PRIMARY KEY,
                standard_number TEXT UNIQUE,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        '''
    }
    
    for table_name, create_sql in cache_tables.items():
        if create_table_with_verification(cursor, conn, table_name, create_sql):
            success_count += 1
        else:
            fail_count += 1
    
    # 2. Column Config Tables
    print("\n2. Creating Column Config Tables...")
    
    config_tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_change_column_config',
        'partner_standards_column_config'  # 이것도 추가
    ]
    
    config_create_sql = '''
        CREATE TABLE IF NOT EXISTS {} (
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
    '''
    
    for table in config_tables:
        if create_table_with_verification(cursor, conn, table, config_create_sql.format(table)):
            success_count += 1
        else:
            fail_count += 1
    
    # 3. Final Verification
    print("\n" + "="*70)
    print("FINAL VERIFICATION")
    print("="*70)
    
    all_tables = list(cache_tables.keys()) + config_tables
    
    missing = []
    existing = []
    
    for table in all_tables:
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table,))
        exists = cursor.fetchone()[0]
        
        if exists:
            existing.append(table)
        else:
            missing.append(table)
    
    print(f"\nSummary:")
    print(f"  Total tables checked: {len(all_tables)}")
    print(f"  Successfully created: {success_count}")
    print(f"  Failed to create: {fail_count}")
    print(f"  Currently existing: {len(existing)}")
    print(f"  Still missing: {len(missing)}")
    
    if missing:
        print(f"\nSTILL MISSING TABLES:")
        for table in missing:
            print(f"  - {table}")
    
    cursor.close()
    conn.close()
    
    if missing:
        print("\nWARNING: Some tables are still missing!")
        print("Check PostgreSQL logs for details.")
    else:
        print("\nSUCCESS: All tables created!")

if __name__ == "__main__":
    create_missing_tables()