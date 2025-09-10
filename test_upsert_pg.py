#!/usr/bin/env python3
"""
PostgreSQL UPSERT 테스트 (테이블 생성 없이 호환성만 테스트)
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert

def test_postgresql_upsert_syntax():
    """PostgreSQL UPSERT 문법 테스트 (실제 테이블 없이)"""
    print("\n=== PostgreSQL UPSERT 문법 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 임시 테스트 테이블 생성
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TEMP TABLE test_upsert (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                value INTEGER DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 테스트 데이터로 UPSERT
        test_data = {
            'id': 1,
            'name': 'test1',
            'value': 100,
            'updated_at': None  # CURRENT_TIMESTAMP로 자동 설정됨
        }
        
        # 첫 번째 INSERT
        result = safe_upsert(conn, 'test_upsert', test_data, 
                           conflict_cols=['id'], 
                           update_cols=['name', 'value', 'updated_at'])
        print(f"OK - 첫 번째 UPSERT 결과: {result}개 행 영향")
        
        # 결과 확인
        cursor.execute("SELECT * FROM test_upsert WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - 저장된 데이터: id={row[0]}, name={row[1]}, value={row[2]}")
        
        # 두 번째 UPSERT (UPDATE)
        test_data['name'] = 'updated_test1'
        test_data['value'] = 200
        
        result = safe_upsert(conn, 'test_upsert', test_data,
                           conflict_cols=['id'],
                           update_cols=['name', 'value', 'updated_at'])
        print(f"OK - 두 번째 UPSERT 결과: {result}개 행 영향")
        
        # 업데이트 확인
        cursor.execute("SELECT * FROM test_upsert WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - 업데이트된 데이터: id={row[0]}, name={row[1]}, value={row[2]}")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"ERROR - PostgreSQL UPSERT 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """PostgreSQL UPSERT 테스트 실행"""
    print("SETUP - PostgreSQL UPSERT 테스트 시작")
    
    try:
        if test_postgresql_upsert_syntax():
            print("SUCCESS - PostgreSQL UPSERT 테스트 성공!")
            return True
        else:
            print("FAIL - PostgreSQL UPSERT 테스트 실패")
            return False
    except Exception as e:
        print(f"ERROR - 테스트 실행 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)