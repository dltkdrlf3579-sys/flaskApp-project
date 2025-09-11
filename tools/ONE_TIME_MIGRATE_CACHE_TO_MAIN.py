#!/usr/bin/env python3
"""
One-time migration: cache tables -> main tables for content boards

Boards covered:
  - Safety Instruction: safety_instructions_cache -> safety_instructions
  - Follow SOP: follow_sop_cache / followsop_cache -> follow_sop
  - Full Process: full_process_cache / fullprocess_cache -> full_process

Behavior:
  - Reads all rows from the first existing cache table (if any) per board
  - Builds a minimal record and UPSERTs into the main table
  - Preserves is_deleted (if present). detailed_content (SI) is taken from custom_data when available
  - Idempotent: safe_upsert used with (unique key) conflict

Notes:
  - Does NOT drop cache tables by default. Pass --drop-caches to drop after migration
  - Does NOT toggle config.ini. Disable external queries if you won’t use caches anymore
"""

import sys
import json
import argparse
import logging
from typing import Dict, Any, List

from db_connection import get_db_connection
from db.upsert import safe_upsert


def table_exists(conn, table: str) -> bool:
    try:
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cur = conn.cursor()
            cur.execute(
                "SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = %s",
                (table.lower(),)
            )
            return cur.fetchone() is not None
        else:
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
            return cur.fetchone() is not None
    except Exception:
        return False


def has_rows(conn, table: str) -> bool:
    try:
        if not table_exists(conn, table):
            return False
        cur = conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        row = cur.fetchone()
        return (row and (row[0] or 0) > 0)
    except Exception:
        return False


def read_cache_rows(conn, table: str) -> List[Dict[str, Any]]:
    if not table_exists(conn, table):
        return []
    cur = conn.cursor()
    try:
        cur.execute(f"SELECT * FROM {table} ORDER BY created_at")
    except Exception:
        cur.execute(f"SELECT * FROM {table}")
    rows = cur.fetchall()
    return [dict(r) for r in rows]


def parse_custom_data(raw) -> Dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}


def migrate_safety_instructions(conn, dry_run=False) -> int:
    cache_table = 'safety_instructions_cache'
    if not has_rows(conn, cache_table):
        logging.info("[SI] No cache rows to migrate")
        return 0

    rows = read_cache_rows(conn, cache_table)
    migrated = 0
    for r in rows:
        issue_number = (r.get('issue_number') or '').strip()
        if not issue_number:
            continue
        cd = parse_custom_data(r.get('custom_data'))
        detailed = (cd.get('detailed_content') or r.get('detailed_content') or '').strip()
        is_deleted = int(r.get('is_deleted', 0) or 0)

        data = {
            'issue_number': issue_number,
            'custom_data': cd,
            'detailed_content': detailed,
            'is_deleted': is_deleted,
            'created_at': None,   # keep DEFAULT
            'updated_at': None,   # let UPSERT set CURRENT_TIMESTAMP on update
        }
        if not dry_run:
            safe_upsert(
                conn,
                'safety_instructions',
                data,
                conflict_cols=['issue_number'],
                update_cols=['custom_data', 'detailed_content', 'is_deleted', 'updated_at']
            )
        migrated += 1

    logging.info(f"[SI] Migrated {migrated} rows from {cache_table} -> safety_instructions")
    return migrated


def migrate_generic(conn, cache_candidates: List[str], main_table: str, key_col: str, dry_run=False) -> int:
    source = None
    for name in cache_candidates:
        if has_rows(conn, name):
            source = name
            break
    if not source:
        logging.info(f"[{main_table}] No cache rows found among {cache_candidates}")
        return 0

    rows = read_cache_rows(conn, source)
    migrated = 0
    for r in rows:
        key = (r.get(key_col) or '').strip()
        if not key:
            continue
        cd = parse_custom_data(r.get('custom_data'))
        is_deleted = int(r.get('is_deleted', 0) or 0)
        data = {
            key_col: key,
            'custom_data': cd,
            'is_deleted': is_deleted,
            'created_at': None,
            'updated_at': None,
        }
        if not dry_run:
            safe_upsert(
                conn,
                main_table,
                data,
                conflict_cols=[key_col],
                update_cols=['custom_data', 'is_deleted', 'updated_at']
            )
        migrated += 1

    logging.info(f"[{main_table}] Migrated {migrated} rows from {source} -> {main_table}")
    return migrated


def drop_table(conn, table: str):
    try:
        cur = conn.cursor()
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            cur.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
        else:
            cur.execute(f"DROP TABLE IF EXISTS {table}")
        logging.info(f"Dropped table: {table}")
    except Exception as e:
        logging.warning(f"Failed to drop table {table}: {e}")


def main():
    parser = argparse.ArgumentParser(description='One-time migrate cache tables to main tables (SI/FollowSOP/FullProcess)')
    parser.add_argument('--dry-run', action='store_true', help='Do not write, only log what would be done')
    parser.add_argument('--drop-caches', action='store_true', help='Drop cache tables after successful migration')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')

    conn = None
    try:
        conn = get_db_connection()
        conn.row_factory = None
        logging.info("Starting one-time migration from caches -> main tables")

        total = 0
        # Safety Instruction
        total += migrate_safety_instructions(conn, dry_run=args.dry_run)
        # Follow SOP (try both aliases)
        total += migrate_generic(conn, ['follow_sop_cache', 'followsop_cache'], 'follow_sop', 'work_req_no', dry_run=args.dry_run)
        # Full Process (try both aliases)
        total += migrate_generic(conn, ['full_process_cache', 'fullprocess_cache'], 'full_process', 'fullprocess_number', dry_run=args.dry_run)

        if not args.dry_run:
            conn.commit()

        logging.info(f"Done. Migrated total rows: {total}")

        if args.drop_caches and not args.dry_run:
            for tbl in ['safety_instructions_cache', 'follow_sop_cache', 'followsop_cache', 'full_process_cache', 'fullprocess_cache']:
                if table_exists(conn, tbl):
                    drop_table(conn, tbl)
            conn.commit()
            logging.info("Cache tables dropped.")

    except Exception as e:
        logging.error(f"Migration failed: {e}")
        import traceback
        logging.error(traceback.format_exc())
        if conn:
            conn.rollback()
        sys.exit(1)
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


if __name__ == '__main__':
    main()

