"""
Backfill missing top-level accident fields from custom_data or external query.

- Only fills when the top-level value is NULL or empty string
- Never overwrites non-empty values

Usage:
  python3 tools/BACKFILL_ACCIDENT_FIELDS.py --from custom_data
  python3 tools/BACKFILL_ACCIDENT_FIELDS.py --from external

For --from external, ACCIDENTS_QUERY must be configured and available via IQADB.
"""
import argparse
import json
import sqlite3
from typing import Dict
from db_connection import get_db_connection
from database_config import partner_manager

TARGET_KEYS = [
    'accident_name','workplace','accident_grade','major_category',
    'injury_form','injury_type','accident_date','day_of_week','report_date',
    'building','floor','location_category','location_detail'
]

def _is_empty(v):
    if v is None:
        return True
    if isinstance(v, str) and v.strip() == '':
        return True
    return False

def backfill_from_custom_data():
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    rows = cur.execute("SELECT id, accident_number, custom_data, "
                       + ",".join(TARGET_KEYS)
                       + " FROM accidents_cache").fetchall()
    updated = 0
    for row in rows:
        cd = row['custom_data']
        if not cd:
            continue
        try:
            data = cd if isinstance(cd, dict) else json.loads(cd)
        except Exception:
            continue
        sets = []
        vals = []
        for k in TARGET_KEYS:
            if _is_empty(row[k]) and k in data and not _is_empty(data[k]):
                sets.append(f"{k} = ?")
                vals.append(data[k])
        if sets:
            vals.append(row['id'])
            cur.execute(f"UPDATE accidents_cache SET {', '.join(sets)} WHERE id = ?", vals)
            updated += 1
    conn.commit()
    conn.close()
    print(f"Backfill from custom_data done. Rows updated: {updated}")

def backfill_from_external():
    # Reuse existing external sync but with UPSERT behavior already applied
    ok = partner_manager.sync_accidents_from_external_db()
    print(f"External backfill result: {'OK' if ok else 'FAILED'}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--from', dest='source', choices=['custom_data','external'], required=True)
    args = parser.parse_args()
    if args.source == 'custom_data':
        backfill_from_custom_data()
    else:
        backfill_from_external()

