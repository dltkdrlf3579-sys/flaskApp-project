#!/usr/bin/env python3
"""
Quick check: ensure *_column_config tables have is_active/is_deleted columns.

Run:
  python tools/CHECK_COLS.py
"""
import configparser

def main():
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    dsn = cfg.get('DATABASE', 'postgres_dsn', fallback=None)

    try:
        import psycopg as _pg
        conn = _pg.connect(dsn)
        driver = 'psycopg3'
    except Exception:
        import psycopg2 as _pg
        conn = _pg.connect(dsn)
        driver = 'psycopg2'
    cur = conn.cursor()

    tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
    ]
    for t in tables:
        cur.execute(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_schema='public' AND table_name=%s
            ORDER BY ordinal_position
            """,
            (t,)
        )
        cols = [r[0] for r in cur.fetchall()]
        print(f"{t}: {'is_active' in cols=}, {'is_deleted' in cols=}")

    cur.close()
    conn.close()

if __name__ == '__main__':
    main()

