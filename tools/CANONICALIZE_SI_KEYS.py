#!/usr/bin/env python3
"""
Canonicalize Safety Instruction column keys and data keys in one pass.

Goals
- Enforce a single canonical key set for popup/linked fields
- Rename column_config keys to canonical names (idempotent)
- Update safety_instructions.custom_data to include canonical keys
- Optionally remove legacy keys from custom_data

Canonical keys (target)
- issuer (popup_person), issuer_id (linked), issuer_dept (linked_dept)
- issuer_incharge_dept (popup_department)
- primary_company (popup_company), primary_company_bizno (linked_text)
- subcontractor (popup_company), subcontractor_bizno (linked_text)

Legacy keys that are normalized
- issuer_department -> issuer_dept
- primary_business_number -> primary_company_bizno
- primary_company_business_number -> primary_company_bizno
- secondary_company -> subcontractor
- secondary_company_bizno -> subcontractor_bizno
- secondary_company_business_number -> subcontractor_bizno
- subcontractor_business_number -> subcontractor_bizno
- discipline_department -> issuer_incharge_dept (only if target is empty)

Usage
  python tools/CANONICALIZE_SI_KEYS.py --dry-run        # report only
  python tools/CANONICALIZE_SI_KEYS.py --apply          # apply changes
  python tools/CANONICALIZE_SI_KEYS.py --apply --remove-legacy  # also drop old keys in JSON

This script is non-destructive by default (keeps legacy keys in data until you pass --remove-legacy).
"""
import argparse
import json
from typing import Dict, Any

from db_connection import get_db_connection


MAPPINGS = {
    # old_key -> new_key (target is the user's canonical list)
    'issuer_department': 'issuer_dept',
    'primary_business_number': 'primary_company_bizno',
    'primary_company_business_number': 'primary_company_bizno',
    'subcontractor': 'secondary_company',
    'subcontractor_bizno': 'secondary_company_bizno',
    'subcontractor_business_number': 'secondary_company_bizno',
    'secondary_company_business_number': 'secondary_company_bizno',
    'safety_violation_grade': 'violation_grade',
    'tema': 'team',
    'department': 'dept',
}

# special: discipline_department -> issuer_incharge_dept (if target empty)
SPECIAL_MAP_SRC = 'discipline_department'
SPECIAL_MAP_DST = 'issuer_incharge_dept'

# desired types for canonical keys
DESIRED_TYPES = {
    'issuer': 'popup_person',
    'issuer_id': 'linked',
    'issuer_dept': 'linked_dept',
    'issuer_incharge_dept': 'popup_department',
    'primary_company': 'popup_company',
    'primary_company_bizno': 'linked_text',
    'secondary_company': 'popup_company',
    'secondary_company_bizno': 'linked_text',
}

BASIC_TAB = 'basic_info'


def ensure_column(cur, key: str, name: str, ctype: str, tab: str = BASIC_TAB):
    # upsert-like: set type/tab, activate
    try:
        cur.execute(
            """
            INSERT INTO safety_instruction_column_config
                (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at)
            VALUES (?, ?, ?, (SELECT COALESCE(MAX(column_order),0)+1 FROM safety_instruction_column_config), 1, 0, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(column_key) DO UPDATE SET
                column_name = excluded.column_name,
                column_type = excluded.column_type,
                tab = COALESCE(NULLIF(safety_instruction_column_config.tab,''), excluded.tab),
                is_active = 1,
                is_deleted = 0,
                updated_at = CURRENT_TIMESTAMP
            """,
            (key, name, ctype, tab)
        )
    except Exception:
        # PostgreSQL compatibility without ON CONFLICT for older wrappers
        cur.execute("SELECT 1 FROM safety_instruction_column_config WHERE column_key = ?", (key,))
        if cur.fetchone():
            try:
                cur.execute(
                    "UPDATE safety_instruction_column_config SET column_name = ?, column_type = ?, tab = COALESCE(NULLIF(tab,''), ?), is_active = 1, is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE column_key = ?",
                    (name, ctype, tab, key)
                )
            except Exception:
                cur.execute(
                    "UPDATE safety_instruction_column_config SET column_name = %s, column_type = %s, tab = COALESCE(NULLIF(tab,''), %s), is_active = 1, is_deleted = 0, updated_at = CURRENT_TIMESTAMP WHERE column_key = %s",
                    (name, ctype, tab, key)
                )
        else:
            try:
                cur.execute(
                    "INSERT INTO safety_instruction_column_config (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at) VALUES (?,?,?, (SELECT COALESCE(MAX(column_order),0)+1 FROM safety_instruction_column_config), 1, 0, ?, CURRENT_TIMESTAMP)",
                    (key, name, ctype, tab)
                )
            except Exception:
                cur.execute(
                    "INSERT INTO safety_instruction_column_config (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at) VALUES (%s,%s,%s, (SELECT COALESCE(MAX(column_order),0)+1 FROM safety_instruction_column_config), 1, 0, %s, CURRENT_TIMESTAMP)",
                    (key, name, ctype, tab)
                )


def rename_column_key(cur, old_key: str, new_key: str):
    # Only rename if old exists and new doesn't
    cur.execute("SELECT 1 FROM safety_instruction_column_config WHERE column_key = ?", (old_key,))
    if not cur.fetchone():
        return False
    cur.execute("SELECT 1 FROM safety_instruction_column_config WHERE column_key = ?", (new_key,))
    if cur.fetchone():
        # new exists; mark old as deleted
        try:
            cur.execute("UPDATE safety_instruction_column_config SET is_active = 0, is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE column_key = ?", (old_key,))
        except Exception:
            cur.execute("UPDATE safety_instruction_column_config SET is_active = 0, is_deleted = 1, updated_at = CURRENT_TIMESTAMP WHERE column_key = %s", (old_key,))
        return False
    # rename
    try:
        cur.execute("UPDATE safety_instruction_column_config SET column_key = ?, updated_at = CURRENT_TIMESTAMP WHERE column_key = ?", (new_key, old_key))
    except Exception:
        cur.execute("UPDATE safety_instruction_column_config SET column_key = %s, updated_at = CURRENT_TIMESTAMP WHERE column_key = %s", (new_key, old_key))
    return True


