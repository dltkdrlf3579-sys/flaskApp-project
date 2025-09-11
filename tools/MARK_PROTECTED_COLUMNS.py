#!/usr/bin/env python3
"""
Mark protected/system columns across all *_column_config tables.

- Sets is_system = 1 for keys in ('attachments','detailed_content','notes','note')
  and optionally ensures is_active = 0 (kept inactive) and is_deleted = 0.

Run:
  python tools/MARK_PROTECTED_COLUMNS.py
"""
import configparser

PROTECTED_COMMON = ('attachments','detailed_content','notes','note','created_at')
TABLES = (
    'safety_instruction_column_config',
    'follow_sop_column_config',
    'full_process_column_config',
    'accident_column_config',
    'change_request_column_config',
)

def main():
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    dsn = cfg.get('DATABASE', 'postgres_dsn', fallback=None)
    try:
        import psycopg as _pg
        conn = _pg.connect(dsn)
    except Exception:
        import psycopg2 as _pg
        conn = _pg.connect(dsn)
    cur = conn.cursor()
    try:
        cur.execute('BEGIN')
        for t in TABLES:
            # Ensure columns exist
            try:
                cur.execute(f"ALTER TABLE {t} ADD COLUMN IF NOT EXISTS is_system INTEGER DEFAULT 0")
            except Exception:
                pass
            # Per-table protected keys (primary keys)
            per_table = {
                'safety_instruction_column_config': ('issue_number',),
                'follow_sop_column_config': ('work_req_no',),
                'full_process_column_config': ('fullprocess_number',),
                'accident_column_config': ('accident_number',),
                'change_request_column_config': ('request_number',),
            }
            keys = list(PROTECTED_COMMON) + list(per_table.get(t, ()))
            cur.execute(
                f"UPDATE {t} SET is_system = 1, is_active = 0 WHERE LOWER(column_key) = ANY(%s)",
                ([k.lower() for k in keys],)
            )
        conn.commit()
        print('Protected columns marked and deactivated where present.')
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('ERROR:', e)
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    main()
