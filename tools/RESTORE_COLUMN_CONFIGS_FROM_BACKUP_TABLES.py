#!/usr/bin/env python3
"""
Restore *_column_config tables from existing backup tables listed in backup_tables.txt.

- Works on PostgreSQL using psycopg/psycopg2
- Non-destructive: wraps in a transaction; validates backup tables exist
-
Usage:
  python tools/RESTORE_COLUMN_CONFIGS_FROM_BACKUP_TABLES.py [timestamp]

If timestamp is omitted, tries to parse the last block in backup_tables.txt.
"""
import re
import sys
import configparser


def connect_pg():
    cfg = configparser.ConfigParser()
    cfg.read('config.ini', encoding='utf-8')
    dsn = cfg.get('DATABASE', 'postgres_dsn')
    try:
        import psycopg as _pg
        return _pg.connect(dsn)
    except Exception:
        import psycopg2 as _pg2
        return _pg2.connect(dsn)


def get_last_timestamp_from_file(path='backup_tables.txt'):
    try:
        with open(path, encoding='utf-8') as f:
            content = f.read()
    except Exception:
        return None
    matches = re.findall(r'Backup created at (\d{8}_\d{6})', content)
    return matches[-1] if matches else None


def table_exists(cur, name):
    cur.execute(
        """
        SELECT EXISTS (
          SELECT FROM information_schema.tables
          WHERE table_schema = 'public' AND table_name = %s
        )
        """,
        (name,)
    )
    return cur.fetchone()[0]


def get_columns(cur, table):
    cur.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s
        ORDER BY ordinal_position
        """,
        (table,)
    )
    return [r[0] for r in cur.fetchall()]


def restore_from_backup(cur, base_table, backup_table):
    base_cols = set(get_columns(cur, base_table))
    backup_cols = set(get_columns(cur, backup_table))
    cols = [c for c in get_columns(cur, base_table) if c in backup_cols]
    if not cols:
        raise RuntimeError(f'No intersecting columns between {base_table} and {backup_table}')
    cols_csv = ','.join(cols)
    # Wipe and copy
    cur.execute(f'DELETE FROM {base_table}')
    cur.execute(f'INSERT INTO {base_table} ({cols_csv}) SELECT {cols_csv} FROM {backup_table}')
    # Rowcount not always reliable across drivers; optional verify


def main():
    ts = sys.argv[1] if len(sys.argv) > 1 else get_last_timestamp_from_file()
    if not ts:
        print('ERROR: Cannot determine backup timestamp. Provide explicitly.')
        sys.exit(1)

    mapping = {
        'safety_instruction_column_config': f'safety_instruction_column_config_backup_{ts}',
        'follow_sop_column_config': f'follow_sop_column_config_backup_{ts}',
        'full_process_column_config': f'full_process_column_config_backup_{ts}',
        'change_request_column_config': f'change_request_column_config_backup_{ts}',
        'accident_column_config': f'accident_column_config_backup_{ts}',
    }

    conn = connect_pg()
    cur = conn.cursor()
    try:
        # Validate backups exist
        for base, backup in mapping.items():
            if not table_exists(cur, backup):
                raise RuntimeError(f'Backup table missing: {backup}')

        # Transactional restore
        cur.execute('BEGIN')
        for base, backup in mapping.items():
            print(f'[RESTORE] {base} <- {backup}')
            restore_from_backup(cur, base, backup)
        conn.commit()
        print('[DONE] Restored all column_config tables from backups')
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('ERROR:', e)
        sys.exit(1)
    finally:
        cur.close(); conn.close()


if __name__ == '__main__':
    main()

