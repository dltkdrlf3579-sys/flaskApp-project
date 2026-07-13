#!/usr/bin/env python3
"""
Update scoring_config with proper JSON data
"""
from db_connection import get_db_connection
import json

def update_scoring_configs():
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Sample scoring config
    scoring_config = {
        "type": "scoring",
        "base_score": 100,
        "items": [
            {
                "id": "item_1",
                "label": "안전모 미착용",
                "per_unit_delta": -5,
                "max_count": 10
            },
            {
                "id": "item_2", 
                "label": "안전화 미착용",
                "per_unit_delta": -3,
                "max_count": 10
            },
            {
                "id": "item_3",
                "label": "정리정돈 미흡",
                "per_unit_delta": -2,
                "max_count": 5
            },
            {
                "id": "item_4",
                "label": "우수 사례",
                "per_unit_delta": 5,
                "max_count": 3
            }
        ],
        "grade_criteria": {
            "critical": {"min": -999, "max": -10},
            "major": {"min": -9, "max": -5},
            "minor": {"min": -4, "max": -1},
            "bonus": {"min": 0.1, "max": 999}
        }
    }
    
    score_total_config = {
        "type": "score_total",
        "base_score": 100,
        "grade_criteria": {
            "critical": {"min": -999, "max": -10},
            "major": {"min": -9, "max": -5},
            "minor": {"min": -4, "max": -1},
            "bonus": {"min": 0.1, "max": 999}
        }
    }
    
    # Update full_process_column_config
    try:
        # Update scoring type columns
        cur.execute("""
            UPDATE full_process_column_config 
            SET scoring_config = %s
            WHERE column_type = 'scoring'
        """, (json.dumps(scoring_config, ensure_ascii=False),))
        
        # Update score_total type columns
        cur.execute("""
            UPDATE full_process_column_config 
            SET scoring_config = %s
            WHERE column_type = 'score_total'
        """, (json.dumps(score_total_config, ensure_ascii=False),))
        
        print(f"Updated full_process_column_config: {cur.rowcount} rows")
        
        # Update safety_instruction_column_config
        cur.execute("""
            UPDATE safety_instruction_column_config 
            SET scoring_config = %s
            WHERE column_type = 'scoring'
        """, (json.dumps(scoring_config, ensure_ascii=False),))
        
        cur.execute("""
            UPDATE safety_instruction_column_config 
            SET scoring_config = %s
            WHERE column_type = 'score_total'
        """, (json.dumps(score_total_config, ensure_ascii=False),))
        
        print(f"Updated safety_instruction_column_config: {cur.rowcount} rows")
        
        # Also activate the columns
        cur.execute("""
            UPDATE full_process_column_config 
            SET is_active = 1
            WHERE column_type IN ('scoring', 'score_total')
        """)
        
        cur.execute("""
            UPDATE safety_instruction_column_config 
            SET is_active = 1
            WHERE column_type IN ('scoring', 'score_total')
        """)
        
        conn.commit()
        print("\n✅ Successfully updated scoring configurations!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Error updating configs: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    update_scoring_configs()