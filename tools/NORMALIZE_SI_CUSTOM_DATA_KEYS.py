#!/usr/bin/env python3
"""
Normalize safety_instructions.custom_data keys to standard linked/popup keys

Why:
 - After migrating from caches, custom_data may have legacy keys that don't match
   the current column_key naming (e.g., primary_business_number → primary_company_bizno).
 - Linked/popup rendering and sibling detection rely on unified keys.

What it does (idempotent):
 - issuer_department → issuer_dept (if issuer_dept absent)
 - subcontractor_business_number → subcontractor_bizno
 - primary_business_number / primary_company_business_number → primary_company_bizno
 - secondary_company_business_number → secondary_company_bizno
 - discipline_department → issuer_incharge_dept (only if issuer_incharge_dept absent)

Usage:
  python tools/NORMALIZE_SI_CUSTOM_DATA_KEYS.py
"""
import json
from db_connection import get_db_connection


MAPPINGS = [
    ('issuer_department', 'issuer_dept'),
    ('subcontractor_business_number', 'subcontractor_bizno'),
    ('primary_business_number', 'primary_company_bizno'),
    ('primary_company_business_number', 'primary_company_bizno'),
    ('secondary_company_business_number', 'secondary_company_bizno'),
]


def normalize_record(cd: dict) -> tuple[dict, int]:
    changed = 0
    # direct renames
    for src, dst in MAPPINGS:
        if src in cd and (dst not in cd or not cd.get(dst)):
            cd[dst] = cd[src]
            changed += 1
    # discipline_department → issuer_incharge_dept (semantic repurpose)
    if 'issuer_incharge_dept' not in cd and 'discipline_department' in cd:
        cd['issuer_incharge_dept'] = cd['discipline_department']
        changed += 1
    return cd, changed


def main():
    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("SELECT issue_number, custom_data FROM safety_instructions")
    except Exception as e:
        print(f"[ERROR] safety_instructions 조회 실패: {e}")
        conn.close()
        return

    rows = cur.fetchall()
    total = 0
    changed_rows = 0
    changes = 0
    for r in rows:
        total += 1
        issue_number = r[0] if not isinstance(r, dict) else r['issue_number']
        raw = r[1] if not isinstance(r, dict) else r['custom_data']
        if not raw:
            continue
        if isinstance(raw, dict):
            cd = raw
        else:
            try:
                cd = json.loads(raw)
            except Exception:
                continue

        cd2, n = normalize_record(dict(cd))
        if n > 0:
            # write back
            try:
                cur.execute(
                    "UPDATE safety_instructions SET custom_data = ?, updated_at = CURRENT_TIMESTAMP WHERE issue_number = ?",
                    (json.dumps(cd2, ensure_ascii=False), issue_number)
                )
            except Exception:
                # Postgres style
                cur.execute(
                    "UPDATE safety_instructions SET custom_data = %s, updated_at = CURRENT_TIMESTAMP WHERE issue_number = %s",
                    (json.dumps(cd2, ensure_ascii=False), issue_number)
                )
            changed_rows += 1
            changes += n

    conn.commit()
    conn.close()
    print(f"[OK] safety_instructions custom_data normalized: {changed_rows}/{total} rows, {changes} changes")


if __name__ == '__main__':
    main()

