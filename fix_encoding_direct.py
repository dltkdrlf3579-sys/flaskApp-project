#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3

conn = sqlite3.connect('portal.db', timeout=30.0)
conn.execute("PRAGMA encoding = 'UTF-8'")
cursor = conn.cursor()

# 정확한 한글 값으로 업데이트
updates = [
    ('accident_date', '재해날짜'),
    ('injury_type', '부상형태'), 
    ('injury_form', '부상부위'),
    ('injured_count', '부상자수'),
    ('injured_person', '재해자명단')  # 부상자명단이 아니라 재해자명단
]

for key, name in updates:
    try:
        cursor.execute("UPDATE accident_column_config SET column_name = ? WHERE column_key = ?", (name, key))
        print(f"Updated {key} to {name}")
    except Exception as e:
        print(f"Error updating {key}: {e}")

# 전체 컬럼 확인
cursor.execute("SELECT column_key, column_name FROM accident_column_config")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.commit()
conn.close()
print("Done!")