#!/usr/bin/env python3
"""
Normalize table names and fix timestamp columns across environments.

This script:
- Renames legacy tables without underscores to the new underscore names
  (followsop -> follow_sop, fullprocess -> full_process, plus related *_column_config,
   *_details, *_attachments). Cache tables keep their original names
  (followsop_cache, fullprocess_cache) to match current code.
- Ensures created_at/updated_at columns exist where required
  (safety_instruction, accident, follow_sop, full_process) with sensible defaults.

It works for both SQLite and PostgreSQL via CompatConnection.
Run on the target machine where the issue occurs.

Usage:
  python3 migrations/normalize_follow_full_tables.py
"""
import logging
import sqlite3
from db_connection import get_db_connection

logging.basicConfig(level=logging.INFO, format='%(message)s')


def table_exists(cur, table: str, is_pg: bool) -> bool:
    try:
        if is_pg:
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
                (table.lower(),)
            )
            return cur.fetchone() is not None
        else:
            cur.execute(f"PRAGMA table_info({table})")
            return cur.fetchone() is not None
    except Exception:
        return False


def column_exists(cur, table: str, column: str, is_pg: bool) -> bool:
    try:
        if is_pg:
            cur.execute(
                "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                (table.lower(), column.lower())
            )
            return cur.fetchone() is not None
        else:
            cur.execute(f"PRAGMA table_info({table})")
            return any(r[1].lower() == column.lower() for r in cur.fetchall())
    except Exception:
        return False


def safe_rename_table(conn, cur, old: str, new: str, is_pg: bool):
    if old == new:
        return
    if table_exists(cur, new, is_pg):
        logging.info(f"[SKIP] {new} already exists")
        return
    if not table_exists(cur, old, is_pg):
        logging.info(f"[SKIP] {old} not found")
        return
    try:
        if is_pg:
            cur.execute(f"ALTER TABLE IF EXISTS {old} RENAME TO {new}")
        else:
            cur.execute(f"ALTER TABLE {old} RENAME TO {new}")
        logging.info(f"[OK] Renamed {old} -> {new}")
    except Exception as e:
        logging.error(f"[ERROR] Rename {old} -> {new}: {e}")


def ensure_timestamp_columns(cur, table: str, is_pg: bool):
    # created_at
    if not column_exists(cur, table, 'created_at', is_pg):
        try:
            if is_pg:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            else:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            logging.info(f"[OK] {table}: added created_at")
        except Exception as e:
            logging.error(f"[ERROR] {table}: cannot add created_at - {e}")

    # updated_at
    if not column_exists(cur, table, 'updated_at', is_pg):
        try:
            if is_pg:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            else:
                cur.execute(
                    f"ALTER TABLE {table} ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                )
            logging.info(f"[OK] {table}: added updated_at")
        except Exception as e:
            logging.error(f"[ERROR] {table}: cannot add updated_at - {e}")


def main():
    conn = get_db_connection()
    cur = conn.cursor()
    is_pg = getattr(conn, 'is_postgres', False)

    try:
        # Normalize table names
        pairs = [
            ('followsop', 'follow_sop'),
            ('followsop_column_config', 'follow_sop_column_config'),
            ('followsop_details', 'follow_sop_details'),
            ('followsop_attachments', 'follow_sop_attachments'),
            # cache tables keep legacy names as code refers to followsop_cache
            ('fullprocess', 'full_process'),
            ('fullprocess_column_config', 'full_process_column_config'),
            ('fullprocess_details', 'full_process_details'),
            ('fullprocess_attachments', 'full_process_attachments'),
            # cache tables keep legacy names as code refers to fullprocess_cache
        ]

        # Begin transaction
        if is_pg:
            cur.execute("START TRANSACTION")
        else:
            cur.execute("BEGIN IMMEDIATE")

        for old, new in pairs:
            safe_rename_table(conn, cur, old, new, is_pg)

        # Ensure timestamp columns on key tables
        for table in ['safety_instruction', 'accident', 'follow_sop', 'full_process']:
            if table_exists(cur, table, is_pg):
                ensure_timestamp_columns(cur, table, is_pg)
            else:
                logging.info(f"[SKIP] {table}: table not found")

        conn.commit()
        logging.info("\n[DONE] Normalization completed.")
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        logging.error(f"[FAILED] {e}")
        raise
    finally:
        try:
            conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()

