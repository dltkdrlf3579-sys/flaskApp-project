#!/usr/bin/env python3
"""
PostgreSQL schema repair for production.

Fixes the most common column/table mismatches observed after migration so the
app stops throwing errors (and psycopg 'pipeline aborted' warnings disappear).

Idempotent: you can run multiple times safely.

What it ensures (non-destructive):
- Core sections tables exist and have required columns
- section_config has required columns/unique constraint
- *_column_config tables have required columns used by the app
- dropdown_option_codes_v2 exists with required columns and unique index
- attachments tables have file_name/file_path/file_size columns

Usage:
  python tools/RUN_SCHEMA_REPAIR.py
"""
import configparser
import sys


def _connect():
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    dsn = cfg.get('DATABASE', 'postgres_dsn', fallback=None)
    if not dsn:
        print("ERROR: [DATABASE].postgres_dsn is not set in config.ini")
        sys.exit(1)

    # Try psycopg v3, fallback to psycopg2
    try:
        import psycopg as _pg
        conn = _pg.connect(dsn)
        driver = 'psycopg3'
    except Exception:
        try:
            import psycopg2 as _pg2
            conn = _pg2.connect(dsn)
            driver = 'psycopg2'
        except Exception as e:
            print(f"ERROR: cannot connect PostgreSQL: {e}")
            sys.exit(1)
    return conn, driver


def exec_safe(cur, sql: str, params=None):
    try:
        if params is not None:
            cur.execute(sql, params)
        else:
            cur.execute(sql)
        return True
    except Exception as e:
        head = sql.strip().splitlines()[0][:200]
        print(f"WARN: {e}\n  SQL: {head}...")
        return False


def column_exists(cur, table: str, column: str) -> bool:
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name=%s AND column_name=%s",
        (table.lower(), column.lower())
    )
    return cur.fetchone() is not None


def ensure_column(cur, table: str, column: str, ddl: str):
    if not column_exists(cur, table, column):
        exec_safe(cur, f"ALTER TABLE {table} ADD COLUMN {ddl}")


def ensure_unique_index(cur, name: str, table: str, cols: str):
    # Create unique index if not exists
    exec_safe(cur, f"CREATE UNIQUE INDEX IF NOT EXISTS {name} ON {table} ({cols})")


