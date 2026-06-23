#!/usr/bin/env python3
"""
Restore Follow SOP and Full Process column/section configs
from JSON backup to fix mismatched tabs/columns after refactor.

This script:
- Backs up current tables to *_backup_restore_YYYYmmdd_HHMMSS
- Replaces follow_sop_column_config and full_process_column_config
  with entries from column_config_backup_*.json (latest by mtime or
  a fixed path if provided)
- Ensures sections tables contain tabs referenced by configs

Usage:
  python3 restore_follow_full_configs.py [path_to_json]
"""
import sys, os, json, sqlite3, glob, datetime

BACKUP_JSON_GLOB = 'column_config_backup_*.json'

def load_backup_json(path: str) -> dict:
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def pick_backup_file(arg_path: str | None) -> str:
    if arg_path:
        return arg_path
    files = sorted(glob.glob(BACKUP_JSON_GLOB), key=os.path.getmtime, reverse=True)
    if not files:
        raise FileNotFoundError('No backup JSON found matching column_config_backup_*.json')
    return files[0]

def connect_db() -> sqlite3.Connection:
    # Reuse app's DB_PATH indirectly via config.ini
    import configparser
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    db_path = cfg.get('DATABASE', 'LOCAL_DB_PATH', fallback='portal.db')
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def backup_table(conn: sqlite3.Connection, table: str, suffix: str) -> str:
    backup_table = f"{table}_backup_restore_{suffix}"
    conn.execute(f"CREATE TABLE IF NOT EXISTS {backup_table} AS SELECT * FROM {table}")
    return backup_table

def replace_table_rows(conn: sqlite3.Connection, table: str, rows: list[dict]):
    # Get actual columns present in table
    cur = conn.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in cur.fetchall()]
    if not cols:
        raise RuntimeError(f"Table not found: {table}")
    # Wipe existing rows
    conn.execute(f"DELETE FROM {table}")
    # Insert rows with intersection of columns
    inserted = 0
    for row in rows:
        data = {k: row.get(k) for k in cols if k in row}
        # Build query
        keys = ','.join(data.keys())
        placeholders = ','.join(['?'] * len(data))
        values = list(data.values())
        conn.execute(f"INSERT INTO {table} ({keys}) VALUES ({placeholders})", values)
        inserted += 1
    return inserted

def ensure_sections(conn: sqlite3.Connection, table: str, required_keys: list[tuple[str,str,int]]):
    # required_keys: [(section_key, section_name, order)]
    cur = conn.cursor()
    # Ensure table exists
    cur.execute(f"CREATE TABLE IF NOT EXISTS {table} (\n"
                "id INTEGER PRIMARY KEY AUTOINCREMENT,\n"
                "section_key TEXT UNIQUE,\n"
                "section_name TEXT,\n"
                "section_order INTEGER DEFAULT 1,\n"
                "is_active INTEGER DEFAULT 1,\n"
                "is_deleted INTEGER DEFAULT 0\n"
                ")")
    # Mark all existing sections active (do not delete data), we'll update specific ones
    cur.execute(f"UPDATE {table} SET is_active = 1")
    # Upsert required sections
    for key, name, order in required_keys:
        row = cur.execute(f"SELECT id FROM {table} WHERE section_key = ?", (key,)).fetchone()
        if row:
            cur.execute(f"UPDATE {table} SET section_name=?, section_order=?, is_active=1, is_deleted=0 WHERE section_key=?",
                        (name, order, key))
        else:
            cur.execute(f"INSERT INTO {table} (section_key, section_name, section_order, is_active, is_deleted) VALUES (?,?,?,?,0)",
                        (key, name, order, 1))

def main():
    path = pick_backup_file(sys.argv[1] if len(sys.argv) > 1 else None)
    data = load_backup_json(path)
    conn = connect_db()
    try:
        ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        conn.execute('BEGIN IMMEDIATE')
        # Restore follow_sop
        if 'follow_sop_column_config' in data:
            print('[INFO] Restoring follow_sop_column_config from', path)
            backup_table(conn, 'follow_sop_column_config', ts)
            rows = data['follow_sop_column_config'].get('data', [])
            inserted = replace_table_rows(conn, 'follow_sop_column_config', rows)
            print(f'[OK] follow_sop_column_config inserted {inserted} rows')
            # Ensure sections according to tabs present in rows
            tabs = {r.get('tab') for r in rows if r.get('tab')}
            # Map to display names and order
            display = {
                'basic_info': ('기본정보', 1),
                'work_info': ('작업정보', 2),
                'additional': ('추가기입정보', 99),
            }
            req = [(t, display.get(t, (t, 50))[0], display.get(t, (t, 50))[1]) for t in tabs]
            ensure_sections(conn, 'follow_sop_sections', req)
        else:
            print('[WARN] follow_sop_column_config not found in backup JSON')

        # Restore full_process
        if 'full_process_column_config' in data:
            print('[INFO] Restoring full_process_column_config from', path)
            backup_table(conn, 'full_process_column_config', ts)
            rows = data['full_process_column_config'].get('data', [])
            inserted = replace_table_rows(conn, 'full_process_column_config', rows)
            print(f'[OK] full_process_column_config inserted {inserted} rows')
            # Sections
            tabs = {r.get('tab') for r in rows if r.get('tab')}
            display = {
                'basic_info': ('기본정보', 1),
                'process_info': ('프로세스 정보', 2),
                'execution_details': ('실행 상세', 3),
                'result_info': ('결과 정보', 4),
                'additional': ('추가기입정보', 99),
            }
            req = [(t, display.get(t, (t, 50))[0], display.get(t, (t, 50))[1]) for t in tabs]
            ensure_sections(conn, 'full_process_sections', req)
        else:
            print('[WARN] full_process_column_config not found in backup JSON')

        conn.commit()
        print('[DONE] Restore completed successfully')
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    main()

