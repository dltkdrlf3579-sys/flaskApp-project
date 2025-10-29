#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""간단한 boolean 수정"""
from db_connection import get_db_connection

# 새 연결 생성
conn = get_db_connection()
cursor = conn.cursor()

# 중요한 테이블만 수정
critical_tables = [
    'accident_column_config',
    'partner_standards_column_config',
    'safety_instruction_column_config',
    'follow_sop_column_config',
    'full_process_column_config',
    'dropdown_codes',
    'dropdown_option_codes_v2'
]

for table in critical_tables:
    try:
        # 각 테이블별로 새 연결
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # is_active 컬럼 수정
        cursor.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN is_active DROP DEFAULT
        """)
        
        cursor.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN is_active TYPE INTEGER
            USING CASE WHEN is_active THEN 1 ELSE 0 END
        """)
        
        cursor.execute(f"""
            ALTER TABLE {table}
            ALTER COLUMN is_active SET DEFAULT 1
        """)
        
        conn.commit()
        print(f"Fixed {table}.is_active")
        
        # is_deleted가 있으면 수정
        cursor.execute(f"""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = '{table}' AND column_name = 'is_deleted'
        """)
        
        if cursor.fetchone():
            cursor.execute(f"""
                ALTER TABLE {table}
                ALTER COLUMN is_deleted DROP DEFAULT
            """)
            
            cursor.execute(f"""
                ALTER TABLE {table}
                ALTER COLUMN is_deleted TYPE INTEGER
                USING CASE WHEN is_deleted THEN 1 ELSE 0 END
            """)
            
            cursor.execute(f"""
                ALTER TABLE {table}
                ALTER COLUMN is_deleted SET DEFAULT 0
            """)
            
            conn.commit()
            print(f"Fixed {table}.is_deleted")
        
        conn.close()
        
    except Exception as e:
        print(f"Error with {table}: {e}")
        conn.close()

print("\nDone!")