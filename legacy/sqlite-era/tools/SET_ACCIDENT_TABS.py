#!/usr/bin/env python3
"""
Set tab values on accident_column_config based on column_key.

Usage:
  python tools/SET_ACCIDENT_TABS.py

Rules (editable in-place):
  basic_info: accident_number, accident_name, accident_date, workplace,
              accident_grade, day_of_week
  accident_info: accident_type, major_category, injury_type, injury_form
  location_info: building, floor, location_category, location_detail
  additional: the rest (left unchanged unless NULL)

Idempotent: Only rows with tab IS NULL or empty are updated.
Works with PostgreSQL or SQLite via db_connection.get_db_connection().
"""
from db_connection import get_db_connection


BASIC = {
    'accident_number', 'accident_name', 'accident_date', 'workplace',
    'accident_grade', 'day_of_week',
}
ACCIDENT = {
    'accident_type', 'major_category', 'injury_type', 'injury_form'
}
LOCATION = {
    'building', 'floor', 'location_category', 'location_detail'
}


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Ensure columns exist
    try:
        cur.execute("PRAGMA table_info(accident_column_config)")
        cols = [r[1] for r in cur.fetchall()]
    except Exception:
        cols = []

    # Update only when tab is NULL or ''
    def set_tab(keys, tab_name):
        if not keys:
            return 0
        placeholders = ','.join(['?'] * len(keys)) if not getattr(conn, 'is_postgres', False) else ','.join(['%s'] * len(keys))
        sql = (
            f"UPDATE accident_column_config "
            f"SET tab = ?, updated_at = CURRENT_TIMESTAMP "
            f"WHERE (tab IS NULL OR tab = '') AND LOWER(column_key) IN ({placeholders})"
        ) if not getattr(conn, 'is_postgres', False) else (
            f"UPDATE accident_column_config "
            f"SET tab = %s, updated_at = CURRENT_TIMESTAMP "
            f"WHERE (tab IS NULL OR tab = '') AND LOWER(column_key) IN ({placeholders})"
        )
        params = [tab_name] + [k.lower() for k in keys]
        cur.execute(sql, tuple(params))
        return cur.rowcount if hasattr(cur, 'rowcount') else 0

    c1 = set_tab(BASIC, 'basic_info')
    c2 = set_tab(ACCIDENT, 'accident_info')
    c3 = set_tab(LOCATION, 'location_info')

    # The rest: mark as 'additional' when tab missing
    if getattr(conn, 'is_postgres', False):
        cur.execute(
            """
            UPDATE accident_column_config
            SET tab = 'additional', updated_at = CURRENT_TIMESTAMP
            WHERE (tab IS NULL OR tab = '')
            """
        )
    else:
        cur.execute(
            """
            UPDATE accident_column_config
            SET tab = 'additional', updated_at = CURRENT_TIMESTAMP
            WHERE (tab IS NULL OR tab = '')
            """
        )

    conn.commit()
    conn.close()
    print(f"Updated tabs: basic={c1}, accident={c2}, location={c3}, others->additional")


if __name__ == '__main__':
    main()