def canonicalize_columns(cur) -> Dict[str, Any]:
    """Rename legacy keys in column_config and ensure canonical keys exist with desired types."""
    cur.execute("SELECT column_key, column_name FROM safety_instruction_column_config")
    rows = cur.fetchall()
    existing = { (r['column_key'] if isinstance(r, dict) else r[0]): (r['column_name'] if isinstance(r, dict) else r[1]) for r in rows }

    renames = []
    for old, new in MAPPINGS.items():
        if old in existing:
            renamed = rename_column_key(cur, old, new)
            renames.append((old, new, 'renamed' if renamed else 'merged'))

    # Ensure canonical keys with expected types
    ensure_column(cur, 'issuer', '발행인', DESIRED_TYPES['issuer'])
    ensure_column(cur, 'issuer_id', '발행인 ID', DESIRED_TYPES['issuer_id'])
    ensure_column(cur, 'issuer_dept', '발행부서', DESIRED_TYPES['issuer_dept'])
    ensure_column(cur, 'issuer_incharge_dept', '징계 발의부서', DESIRED_TYPES['issuer_incharge_dept'])
    ensure_column(cur, 'primary_company', '1차사명', DESIRED_TYPES['primary_company'])
    ensure_column(cur, 'primary_company_bizno', '1차사 사업자번호', DESIRED_TYPES['primary_company_bizno'])
    ensure_column(cur, 'secondary_company', '하도사명', DESIRED_TYPES['secondary_company'])
    ensure_column(cur, 'secondary_company_bizno', '하도사 사업자번호', DESIRED_TYPES['secondary_company_bizno'])

    return { 'renames': renames }


def canonicalize_data(cur, remove_legacy=False) -> Dict[str, int]:
    try:
        cur.execute("SELECT issue_number, custom_data FROM safety_instructions")
    except Exception as e:
        return { 'total': 0, 'updated': 0 }
    rows = cur.fetchall()
    total = 0
    updated = 0
    for r in rows:
        total += 1
        issue_number = r['issue_number'] if isinstance(r, dict) else r[0]
        raw = r['custom_data'] if isinstance(r, dict) else r[1]
        if not raw:
            continue
        if isinstance(raw, dict):
            cd = dict(raw)
        else:
            try:
                cd = json.loads(raw)
            except Exception:
                continue
        changed = False
        # canonical copies
        for old, new in MAPPINGS.items():
            if old in cd and (new not in cd or cd.get(new) in (None, '')):
                cd[new] = cd[old]
                changed = True
            # remove legacy if asked
            if remove_legacy and old in cd:
                try:
                    del cd[old]
                    changed = True
                except Exception:
                    pass
        # special map
        if SPECIAL_MAP_SRC in cd and (cd.get(SPECIAL_MAP_DST) in (None, '') or SPECIAL_MAP_DST not in cd):
            cd[SPECIAL_MAP_DST] = cd[SPECIAL_MAP_SRC]
            if remove_legacy:
                try:
                    del cd[SPECIAL_MAP_SRC]
                except Exception:
                    pass
            changed = True

        if changed:
            try:
                cur.execute(
                    "UPDATE safety_instructions SET custom_data = ?, updated_at = CURRENT_TIMESTAMP WHERE issue_number = ?",
                    (json.dumps(cd, ensure_ascii=False), issue_number)
                )
            except Exception:
                cur.execute(
                    "UPDATE safety_instructions SET custom_data = %s, updated_at = CURRENT_TIMESTAMP WHERE issue_number = %s",
                    (json.dumps(cd, ensure_ascii=False), issue_number)
                )
            updated += 1
    return { 'total': total, 'updated': updated }


def main():
    parser = argparse.ArgumentParser(description='Canonicalize Safety Instruction keys (columns + data)')
    parser.add_argument('--apply', action='store_true', help='Apply changes (default is dry-run report)')
    parser.add_argument('--remove-legacy', action='store_true', help='Remove legacy keys in custom_data (use with --apply)')
    args = parser.parse_args()

    conn = get_db_connection()
    cur = conn.cursor()
    # ensure table exists
    try:
        cur.execute("SELECT 1 FROM safety_instruction_column_config LIMIT 1")
    except Exception:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0,
                dropdown_options TEXT,
                tab TEXT,
                column_span INTEGER DEFAULT 1,
                linked_columns TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

    # columns
    report = canonicalize_columns(cur)
    # data
    data_report = canonicalize_data(cur, remove_legacy=(args.apply and args.remove_legacy))

    print("[REPORT] Column renames:")
    for old, new, mode in report['renames']:
        print(f"  - {old} -> {new} ({mode})")
    print(f"[REPORT] Data updated: {data_report['updated']} / {data_report['total']} rows")

    if args.apply:
        conn.commit()
        print("[APPLY] Changes committed.")
        if args.remove_legacy:
            print("[APPLY] Legacy keys removed from custom_data.")
    else:
        conn.rollback()
        print("[DRY-RUN] Rolled back (no changes saved). Run with --apply to persist.")

    conn.close()


if __name__ == '__main__':
    main()
