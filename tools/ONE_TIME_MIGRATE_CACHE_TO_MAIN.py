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
import configparser

try:
    # Optional external DB access (IQADB)
    from database_config import execute_SQL, IQADB_AVAILABLE
except Exception:
    execute_SQL = None
    IQADB_AVAILABLE = False


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


def _norm_key(k: str) -> str:
    return ''.join((k or '').strip().lower().replace('_', '').split())


def _pick(src: Dict[str, Any], *keys):
    for k in keys:
        if k in src and src[k] not in (None, ''):
            return src[k]
    # try normalized matching (handles localized/underscores/spaces)
    nmap = { _norm_key(k): v for k, v in src.items() }
    for k in keys:
        nk = _norm_key(k)
        if nk in nmap and nmap[nk] not in (None, ''):
            return nmap[nk]
    return ''


def _next_cr_number(conn, base_yyyymm: str) -> str:
    prefix = f"CR-{base_yyyymm}-"
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT request_number FROM partner_change_requests
            WHERE request_number LIKE ?
            ORDER BY request_number DESC
            LIMIT 1
            """,
            (prefix + '%',)
        )
        row = cur.fetchone()
        if row and row[0]:
            try:
                last = int(str(row[0])[-2:])
            except Exception:
                last = 0
            seq = str(last + 1).zfill(2)
        else:
            seq = '01'
        return f"{prefix}{seq}"
    except Exception:
        return f"{prefix}01"


def _yyyymm_from_any(val: Any) -> str:
    from datetime import datetime
    import pandas as pd
    if not val:
        return datetime.now().strftime('%Y%m')
    try:
        if isinstance(val, str):
            # common patterns
            for fmt in ('%Y-%m-%d', '%Y/%m/%d', '%Y.%m.%d', '%Y-%m-%d %H:%M:%S'):
                try:
                    dt = datetime.strptime(val[:19], fmt)
                    return dt.strftime('%Y%m')
                except Exception:
                    continue
        # pandas/np datetime
        if 'Timestamp' in str(type(val)):
            return pd.to_datetime(val).strftime('%Y%m')
    except Exception:
        pass
    return datetime.now().strftime('%Y%m')


def migrate_change_requests(conn, dry_run=False) -> int:
    """One-time import of change requests into partner_change_requests.
    Prefers external query CHANGE_REQUESTS_QUERY; falls back to change_requests_cache.
    """
    migrated = 0

    # Try external query first
    query = None
    try:
        cfg = configparser.ConfigParser()
        cfg.read('config.ini', encoding='utf-8')
        if cfg.has_option('CONTENT_DATA_QUERIES', 'CHANGE_REQUESTS_QUERY'):
            query = cfg.get('CONTENT_DATA_QUERIES', 'CHANGE_REQUESTS_QUERY')
        elif cfg.has_option('MASTER_DATA_QUERIES', 'CHANGE_REQUESTS_QUERY'):
            query = cfg.get('MASTER_DATA_QUERIES', 'CHANGE_REQUESTS_QUERY')
    except Exception:
        query = None

    def upsert_row(row_dict: Dict[str, Any]):
        nonlocal migrated
        cd = dict(row_dict)
        # Standard fields mapping
        req_no = _pick(row_dict, 'request_number', '요청번호', 'cr_no', 'cr_number', 'req_no')
        requester = _pick(row_dict, 'requester_name', '요청자', '신청자', 'req_name')
        req_dept = _pick(row_dict, 'requester_department', '요청부서', '신청부서', 'req_name_dept', 'department')
        comp = _pick(row_dict, 'company_name', '회사명', '업체명', 'compname')
        bizno = _pick(row_dict, 'business_number', '사업자번호', 'compname_bizno', 'bizno')
        ctype = _pick(row_dict, 'change_type', '변경유형', '항목')
        curv = _pick(row_dict, 'current_value', '현값', '기존값')
        newv = _pick(row_dict, 'new_value', '신값', '변경값', '변경후')
        reason = _pick(row_dict, 'change_reason', '변경사유', '사유')
        status = _pick(row_dict, 'status', '상태') or 'requested'
        created = _pick(row_dict, 'created_at', '요청일자', '등록일', 'requested_at')

        # Auto-generate request_number if missing
        if not str(req_no).strip():
            yyyymm = _yyyymm_from_any(created)
            req_no = _next_cr_number(conn, yyyymm)

        data = {
            'request_number': str(req_no),
            'requester_name': str(requester or ''),
            'requester_department': str(req_dept or ''),
            'company_name': str(comp or ''),
            'business_number': str(bizno or ''),
            'change_type': str(ctype or ''),
            'current_value': str(curv or ''),
            'new_value': str(newv or ''),
            'change_reason': str(reason or ''),
            'status': str(status or 'requested'),
            'custom_data': cd,
            'updated_at': None,
        }
        if not dry_run:
            safe_upsert(
                conn,
                'partner_change_requests',
                data,
                conflict_cols=['request_number'],
                update_cols=['requester_name', 'requester_department', 'company_name', 'business_number',
                             'change_type', 'current_value', 'new_value', 'change_reason', 'status',
                             'custom_data', 'updated_at']
            )
        migrated += 1

    used_external = False
    if query and execute_SQL and IQADB_AVAILABLE:
        try:
            import pandas as pd
            df = execute_SQL(query)
            if hasattr(df, 'empty') and not df.empty:
                # Normalize column names to lower
                try:
                    df.columns = [str(c) for c in df.columns]
                except Exception:
                    pass
                for _, r in df.iterrows():
                    row = r.to_dict() if hasattr(r, 'to_dict') else dict(r)
                    # Ensure JSON-serializable values
                    for k, v in list(row.items()):
                        try:
                            import pandas as pd
                            from datetime import datetime, date
                            if pd.isna(v):
                                row[k] = None
                            elif isinstance(v, (pd.Timestamp, datetime, date)):
                                row[k] = str(v)
                        except Exception:
                            pass
                    upsert_row(row)
                used_external = True
                logging.info(f"[CR] Migrated {migrated} from external query")
        except Exception as e:
            logging.warning(f"[CR] External query migration failed: {e}")

    if not used_external:
        # Fallback to cache
        cache_rows = read_cache_rows(conn, 'change_requests_cache') if table_exists(conn, 'change_requests_cache') else []
        for r in cache_rows:
            cd = parse_custom_data(r.get('custom_data'))
            base = dict(r)
            base.update(cd)
            upsert_row(base)

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
        # Change Requests (prefer external query; fallback to cache)
        total += migrate_change_requests(conn, dry_run=args.dry_run)

        if not args.dry_run:
            conn.commit()

        logging.info(f"Done. Migrated total rows: {total}")

        if args.drop_caches and not args.dry_run:
            for tbl in ['safety_instructions_cache', 'follow_sop_cache', 'followsop_cache', 'full_process_cache', 'fullprocess_cache', 'change_requests_cache']:
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
