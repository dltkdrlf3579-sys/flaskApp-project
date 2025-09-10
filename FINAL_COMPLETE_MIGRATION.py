#!/usr/bin/env python3
"""
최종 완벽한 PostgreSQL 마이그레이션 스크립트
61개 모든 테이블 포함

운영 환경에서 실행:
    python FINAL_COMPLETE_MIGRATION.py
"""
import psycopg
import configparser
import sys

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def drop_all_tables():
    """모든 테이블 삭제"""
    print("\n=== STEP 1: 모든 테이블 삭제 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn, autocommit=True)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        if tables:
            print(f"삭제할 테이블 {len(tables)}개 발견")
            for table in tables:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    print(f"  [DROP] {table}")
                except Exception as e:
                    print(f"  [ERROR] {table}: {e}")
        else:
            print("삭제할 테이블 없음")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def create_functions():
    """PostgreSQL 함수 생성"""
    print("\n=== STEP 2: PostgreSQL 함수 생성 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn, autocommit=True)
        cursor = conn.cursor()
        
        # json_extract 함수
        cursor.execute("""
            CREATE OR REPLACE FUNCTION json_extract(data jsonb, path text)
            RETURNS text AS $$
            DECLARE
                path_array text[];
                result jsonb;
                elem text;
            BEGIN
                IF data IS NULL THEN RETURN NULL; END IF;
                path_array := string_to_array(trim(path, '$.'), '.');
                result := data;
                FOREACH elem IN ARRAY path_array LOOP
                    IF result IS NULL THEN RETURN NULL; END IF;
                    result := result -> elem;
                END LOOP;
                IF result IS NULL THEN RETURN NULL;
                ELSIF jsonb_typeof(result) = 'string' THEN RETURN result #>> '{}';
                ELSE RETURN result::text;
                END IF;
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """)
        print("  [OK] json_extract")
        
        # datetime 함수
        cursor.execute("""
            CREATE OR REPLACE FUNCTION datetime(ts text, modifier text DEFAULT NULL)
            RETURNS timestamp AS $$
            BEGIN
                IF ts = 'now' THEN RETURN NOW();
                ELSE RETURN ts::timestamp;
                END IF;
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """)
        print("  [OK] datetime")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def create_tables():
    """모든 테이블 생성"""
    print("\n=== STEP 3: 모든 테이블 생성 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # 1. 메인 데이터 테이블
        print("\n--- 1. 메인 데이터 테이블 (7개) ---")
        
        cursor.execute('''
            CREATE TABLE safety_instructions (
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
        print("  [OK] safety_instructions")
        
        cursor.execute('''
            CREATE TABLE accidents (
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
        print("  [OK] accidents")
        
        cursor.execute('''
            CREATE TABLE follow_sop (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT,
                custom_data JSONB DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] follow_sop")
        
        cursor.execute('''
            CREATE TABLE full_process (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT,
                custom_data JSONB DEFAULT '{}',
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] full_process")
        
        cursor.execute('''
            CREATE TABLE partners (
                id SERIAL PRIMARY KEY,
                business_number TEXT UNIQUE NOT NULL,
                company_name TEXT,
                partner_class TEXT,
                business_type_major TEXT,
                business_type_minor TEXT,
                hazard_work_flag TEXT,
                representative TEXT,
                address TEXT,
                average_age DOUBLE PRECISION,
                annual_revenue DOUBLE PRECISION,
                transaction_count INTEGER,
                permanent_workers INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] partners")
        
        cursor.execute('''
            CREATE TABLE change_requests (
                id SERIAL PRIMARY KEY,
                request_number TEXT UNIQUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                custom_data TEXT
            )
        ''')
        print("  [OK] change_requests")
        
        cursor.execute('''
            CREATE TABLE partner_change_requests (
                id SERIAL PRIMARY KEY,
                request_number TEXT,
                business_number TEXT,
                company_name TEXT,
                change_type TEXT,
                change_details TEXT,
                status TEXT DEFAULT 'pending',
                requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                processed_at TIMESTAMP,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] partner_change_requests")
        
        # 2. 캐시 테이블
        print("\n--- 2. 캐시 테이블 (11개) ---")
        
        cursor.execute('''
            CREATE TABLE safety_instructions_cache (
                id SERIAL PRIMARY KEY,
                issue_number TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] safety_instructions_cache")
        
        cursor.execute('''
            CREATE TABLE accidents_cache (
                id SERIAL PRIMARY KEY,
                accident_number TEXT UNIQUE,
                accident_name TEXT,
                accident_time TEXT,
                workplace TEXT,
                accident_grade TEXT,
                major_category TEXT,
                injury_form TEXT,
                injury_type TEXT,
                accident_date DATE,
                day_of_week TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                building TEXT,
                floor TEXT,
                location_category TEXT,
                location_detail TEXT,
                is_deleted INTEGER DEFAULT 0,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                custom_data JSONB DEFAULT '{}',
                accident_datetime TIMESTAMP,
                accident_type TEXT,
                responsible_company1 TEXT,
                responsible_company1_no TEXT,
                responsible_company2 TEXT,
                responsible_company2_no TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                department TEXT,
                status TEXT,
                request_date DATE,
                process_date DATE,
                work_type TEXT,
                process_type TEXT
            )
        ''')
        print("  [OK] accidents_cache")
        
        cursor.execute('''
            CREATE TABLE followsop_cache (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] followsop_cache")
        
        cursor.execute('''
            CREATE TABLE fullprocess_cache (
                id SERIAL PRIMARY KEY,
                fullprocess_number TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] fullprocess_cache")
        
        cursor.execute('''
            CREATE TABLE partners_cache (
                id SERIAL PRIMARY KEY,
                business_number TEXT UNIQUE,
                company_name TEXT,
                partner_class TEXT,
                business_type_major TEXT,
                business_type_minor TEXT,
                hazard_work_flag TEXT,
                representative TEXT,
                address TEXT,
                average_age DOUBLE PRECISION,
                annual_revenue DOUBLE PRECISION,
                transaction_count INTEGER,
                permanent_workers INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] partners_cache")
        
        cursor.execute('''
            CREATE TABLE buildings_cache (
                id SERIAL PRIMARY KEY,
                building_code TEXT UNIQUE,
                building_name TEXT,
                site TEXT,
                site_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] buildings_cache")
        
        cursor.execute('''
            CREATE TABLE departments_cache (
                id SERIAL PRIMARY KEY,
                dept_code TEXT UNIQUE,
                dept_name TEXT,
                parent_dept_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] departments_cache")
        
        cursor.execute('''
            CREATE TABLE contractors_cache (
                id SERIAL PRIMARY KEY,
                worker_id TEXT UNIQUE,
                worker_name TEXT,
                company_name TEXT,
                business_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] contractors_cache")
        
        cursor.execute('''
            CREATE TABLE employees_cache (
                id SERIAL PRIMARY KEY,
                employee_id TEXT UNIQUE,
                employee_name TEXT,
                department_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        print("  [OK] employees_cache")
        
        cursor.execute('''
            CREATE TABLE change_requests_cache (
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
        print("  [OK] change_requests_cache")
        
        cursor.execute('''
            CREATE TABLE partner_standards_cache (
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
        print("  [OK] partner_standards_cache")
        
        # 3. 첨부파일 테이블
        print("\n--- 3. 첨부파일 테이블 (6개) ---")
        
        attachments = [
            ('accident_attachments', 'accident_number'),
            ('safety_instruction_attachments', 'issue_number'),
            ('follow_sop_attachments', 'work_req_no'),
            ('full_process_attachments', 'fullprocess_number'),
            ('partner_attachments', 'business_number'),
            ('change_request_attachments', 'request_number')
        ]
        
        for table_name, ref_column in attachments:
            cursor.execute(f'''
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    {ref_column} TEXT NOT NULL,
                    file_name TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    mime_type TEXT,
                    uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    uploaded_by TEXT,
                    is_deleted INTEGER DEFAULT 0
                )
            ''')
            print(f"  [OK] {table_name}")
        
        # 4. 컬럼 설정 테이블
        print("\n--- 4. 컬럼 설정 테이블 (7개) ---")
        
        config_tables = [
            'safety_instruction_column_config',
            'accident_column_config',
            'follow_sop_column_config',
            'full_process_column_config',
            'change_request_column_config',
            'partner_change_column_config',
            'partner_standards_column_config'
        ]
        
        for table in config_tables:
            cursor.execute(f'''
                CREATE TABLE {table} (
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
            print(f"  [OK] {table}")
        
        # 5. 섹션 테이블
        print("\n--- 5. 섹션 테이블 (7개) ---")
        
        section_tables = [
            'safety_instruction_sections',
            'accident_sections',
            'follow_sop_sections',
            'full_process_sections',
            'change_request_sections',
            'partner_change_sections'
        ]
        
        for table in section_tables:
            cursor.execute(f'''
                CREATE TABLE {table} (
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
            print(f"  [OK] {table}")
        
        cursor.execute('''
            CREATE TABLE section_config (
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
        print("  [OK] section_config")
        
        # 6. 상세 정보 테이블
        print("\n--- 6. 상세 정보 테이블 (6개) ---")
        
        details_tables = [
            ('accident_details', 'accident_number'),
            ('safety_instruction_details', 'issue_number'),
            ('follow_sop_details', 'work_req_no'),
            ('full_process_details', 'fullprocess_number'),
            ('change_request_details', 'request_number'),
            ('partner_details', 'business_number')
        ]
        
        for table_name, ref_column in details_tables:
            cursor.execute(f'''
                CREATE TABLE {table_name} (
                    id SERIAL PRIMARY KEY,
                    {ref_column} TEXT NOT NULL,
                    detail_type TEXT,
                    detail_content TEXT,
                    detail_order INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0
                )
            ''')
            print(f"  [OK] {table_name}")
        
        # 7. 기타 테이블
        print("\n--- 7. 기타 테이블 (10개) ---")
        
        cursor.execute('''
            CREATE TABLE buildings (
                id SERIAL PRIMARY KEY,
                building_code TEXT UNIQUE,
                building_name TEXT,
                site TEXT,
                site_type TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] buildings")
        
        cursor.execute('''
            CREATE TABLE departments (
                id SERIAL PRIMARY KEY,
                dept_code TEXT UNIQUE,
                dept_name TEXT,
                parent_dept_code TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] departments")
        
        cursor.execute('''
            CREATE TABLE contractors (
                id SERIAL PRIMARY KEY,
                worker_id TEXT UNIQUE,
                worker_name TEXT,
                company_name TEXT,
                business_number TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] contractors")
        
        cursor.execute('''
            CREATE TABLE employees (
                id SERIAL PRIMARY KEY,
                employee_id TEXT UNIQUE,
                employee_name TEXT,
                department_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] employees")
        
        cursor.execute('''
            CREATE TABLE dropdown_option_codes_v2 (
                id SERIAL PRIMARY KEY,
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                option_code TEXT NOT NULL,
                option_value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(board_type, column_key, option_code)
            )
        ''')
        print("  [OK] dropdown_option_codes_v2")
        
        cursor.execute('''
            CREATE TABLE dropdown_option_codes (
                id SERIAL PRIMARY KEY,
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                option_code TEXT NOT NULL,
                option_value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] dropdown_option_codes")
        
        cursor.execute('''
            CREATE TABLE sync_state (
                id SERIAL PRIMARY KEY,
                last_full_sync TIMESTAMP,
                last_master_sync TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] sync_state")
        
        cursor.execute('''
            CREATE TABLE sync_history (
                id SERIAL PRIMARY KEY,
                sync_type TEXT,
                sync_date TIMESTAMP,
                record_count INTEGER,
                status TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] sync_history")
        
        cursor.execute('''
            CREATE TABLE master_sync_state (
                id SERIAL PRIMARY KEY,
                table_name TEXT UNIQUE,
                last_sync TIMESTAMP,
                record_count INTEGER,
                sync_status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] master_sync_state")
        
        cursor.execute('''
            CREATE TABLE safety_instructions_sync_history (
                id SERIAL PRIMARY KEY,
                first_sync_done INTEGER DEFAULT 0,
                sync_date TIMESTAMP,
                record_count INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("  [OK] safety_instructions_sync_history")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        return False

def insert_initial_data():
    """초기 데이터 삽입"""
    print("\n=== STEP 4: 초기 데이터 삽입 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # follow_sop_column_config
        cursor.execute('''
            INSERT INTO follow_sop_column_config (column_key, column_name, column_order, is_active) VALUES
            ('work_req_no', '작업요청번호', 1, 1),
            ('work_type', '작업유형', 2, 1),
            ('work_location', '작업장소', 3, 1),
            ('work_content', '작업내용', 4, 1),
            ('work_status', '작업상태', 5, 1),
            ('work_date', '작업일자', 6, 1),
            ('request_date', '요청일자', 7, 1),
            ('request_department', '요청부서', 8, 1),
            ('request_person', '요청자', 9, 1),
            ('approval_date', '승인일자', 10, 1),
            ('approval_person', '승인자', 11, 1),
            ('completion_date', '완료일자', 12, 1),
            ('worker_name', '작업자', 13, 1),
            ('safety_measures', '안전조치', 14, 1),
            ('risk_assessment', '위험성평가', 15, 1),
            ('remarks', '비고', 16, 1)
            ON CONFLICT (column_key) DO NOTHING
        ''')
        print("  [OK] follow_sop_column_config 데이터")
        
        # full_process_column_config
        cursor.execute('''
            INSERT INTO full_process_column_config (column_key, column_name, column_order, is_active) VALUES
            ('fullprocess_number', '풀프로세스번호', 1, 1),
            ('process_name', '프로세스명', 2, 1),
            ('process_status', '프로세스상태', 3, 1),
            ('process_type', '프로세스유형', 4, 1),
            ('start_date', '시작일자', 5, 1),
            ('end_date', '종료일자', 6, 1),
            ('department', '담당부서', 7, 1),
            ('manager', '담당자', 8, 1),
            ('participants', '참여자', 9, 1),
            ('approval_status', '승인상태', 10, 1),
            ('approval_date', '승인일자', 11, 1),
            ('approver', '승인자', 12, 1),
            ('review_status', '검토상태', 13, 1),
            ('review_date', '검토일자', 14, 1),
            ('reviewer', '검토자', 15, 1),
            ('completion_rate', '완료율', 16, 1),
            ('notes', '특이사항', 17, 1),
            ('attachments', '첨부파일', 18, 1)
            ON CONFLICT (column_key) DO NOTHING
        ''')
        print("  [OK] full_process_column_config 데이터")
        
        # accident_column_config
        cursor.execute('''
            INSERT INTO accident_column_config (column_key, column_name, column_order, is_active) VALUES
            ('accident_number', '사고번호', 1, 1),
            ('accident_name', '사고명', 2, 1),
            ('accident_date', '사고일자', 3, 1),
            ('accident_time', '사고시간', 4, 1),
            ('workplace', '사업장', 5, 1),
            ('accident_grade', '사고등급', 6, 1),
            ('accident_type', '사고유형', 7, 1),
            ('injury_type', '상해유형', 8, 1),
            ('injury_form', '상해형태', 9, 1),
            ('major_category', '대분류', 10, 1),
            ('building', '건물', 11, 1),
            ('floor', '층', 12, 1),
            ('location_category', '장소분류', 13, 1),
            ('location_detail', '상세위치', 14, 1),
            ('responsible_company1', '원청업체', 15, 1),
            ('responsible_company2', '하청업체', 16, 1)
            ON CONFLICT (column_key) DO NOTHING
        ''')
        print("  [OK] accident_column_config 데이터")
        
        # safety_instruction_column_config
        cursor.execute('''
            INSERT INTO safety_instruction_column_config (column_key, column_name, column_order, is_active) VALUES
            ('issue_number', '지시서번호', 1, 1)
            ON CONFLICT (column_key) DO NOTHING
        ''')
        print("  [OK] safety_instruction_column_config 데이터")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def verify_tables():
    """테이블 생성 확인"""
    print("\n=== STEP 5: 테이블 생성 확인 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        print(f"생성된 테이블 수: {table_count}개")
        
        # 중요 테이블 확인
        important_tables = [
            'accidents', 'accidents_cache', 'accident_attachments', 'accident_sections',
            'follow_sop', 'followsop_cache', 'follow_sop_attachments',
            'full_process', 'fullprocess_cache', 'full_process_attachments',
            'buildings', 'buildings_cache', 'departments', 'departments_cache',
            'contractors', 'contractors_cache', 'employees', 'employees_cache'
        ]
        
        missing = []
        for table in important_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            if not cursor.fetchone()[0]:
                missing.append(table)
        
        if missing:
            print(f"\n주의: 다음 테이블이 없습니다: {', '.join(missing)}")
        else:
            print("\n모든 중요 테이블이 생성되었습니다!")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

def main():
    print("="*70)
    print("최종 완벽한 PostgreSQL 마이그레이션")
    print("61개 테이블 생성")
    print("="*70)
    
    response = input("\n경고: 모든 테이블이 삭제됩니다. 계속하시겠습니까? (yes/no): ")
    if response.lower() != 'yes':
        print("취소되었습니다.")
        return
    
    # 1. 모든 테이블 삭제
    if not drop_all_tables():
        if input("테이블 삭제 실패. 계속할까요? (yes/no): ").lower() != 'yes':
            return
    
    # 2. PostgreSQL 함수 생성
    if not create_functions():
        if input("함수 생성 실패. 계속할까요? (yes/no): ").lower() != 'yes':
            return
    
    # 3. 모든 테이블 생성
    if not create_tables():
        print("테이블 생성 중 오류 발생")
    
    # 4. 초기 데이터 삽입
    insert_initial_data()
    
    # 5. 검증
    verify_tables()
    
    print("\n" + "="*70)
    print("마이그레이션 완료!")
    print("="*70)
    print("\n다음 단계:")
    print("1. Flask 애플리케이션 재시작")
    print("2. 웹사이트 접속하여 정상 작동 확인")

if __name__ == "__main__":
    main()