def ensure_sections(cur):
    # Dedicated sections tables
    for t in ['safety_instruction_sections', 'follow_sop_sections', 'full_process_sections']:
        exec_safe(cur, f"""
            CREATE TABLE IF NOT EXISTS {t} (
                id SERIAL PRIMARY KEY,
                section_key TEXT UNIQUE NOT NULL,
                section_name TEXT NOT NULL,
                section_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    # Seed defaults if empty
    default_maps = {
        'safety_instruction_sections': [('basic_info','기본정보'),('violation_info','위반정보'),('additional','추가정보')],
        'follow_sop_sections': [('basic_info','기본정보'),('work_info','작업정보'),('additional','추가정보')],
        'full_process_sections': [('basic_info','기본정보'),('process_info','프로세스정보'),('additional','추가정보')],
    }
    for table, items in default_maps.items():
        for i, (key, name) in enumerate(items, start=1):
            exec_safe(
                cur,
                f"INSERT INTO {table} (section_key, section_name, section_order, is_active, is_deleted) "
                f"VALUES (%s, %s, %s, 1, 0) ON CONFLICT (section_key) DO NOTHING",
                (key, name, i)
            )


def ensure_section_config(cur):
    exec_safe(cur, """
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
    """)
    ensure_column(cur, 'section_config', 'is_deleted', 'is_deleted INTEGER DEFAULT 0')
    ensure_unique_index(cur, 'uniq_section_config_board_key', 'section_config', 'board_type, section_key')
    # Seed defaults for boards that use section_config (safety_instruction, accident)
    # safety_instruction
    cur.execute("SELECT COUNT(*) FROM section_config WHERE board_type = %s", ('safety_instruction',))
    if (cur.fetchone() or [0])[0] == 0:
        exec_safe(cur, (
            "INSERT INTO section_config (board_type, section_key, section_name, section_order, is_active, is_deleted) "
            "VALUES (%s,%s,%s,%s,1,0),(%s,%s,%s,%s,1,0),(%s,%s,%s,%s,1,0)"
        ), (
            'safety_instruction','basic_info','기본정보',1,
            'safety_instruction','violation_info','위반정보',2,
            'safety_instruction','additional','추가기입정보',3,
        ))
    # accident
    cur.execute("SELECT COUNT(*) FROM section_config WHERE board_type = %s", ('accident',))
    if (cur.fetchone() or [0])[0] == 0:
        exec_safe(cur, (
            "INSERT INTO section_config (board_type, section_key, section_name, section_order, is_active, is_deleted) "
            "VALUES (%s,%s,%s,%s,1,0),(%s,%s,%s,%s,1,0),(%s,%s,%s,%s,1,0),(%s,%s,%s,%s,1,0)"
        ), (
            'accident','basic_info','기본정보',1,
            'accident','accident_info','사고정보',2,
            'accident','location_info','장소정보',3,
            'accident','additional','추가정보',4,
        ))


def ensure_column_config_tables(cur):
    tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_standards_column_config',
    ]
    for t in tables:
        exec_safe(cur, f"""
            CREATE TABLE IF NOT EXISTS {t} (
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
        """)
        # Ensure commonly missing columns
        ensure_column(cur, t, 'tab', 'tab TEXT')
        ensure_column(cur, t, 'column_span', 'column_span INTEGER DEFAULT 1')
        ensure_column(cur, t, 'linked_columns', 'linked_columns TEXT')
        ensure_column(cur, t, 'is_deleted', 'is_deleted INTEGER DEFAULT 0')
        ensure_column(cur, t, 'is_list_display', 'is_list_display INTEGER DEFAULT 0')
        ensure_column(cur, t, 'is_system', 'is_system INTEGER DEFAULT 0')
        ensure_column(cur, t, 'is_required', 'is_required INTEGER DEFAULT 0')
        ensure_column(cur, t, 'input_type', "input_type TEXT DEFAULT 'text'")
        ensure_column(cur, t, 'scoring_config', 'scoring_config TEXT')

    # Seed accident_column_config minimal set if empty
    cur.execute("SELECT COUNT(*) FROM accident_column_config")
    if (cur.fetchone() or [0])[0] == 0:
        rows = [
            ('accident_number','사고번호',1),
            ('accident_name','사고명',2),
            ('accident_date','사고일자',3),
            ('accident_time','사고시간',4),
            ('workplace','사업장',5),
            ('accident_grade','사고등급',6),
            ('accident_type','사고유형',7),
            ('injury_type','상해유형',8),
            ('injury_form','상해형태',9),
            ('major_category','대분류',10),
            ('building','건물',11),
            ('floor','층',12),
            ('location_category','장소분류',13),
            ('location_detail','상세위치',14),
            ('responsible_company1','원청업체',15),
            ('responsible_company2','하청업체',16),
        ]
        for key, name, order in rows:
            exec_safe(
                cur,
                "INSERT INTO accident_column_config (column_key, column_name, column_order, is_active) VALUES (%s,%s,%s,1) "
                "ON CONFLICT (column_key) DO NOTHING",
                (key, name, order)
            )


def ensure_dropdown_codes(cur):
    # canonical v2 table used by app
    exec_safe(cur, """
        CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
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
    """)
    ensure_unique_index(cur, 'idx_doc_v2_uniq', 'dropdown_option_codes_v2', 'board_type, column_key, option_code')
    # Migrate from older shape if present
    # code/name -> option_code/option_value
    if column_exists(cur, 'dropdown_option_codes_v2', 'code') and not column_exists(cur, 'dropdown_option_codes_v2', 'option_code'):
        exec_safe(cur, "ALTER TABLE dropdown_option_codes_v2 ADD COLUMN option_code TEXT")
        exec_safe(cur, "UPDATE dropdown_option_codes_v2 SET option_code = code WHERE option_code IS NULL")
    if column_exists(cur, 'dropdown_option_codes_v2', 'name') and not column_exists(cur, 'dropdown_option_codes_v2', 'option_value'):
        exec_safe(cur, "ALTER TABLE dropdown_option_codes_v2 ADD COLUMN option_value TEXT")
        exec_safe(cur, "UPDATE dropdown_option_codes_v2 SET option_value = name WHERE option_value IS NULL")


def ensure_attachments(cur):
    tables = [
        ('accident_attachments', 'accident_number'),
        ('safety_instruction_attachments', 'issue_number'),
        ('follow_sop_attachments', 'work_req_no'),
        ('full_process_attachments', 'fullprocess_number'),
        ('partner_attachments', None),
    ]
    for t, ref in tables:
        exec_safe(cur, f"""
            CREATE TABLE IF NOT EXISTS {t} (
                id SERIAL PRIMARY KEY,
                {ref + ' TEXT NOT NULL,' if ref else ''}
                file_name TEXT,
                file_path TEXT,
                file_size INTEGER,
                description TEXT,
                upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by TEXT
            )
        """)
        ensure_column(cur, t, 'file_name', 'file_name TEXT')
        ensure_column(cur, t, 'file_path', 'file_path TEXT')
        ensure_column(cur, t, 'file_size', 'file_size INTEGER')
        ensure_column(cur, t, 'description', 'description TEXT')
        ensure_column(cur, t, 'upload_date', 'upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP')


def ensure_main_tables(cur):
    """Ensure core data tables used by the app exist (follow_sop, full_process)."""
    # follow_sop
    exec_safe(cur, """
        CREATE TABLE IF NOT EXISTS follow_sop (
            work_req_no TEXT PRIMARY KEY,
            custom_data JSONB DEFAULT '{}'::JSONB,
            is_deleted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)
    # full_process
    exec_safe(cur, """
        CREATE TABLE IF NOT EXISTS full_process (
            fullprocess_number TEXT PRIMARY KEY,
            custom_data JSONB DEFAULT '{}'::JSONB,
            is_deleted INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_by TEXT
        )
    """)


def ensure_caches(cur):
    """Ensure *_cache tables and required columns used by the app exist."""
    # safety_instructions_cache
    exec_safe(cur, """
        CREATE TABLE IF NOT EXISTS safety_instructions_cache (
            id SERIAL PRIMARY KEY
        )
    """)
    ensure_column(cur, 'safety_instructions_cache', 'issue_number', 'issue_number TEXT UNIQUE')
    ensure_column(cur, 'safety_instructions_cache', 'issue_title', 'issue_title TEXT')
    ensure_column(cur, 'safety_instructions_cache', 'issue_date', 'issue_date DATE')
    ensure_column(cur, 'safety_instructions_cache', 'instruction_type', 'instruction_type TEXT')
    ensure_column(cur, 'safety_instructions_cache', 'department', 'department TEXT')
    ensure_column(cur, 'safety_instructions_cache', 'target_audience', 'target_audience TEXT')
    ensure_column(cur, 'safety_instructions_cache', 'related_regulation', 'related_regulation TEXT')
    ensure_column(cur, 'safety_instructions_cache', 'custom_data', "custom_data JSONB DEFAULT '{}'::JSONB")
    ensure_column(cur, 'safety_instructions_cache', 'is_deleted', 'is_deleted INTEGER DEFAULT 0')
    ensure_column(cur, 'safety_instructions_cache', 'created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ensure_column(cur, 'safety_instructions_cache', 'updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
    ensure_column(cur, 'safety_instructions_cache', 'synced_at', 'synced_at TIMESTAMP')

    # accidents_cache (subset required by views)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS accidents_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('accident_number', 'accident_number TEXT UNIQUE'),
        ('accident_name', 'accident_name TEXT'),
        ('workplace', 'workplace TEXT'),
        ('accident_grade', 'accident_grade TEXT'),
        ('accident_date', 'accident_date DATE'),
        ('building', 'building TEXT'),
        ('floor', 'floor TEXT'),
        ('location_category', 'location_category TEXT'),
        ('location_detail', 'location_detail TEXT'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
    ]:
        ensure_column(cur, 'accidents_cache', col, ddl)

    # followsop_cache (legacy) and follow_sop_cache (current)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS followsop_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('work_req_no', 'work_req_no TEXT UNIQUE'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('synced_at', 'synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]:
        ensure_column(cur, 'followsop_cache', col, ddl)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS follow_sop_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('work_req_no', 'work_req_no TEXT UNIQUE'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('synced_at', 'synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]:
        ensure_column(cur, 'follow_sop_cache', col, ddl)

    # fullprocess_cache (legacy) and full_process_cache (current)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS fullprocess_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('fullprocess_number', 'fullprocess_number TEXT UNIQUE'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('synced_at', 'synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]:
        ensure_column(cur, 'fullprocess_cache', col, ddl)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS full_process_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('fullprocess_number', 'fullprocess_number TEXT UNIQUE'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('synced_at', 'synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]:
        ensure_column(cur, 'full_process_cache', col, ddl)

    # change_requests_cache (used in some views)
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS change_requests_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('request_number', 'request_number TEXT UNIQUE'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('synced_at', 'synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]:
        ensure_column(cur, 'change_requests_cache', col, ddl)

    # partners_cache/buildings_cache/departments_cache/employees_cache minimal shape
    exec_safe(cur, "CREATE TABLE IF NOT EXISTS partners_cache (id SERIAL PRIMARY KEY)")
    for col, ddl in [
        ('business_number', 'business_number TEXT UNIQUE'),
        ('company_name', 'company_name TEXT'),
        ('partner_class', 'partner_class TEXT'),
        ('address', 'address TEXT'),
        ('custom_data', "custom_data JSONB DEFAULT '{}'::JSONB"),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
    ]:
        ensure_column(cur, 'partners_cache', col, ddl)

    for t, uniq_col in [('buildings_cache','building_code'), ('departments_cache','dept_code'), ('employees_cache','employee_id')]:
        exec_safe(cur, f"CREATE TABLE IF NOT EXISTS {t} (id SERIAL PRIMARY KEY)")
        ensure_column(cur, t, uniq_col, f"{uniq_col} TEXT UNIQUE")
        ensure_column(cur, t, 'created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ensure_column(cur, t, 'updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP')
        ensure_column(cur, t, 'is_deleted', 'is_deleted INTEGER DEFAULT 0')


def main():
    print("=== RUN SCHEMA REPAIR (PostgreSQL) ===")
    conn, driver = _connect()
    print(f"Connected via {driver}")
    cur = conn.cursor()

    try:
        ensure_sections(cur)
        ensure_section_config(cur)
        ensure_column_config_tables(cur)
        ensure_dropdown_codes(cur)
        ensure_attachments(cur)
        ensure_caches(cur)
        ensure_main_tables(cur)

        conn.commit()
        print("OK: schema repair completed.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f"FAILED: {e}")
        sys.exit(1)
    finally:
        try:
            cur.close()
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
