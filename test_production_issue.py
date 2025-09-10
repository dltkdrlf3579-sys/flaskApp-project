#!/usr/bin/env python3
"""
운영 환경 문제 재현 테스트
운영 환경에서 sync_date 타입 에러가 발생하는 상황을 재현
"""
import psycopg
import configparser
from db.upsert import safe_upsert
from db.compat import CompatConnection

def test_upsert_with_empty_string():
    """safe_upsert로 빈 문자열 테스트"""
    
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    dsn = config.get('DATABASE', 'postgres_dsn')
    
    # CompatConnection 사용 (실제 앱과 동일)
    conn = CompatConnection(dsn)
    
    print("Testing safe_upsert with various sync_date values...\n")
    
    # 테스트 케이스들
    test_cases = [
        {
            'work_req_no': 'TEST001',
            'custom_data': {},
            'sync_date': None  # None
        },
        {
            'work_req_no': 'TEST002', 
            'custom_data': {},
            'sync_date': ''  # 빈 문자열 (문제의 원인?)
        },
        {
            'work_req_no': 'TEST003',
            'custom_data': {},
            'sync_date': '2025-01-10 15:00:00'  # 정상 문자열
        },
        {
            'work_req_no': 'TEST004',
            'custom_data': {},
            # sync_date 생략 (DEFAULT 사용)
        }
    ]
    
    for i, test_data in enumerate(test_cases, 1):
        print(f"Test {i}: sync_date = {repr(test_data.get('sync_date', 'NOT PROVIDED'))}")
        try:
            # safe_upsert 호출 (실제 앱과 동일한 방식)
            result = safe_upsert(conn, 'followsop_cache', test_data)
            print(f"  [OK] Upsert successful, affected rows: {result}")
            conn.commit()
        except Exception as e:
            print(f"  [ERROR] {e}")
            conn.rollback()
        print()
    
    # 결과 확인
    cursor = conn.cursor()
    cursor.execute("SELECT work_req_no, sync_date FROM followsop_cache WHERE work_req_no LIKE 'TEST%'")
    results = cursor.fetchall()
    
    print("Final results in database:")
    for row in results:
        print(f"  {row[0]}: sync_date = {row[1]}")
    
    # 테스트 데이터 삭제
    cursor.execute("DELETE FROM followsop_cache WHERE work_req_no LIKE 'TEST%'")
    conn.commit()
    print("\nTest data cleaned up.")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_upsert_with_empty_string()