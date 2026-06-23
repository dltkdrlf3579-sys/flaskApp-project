#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""컬럼 설정 데이터 복사"""
import sqlite3
from db_connection import get_db_connection

sqlite_conn = sqlite3.connect('portal.db')
sqlite_conn.row_factory = sqlite3.Row
pg_conn = get_db_connection()
pg_cursor = pg_conn.cursor()

# accident_column_config 데이터 복사
cursor = sqlite_conn.cursor()
cursor.execute("SELECT * FROM accident_column_config")
rows = cursor.fetchall()

print(f"Copying {len(rows)} accident_column_config rows...")

for row in rows:
    data = dict(row)
    # Boolean 변환
    for key in ['is_active', 'is_required', 'is_deleted', 'is_readonly']:
        if key in data and data[key] is not None:
            data[key] = bool(data[key])
    
    # 각 필드를 직접 INSERT
    columns = list(data.keys())
    placeholders = ['%s'] * len(columns)
    
    sql = f"""
        INSERT INTO accident_column_config ({','.join(columns)})
        VALUES ({','.join(placeholders)})
        ON CONFLICT (column_key) DO UPDATE SET
        {','.join([f'{col} = EXCLUDED.{col}' for col in columns if col != 'column_key'])}
    """
    
    try:
        pg_cursor.execute(sql, tuple(data.values()))
    except Exception as e:
        print(f"Error: {e}")

pg_conn.commit()
print("Done!")

sqlite_conn.close()
pg_conn.close()