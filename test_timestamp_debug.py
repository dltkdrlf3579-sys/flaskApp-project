#!/usr/bin/env python3
"""
PostgreSQL timestamp 처리 디버그
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert
import logging

# DEBUG 레벨 로깅 활성화
logging.basicConfig(level=logging.DEBUG)

def test_timestamp_debug():
    """timestamp 처리 디버그"""
    print("\n=== PostgreSQL timestamp 디버그 ===")
    
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        
        # 임시 테이블 생성
        cursor.execute("""
            CREATE TEMP TABLE test_debug (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        print("테이블 생성 완료")
        
        # safe_upsert 호출 (DEBUG 로그로 실제 SQL 확인)
        test_data = {
            'id': 1,
            'name': 'test1',
            'updated_at': None  # 이것이 제외되어야 함
        }
        
        print(f"UPSERT 호출 전 데이터: {test_data}")
        result = safe_upsert(conn, 'test_debug', test_data, 
                           conflict_cols=['id'], 
                           update_cols=['name', 'updated_at'])
        print(f"UPSERT 결과: {result}")
        
        # 결과 확인
        cursor.execute("SELECT id, name, updated_at FROM test_debug WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"결과: id={row['id'] if hasattr(row, 'keys') else row[0]}")
            print(f"      name={row['name'] if hasattr(row, 'keys') else row[1]}")
            print(f"      updated_at={row['updated_at'] if hasattr(row, 'keys') else row[2]}")
            
            updated_at_value = row['updated_at'] if hasattr(row, 'keys') else row[2]
            if updated_at_value is None:
                print("ERROR - updated_at is NULL! DEFAULT was not applied")
                return False
            else:
                print("OK - updated_at has value, DEFAULT was applied")
                return True
        
        conn.commit()
        
    except Exception as e:
        print(f"ERROR - {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    test_timestamp_debug()