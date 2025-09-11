#!/usr/bin/env python3
"""
Ensure partners_cache schema matches what the app queries on production (PostgreSQL).

Fixes common causes of "current transaction is aborted" when loading
the Partner Standards page:
 - Missing columns like permanent_workers used in ORDER BY/filters
 - Wrong type for is_deleted (BOOLEAN instead of INTEGER)

Idempotent: safe to run multiple times.

Usage:
  python tools/FIX_PARTNERS_CACHE_SCHEMA.py
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


def col_exists(cur, table, col):
    cur.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table.lower(), col.lower())
    )
    return cur.fetchone() is not None


def get_col_type(cur, table, col):
    cur.execute(
        """
        SELECT data_type FROM information_schema.columns
        WHERE table_schema='public' AND table_name=%s AND column_name=%s
        """,
        (table.lower(), col.lower())
    )
    row = cur.fetchone()
    return row[0] if row else None


def ensure_column(cur, table, name, ddl):
    if not col_exists(cur, table, name):
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")
        return True
    return False


def main():
    print('=== FIX partners_cache schema (PostgreSQL) ===')
    conn, driver = connect_pg()
    cur = conn.cursor()

    created_table = False
    # Ensure table exists minimally
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS partners_cache (
            id SERIAL PRIMARY KEY
        )
        """
    )
    conn.commit()

    added = []
    # Required columns used by queries/UI
    required = [
        ('business_number', 'business_number TEXT UNIQUE'),
        ('company_name', 'company_name TEXT'),
        ('partner_class', 'partner_class TEXT'),
        ('business_type_major', 'business_type_major TEXT'),
        ('business_type_minor', 'business_type_minor TEXT'),
        ('hazard_work_flag', 'hazard_work_flag TEXT'),
        ('representative', 'representative TEXT'),
        ('address', 'address TEXT'),
        ('average_age', 'average_age DOUBLE PRECISION'),
        ('annual_revenue', 'annual_revenue DOUBLE PRECISION'),
        ('transaction_count', 'transaction_count INTEGER'),
        ('permanent_workers', 'permanent_workers INTEGER'),
        ('created_at', 'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('updated_at', 'updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'),
        ('is_deleted', 'is_deleted INTEGER DEFAULT 0'),
    ]

    try:
        for col, ddl in required:
            if ensure_column(cur, 'partners_cache', col, ddl):
                added.append(col)

        # If is_deleted exists but is BOOLEAN, convert to INTEGER (0/1)
        if col_exists(cur, 'partners_cache', 'is_deleted'):
            ctype = get_col_type(cur, 'partners_cache', 'is_deleted')
            if ctype and ctype.lower() == 'boolean':
                # convert boolean -> integer (0/1)
                cur.execute(
                    """
                    ALTER TABLE partners_cache
                    ALTER COLUMN is_deleted DROP DEFAULT,
                    ALTER COLUMN is_deleted TYPE INTEGER
                    USING CASE WHEN is_deleted THEN 1 ELSE 0 END,
                    ALTER COLUMN is_deleted SET DEFAULT 0
                    """
                )
                print('Converted partners_cache.is_deleted from BOOLEAN to INTEGER')

        conn.commit()
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        print('ERROR while fixing schema:', e)
        sys.exit(1)
    finally:
        try:
            cur.close(); conn.close()
        except Exception:
            pass

    if added:
        print('Added columns:', ', '.join(added))
    else:
        print('No columns needed to be added (already up-to-date).')
    print('OK')


if __name__ == '__main__':
    main()

