#!/usr/bin/env python3
"""
Update labels for accident board columns and soft-delete an obsolete column.

Changes (idempotent):
  - accident_date   → column_name = '재해날짜'
  - accident_time   → column_name = '재해시간'
  - injury_type     → column_name = '재해유형'
  - injury_form     → column_name = '재해형태'
  - accident_type   → is_active = 0, is_deleted = 1

Usage:
  python tools/UPDATE_ACCIDENT_COLUMN_LABELS.py

Works with SQLite/PostgreSQL via CompatConnection (db_connection.get_db_connection).
"""
from db_connection import get_db_connection


MAPPINGS = [
    ("accident_date", "재해날짜"),
    ("accident_time", "재해시간"),
    ("injury_type",  "재해유형"),
    ("injury_form",  "재해형태"),
]

SOFT_DELETE_KEYS = [
    "accident_type",
]


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Ensure table exists gracefully
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accident_column_config (
                id INTEGER PRIMARY KEY,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT,
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    except Exception:
        pass

    # Apply label mappings
    total_updated = 0
    for key, new_name in MAPPINGS:
        if getattr(conn, 'is_postgres', False):
            cur.execute(
                """
                UPDATE accident_column_config
                SET column_name = %s, updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(column_key) = %s
                  AND (column_name IS DISTINCT FROM %s)
                """,
                (new_name, key.lower(), new_name)
            )
        else:
            cur.execute(
                """
                UPDATE accident_column_config
                SET column_name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(column_key) = ? AND column_name <> ?
                """,
                (new_name, key.lower(), new_name)
            )
        total_updated += cur.rowcount if hasattr(cur, 'rowcount') else 0

    # Soft-delete obsolete columns
    total_deleted = 0
    for key in SOFT_DELETE_KEYS:
        if getattr(conn, 'is_postgres', False):
            cur.execute(
                """
                UPDATE accident_column_config
                SET is_active = 0, is_deleted = 1, updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(column_key) = %s AND (is_deleted = 0 OR is_deleted IS NULL)
                """,
                (key.lower(),)
            )
        else:
            cur.execute(
                """
                UPDATE accident_column_config
                SET is_active = 0, is_deleted = 1, updated_at = CURRENT_TIMESTAMP
                WHERE LOWER(column_key) = ? AND (is_deleted = 0 OR is_deleted IS NULL)
                """,
                (key.lower(),)
            )
        total_deleted += cur.rowcount if hasattr(cur, 'rowcount') else 0

    conn.commit()
    conn.close()

    print(f"Labels updated: {total_updated}")
    print(f"Columns soft-deleted: {total_deleted}")
    print("Done.")


if __name__ == '__main__':
    main()

