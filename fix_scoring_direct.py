#!/usr/bin/env python3
"""
Fix scoring config directly
"""
from db_connection import get_db_connection
import json

conn = get_db_connection()
cur = conn.cursor()

# Correct scoring config
config = '''{"type":"scoring","base_score":100,"items":[{"id":"item_1","label":"안전모 미착용","per_unit_delta":-5,"max_count":10},{"id":"item_2","label":"안전화 미착용","per_unit_delta":-3,"max_count":10},{"id":"item_3","label":"정리정돈 미흡","per_unit_delta":-2,"max_count":5},{"id":"item_4","label":"우수 사례","per_unit_delta":5,"max_count":3}],"grade_criteria":{"critical":{"min":-999,"max":-10},"major":{"min":-9,"max":-5},"minor":{"min":-4,"max":-1},"bonus":{"min":0.1,"max":999}}}'''

total_config = '''{"type":"score_total","base_score":100,"grade_criteria":{"critical":{"min":-999,"max":-10},"major":{"min":-9,"max":-5},"minor":{"min":-4,"max":-1},"bonus":{"min":0.1,"max":999}}}'''

try:
    # Check current state
    cur.execute("SELECT id, column_key, column_type, scoring_config FROM full_process_column_config WHERE column_type IN ('scoring', 'score_total')")
    rows = cur.fetchall()
    print("Current state:")
    for row in rows:
        print(f"  ID: {row[0]}, Key: {row[1]}, Type: {row[2]}, Config length: {len(str(row[3]))}")
    
    # Update using direct SQL
    cur.execute(f"UPDATE full_process_column_config SET scoring_config = '{config}', is_active = 1 WHERE column_type = 'scoring'")
    print(f"Updated scoring: {cur.rowcount} rows")
    
    cur.execute(f"UPDATE full_process_column_config SET scoring_config = '{total_config}', is_active = 1 WHERE column_type = 'score_total'") 
    print(f"Updated score_total: {cur.rowcount} rows")
    
    # Same for safety_instruction
    cur.execute(f"UPDATE safety_instruction_column_config SET scoring_config = '{config}', is_active = 1 WHERE column_type = 'scoring'")
    print(f"Updated safety scoring: {cur.rowcount} rows")
    
    cur.execute(f"UPDATE safety_instruction_column_config SET scoring_config = '{total_config}', is_active = 1 WHERE column_type = 'score_total'")
    print(f"Updated safety score_total: {cur.rowcount} rows")
    
    conn.commit()
    
    # Verify
    cur.execute("SELECT column_key, column_type, scoring_config FROM full_process_column_config WHERE column_type IN ('scoring', 'score_total')")
    rows = cur.fetchall()
    print("\nAfter update:")
    for row in rows:
        print(f"  Key: {row[0]}, Type: {row[1]}")
        try:
            cfg = json.loads(row[2]) if row[2] else {}
            print(f"    Items: {len(cfg.get('items', []))}")
        except:
            print(f"    Config: {row[2][:50]}...")
            
except Exception as e:
    print(f"Error: {e}")
    conn.rollback()
finally:
    conn.close()