#!/usr/bin/env python3
"""
sync_date 타입 문제 테스트
"""
import psycopg
import configparser
from datetime import datetime

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn')

def test_sync_date():
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("Testing sync_date issues...\n")
    
    # 1. 직접 INSERT 테스트
    print("1. Direct INSERT test:")
    try:
        cursor.execute("""
            INSERT INTO followsop_cache (work_req_no, custom_data, sync_date)
            VALUES ('TEST001', '{}', CURRENT_TIMESTAMP)
        """)
        print("  [OK] Direct INSERT with CURRENT_TIMESTAMP works")
        conn.rollback()
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        conn.rollback()
    
    # 2. None 값으로 INSERT 테스트
    print("\n2. INSERT with None value:")
    try:
        cursor.execute("""
            INSERT INTO followsop_cache (work_req_no, custom_data, sync_date)
            VALUES (%s, %s, %s)
        """, ('TEST002', '{}', None))
        print("  [OK] INSERT with None (uses DEFAULT) works")
        conn.rollback()
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        conn.rollback()
    
    # 3. 빈 문자열로 INSERT 테스트 (문제의 원인?)
    print("\n3. INSERT with empty string:")
    try:
        cursor.execute("""
            INSERT INTO followsop_cache (work_req_no, custom_data, sync_date)
            VALUES (%s, %s, %s)
        """, ('TEST003', '{}', ''))
        print("  [OK] INSERT with empty string works")
        conn.rollback()
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        conn.rollback()
    
    # 4. 문자열 날짜로 INSERT 테스트
    print("\n4. INSERT with string date:")
    try:
        cursor.execute("""
            INSERT INTO followsop_cache (work_req_no, custom_data, sync_date)
            VALUES (%s, %s, %s)
        """, ('TEST004', '{}', '2025-09-10 14:00:00'))
        print("  [OK] INSERT with string date works")
        conn.rollback()
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        conn.rollback()
    
    # 5. sync_date 컬럼 제외하고 INSERT (DEFAULT 사용)
    print("\n5. INSERT without sync_date column:")
    try:
        cursor.execute("""
            INSERT INTO followsop_cache (work_req_no, custom_data)
            VALUES (%s, %s)
        """, ('TEST005', '{}'))
        print("  [OK] INSERT without sync_date (uses DEFAULT) works")
        conn.rollback()
    except Exception as e:
        print(f"  [ERROR] Error: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()
    print("\nTest completed!")

if __name__ == "__main__":
    test_sync_date()