#!/usr/bin/env python3
"""
Check scoring columns in database
"""
from db_connection import get_db_connection
import json

def check_scoring_columns():
    conn = get_db_connection()
    cur = conn.cursor()
    
    tables = [
        'full_process_column_config',
        'follow_sop_column_config', 
        'safety_instruction_column_config'
    ]
    
    for table in tables:
        print(f"\n=== {table} ===")
        try:
            # Check if table exists
            cur.execute(f"SELECT * FROM {table} WHERE column_type IN ('scoring', 'score_total') ORDER BY column_order")
            columns = cur.fetchall()
            
            if columns:
                print(f"Found {len(columns)} scoring columns:")
                for col in columns:
                    # Print column details
                    print(f"\n  Column: {col[2] if len(col) > 2 else 'N/A'}")  # column_name
                    print(f"  Key: {col[1] if len(col) > 1 else 'N/A'}")  # column_key
                    print(f"  Type: {col[3] if len(col) > 3 else 'N/A'}")  # column_type
                    print(f"  Tab: {col[4] if len(col) > 4 else 'N/A'}")  # tab
                    print(f"  Active: {col[6] if len(col) > 6 else 'N/A'}")  # is_active
                    
                    # Check scoring_config
                    if len(col) > 8 and col[8]:  # scoring_config is usually at index 8
                        try:
                            config = json.loads(col[8]) if isinstance(col[8], str) else col[8]
                            print(f"  Config: {json.dumps(config, indent=2, ensure_ascii=False)}")
                        except:
                            print(f"  Config (raw): {col[8]}")
                    else:
                        print("  Config: None")
            else:
                print("No scoring columns found")
                
        except Exception as e:
            print(f"Error checking {table}: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_scoring_columns()