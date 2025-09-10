#!/usr/bin/env python3
"""
PostgreSQL 호환성 테스트 스크립트 - v7
실제 애플리케이션 코드 패턴들을 테스트
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
import sqlite3
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def test_basic_connection():
    """기본 연결 테스트"""
    print("=== 1. 기본 연결 테스트 ===")
    
    try:
        conn = get_db_connection()
        print(f"OK - 연결 성공: {type(conn)}")
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        print(f"OK - 기본 쿼리: {result}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - 연결 실패: {e}")
        return False

def test_row_factory_compatibility():
    """row_factory 호환성 테스트 (app.py에서 많이 사용)"""
    print("\n=== 2. row_factory 호환성 테스트 ===")
    
    try:
        # app.py 패턴: conn.row_factory = sqlite3.Row
        conn = get_db_connection()
        conn.row_factory = sqlite3.Row
        print("OK - row_factory 설정 성공")
        
        cursor = conn.cursor()
        cursor.execute("SELECT 1 as test_col, 'test_value' as test_text")
        row = cursor.fetchone()
        
        # SQLite Row 방식 접근 테스트
        print(f"OK - 컬럼 접근 [0]: {row[0]}")
        print(f"OK - 컬럼 접근 ['test_col']: {row['test_col']}")
        print(f"OK - 컬럼 접근 ['test_text']: {row['test_text']}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - row_factory 테스트 실패: {e}")
        return False

def test_pragma_table_info():
    """PRAGMA table_info 에뮬레이션 테스트"""
    print("\n=== 3. PRAGMA table_info 호환성 테스트 ===")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 임시 테이블 생성해서 테스트
        create_sql = """
        CREATE TABLE IF NOT EXISTS test_table_info (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            value TEXT DEFAULT 'default_val',
            is_active INTEGER DEFAULT 1
        )
        """
        cursor.execute(create_sql)
        
        # app.py 패턴: PRAGMA table_info 사용
        cursor.execute("PRAGMA table_info(test_table_info)")
        columns = cursor.fetchall()
        
        print(f"OK - PRAGMA table_info 결과: {len(columns)} 컬럼")
        
        for col in columns:
            print(f"  - cid:{col[0]}, name:{col[1]}, type:{col[2]}, notnull:{col[3]}, pk:{col[5]}")
        
        print("OK - PRAGMA table_info 인덱스 접근 성공")
        
        # 테스트 테이블 삭제
        cursor.execute("DROP TABLE test_table_info")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - PRAGMA table_info 테스트 실패: {e}")
        print(f"ERROR - Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_json_extract_queries():
    """json_extract 호환성 테스트"""
    print("\n=== 4. json_extract 호환성 테스트 ===")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 임시 테이블과 데이터 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS test_json (
                id INTEGER PRIMARY KEY,
                custom_data TEXT DEFAULT '{}'
            )
        """)
        
        # JSON 데이터 삽입 (id를 명시적으로 지정)
        test_json = '{"workplace": "공장A", "level": 1, "status": "active"}'
        cursor.execute("INSERT INTO test_json (id, custom_data) VALUES (?, ?)", (1, test_json,))
        
        # app.py 패턴: json_extract 사용 (PostgreSQL에서는 JSONB 캐스팅 필요)
        cursor.execute("SELECT json_extract(custom_data::jsonb, '$.workplace') FROM test_json WHERE id = ?", (1,))
        result = cursor.fetchone()
        print(f"OK - json_extract workplace: {result[0]}")
        
        cursor.execute("SELECT json_extract(custom_data::jsonb, '$.level') FROM test_json WHERE id = ?", (1,))
        result = cursor.fetchone()
        print(f"OK - json_extract level: {result[0]}")
        
        # LIKE 검색 테스트 (app.py에서 자주 사용)
        cursor.execute("SELECT * FROM test_json WHERE json_extract(custom_data::jsonb, '$.workplace') LIKE ?", 
                      ('%공장%',))
        result = cursor.fetchone()
        print(f"OK - json_extract LIKE 검색: {result is not None}")
        
        # 테스트 데이터 정리
        cursor.execute("DROP TABLE test_json")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - json_extract 테스트 실패: {e}")
        print(f"ERROR - Exception type: {type(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_datetime_functions():
    """datetime 함수 호환성 테스트"""
    print("\n=== 5. datetime 함수 호환성 테스트 ===")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # datetime('now') 테스트
        cursor.execute("SELECT datetime('now')")
        result = cursor.fetchone()[0]
        print(f"OK - datetime('now'): {result}")
        
        # 일반 datetime 변환 테스트
        cursor.execute("SELECT datetime('2024-01-01 12:00:00')")
        result = cursor.fetchone()[0]
        print(f"OK - datetime('2024-01-01 12:00:00'): {result}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - datetime 함수 테스트 실패: {e}")
        return False

def test_placeholder_conversion():
    """플레이스홀더 변환 안전성 테스트"""
    print("\n=== 6. 플레이스홀더 안전 변환 테스트 ===")
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 문자열 리터럴 내 ? 보호 테스트
        cursor.execute("SELECT 'What is this?' as question, ? as answer", ('This is a test',))
        result = cursor.fetchone()
        print(f"OK - 문자열 리터럴 보호: question='{result[0]}', answer='{result[1]}'")
        
        # 복합 쿼리 테스트
        cursor.execute("SELECT ? as param1, 'Question?' as literal, ? as param2", ('value1', 'value2'))
        result = cursor.fetchone()
        print(f"OK - 복합 쿼리: {result}")
        
        conn.close()
        return True
    except Exception as e:
        print(f"ERROR - 플레이스홀더 테스트 실패: {e}")
        return False

def main():
    """전체 호환성 테스트 실행"""
    print("SETUP - PostgreSQL 호환성 테스트 시작")
    print(f"현재 백엔드: PostgreSQL 모드")
    
    tests = [
        ("기본 연결", test_basic_connection),
        ("row_factory 호환성", test_row_factory_compatibility),
        ("PRAGMA table_info", test_pragma_table_info),
        ("json_extract 쿼리", test_json_extract_queries),
        ("datetime 함수", test_datetime_functions),
        ("플레이스홀더 안전성", test_placeholder_conversion),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
                print(f"OK - {name}: PASS")
            else:
                print(f"FAIL - {name}: FAIL")
        except Exception as e:
            print(f"ERROR - {name}: {e}")
    
    print(f"\nRESULT - 테스트 결과: {passed}/{total} ({passed/total*100:.1f}%)")
    
    if passed == total:
        print("SUCCESS - 모든 호환성 테스트 통과!")
        print("READY - PostgreSQL 마이그레이션 준비 완료!")
    else:
        print(f"WARNING - {total-passed}개 테스트 실패")
        print("ACTION - 실패한 테스트를 수정해야 합니다.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)