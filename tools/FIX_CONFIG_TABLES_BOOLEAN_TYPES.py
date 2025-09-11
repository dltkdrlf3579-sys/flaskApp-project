#!/usr/bin/env python3
"""
Normalize boolean-ish columns in *_column_config tables to INTEGER (0/1).

Why: App SQL uses "... = 1/0" patterns. If these columns are BOOLEAN in
PostgreSQL, comparisons like "is_active = 1" raise
  operator does not exist: boolean = integer
and lead to "current transaction is aborted" cascades.

This script converts BOOLEAN -> INTEGER for commonly used flags and ensures
numeric columns exist, idempotently.

Tables:
  - safety_instruction_column_config
  - accident_column_config
  - follow_sop_column_config
  - full_process_column_config
  - change_request_column_config
  - partner_standards_column_config

Columns converted if BOOLEAN:
  - is_active, is_deleted, is_system, is_required, is_list_display

Other columns ensured:
  - column_order INTEGER DEFAULT 0

Usage:
  python tools/FIX_CONFIG_TABLES_BOOLEAN_TYPES.py
"""
import sys
import configparser


def connect_pg():
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    dsn = cfg.get('DATABASE', 'postgres_dsn', fallback=None)
    if not dsn:
        print('ERROR: DATABASE.postgres_dsn not set in config.ini')
        sys.exit(1)
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
            print('ERROR: cannot connect to PostgreSQL:', e)
            sys.exit(1)
    return conn, driver


def col_type(cur, table, col):
    cur.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table.lower(), col.lower())
    )
    row = cur.fetchone()
    return row[0] if row else None


def has_column(cur, table, col):
    return col_type(cur, table, col) is not None


def ensure_column(cur, table, ddl):
    # ddl like "column_order INTEGER DEFAULT 0"
    name = ddl.split()[0]
    if not has_column(cur, table, name):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        return True
    return False


def convert_bool_to_int(cur, table, col):
    t = col_type(cur, table, col)
    if t and t.lower() == 'boolean':
        cur.execute(
            f"""
            ALTER TABLE {table}
            ALTER COLUMN {col} DROP DEFAULT,
            ALTER COLUMN {col} TYPE INTEGER USING CASE WHEN {col} THEN 1 ELSE 0 END,
            ALTER COLUMN {col} SET DEFAULT 0
            """
        )
        return True
    return False


def main():
    print('=== FIX boolean types in *_column_config (PostgreSQL) ===')
    conn, driver = connect_pg()
    cur = conn.cursor()

    tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_standards_column_config',
    ]
    changed = []
    added_cols = []
    try:
        for t in tables:
            # ensure table exists minimally
            cur.execute(f"CREATE TABLE IF NOT EXISTS {t} (id SERIAL PRIMARY KEY, column_key TEXT UNIQUE, column_name TEXT)")
            # ensure numeric ordering column
            if ensure_column(cur, t, 'column_order INTEGER DEFAULT 0'):
                added_cols.append((t, 'column_order'))
            # convert boolean-ish flags
            for c in ['is_active', 'is_deleted', 'is_system', 'is_required', 'is_list_display']:
                if has_column(cur, t, c):
                    if convert_bool_to_int(cur, t, c):
                        changed.append((t, c))
                else:
                    # add as INTEGER if missing
                    if ensure_column(cur, t, f'{c} INTEGER DEFAULT 0'):
                        added_cols.append((t, c))
        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('ERROR:', e)
        sys.exit(1)
    finally:
        try:
            cur.close(); conn.close()
        except Exception:
            pass

    if changed:
        print('Converted to INTEGER:', ', '.join([f"{t}.{c}" for t,c in changed]))
    if added_cols:
        print('Added columns:', ', '.join([f"{t}.{c}" for t,c in added_cols]))
    if not changed and not added_cols:
        print('No changes needed.')
    print('OK')


if __name__ == '__main__':
    main()
