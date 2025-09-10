#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""나머지 데이터 마이그레이션"""
import sqlite3
import json
from db_connection import get_db_connection
from db.upsert import safe_upsert

sqlite_conn = sqlite3.connect('portal.db')
sqlite_conn.row_factory = sqlite3.Row
pg_conn = get_db_connection()

# accidents_cache 마이그레이션
cursor = sqlite_conn.cursor()
cursor.execute("SELECT * FROM accidents_cache")
accidents = cursor.fetchall()

print(f"Migrating {len(accidents)} accidents...")
for acc in accidents:
    try:
        data = dict(acc)
        if 'custom_data' in data and isinstance(data['custom_data'], str):
            try:
                data['custom_data'] = json.loads(data['custom_data'])
            except:
                data['custom_data'] = {}
        safe_upsert(pg_conn, 'accidents_cache', data, ['id'])
    except Exception as e:
        print(f"Accident error: {e}")

pg_conn.commit()

# safety_instructions_cache 마이그레이션
cursor.execute("SELECT * FROM safety_instructions_cache")
safety = cursor.fetchall()

print(f"Migrating {len(safety)} safety instructions...")
for saf in safety:
    try:
        data = dict(saf)
        if 'custom_data' in data and isinstance(data['custom_data'], str):
            try:
                data['custom_data'] = json.loads(data['custom_data'])
            except:
                data['custom_data'] = {}
        safe_upsert(pg_conn, 'safety_instructions_cache', data, ['id'])
    except Exception as e:
        print(f"Safety error: {e}")

pg_conn.commit()

print("Migration complete!")
sqlite_conn.close()
pg_conn.close()