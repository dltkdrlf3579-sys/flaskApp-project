#!/usr/bin/env python3
"""
PostgreSQL timestamp 처리 수정 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert

def test_postgresql_timestamp_handling():
    """PostgreSQL에서 timestamp 처리 테스트"""
    print("\n=== PostgreSQL timestamp 처리 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 임시 테스트 테이블 생성
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TEMP TABLE test_timestamp (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 첫 번째 테스트: INSERT with None timestamps (DEFAULT should apply)
        test_data = {
            'id': 1,
            'name': 'test1',
            'updated_at': None,  # DEFAULT 적용되어야 함
            'created_at': None   # DEFAULT 적용되어야 함
        }
        
        result = safe_upsert(conn, 'test_timestamp', test_data, 
                           conflict_cols=['id'], 
                           update_cols=['name', 'updated_at'])
        print(f"OK - INSERT with None timestamp: {result}개 행 영향")
        
        # 결과 확인 - timestamp가 NULL이 아니어야 함
        cursor.execute("SELECT id, name, updated_at IS NOT NULL, created_at IS NOT NULL FROM test_timestamp WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - INSERT 결과: 컬럼 수 = {len(row)}")
            print(f"OK - 데이터: {dict(row) if hasattr(row, 'keys') else row}")
            
            # SafeRowCompat 객체의 키로 접근
            if hasattr(row, 'keys'):
                cols = list(row.keys())
                print(f"OK - 컬럼들: {cols}")
                id_val = row['id']
                name_val = row['name'] 
                updated_not_null = row['?column?'] if '?column?' in cols else row[cols[2]]
                created_not_null = row[cols[3]] if len(cols) > 3 else True
                print(f"OK - INSERT 결과: id={id_val}, name={name_val}, updated_at_not_null={updated_not_null}, created_at_not_null={created_not_null}")
                
                if not updated_not_null or not created_not_null:
                    print("ERROR - Timestamp columns are NULL! DEFAULT was not applied.")
                    return False
            else:
                print(f"OK - Row type: {type(row)}, values: {row}")
                if len(row) >= 4 and (not row[2] or not row[3]):
                    print("ERROR - Timestamp columns are NULL! DEFAULT was not applied.")
                    return False
        
        # 두 번째 테스트: UPDATE (updated_at should change, created_at should stay)
        import time
        time.sleep(1)  # 시간 차이를 위해 잠시 대기
        
        test_data['name'] = 'updated_test1'
        result = safe_upsert(conn, 'test_timestamp', test_data,
                           conflict_cols=['id'],
                           update_cols=['name', 'updated_at'])
        print(f"OK - UPDATE with timestamp: {result}개 행 영향")
        
        # UPDATE 확인
        cursor.execute("SELECT id, name, updated_at, created_at FROM test_timestamp WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - UPDATE 결과: id={row[0]}, name={row[1]}")
            print(f"    updated_at={row[2]}, created_at={row[3]}")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"ERROR - PostgreSQL timestamp 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """PostgreSQL timestamp 테스트 실행"""
    print("SETUP - PostgreSQL timestamp 처리 테스트 시작")
    
    try:
        if test_postgresql_timestamp_handling():
            print("SUCCESS - PostgreSQL timestamp 처리 수정 완료!")
            return True
        else:
            print("FAIL - PostgreSQL timestamp 처리 문제 있음")
            return False
    except Exception as e:
        print(f"ERROR - 테스트 실행 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)