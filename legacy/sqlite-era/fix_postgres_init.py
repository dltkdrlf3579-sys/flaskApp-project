import re

# app.py 읽기
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# init_db 함수 찾기
init_db_start = content.find('def init_db():')
init_db_end = content.find('\n\ndef ', init_db_start + 1)
if init_db_end == -1:
    init_db_end = len(content)

# init_db 함수 내용만 추출
init_db_content = content[init_db_start:init_db_end]

# 수정된 init_db 함수 생성
new_init_db = '''def init_db():
    """데이터베이스 초기화"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # PostgreSQL 여부 확인
        is_postgres = hasattr(conn, 'is_postgres') and conn.is_postgres

        # Pages table
        if is_postgres:
            cursor.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS pages (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE,
                    title TEXT,
                    content TEXT
                )
            \'\'\')
        else:
            cursor.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS pages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    url TEXT UNIQUE,
                    title TEXT,
                    content TEXT
                )
            \'\'\')

        # Dropdown v2 table
        if is_postgres:
            cursor.execute(\'\'\'
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
                    created_by TEXT,
                    updated_by TEXT,
                    UNIQUE(board_type, column_key, option_code)
                )
            \'\'\')
        else:
            cursor.execute(\'\'\'
                CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    board_type TEXT NOT NULL,
                    column_key TEXT NOT NULL,
                    option_code TEXT NOT NULL,
                    option_value TEXT NOT NULL,
                    display_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    created_by TEXT,
                    updated_by TEXT,
                    UNIQUE(board_type, column_key, option_code)
                )
            \'\'\')

        # 기타 테이블들도 같은 패턴으로 변경...
        tables_to_create = [
            ('accident_column_config', True),
            ('safety_instruction_column_config', True),
            ('section_config', True),
            ('partner_standards_column_config', True),
            ('follow_sop_column_config', True),
            ('full_process_column_config', True),
            ('safe_workplace_column_config', True),
        ]

        for table_name, has_columns in tables_to_create:
            if is_postgres:
                sql = f\'\'\'
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id SERIAL PRIMARY KEY,
                        column_key TEXT UNIQUE NOT NULL,
                        column_name TEXT NOT NULL,
                        column_type TEXT DEFAULT 'text',
                        column_order INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        is_deleted INTEGER DEFAULT 0,
                        dropdown_options TEXT,
                        tab TEXT,
                        column_span INTEGER DEFAULT 1,
                        linked_columns TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\'
            else:
                sql = f\'\'\'
                    CREATE TABLE IF NOT EXISTS {table_name} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        column_key TEXT UNIQUE NOT NULL,
                        column_name TEXT NOT NULL,
                        column_type TEXT DEFAULT 'text',
                        column_order INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        is_deleted INTEGER DEFAULT 0,
                        dropdown_options TEXT,
                        tab TEXT,
                        column_span INTEGER DEFAULT 1,
                        linked_columns TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\'

            try:
                cursor.execute(sql)
            except Exception as e:
                # 테이블이 이미 존재하면 무시
                conn.rollback()

        # 섹션 테이블들
        section_tables = ['follow_sop_sections', 'full_process_sections', 'safe_workplace_sections']

        for table in section_tables:
            if is_postgres:
                sql = f\'\'\'
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
                \'\'\'
            else:
                sql = f\'\'\'
                    CREATE TABLE IF NOT EXISTS {table} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        section_key TEXT UNIQUE NOT NULL,
                        section_name TEXT NOT NULL,
                        section_order INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        is_deleted INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                \'\'\'

            try:
                cursor.execute(sql)
            except Exception as e:
                conn.rollback()

        conn.commit()
        conn.close()
        logging.info("Database initialized successfully")

    except Exception as e:
        logging.error(f"[BOOT] init_db failed: {e}")
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass'''

# 전체 파일 내용 수정
new_content = content[:init_db_start] + new_init_db + content[init_db_end:]

# 파일 저장
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print("init_db 함수를 PostgreSQL 호환으로 수정했습니다.")