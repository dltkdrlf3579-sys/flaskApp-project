#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Column Config 백업 스크립트
2025-09-08 백업 생성
"""

import json
from datetime import datetime
from database_config import get_db_connection
from typing import Dict, List

def backup_column_configs():
    """모든 column_config 테이블을 백업"""
    
    tables_to_backup = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'accident_column_config'
    ]
    
    backup_timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    backup_results = {}
    
    try:
        for table in tables_to_backup:
            backup_table_name = f"{table}_backup_{backup_timestamp}"
            
            # 백업 테이블 생성
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {backup_table_name} AS 
                SELECT * FROM {table}
            """)
            
            # 백업된 행 수 확인
            cursor.execute(f"SELECT COUNT(*) FROM {backup_table_name}")
            row_count = cursor.fetchone()[0]
            
            # 원본 데이터도 JSON으로 백업
            cursor.execute(f"""
                SELECT id, column_key, column_name, column_type, column_order, 
                       is_active, dropdown_options, tab, column_span, linked_columns,
                       created_at, updated_at, is_deleted, is_list_display
                FROM {table}
                ORDER BY column_order
            """)
            
            rows = cursor.fetchall()
            backup_results[table] = {
                'backup_table': backup_table_name,
                'row_count': row_count,
                'data': [
                    {
                        'id': row[0],
                        'column_key': row[1],
                        'column_name': row[2],
                        'column_type': row[3],
                        'column_order': row[4],
                        'is_active': row[5],
                        'dropdown_options': row[6],
                        'tab': row[7],
                        'column_span': row[8],
                        'linked_columns': row[9],
                        'created_at': str(row[10]) if row[10] else None,
                        'updated_at': str(row[11]) if row[11] else None,
                        'is_deleted': row[12],
                        'is_list_display': row[13]
                    } for row in rows
                ]
            }
            
            print(f"[OK] {table} -> {backup_table_name} ({row_count} rows)")
        
        # JSON 파일로도 백업
        backup_filename = f"column_config_backup_{backup_timestamp}.json"
        with open(backup_filename, 'w', encoding='utf-8') as f:
            json.dump(backup_results, f, ensure_ascii=False, indent=2)
        
        conn.commit()
        print(f"\n[SUCCESS] 모든 백업 완료!")
        print(f"JSON 백업 파일: {backup_filename}")
        
        # 백업 테이블 목록 저장
        with open('backup_tables.txt', 'a', encoding='utf-8') as f:
            f.write(f"\n--- Backup created at {backup_timestamp} ---\n")
            for table, info in backup_results.items():
                f.write(f"{table} -> {info['backup_table']}\n")
        
        return backup_results
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 백업 중 오류 발생: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def list_existing_backups():
    """기존 백업 테이블 목록 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name LIKE '%%_column_config_backup_%%'
            ORDER BY table_name
        """)
        
        backups = cursor.fetchall()
        
        if backups:
            print("\n기존 백업 테이블 목록:")
            for backup in backups:
                print(f"  - {backup[0]}")
        else:
            print("\n기존 백업 테이블이 없습니다.")
            
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Column Config 백업 스크립트")
    print("=" * 60)
    
    # 기존 백업 확인
    list_existing_backups()
    
    # 새 백업 생성
    print("\n새 백업 생성 중...")
    backup_column_configs()