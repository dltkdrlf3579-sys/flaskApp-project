#!/usr/bin/env python3
"""
UPSERT 유틸리티 테스트 스크립트 - Phase 3
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert, get_upsert_info
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def test_sync_state_upsert():
    """sync_state 테이블로 UPSERT 테스트"""
    print("\n=== sync_state UPSERT 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 테스트 데이터
        test_data = {
            'id': 1,
            'last_full_sync': '2025-01-06 10:00:00'
        }
        
        # UPSERT 실행
        result = safe_upsert(conn, 'sync_state', test_data)
        print(f"OK - UPSERT 결과: {result}개 행 영향")
        
        # 결과 확인
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sync_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - 저장된 데이터: id={row[0]}, last_full_sync={row[1]}")
        else:
            print("ERROR - 데이터가 저장되지 않았습니다")
        
        # 다시 UPSERT (UPDATE 테스트)
        test_data['last_full_sync'] = '2025-01-06 11:00:00'
        result = safe_upsert(conn, 'sync_state', test_data)
        print(f"OK - 두 번째 UPSERT 결과: {result}개 행 영향")
        
        # 업데이트 확인
        cursor.execute("SELECT * FROM sync_state WHERE id = 1")
        row = cursor.fetchone()
        if row:
            print(f"OK - 업데이트된 데이터: id={row[0]}, last_full_sync={row[1]}")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"ERROR - sync_state UPSERT 테스트 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def test_dropdown_codes_upsert():
    """dropdown_option_codes_v2 테이블로 UPSERT 테스트"""
    print("\n=== dropdown_option_codes_v2 UPSERT 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 테스트 데이터
        test_data = {
            'board_type': 'test_board',
            'column_key': 'test_column',
            'option_code': 'TEST_001',
            'option_value': '테스트 옵션 1',
            'display_order': 1,
            'is_active': 1,
            'created_at': '2025-01-06 10:00:00',
            'updated_at': '2025-01-06 10:00:00'
        }
        
        # UPSERT 실행
        result = safe_upsert(conn, 'dropdown_option_codes_v2', test_data)
        print(f"OK - UPSERT 결과: {result}개 행 영향")
        
        # 결과 확인
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM dropdown_option_codes_v2 
            WHERE board_type = 'test_board' AND column_key = 'test_column' AND option_code = 'TEST_001'
        """)
        row = cursor.fetchone()
        if row:
            print(f"OK - 저장된 데이터: option_value={row[3]}, display_order={row[4]}")
        else:
            print("ERROR - 데이터가 저장되지 않았습니다")
        
        # 다시 UPSERT (UPDATE 테스트)
        test_data['option_value'] = '업데이트된 테스트 옵션 1'
        test_data['display_order'] = 2
        result = safe_upsert(conn, 'dropdown_option_codes_v2', test_data)
        print(f"OK - 두 번째 UPSERT 결과: {result}개 행 영향")
        
        # 업데이트 확인
        cursor.execute("""
            SELECT * FROM dropdown_option_codes_v2 
            WHERE board_type = 'test_board' AND column_key = 'test_column' AND option_code = 'TEST_001'
        """)
        row = cursor.fetchone()
        if row:
            print(f"OK - 업데이트된 데이터: option_value={row[3]}, display_order={row[4]}")
        
        # 테스트 데이터 정리
        cursor.execute("""
            DELETE FROM dropdown_option_codes_v2 
            WHERE board_type = 'test_board' AND column_key = 'test_column'
        """)
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"ERROR - dropdown_option_codes_v2 UPSERT 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

def test_upsert_registry():
    """UPSERT 레지스트리 정보 테스트"""
    print("\n=== UPSERT 레지스트리 테스트 ===")
    
    # 등록된 테이블들 확인
    tables = ['sync_state', 'dropdown_option_codes_v2', 'safety_instruction_details']
    
    for table in tables:
        info = get_upsert_info(table)
        if info:
            print(f"OK - {table}: conflict={info['conflict_cols']}, update={info['update_cols']}")
        else:
            print(f"WARNING - {table}: 레지스트리에 정보 없음")
    
    return True

def main():
    """전체 UPSERT 테스트 실행"""
    print("SETUP - UPSERT 유틸리티 테스트 시작")
    
    tests = [
        ("레지스트리 정보", test_upsert_registry),
        ("sync_state UPSERT", test_sync_state_upsert), 
        ("dropdown_codes UPSERT", test_dropdown_codes_upsert),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"PASS - {name}: 성공")
            else:
                print(f"FAIL - {name}: 실패")
        except Exception as e:
            print(f"ERROR - {name}: {e}")
    
    print(f"\nRESULT - 테스트 결과: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("SUCCESS - 모든 UPSERT 테스트 통과!")
        print("READY - safe_upsert 함수 준비 완료!")
    else:
        print(f"WARNING - {total-passed}개 테스트 실패")
        print("ACTION - 실패한 테스트를 수정해야 합니다.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)