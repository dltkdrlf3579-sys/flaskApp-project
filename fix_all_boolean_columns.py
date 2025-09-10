#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""모든 boolean 컬럼을 integer로 통일"""
from db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# 모든 boolean 컬럼 찾기
cursor.execute("""
    SELECT table_name, column_name
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND data_type = 'boolean'
    ORDER BY table_name, column_name
""")

boolean_columns = cursor.fetchall()

print(f"Found {len(boolean_columns)} boolean columns to convert:")

for table, column in boolean_columns:
    print(f"\nConverting {table}.{column}...")
    
    try:
        # 먼저 기본값 제거
        cursor.execute(f"ALTER TABLE {table} ALTER COLUMN {column} DROP DEFAULT")
        conn.commit()
    except:
        pass  # 기본값이 없을 수도 있음
    
    try:
        # Boolean을 INTEGER로 변환
        cursor.execute(f"""
            ALTER TABLE {table} 
            ALTER COLUMN {column} TYPE INTEGER 
            USING CASE WHEN {column} THEN 1 ELSE 0 END
        """)
        
        # 적절한 기본값 설정
        if 'is_active' in column or 'first_sync_done' in column:
            default_val = 1 if 'is_active' in column else 0
        else:  # is_deleted, is_readonly, is_required 등
            default_val = 0
            
        cursor.execute(f"""
            ALTER TABLE {table} 
            ALTER COLUMN {column} SET DEFAULT {default_val}
        """)
        
        conn.commit()
        print(f"  ✓ Converted successfully")
        
    except Exception as e:
        print(f"  ✗ Error: {e}")
        conn.rollback()

# 결과 확인
cursor.execute("""
    SELECT COUNT(*)
    FROM information_schema.columns
    WHERE table_schema = 'public'
    AND data_type = 'boolean'
""")

remaining = cursor.fetchone()[0]

if remaining == 0:
    print("\n✅ Success! All boolean columns converted to integer.")
else:
    print(f"\n⚠️  {remaining} boolean columns remain.")

conn.close()