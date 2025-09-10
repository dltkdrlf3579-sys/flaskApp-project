#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""accidents_cache 테이블을 SQLite와 동일한 구조로 재생성"""
from db_connection import get_db_connection
import sqlite3

pg_conn = get_db_connection()
pg_cursor = pg_conn.cursor()

# 기존 테이블 백업
print("Backing up existing data...")
pg_cursor.execute("""
    CREATE TABLE IF NOT EXISTS accidents_cache_backup AS 
    SELECT * FROM accidents_cache
""")

# 기존 테이블 삭제
print("Dropping old table...")
pg_cursor.execute("DROP TABLE IF EXISTS accidents_cache")

# SQLite와 동일한 구조로 재생성
print("Creating new table with correct structure...")
pg_cursor.execute("""
    CREATE TABLE accidents_cache (
        id SERIAL PRIMARY KEY,
        accident_number TEXT,
        accident_name TEXT,
        accident_time TEXT,
        workplace TEXT,
        accident_grade TEXT,
        major_category TEXT,
        injury_form TEXT,
        injury_type TEXT,
        accident_date DATE,
        day_of_week TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        building TEXT,
        floor TEXT,
        location_category TEXT,
        location_detail TEXT,
        is_deleted INTEGER DEFAULT 0,
        synced_at TIMESTAMP,
        custom_data JSONB,
        accident_datetime TIMESTAMP,
        accident_type TEXT,
        responsible_company1 TEXT,
        responsible_company1_no TEXT,
        responsible_company2 TEXT,
        responsible_company2_no TEXT
    )
""")

pg_conn.commit()

# SQLite 데이터 복사
print("Copying data from SQLite...")
sqlite_conn = sqlite3.connect('portal.db')
sqlite_conn.row_factory = sqlite3.Row
cursor = sqlite_conn.cursor()

cursor.execute("SELECT * FROM accidents_cache")
rows = cursor.fetchall()

for row in rows:
    data = dict(row)
    
    # NULL 값 처리
    for key in data:
        if data[key] == '':
            data[key] = None
    
    # custom_data가 문자열이면 JSON으로 변환
    if data.get('custom_data'):
        import json
        try:
            if isinstance(data['custom_data'], str):
                data['custom_data'] = json.loads(data['custom_data'])
        except:
            data['custom_data'] = {}
    else:
        data['custom_data'] = {}
    
    # INSERT
    columns = list(data.keys())
    values = [data[col] for col in columns]
    placeholders = ['%s'] * len(columns)
    
    insert_sql = f"""
        INSERT INTO accidents_cache ({','.join(columns)})
        VALUES ({','.join(placeholders)})
    """
    
    try:
        pg_cursor.execute(insert_sql, values)
    except Exception as e:
        print(f"Error inserting row: {e}")

pg_conn.commit()

# 결과 확인
pg_cursor.execute("SELECT COUNT(*) FROM accidents_cache")
count = pg_cursor.fetchone()[0]
print(f"\nSuccess! {count} rows in accidents_cache")

sqlite_conn.close()
pg_conn.close()