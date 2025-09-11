#!/usr/bin/env python3
"""
Fix popup/linked column types and ensure required company/person keys exist
for Safety Instruction (safety_instruction_column_config).

What it fixes (idempotent):
- issuer (popup_person), issuer_id (linked), issuer_dept (linked_dept)
- issuer_incharge_dept (popup_department)
- primary_company (popup_company), primary_company_bizno (linked)
- secondary_company/subcontractor (popup_company), *_bizno (linked)
- Ensures tab defaults to 'basic_info' when empty
- Activates columns (is_active=1, is_deleted=0)
- Renames subcontractor_business_number -> subcontractor_bizno if needed

Usage:
  python tools/FIX_SI_POPUPS.py
"""
from db_connection import get_db_connection


BASIC_TAB = 'basic_info'


def fetch_existing(cur):
    cur.execute("SELECT column_key, column_type, tab, is_active, is_deleted FROM safety_instruction_column_config")
    rows = cur.fetchall()
    out = {}
    for r in rows:
        if isinstance(r, dict):
            k = r['column_key']
            out[k] = dict(r)
        else:
            k = r[0]
            out[k] = {
                'column_key': r[0],
                'column_type': r[1],
                'tab': r[2],
                'is_active': r[3],
                'is_deleted': r[4],
            }
    return out


def ensure_column(cur, existing, key, name, ctype, tab=BASIC_TAB, order_hint=0):
    if key in existing:
        # Update type/tab/flags when needed
        try:
            cur.execute(
                """
                UPDATE safety_instruction_column_config
                SET column_name = ?, column_type = ?,
                    tab = COALESCE(NULLIF(tab,''), ?),
                    is_active = 1, is_deleted = 0, updated_at = CURRENT_TIMESTAMP
                WHERE column_key = ?
                """,
                (name, ctype, tab, key)
            )
        except Exception:
            # Fallback for Postgres style placeholders
            cur.execute(
                """
                UPDATE safety_instruction_column_config
                SET column_name = %s, column_type = %s,
                    tab = COALESCE(NULLIF(tab,''), %s),
                    is_active = 1, is_deleted = 0, updated_at = CURRENT_TIMESTAMP
                WHERE column_key = %s
                """,
                (name, ctype, tab, key)
            )
        return 'updated'
    else:
        # Insert with next order
        try:
            cur.execute("SELECT COALESCE(MAX(column_order),0) FROM safety_instruction_column_config")
        except Exception:
            cur.execute("SELECT 0")
        max_order = (cur.fetchone() or [0])[0]
        next_order = max(max_order, order_hint) + 1
        try:
            cur.execute(
                """
                INSERT INTO safety_instruction_column_config
                    (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at)
                VALUES (?,?,?,?,1,0,?, CURRENT_TIMESTAMP)
                """,
                (key, name, ctype, next_order, tab)
            )
        except Exception:
            cur.execute(
                """
                INSERT INTO safety_instruction_column_config
                    (column_key, column_name, column_type, column_order, is_active, is_deleted, tab, updated_at)
                VALUES (%s,%s,%s,%s,1,0,%s, CURRENT_TIMESTAMP)
                """,
                (key, name, ctype, next_order, tab)
            )
        return 'inserted'


def rename_key(cur, old_key, new_key):
    # Rename only if new_key doesn't already exist
    cur.execute("SELECT 1 FROM safety_instruction_column_config WHERE column_key = ?", (new_key,))
    if cur.fetchone():
        return 'skipped'
    cur.execute("UPDATE safety_instruction_column_config SET column_key = ? WHERE column_key = ?", (new_key, old_key))
    return 'renamed'


def main():
    conn = get_db_connection()
    cur = conn.cursor()

    # Ensure table exists
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

    existing = fetch_existing(cur)
    changes = []

    # Issuer (person)
    changes.append(ensure_column(cur, existing, 'issuer', '발행인(이름)', 'popup_person'))
    changes.append(ensure_column(cur, existing, 'issuer_id', '발행인 ID', 'linked'))
    changes.append(ensure_column(cur, existing, 'issuer_dept', '발행부서', 'linked_dept'))
    changes.append(ensure_column(cur, existing, 'issuer_incharge_dept', '징계 발의부서', 'popup_department'))

    # Companies (primary)
    changes.append(ensure_column(cur, existing, 'primary_company', '1차사명', 'popup_company'))
    changes.append(ensure_column(cur, existing, 'primary_company_bizno', '1차사명 사업자번호', 'linked'))

    # Companies (secondary/subcontractor)
    # Prefer secondary_company, else use subcontractor keys
    if 'secondary_company' in existing or 'secondary_company_bizno' in existing:
        changes.append(ensure_column(cur, existing, 'secondary_company', '하도사명', 'popup_company'))
        changes.append(ensure_column(cur, existing, 'secondary_company_bizno', '하도사명 사업자번호', 'linked'))
    else:
        # Normalize subcontractor_business_number -> subcontractor_bizno
        if 'subcontractor_business_number' in existing and 'subcontractor_bizno' not in existing:
            try:
                rename_key(cur, 'subcontractor_business_number', 'subcontractor_bizno')
            except Exception:
                pass
            existing = fetch_existing(cur)
        changes.append(ensure_column(cur, existing, 'subcontractor', '하도사명', 'popup_company'))
        changes.append(ensure_column(cur, existing, 'subcontractor_bizno', '하도사명 사업자번호', 'linked'))

    conn.commit(); conn.close()
    print("Safety Instruction popup columns fixed.")


if __name__ == '__main__':
    main()

