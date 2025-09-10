#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boolean 타입 통일 - 모두 INTEGER로 변경"""
from db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Boolean을 INTEGER로 변경할 테이블과 컬럼들
tables_to_fix = [
    ('section_config', ['is_active', 'is_deleted']),
    ('dropdown_codes', ['is_active']),
    ('responsible_master', ['is_active']),
    ('partner_change_requests', ['is_deleted']),
    ('partner_standards_column_config', ['is_active']),
    ('accident_column_config', ['is_active', 'is_required', 'is_deleted', 'is_readonly']),
    ('safety_instruction_column_config', ['is_active']),
    ('follow_sop_column_config', ['is_active']),
    ('full_process_column_config', ['is_active']),
    ('follow_sop_sections', ['is_active']),
    ('full_process_sections', ['is_active']),
    ('dropdown_option_codes_v2', ['is_active']),
    ('master_sync_state', ['first_sync_done']),
    ('sync_state', ['first_sync_done'])
]

for table, columns in tables_to_fix:
    for column in columns:
        try:
            # 먼저 현재 타입 확인
            cursor.execute(f"""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                AND column_name = '{column}'
            """)
            result = cursor.fetchone()
            
            if result and result[0] == 'boolean':
                print(f"Converting {table}.{column} from boolean to integer...")
                
                # Boolean을 INTEGER로 변환
                cursor.execute(f"""
                    ALTER TABLE {table} 
                    ALTER COLUMN {column} TYPE INTEGER 
                    USING CASE WHEN {column} THEN 1 ELSE 0 END
                """)
                
                # 기본값 설정
                if column in ['is_active', 'first_sync_done']:
                    default_val = 1 if column == 'is_active' else 0
                    cursor.execute(f"""
                        ALTER TABLE {table} 
                        ALTER COLUMN {column} SET DEFAULT {default_val}
                    """)
                elif column in ['is_deleted', 'is_readonly', 'is_required']:
                    cursor.execute(f"""
                        ALTER TABLE {table} 
                        ALTER COLUMN {column} SET DEFAULT 0
                    """)
                
                conn.commit()
                print(f"  ✓ Converted {table}.{column}")
                
        except Exception as e:
            print(f"  Error with {table}.{column}: {e}")
            conn.rollback()

print("\nDone! All boolean columns converted to integer.")
conn.close()