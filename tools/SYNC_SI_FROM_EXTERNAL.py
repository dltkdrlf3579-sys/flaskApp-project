#!/usr/bin/env python3
"""
Sync safety_instructions data from external query to main table

Problem diagnosed:
- Main list shows data (from real-time external query)
- Detail page shows nothing (DB has empty values)
- Root cause: Data not properly synced to DB, only displayed in UI

Solution:
- Execute SAFETY_INSTRUCTIONS_QUERY from config.ini
- Update safety_instructions table with actual data
- Ensure custom_data fields have real values, not empty strings

Usage:
  python tools/SYNC_SI_FROM_EXTERNAL.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import logging
import configparser
from datetime import datetime
from typing import Dict, Any

from db_connection import get_db_connection
from db.upsert import safe_upsert

try:
    from database_config import execute_SQL, IQADB_AVAILABLE
except Exception as e:
    print(f"[ERROR] Cannot import IQADB: {e}")
    print("[INFO] This script requires IQADB connection for external data sync")
    sys.exit(1)


def sync_safety_instructions():
    """Sync safety instructions from external query to main table"""
    
    # Read config
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    # Get query
    query = None
    if config.has_option('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        query = config.get('CONTENT_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
    elif config.has_option('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY'):
        query = config.get('MASTER_DATA_QUERIES', 'SAFETY_INSTRUCTIONS_QUERY')
    
    if not query:
        print("[ERROR] SAFETY_INSTRUCTIONS_QUERY not found in config.ini")
        return 0
    
    if not IQADB_AVAILABLE:
        print("[ERROR] IQADB not available")
        return 0
    
    print(f"[INFO] Executing external query...")
    
    try:
        import pandas as pd
        df = execute_SQL(query)
        
        if df is None or df.empty:
            print("[WARNING] Query returned no data")
            return 0
        
        print(f"[INFO] Query returned {len(df)} records")
        
        conn = get_db_connection()
        synced = 0
        
        for _, row in df.iterrows():
            row_dict = row.to_dict()
            
            # Extract issue_number (required)
            issue_number = str(row_dict.get('issue_number', '')).strip()
            if not issue_number:
                continue
            
            # Build custom_data with all fields
            custom_data = {}
            
            # Map all fields to custom_data
            for key, value in row_dict.items():
                if key != 'issue_number':
                    # Convert pandas NaT/NaN to None
                    if pd.isna(value):
                        value = None
                    elif isinstance(value, (pd.Timestamp, datetime)):
                        value = str(value)
                    
                    # Store non-empty values
                    if value is not None and str(value).strip():
                        custom_data[key] = value
            
            # Extract detailed_content if exists
            detailed_content = custom_data.pop('detailed_content', '') or ''
            
            # Prepare upsert data
            upsert_data = {
                'issue_number': issue_number,
                'custom_data': custom_data,
                'detailed_content': detailed_content,
                'is_deleted': 0,
                'updated_at': None  # Will be set by DB
            }
            
            # Upsert to main table
            safe_upsert(
                conn,
                'safety_instructions',
                upsert_data,
                conflict_cols=['issue_number'],
                update_cols=['custom_data', 'detailed_content', 'is_deleted', 'updated_at']
            )
            
            synced += 1
            
            if synced % 10 == 0:
                print(f"[INFO] Synced {synced} records...")
        
        conn.commit()
        conn.close()
        
        print(f"[SUCCESS] Synced {synced} records from external query")
        return synced
        
    except Exception as e:
        print(f"[ERROR] Sync failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


def main():
    logging.basicConfig(level=logging.INFO)
    
    print("=" * 60)
    print("Safety Instructions External Data Sync")
    print("=" * 60)
    
    # Check current status
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # Count empty records
        cur.execute("""
            SELECT COUNT(*) FROM safety_instructions 
            WHERE custom_data = '{}' OR custom_data IS NULL
        """)
        empty_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM safety_instructions")
        total_count = cur.fetchone()[0]
        
        print(f"[INFO] Current status: {total_count} total, {empty_count} empty")
        
    except Exception as e:
        print(f"[WARNING] Cannot check current status: {e}")
    
    conn.close()
    
    # Run sync
    result = sync_safety_instructions()
    
    if result > 0:
        print(f"\n[SUCCESS] Sync completed. {result} records updated.")
        print("[INFO] Detail pages should now show data properly.")
    else:
        print("\n[FAILED] No records were synced.")
        print("[INFO] Check IQADB connection and query configuration.")


if __name__ == '__main__':
    main()