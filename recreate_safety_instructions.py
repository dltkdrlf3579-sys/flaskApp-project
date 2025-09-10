#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""safety_instructions_cache 테이블 재생성"""
from db_connection import get_db_connection
import sqlite3

pg_conn = get_db_connection()
pg_cursor = pg_conn.cursor()

# 백업
pg_cursor.execute("""
    CREATE TABLE IF NOT EXISTS safety_instructions_cache_backup AS 
    SELECT * FROM safety_instructions_cache
""")

# 삭제
pg_cursor.execute("DROP TABLE IF EXISTS safety_instructions_cache")

# SQLite 구조 확인하고 재생성
sqlite_conn = sqlite3.connect('portal.db')
cursor = sqlite_conn.cursor()
cursor.execute("PRAGMA table_info(safety_instructions_cache)")
cols = cursor.fetchall()

print("Creating safety_instructions_cache with SQLite structure...")

# 테이블 생성
pg_cursor.execute("""
    CREATE TABLE safety_instructions_cache (
        id SERIAL PRIMARY KEY,
        issue_number TEXT,
        issue_title TEXT,
        issue_date DATE,
        instruction_type TEXT,
        department TEXT,
        target_audience TEXT,
        related_regulation TEXT,
        custom_data JSONB,
        is_deleted INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        synced_at TIMESTAMP
    )
""")

pg_conn.commit()

# 데이터 복사
sqlite_conn.row_factory = sqlite3.Row
cursor = sqlite_conn.cursor()
cursor.execute("SELECT * FROM safety_instructions_cache")
rows = cursor.fetchall()

for row in rows:
    data = dict(row)
    
    # custom_data 처리
    if data.get('custom_data'):
        import json
        try:
            if isinstance(data['custom_data'], str):
                data['custom_data'] = json.loads(data['custom_data'])
        except:
            data['custom_data'] = {}
    else:
        data['custom_data'] = {}
    
    # NULL 처리
    for key in data:
        if data[key] == '':
            data[key] = None
    
    # INSERT (id 제외, SERIAL로 자동 생성)
    pg_cursor.execute("""
        INSERT INTO safety_instructions_cache 
        (issue_number, issue_title, issue_date, instruction_type, 
         department, target_audience, related_regulation, custom_data, 
         is_deleted, created_at, updated_at, synced_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, (
        data.get('issue_number'),
        data.get('issue_title'),
        data.get('issue_date'),
        data.get('instruction_type'),
        data.get('department'),
        data.get('target_audience'),
        data.get('related_regulation'),
        data.get('custom_data'),
        data.get('is_deleted', 0),
        data.get('created_at'),
        data.get('updated_at'),
        data.get('synced_at')
    ))

pg_conn.commit()

pg_cursor.execute("SELECT COUNT(*) FROM safety_instructions_cache")
count = pg_cursor.fetchone()[0]
print(f"Success! {count} rows in safety_instructions_cache")

sqlite_conn.close()
pg_conn.close()