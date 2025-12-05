#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# SQLite에서 column_config 관련 테이블 찾기
cursor.execute("""
    SELECT name FROM sqlite_master 
    WHERE type='table' 
    AND name LIKE '%column%'
    ORDER BY name
""")

tables = cursor.fetchall()
print('Column 관련 테이블 목록:')
for table in tables:
    print(f'  - {table[0]}')
    
    # 각 테이블에서 detailed_content 찾기
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    for col in columns:
        if 'detailed_content' in col[1] or 'detail_content' in col[1]:
            print(f'    └─ {col[1]} 컬럼 발견!')

conn.close()