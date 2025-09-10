#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""긴급 데이터 마이그레이션"""
import sqlite3
from db_connection import get_db_connection
from db.upsert import safe_upsert

# SQLite에서 데이터 가져오기
sqlite_conn = sqlite3.connect('portal.db')
sqlite_conn.row_factory = sqlite3.Row
sqlite_cursor = sqlite_conn.cursor()

# PostgreSQL 연결
pg_conn = get_db_connection()

# partners_cache 마이그레이션
sqlite_cursor.execute("SELECT * FROM partners_cache")
partners = sqlite_cursor.fetchall()

print(f"Migrating {len(partners)} partners...")

for i, partner in enumerate(partners):
    try:
        data = dict(partner)
        safe_upsert(pg_conn, 'partners_cache', data, ['business_number'])
        if (i + 1) % 20 == 0:
            print(f"  {i + 1} done...")
    except Exception as e:
        print(f"Error: {e}")

pg_conn.commit()

# 확인
pg_cursor = pg_conn.cursor()
pg_cursor.execute("SELECT COUNT(*) FROM partners_cache")
count = pg_cursor.fetchone()[0]

print(f"\nSuccess! PostgreSQL now has {count} partners")

sqlite_conn.close()
pg_conn.close()