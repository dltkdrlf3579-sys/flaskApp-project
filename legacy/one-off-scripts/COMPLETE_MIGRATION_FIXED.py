#!/usr/bin/env python3
"""
완벽한 PostgreSQL 마이그레이션 스크립트 (트랜잭션 문제 수정)
각 단계마다 새로운 연결 사용

운영 환경에서 실행:
    python COMPLETE_MIGRATION_FIXED.py
"""
import psycopg
import configparser
import sys
import traceback

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def drop_all_tables():
    """모든 테이블 삭제 (새 연결 사용)"""
    print("\n=== STEP 1: 모든 테이블 삭제 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn, autocommit=True)  # autocommit 모드
        cursor = conn.cursor()
        
        # 모든 테이블 목록 가져오기
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
        print(f"ERROR in drop_all_tables: {e}")
        return False

def create_postgresql_functions():
    """PostgreSQL 호환 함수 생성 (새 연결 사용)"""
    print("\n=== STEP 2: PostgreSQL 함수 생성 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn, autocommit=True)  # autocommit 모드
        cursor = conn.cursor()
        
        # json_extract 함수
        try:
            cursor.execute("DROP FUNCTION IF EXISTS json_extract(jsonb, text)")
        except:
            pass
            
        cursor.execute("""
            CREATE OR REPLACE FUNCTION json_extract(data jsonb, path text)
            RETURNS text AS $$
            DECLARE
                path_array text[];
                result jsonb;
                elem text;
            BEGIN
                IF data IS NULL THEN
                    RETURN NULL;
                END IF;
                
                path_array := string_to_array(trim(path, '$.'), '.');
                result := data;
                
                FOREACH elem IN ARRAY path_array LOOP
                    IF result IS NULL THEN
                        RETURN NULL;
                    END IF;
                    result := result -> elem;
                END LOOP;
                
                IF result IS NULL THEN
                    RETURN NULL;
                ELSIF jsonb_typeof(result) = 'string' THEN
                    RETURN result #>> '{}';
                ELSE
                    RETURN result::text;
                END IF;
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """)
        print("  [OK] json_extract 함수 생성")
        
        # datetime 함수
        try:
            cursor.execute("DROP FUNCTION IF EXISTS datetime(text, text)")
        except:
            pass
            
        cursor.execute("""
            CREATE OR REPLACE FUNCTION datetime(ts text, modifier text DEFAULT NULL)
            RETURNS timestamp AS $$
            BEGIN
                IF ts = 'now' THEN
                    RETURN NOW();
                ELSE
                    RETURN ts::timestamp;
                END IF;
            END;
            $$ LANGUAGE plpgsql IMMUTABLE;
        """)
        print("  [OK] datetime 함수 생성")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in create_postgresql_functions: {e}")
        traceback.print_exc()
        return False

def create_main_tables():
    """메인 테이블 생성"""
    print("\n--- 메인 테이블 생성 ---")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        tables = [
            ('safety_instructions', '''
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
            '''),
            ('accidents', '''
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
            '''),
            ('follow_sop', '''
                CREATE TABLE IF NOT EXISTS follow_sop (
                    id SERIAL PRIMARY KEY,
                    work_req_no TEXT,
                    custom_data JSONB DEFAULT '{}',
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('full_process', '''
                CREATE TABLE IF NOT EXISTS full_process (
                    id SERIAL PRIMARY KEY,
                    fullprocess_number TEXT,
                    custom_data JSONB DEFAULT '{}',
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('partners', '''
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
                    average_age DOUBLE PRECISION,
                    annual_revenue DOUBLE PRECISION,
                    transaction_count INTEGER,
                    permanent_workers INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('change_requests', '''
                CREATE TABLE IF NOT EXISTS change_requests (
                    id SERIAL PRIMARY KEY,
                    request_number TEXT UNIQUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    custom_data TEXT
                )
            '''),
            ('partner_change_requests', '''
                CREATE TABLE IF NOT EXISTS partner_change_requests (
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
        ]
        
        for table_name, create_sql in tables:
            try:
                cursor.execute(create_sql)
                print(f"  [OK] {table_name}")
            except Exception as e:
                print(f"  [ERROR] {table_name}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in create_main_tables: {e}")
        return False

def create_cache_tables():
    """캐시 테이블 생성"""
    print("\n--- 캐시 테이블 생성 ---")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        tables = [
            ('safety_instructions_cache', '''
                CREATE TABLE IF NOT EXISTS safety_instructions_cache (
                    id SERIAL PRIMARY KEY,
                    issue_number TEXT UNIQUE,
                    custom_data JSONB DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0
                )
            '''),
            ('accidents_cache', '''
                CREATE TABLE IF NOT EXISTS accidents_cache (
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
            '''),
            ('followsop_cache', '''
                CREATE TABLE IF NOT EXISTS followsop_cache (
                    id SERIAL PRIMARY KEY,
                    work_req_no TEXT UNIQUE,
                    custom_data JSONB DEFAULT '{}',
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0
                )
            '''),
            ('fullprocess_cache', '''
                CREATE TABLE IF NOT EXISTS fullprocess_cache (
                    id SERIAL PRIMARY KEY,
                    fullprocess_number TEXT UNIQUE,
                    custom_data JSONB DEFAULT '{}',
                    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_deleted INTEGER DEFAULT 0
                )
            '''),
            ('partners_cache', '''
                CREATE TABLE IF NOT EXISTS partners_cache (
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
            '''),
            ('change_requests_cache', '''
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
            '''),
            ('partner_standards_cache', '''
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
        ]
        
        for table_name, create_sql in tables:
            try:
                cursor.execute(create_sql)
                print(f"  [OK] {table_name}")
            except Exception as e:
                print(f"  [ERROR] {table_name}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in create_cache_tables: {e}")
        return False

def create_config_tables():
    """설정 테이블 생성"""
    print("\n--- 컬럼 설정 테이블 생성 ---")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        config_tables = [
            'safety_instruction_column_config',
            'accident_column_config',
            'follow_sop_column_config',
            'full_process_column_config',
            'change_request_column_config',
            'partner_change_column_config'
        ]
        
        for table in config_tables:
            try:
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
                print(f"  [OK] {table}")
            except Exception as e:
                print(f"  [ERROR] {table}: {e}")
                conn.rollback()
                continue
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in create_config_tables: {e}")
        return False

def create_section_tables():
    """섹션 테이블 생성"""
    print("\n--- 섹션 테이블 생성 ---")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        section_tables = [
            'safety_instruction_sections',
            'accident_sections',
            'follow_sop_sections',
            'full_process_sections',
            'change_request_sections',
            'partner_change_sections'
        ]
        
        for table in section_tables:
            try:
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
                print(f"  [OK] {table}")
            except Exception as e:
                print(f"  [ERROR] {table}: {e}")
                conn.rollback()
                continue
        
        # section_config 테이블도 생성
        try:
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
            print("  [OK] section_config")
        except Exception as e:
            print(f"  [ERROR] section_config: {e}")
        
        # dropdown_option_codes_v2 테이블
        try:
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
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
        except Exception as e:
            print(f"  [ERROR] dropdown_option_codes_v2: {e}")
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in create_section_tables: {e}")
        return False

def insert_initial_data():
    """초기 컬럼 설정 데이터 삽입"""
    print("\n=== STEP 4: 초기 데이터 삽입 ===")
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # follow_sop_column_config
        try:
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
            print("  [OK] follow_sop_column_config 초기 데이터")
        except Exception as e:
            print(f"  [ERROR] follow_sop_column_config: {e}")
            conn.rollback()
        
        # full_process_column_config
        try:
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
            print("  [OK] full_process_column_config 초기 데이터")
        except Exception as e:
            print(f"  [ERROR] full_process_column_config: {e}")
            conn.rollback()
        
        # accident_column_config
        try:
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
            print("  [OK] accident_column_config 초기 데이터")
        except Exception as e:
            print(f"  [ERROR] accident_column_config: {e}")
            conn.rollback()
        
        # safety_instruction_column_config
        try:
            cursor.execute('''
                INSERT INTO safety_instruction_column_config (column_key, column_name, column_order, is_active) VALUES
                ('issue_number', '지시서번호', 1, 1)
                ON CONFLICT (column_key) DO NOTHING
            ''')
            print("  [OK] safety_instruction_column_config 초기 데이터")
        except Exception as e:
            print(f"  [ERROR] safety_instruction_column_config: {e}")
            conn.rollback()
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"ERROR in insert_initial_data: {e}")
        return False

def main():
    print("="*70)
    print("완벽한 PostgreSQL 마이그레이션 시작 (수정된 버전)")
    print("="*70)
    
    # 경고
    response = input("\n경고: 모든 테이블이 삭제됩니다. 계속하시겠습니까? (yes/no): ")
    if response.lower() != 'yes':
        print("취소되었습니다.")
        return
    
    # 1. 모든 테이블 삭제
    if not drop_all_tables():
        print("테이블 삭제 실패. 계속하시겠습니까? (yes/no): ")
        if input().lower() != 'yes':
            return
    
    # 2. PostgreSQL 함수 생성
    if not create_postgresql_functions():
        print("함수 생성 실패. 계속하시겠습니까? (yes/no): ")
        if input().lower() != 'yes':
            return
    
    # 3. 테이블 생성 (단계별로)
    print("\n=== STEP 3: 모든 테이블 생성 ===")
    
    create_main_tables()
    create_cache_tables()
    create_config_tables()
    create_section_tables()
    
    # 4. 초기 데이터 삽입
    insert_initial_data()
    
    # 5. 최종 확인
    print("\n=== STEP 5: 최종 확인 ===")
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
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"확인 중 에러: {e}")
    
    print("\n" + "="*70)
    print("마이그레이션 완료!")
    print("="*70)
    print("\n다음 단계:")
    print("1. Flask 애플리케이션 재시작")
    print("2. 웹사이트 접속하여 정상 작동 확인")

if __name__ == "__main__":
    main()