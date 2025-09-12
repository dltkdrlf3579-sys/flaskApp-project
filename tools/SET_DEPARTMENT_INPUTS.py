#!/usr/bin/env python3
"""
Force team, dept, business_division columns to department selection.

Targets:
- accident_column_config
- safety_instruction_column_config

Action:
- Set column_type='popup_department', is_active=1 (and is_deleted=0 if exists)
- Create missing rows with sensible defaults and next column_order

Idempotent; safe to run multiple times.
"""

import os, sys
# Ensure project root on sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db_connection import get_db_connection

DEPT_KEYS = [
    ('team', '팀'),
    ('dept', '부서'),
    ('business_division', '사업부'),
]

TABLES = [
    ('accident_column_config', False),
    ('safety_instruction_column_config', True),
]

def table_has_column(cur, table, col):
    try:
        rows = cur.execute(f"PRAGMA table_info({table})").fetchall()
        cols = { (r[1] if not hasattr(r, 'keys') else r['name']).lower() for r in rows }
        return col.lower() in cols
    except Exception:
        # PostgreSQL fallback via information_schema
        try:
            rows = cur.execute(
                """
                SELECT column_name FROM information_schema.columns
                WHERE table_name = %s
                """,
                (table,)
            ).fetchall()
            cols = { (r[0] if not hasattr(r, 'keys') else r['column_name']).lower() for r in rows }
            return col.lower() in cols
        except Exception:
            return False

def ensure_dept_columns(conn):
    cur = conn.cursor()
    for table, has_soft_delete in TABLES:
        # collect existing
        try:
            rows = cur.execute(f"SELECT column_key, column_type FROM {table}").fetchall()
            existing = { (r[0] if not hasattr(r, 'keys') else r['column_key']).lower(): (r[1] if not hasattr(r, 'keys') else r['column_type']) for r in rows }
        except Exception as e:
            print(f"[WARN] Cannot read {table}: {e}")
            continue

        # get max order
        try:
            r = cur.execute(f"SELECT COALESCE(MAX(column_order),0) FROM {table}").fetchone()
            max_order = r[0] if not hasattr(r, 'keys') else list(r.values())[0]
            if max_order is None:
                max_order = 0
        except Exception:
            max_order = 0

        # add/update
        for key, label in DEPT_KEYS:
            key_l = key.lower()
            if key_l in existing:
                # update type -> popup_department
                try:
                    sql = f"UPDATE {table} SET column_type = ?, is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE LOWER(column_key) = ?"
                    cur.execute(sql, ('popup_department', key_l))
                    if has_soft_delete and table_has_column(cur, table, 'is_deleted'):
                        cur.execute(f"UPDATE {table} SET is_deleted = 0 WHERE LOWER(column_key) = ?", (key_l,))
                except Exception:
                    # PostgreSQL style
                    sql = f"UPDATE {table} SET column_type = %s, is_active = 1, updated_at = CURRENT_TIMESTAMP WHERE LOWER(column_key) = %s"
                    cur.execute(sql, ('popup_department', key_l))
                    if has_soft_delete and table_has_column(cur, table, 'is_deleted'):
                        cur.execute(f"UPDATE {table} SET is_deleted = 0 WHERE LOWER(column_key) = %s", (key_l,))
                print(f"[OK] {table}.{key} -> popup_department")
            else:
                # insert new row
                max_order += 1
                try:
                    # prefer SQLite style first
                    cols = ['column_key','column_name','column_type','column_order','is_active']
                    vals = [key_l, label, 'popup_department', max_order, 1]
                    # optional columns
                    if table_has_column(cur, table, 'is_deleted'):
                        cols.append('is_deleted'); vals.append(0)
                    if table_has_column(cur, table, 'tab'):
                        cols.append('tab'); vals.append('basic_info')
                    placeholders = ','.join('?' for _ in vals)
                    cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
                except Exception:
                    # PostgreSQL style
                    cols = ['column_key','column_name','column_type','column_order','is_active']
                    vals = [key_l, label, 'popup_department', max_order, 1]
                    if table_has_column(cur, table, 'is_deleted'):
                        cols.append('is_deleted'); vals.append(0)
                    if table_has_column(cur, table, 'tab'):
                        cols.append('tab'); vals.append('basic_info')
                    placeholders = ','.join('%s' for _ in vals)
                    cur.execute(f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})", vals)
                print(f"[ADD] {table}.{key} inserted as popup_department (order {max_order})")

    conn.commit()


def main():
    conn = get_db_connection()
    ensure_dept_columns(conn)
    conn.close()
    print("[DONE] Department inputs enforced for team/dept/business_division")


if __name__ == '__main__':
    main()
