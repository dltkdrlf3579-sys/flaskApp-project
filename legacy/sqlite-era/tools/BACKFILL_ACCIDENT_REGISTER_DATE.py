#!/usr/bin/env python3
"""
accidents_cache 등록일 채움 스크립트

규칙:
  report_date := report_date 
              or accident_date 
              or created_at(날짜부분)

사용:
  python tools/BACKFILL_ACCIDENT_REGISTER_DATE.py
  python tools/BACKFILL_ACCIDENT_REGISTER_DATE.py --dry-run
"""
import argparse
import sqlite3
from db_connection import get_db_connection


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        # report_date가 NULL/빈값인 대상 추출
        rows = cur.execute(
            """
            SELECT id, accident_number, report_date, accident_date, created_at
            FROM accidents_cache
            WHERE (report_date IS NULL OR report_date = '')
            """
        ).fetchall()
    except Exception:
        # Postgres 호환: 조건 그대로 동작
        rows = cur.execute(
            "SELECT id, accident_number, report_date, accident_date, created_at FROM accidents_cache"
        ).fetchall()
        rows = [r for r in rows if not (r['report_date'] or '').strip()]

    updated = 0
    for r in rows:
        rid = r['id'] if isinstance(r, dict) else r[0]
        rn = r['accident_number'] if isinstance(r, dict) else r[1]
        rd = (r['accident_date'] if isinstance(r, dict) else r[3]) or ''
        ca = (r['created_at'] if isinstance(r, dict) else r[4]) or ''
        # 날짜부분만 취함
        ca_date = str(ca).split(' ')[0] if ca else ''
        new_date = (rd or ca_date)
        if not new_date:
            continue
        if args.dry_run:
            updated += 1
            continue
        try:
            cur.execute(
                "UPDATE accidents_cache SET report_date = ? WHERE id = ?",
                (new_date, rid)
            )
            updated += 1
        except Exception:
            # Postgres
            cur.execute(
                "UPDATE accidents_cache SET report_date = %s WHERE id = %s",
                (new_date, rid)
            )
            updated += 1

    if not args.dry_run:
        conn.commit()
    conn.close()
    print(f"[OK] backfilled report_date rows: {updated}")


if __name__ == '__main__':
    main()

