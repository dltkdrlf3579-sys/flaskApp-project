#!/usr/bin/env python3
"""
PostgreSQL schema compatibility fixer for this portal.

Fixes mismatches between earlier migration scripts and the application code
expectations so that initial sync and content sync run cleanly.

What it does:
- Ensure master_sync_state has column last_master_sync and a row with id=1
- Ensure sync_state has a row with id=1
- Add missing requester_* columns to partner_change_requests
- Add UNIQUE constraints needed for ON CONFLICT on follow_sop/full_process

Run:
    python FIX_POSTGRES_SCHEMA_COMPAT.py
"""

import sys
import configparser

def _connect():
    dsn = None
    try:
        cfg = configparser.ConfigParser()
        cfg.read('config.ini', encoding='utf-8')
        dsn = cfg.get('DATABASE', 'postgres_dsn')
    except Exception:
        pass

    if not dsn:
        print("ERROR: postgres_dsn is not set in config.ini [DATABASE]")
        sys.exit(1)

    # Try psycopg v3 then psycopg2
    try:
        import psycopg as _pg
        conn = _pg.connect(dsn, autocommit=True)
        driver = 'psycopg3'
        return conn, driver
    except Exception as e:
        try:
            import psycopg2 as _pg2
            conn = _pg2.connect(dsn)
            conn.autocommit = True
            driver = 'psycopg2'
            return conn, driver
        except Exception as e2:
            print(f"ERROR: could not connect to PostgreSQL. v3 error={e}, v2 error={e2}")
            sys.exit(1)


def col_exists(cur, table, column):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table, column)
    )
    return cur.fetchone() is not None


def constraint_exists(cur, table, constraint_name):
    cur.execute(
        """
        SELECT 1
        FROM information_schema.table_constraints
        WHERE table_schema='public' AND table_name=%s AND constraint_name=%s
        """,
        (table, constraint_name)
    )
    return cur.fetchone() is not None


def has_duplicates(cur, table, column):
    cur.execute(
        f"SELECT {column}, COUNT(*) FROM {table} GROUP BY {column} HAVING COUNT(*) > 1"
    )
    rows = cur.fetchall()
    return len(rows) > 0, rows


def ensure_row_id_one(cur, table):
    # Ensure a row with id=1 exists
    try:
        cur.execute(f"INSERT INTO {table} (id) VALUES (1) ON CONFLICT (id) DO NOTHING")
    except Exception:
        # If table has no 'id' column, ignore
        pass


def main():
    print("=== Fixing PostgreSQL schema for application compatibility ===")
    conn, driver = _connect()
    print(f"Connected using: {driver}")
    cur = conn.cursor()

    # 1) master_sync_state: add last_master_sync + ensure id=1
    try:
        # Create table if a different variant exists; only add column if missing
        if not col_exists(cur, 'master_sync_state', 'last_master_sync'):
            print("- Adding column master_sync_state.last_master_sync TIMESTAMP")
            cur.execute("ALTER TABLE master_sync_state ADD COLUMN last_master_sync TIMESTAMP")
        ensure_row_id_one(cur, 'master_sync_state')
    except Exception as e:
        print(f"WARNING: master_sync_state fix failed: {e}")

    # 2) sync_state: ensure id=1 row (column exists from migrations)
    try:
        ensure_row_id_one(cur, 'sync_state')
    except Exception as e:
        print(f"WARNING: sync_state id=1 ensure failed: {e}")

    # 3) partner_change_requests: add requester_* columns if missing
    try:
        if not col_exists(cur, 'partner_change_requests', 'requester_name'):
            print("- Adding partner_change_requests.requester_name TEXT")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN requester_name TEXT")
        if not col_exists(cur, 'partner_change_requests', 'requester_department'):
            print("- Adding partner_change_requests.requester_department TEXT")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN requester_department TEXT")
        # Optional common columns used by app
        if not col_exists(cur, 'partner_change_requests', 'status'):
            print("- Adding partner_change_requests.status TEXT DEFAULT 'pending'")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN status TEXT DEFAULT 'pending'")
        if not col_exists(cur, 'partner_change_requests', 'custom_data'):
            print("- Adding partner_change_requests.custom_data TEXT")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN custom_data TEXT")
        if not col_exists(cur, 'partner_change_requests', 'is_deleted'):
            print("- Adding partner_change_requests.is_deleted INTEGER DEFAULT 0")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN is_deleted INTEGER DEFAULT 0")
        if not col_exists(cur, 'partner_change_requests', 'requested_at'):
            print("- Adding partner_change_requests.requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        if not col_exists(cur, 'partner_change_requests', 'processed_at'):
            print("- Adding partner_change_requests.processed_at TIMESTAMP")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN processed_at TIMESTAMP")
        if not col_exists(cur, 'partner_change_requests', 'created_at'):
            print("- Adding partner_change_requests.created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        if not col_exists(cur, 'partner_change_requests', 'updated_at'):
            print("- Adding partner_change_requests.updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        if not col_exists(cur, 'partner_change_requests', 'request_number'):
            print("- Adding partner_change_requests.request_number TEXT UNIQUE")
            cur.execute("ALTER TABLE partner_change_requests ADD COLUMN request_number TEXT UNIQUE")
    except Exception as e:
        print(f"WARNING: partner_change_requests fix failed: {e}")

    # 4) follow_sop: ensure UNIQUE(work_req_no) for ON CONFLICT
    try:
        # Check duplicates before adding constraint
        dup, rows = has_duplicates(cur, 'follow_sop', 'work_req_no')
        if dup:
            print("ERROR: follow_sop has duplicate work_req_no values. Cannot add UNIQUE constraint.")
            for r in rows[:10]:
                print("  duplicate:", r)
            print("Please de-duplicate follow_sop first, then re-run this script.")
        else:
            cname = 'follow_sop_work_req_no_key'
            if not constraint_exists(cur, 'follow_sop', cname):
                print("- Adding UNIQUE constraint follow_sop(work_req_no)")
                cur.execute(f"ALTER TABLE follow_sop ADD CONSTRAINT {cname} UNIQUE(work_req_no)")
    except Exception as e:
        print(f"WARNING: follow_sop unique fix failed: {e}")

    # 5) full_process: ensure UNIQUE(fullprocess_number) for ON CONFLICT
    try:
        dup, rows = has_duplicates(cur, 'full_process', 'fullprocess_number')
        if dup:
            print("ERROR: full_process has duplicate fullprocess_number values. Cannot add UNIQUE constraint.")
            for r in rows[:10]:
                print("  duplicate:", r)
            print("Please de-duplicate full_process first, then re-run this script.")
        else:
            cname = 'full_process_fullprocess_number_key'
            if not constraint_exists(cur, 'full_process', cname):
                print("- Adding UNIQUE constraint full_process(fullprocess_number)")
                cur.execute(f"ALTER TABLE full_process ADD CONSTRAINT {cname} UNIQUE(fullprocess_number)")
    except Exception as e:
        print(f"WARNING: full_process unique fix failed: {e}")

    # Done
    try:
        conn.commit()
    except Exception:
        pass
    cur.close()
    conn.close()
    print("All compatibility fixes attempted.")


if __name__ == '__main__':
    main()

