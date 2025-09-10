#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""컬럼 타입 확인"""
from db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

tables = ['accidents_cache', 'partners_cache', 'safety_instructions_cache']

for table in tables:
    cursor.execute(f"""
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = '{table}' 
        AND column_name IN ('is_deleted', 'is_active')
    """)
    cols = cursor.fetchall()
    
    if cols:
        print(f'{table}:')
        for col in cols:
            print(f'  {col[0]}: {col[1]}')

conn.close()