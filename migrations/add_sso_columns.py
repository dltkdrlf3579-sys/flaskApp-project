"""
Add SSO-related columns to person_master if missing.

Columns:
- sso_id (unique)
- login_id
- grade
- last_login (timestamp)
- is_sso_user (boolean/integer default true)

Safe for both SQLite and PostgreSQL.
"""
from db_connection import get_db_connection


def column_exists(cursor, conn, table, column):
    try:
        if getattr(conn, 'is_postgres', False):
            cursor.execute(
                """
                SELECT 1 FROM information_schema.columns
                WHERE table_name = %s AND column_name = %s
                """,
                (table, column),
            )
            return cursor.fetchone() is not None
        else:
            cursor.execute(f"PRAGMA table_info({table})")
            return any(row[1] == column for row in cursor.fetchall())
    except Exception:
        return False


def run():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        # Quick existence check for table
        table_exists = False
        try:
            if getattr(conn, 'is_postgres', False):
                cur.execute(
                    "SELECT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = %s)",
                    ('person_master',),
                )
                table_exists = bool(cur.fetchone()[0])
            else:
                cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='person_master'")
                table_exists = cur.fetchone() is not None
        except Exception:
            table_exists = False

        if not table_exists:
            print('[SSO MIGRATION] person_master table not found; skipping')
            conn.close()
            return

        # Add columns
        if not column_exists(cur, conn, 'person_master', 'sso_id'):
            if getattr(conn, 'is_postgres', False):
                cur.execute("ALTER TABLE person_master ADD COLUMN sso_id VARCHAR(255)")
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_person_sso_id ON person_master(sso_id)")
            else:
                cur.execute("ALTER TABLE person_master ADD COLUMN sso_id TEXT")
                # SQLite cannot add unique constraint easily; create index
                cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_person_sso_id ON person_master(sso_id)")

        if not column_exists(cur, conn, 'person_master', 'login_id'):
            if getattr(conn, 'is_postgres', False):
                cur.execute("ALTER TABLE person_master ADD COLUMN login_id VARCHAR(100)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_person_login_id ON person_master(login_id)")
            else:
                cur.execute("ALTER TABLE person_master ADD COLUMN login_id TEXT")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_person_login_id ON person_master(login_id)")

        if not column_exists(cur, conn, 'person_master', 'grade'):
            if getattr(conn, 'is_postgres', False):
                cur.execute("ALTER TABLE person_master ADD COLUMN grade VARCHAR(100)")
            else:
                cur.execute("ALTER TABLE person_master ADD COLUMN grade TEXT")

        if not column_exists(cur, conn, 'person_master', 'last_login'):
            if getattr(conn, 'is_postgres', False):
                cur.execute("ALTER TABLE person_master ADD COLUMN last_login TIMESTAMP")
            else:
                cur.execute("ALTER TABLE person_master ADD COLUMN last_login DATETIME")

        if not column_exists(cur, conn, 'person_master', 'is_sso_user'):
            if getattr(conn, 'is_postgres', False):
                cur.execute("ALTER TABLE person_master ADD COLUMN is_sso_user BOOLEAN DEFAULT TRUE")
            else:
                cur.execute("ALTER TABLE person_master ADD COLUMN is_sso_user INTEGER DEFAULT 1")

        conn.commit()
        print('[SSO MIGRATION] Completed')
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print(f'[SSO MIGRATION] Error: {e}')
        raise
    finally:
        conn.close()


if __name__ == '__main__':
    run()

