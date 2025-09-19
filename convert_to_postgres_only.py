"""
PostgreSQL 전용 코드로 전환하는 스크립트
SQLite 호환성 코드를 모두 제거하고 PostgreSQL 전용으로 변경
"""

import re

# app.py 파일 읽기
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# init_db 함수를 PostgreSQL 전용으로 변경
new_init_db = '''def init_db():
    """데이터베이스 초기화 - PostgreSQL 전용"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Pages table - PostgreSQL
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE,
                title TEXT,
                content TEXT
            )
        ''')

        # Dropdown v2 table - PostgreSQL
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
                created_by TEXT,
                updated_by TEXT,
                UNIQUE(board_type, column_key, option_code)
            )
        ''')

        # 컬럼 설정 테이블들 - PostgreSQL
        tables_to_create = [
            'accident_column_config',
            'safety_instruction_column_config',
            'section_config',
            'partner_standards_column_config',
            'follow_sop_column_config',
            'full_process_column_config',
            'safe_workplace_column_config',
        ]

        for table_name in tables_to_create:
            cursor.execute(f\'\'\'
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
            \'\'\')

        # 섹션 테이블들 - PostgreSQL
        section_tables = ['follow_sop_sections', 'full_process_sections', 'safe_workplace_sections']

        for table in section_tables:
            cursor.execute(f\'\'\'
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
            \'\'\')

        conn.commit()
        conn.close()
        logging.info("PostgreSQL 데이터베이스 초기화 완료")

    except Exception as e:
        logging.error(f"[BOOT] PostgreSQL init_db 실패: {e}")
        try:
            conn.rollback()
        except:
            pass
        try:
            conn.close()
        except:
            pass'''

# init_db 함수 찾아서 교체
init_db_start = content.find('def init_db():')
if init_db_start != -1:
    # 다음 def 찾기
    next_def = content.find('\ndef ', init_db_start + 1)
    if next_def == -1:
        next_def = len(content)

    # init_db 함수 교체
    content = content[:init_db_start] + new_init_db + content[next_def:]

    print("✅ init_db 함수를 PostgreSQL 전용으로 변경했습니다.")
else:
    print("❌ init_db 함수를 찾을 수 없습니다.")

# get_db_connection 함수도 PostgreSQL 전용으로 수정
get_db_pattern = r'def get_db_connection\([^)]*\):[^}]+?(?=\ndef\s|\Z)'
get_db_match = re.search(get_db_pattern, content, re.DOTALL)

if get_db_match:
    new_get_db = '''def get_db_connection(database=None):
    """PostgreSQL 전용 DB 연결"""
    try:
        import psycopg2
        from psycopg2.extras import DictCursor

        # PostgreSQL 연결
        conn = psycopg2.connect(
            host=os.getenv('PGHOST', 'localhost'),
            port=os.getenv('PGPORT', 5432),
            database=database or DB_NAME,
            user=os.getenv('PGUSER', 'postgres'),
            password=os.getenv('PGPASSWORD', ''),
            cursor_factory=DictCursor
        )

        # PostgreSQL 표시를 위한 속성 추가
        conn.is_postgres = True

        return conn
    except Exception as e:
        logging.error(f"PostgreSQL 연결 실패: {e}")
        raise'''

    content = content[:get_db_match.start()] + new_get_db + content[get_db_match.end():]
    print("✅ get_db_connection 함수를 PostgreSQL 전용으로 변경했습니다.")

# 파일 저장
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n✅ PostgreSQL 전용 코드로 전환 완료!")
print("⚠️  주의: 이제 SQLite는 지원하지 않습니다.")