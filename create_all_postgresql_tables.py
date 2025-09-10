#!/usr/bin/env python3
"""
PostgreSQL 모든 메인 테이블 생성 스크립트
운영 환경에서 PostgreSQL 초기 셋업 시 실행

Usage:
    python create_all_postgresql_tables.py
"""
import psycopg
import configparser
import sys

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def create_all_tables():
    """모든 필수 테이블 생성"""
    try:
        dsn = get_postgres_dsn()
        print(f'Connecting to PostgreSQL...')
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        print('PostgreSQL 메인 테이블 생성 시작...\n')

        # 1. safety_instructions 테이블 (중요!)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_instructions (
                id SERIAL PRIMARY KEY,
                issue_number TEXT UNIQUE NOT NULL,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                disciplined_person TEXT,
                disciplined_person_id TEXT,
                violation_content TEXT,
                detailed_content TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] safety_instructions 테이블 생성')

        # 2. accidents 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accidents (
                id SERIAL PRIMARY KEY,
                accident_number TEXT UNIQUE NOT NULL,
                accident_name TEXT,
                workplace TEXT,
                accident_grade TEXT,
                accident_date DATE,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] accidents 테이블 생성')

        # 3. follow_sop 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS follow_sop (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT UNIQUE NOT NULL,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] follow_sop 테이블 생성')

        # 4. full_process 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS full_process (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT UNIQUE NOT NULL,
                primary_company TEXT,
                primary_business_number TEXT,
                subcontractor TEXT,
                subcontractor_business_number TEXT,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] full_process 테이블 생성')

        # 5. change_requests 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS change_requests (
                id SERIAL PRIMARY KEY,
                request_number TEXT UNIQUE NOT NULL,
                request_type TEXT,
                status TEXT DEFAULT 'pending',
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] change_requests 테이블 생성')

        # 6. partner_change_requests 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partner_change_requests (
                id SERIAL PRIMARY KEY,
                request_id TEXT UNIQUE NOT NULL,
                business_number TEXT,
                company_name TEXT,
                change_type TEXT,
                status TEXT DEFAULT 'pending',
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print('[OK] partner_change_requests 테이블 생성')

        # 7. partners 테이블 (마스터 데이터)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partners (
                id SERIAL PRIMARY KEY,
                business_number TEXT UNIQUE NOT NULL,
                company_name TEXT,
                partner_class TEXT,
                business_type_major TEXT,
                business_type_minor TEXT,
                hazard_work_flag TEXT,
                representative TEXT,
                address TEXT,
                average_age FLOAT,
                annual_revenue FLOAT,
                transaction_count INTEGER,
                permanent_workers INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print('[OK] partners 테이블 생성')

        print('\n--- 컬럼 설정 테이블들 생성 중 ---')
        
        # 8. 컬럼 설정 테이블들 (모든 보드 타입)
        column_config_tables = [
            'safety_instruction_column_config',
            'accident_column_config', 
            'follow_sop_column_config',
            'full_process_column_config',
            'change_request_column_config',
            'partner_change_column_config'
        ]

        for table in column_config_tables:
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
            print(f'[OK] {table} 테이블 생성')

        print('\n--- 섹션 테이블들 생성 중 ---')

        # 9. 섹션 테이블들
        section_tables = [
            'safety_instruction_sections',
            'accident_sections',
            'follow_sop_sections', 
            'full_process_sections',
            'change_request_sections'
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
            print(f'[OK] {table} 테이블 생성')

        # 10. section_config 테이블 (통합 섹션 설정)
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS section_config (
                id SERIAL PRIMARY KEY,
                board_type TEXT NOT NULL,
                section_key TEXT NOT NULL,
                section_name TEXT NOT NULL,
                section_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(board_type, section_key)
            )
        ''')
        print('[OK] section_config 테이블 생성')

        print('\n--- 상세 내용 테이블들 생성 중 ---')

        # 11. 상세 내용 테이블들
        detail_tables = [
            ('safety_instruction_details', 'issue_number'),
            ('accident_details', 'accident_number'),
            ('follow_sop_details', 'work_req_no'),
            ('full_process_details', 'fullprocess_number')
        ]

        for table, ref_col in detail_tables:
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    id SERIAL PRIMARY KEY,
                    {ref_col} TEXT UNIQUE NOT NULL,
                    detailed_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            print(f'[OK] {table} 테이블 생성')

        print('\n--- 첨부파일 테이블들 생성 중 ---')

        # 12. 첨부파일 테이블들
        attachment_tables = [
            ('safety_instruction_attachments', 'issue_number'),
            ('accident_attachments', 'accident_number'),
            ('follow_sop_attachments', 'work_req_no'),
            ('full_process_attachments', 'fullprocess_number')
        ]

        for table, ref_col in attachment_tables:
            cursor.execute(f'''
                CREATE TABLE IF NOT EXISTS {table} (
                    id SERIAL PRIMARY KEY,
                    {ref_col} TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by TEXT
                )
            ''')
            print(f'[OK] {table} 테이블 생성')

        print('\n--- 기타 필수 테이블들 생성 중 ---')

        # 13. 코드 관리 테이블들
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dropdown_codes (
                id SERIAL PRIMARY KEY,
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                code_value TEXT NOT NULL,
                code_label TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(board_type, column_key, code_value)
            )
        ''')
        print('[OK] dropdown_codes 테이블 생성')

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dropdown_items (
                id SERIAL PRIMARY KEY,
                dropdown_key TEXT NOT NULL,
                item_value TEXT NOT NULL,
                item_label TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(dropdown_key, item_value)
            )
        ''')
        print('[OK] dropdown_items 테이블 생성')

        # 14. 동기화 이력 테이블
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS sync_history (
                id SERIAL PRIMARY KEY,
                sync_type TEXT NOT NULL,
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                record_count INTEGER DEFAULT 0,
                status TEXT DEFAULT 'completed',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print('[OK] sync_history 테이블 생성')

        conn.commit()
        print('\n' + '='*50)
        print('[완료] 모든 PostgreSQL 테이블 생성 완료!')
        print('='*50)
        
        # 생성된 테이블 개수 확인
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        print(f'\n총 {table_count}개의 테이블이 존재합니다.')
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f'\n[ERROR] 테이블 생성 실패: {e}')
        sys.exit(1)

if __name__ == '__main__':
    create_all_tables()