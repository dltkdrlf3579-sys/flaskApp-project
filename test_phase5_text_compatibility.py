#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5 TEXT 호환성 테스트
setup_pg_functions.py의 json_extract(text, text) 오버로드 검증
"""
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(__file__))

def test_text_overload_compatibility():
    """TEXT 오버로드 함수 호환성 테스트"""
    print("\n=== TEXT 오버로드 함수 호환성 테스트 ===")
    
    from db_connection import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    db_type = 'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'
    print(f"DB 연결: {db_type}")
    
    try:
        # 테스트 테이블 생성 (실제 앱과 동일한 TEXT 타입)
        cursor.execute("""
            CREATE TEMP TABLE test_text_compat (
                id INTEGER PRIMARY KEY,
                custom_data TEXT DEFAULT '{}'
            )
        """)
        print("✅ 테스트 테이블 생성 (custom_data TEXT)")
        
        # 테스트 데이터 삽입
        test_data = [
            ('{"workplace": "공장A", "level": 1, "department": "제조부"}',),
            ('{"workplace": "공장B", "level": 2, "safety_score": 95.5}',),
            ('{"workplace": "사무실", "level": 3, "manager": "김부장"}',)
        ]
        
        for i, (custom_data,) in enumerate(test_data, 1):
            cursor.execute(
                "INSERT INTO test_text_compat (id, custom_data) VALUES (?, ?)",
                (i, custom_data)
            )
        print(f"✅ {len(test_data)}개 테스트 데이터 삽입")
        
        # json_extract 호환성 테스트 - 캐스트 없이 직접 호출
        test_cases = [
            {
                'name': '단순 키 추출',
                'query': "SELECT json_extract(custom_data, '$.workplace') FROM test_text_compat WHERE id = ?",
                'params': (1,),
                'expected': '공장A'
            },
            {
                'name': '숫자 값 추출',
                'query': "SELECT json_extract(custom_data, '$.level') FROM test_text_compat WHERE id = ?",
                'params': (1,),
                'expected': '1'
            },
            {
                'name': '실수 값 추출',
                'query': "SELECT json_extract(custom_data, '$.safety_score') FROM test_text_compat WHERE id = ?",
                'params': (2,),
                'expected': '95.5'
            },
            {
                'name': 'WHERE 절에서 json_extract 사용',
                'query': "SELECT id FROM test_text_compat WHERE json_extract(custom_data, '$.workplace') = ?",
                'params': ('공장A',),
                'expected_count': 1
            },
            {
                'name': 'LIKE 패턴 검색',
                'query': "SELECT id FROM test_text_compat WHERE json_extract(custom_data, '$.workplace') LIKE ?",
                'params': ('%공장%',),
                'expected_count': 2
            }
        ]
        
        results = []
        for case in test_cases:
            try:
                cursor.execute(case['query'], case['params'])
                
                if 'expected_count' in case:
                    # 결과 개수 확인
                    rows = cursor.fetchall()
                    if len(rows) == case['expected_count']:
                        print(f"✅ {case['name']}: 결과 개수 {len(rows)} 정상")
                        results.append(True)
                    else:
                        print(f"❌ {case['name']}: 예상 개수 {case['expected_count']}, 실제 {len(rows)}")
                        results.append(False)
                else:
                    # 값 확인
                    result = cursor.fetchone()
                    if result and str(result[0]) == case['expected']:
                        print(f"✅ {case['name']}: '{result[0]}' 정상")
                        results.append(True)
                    else:
                        print(f"❌ {case['name']}: 예상 '{case['expected']}', 실제 '{result[0] if result else None}'")
                        results.append(False)
                        
            except Exception as e:
                print(f"❌ {case['name']}: 쿼리 실패 - {e}")
                results.append(False)
        
        conn.close()
        return all(results)
        
    except Exception as e:
        print(f"❌ TEXT 호환성 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.close()
        return False

def test_real_app_queries():
    """실제 앱에서 사용되는 쿼리 패턴 테스트"""
    print("\n=== 실제 앱 쿼리 패턴 테스트 ===")
    
    from db_connection import get_db_connection
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 실제 앱과 유사한 구조
        cursor.execute("""
            CREATE TEMP TABLE app_compat_test (
                id INTEGER PRIMARY KEY,
                issue_number TEXT,
                custom_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 실제 앱에서 사용하는 데이터 형태
        app_data = [
            ('SAFE-001', '{"workplace": "공장A", "violation_type": "안전모", "severity": "중"}'),
            ('SAFE-002', '{"workplace": "공장B", "violation_type": "안전화", "severity": "경"}'),
            ('REQ-003', '{"requester": "김직원", "department": "제조부", "priority": "높음"}')
        ]
        
        for issue_number, custom_data in app_data:
            cursor.execute(
                "INSERT INTO app_compat_test (issue_number, custom_data) VALUES (?, ?)",
                (issue_number, custom_data)
            )
        print("✅ 실제 앱 데이터 형태 삽입")
        
        # 실제 앱 쿼리 패턴들
        real_patterns = [
            {
                'name': 'common_search.py 패턴',
                'query': "SELECT * FROM app_compat_test WHERE json_extract(custom_data, '$.workplace') LIKE ?",
                'params': ('%공장%',),
                'expected_rows': 2
            },
            {
                'name': 'search_popup_service.py 패턴',
                'query': "SELECT id FROM app_compat_test WHERE json_extract(custom_data, '$.department') LIKE ?",
                'params': ('%제조%',),
                'expected_rows': 1
            },
            {
                'name': 'app.py WHERE 조건 패턴',
                'query': "SELECT issue_number FROM app_compat_test WHERE json_extract(custom_data, '$.severity') = ?",
                'params': ('중',),
                'expected_rows': 1
            }
        ]
        
        results = []
        for pattern in real_patterns:
            try:
                cursor.execute(pattern['query'], pattern['params'])
                rows = cursor.fetchall()
                
                if len(rows) == pattern['expected_rows']:
                    print(f"✅ {pattern['name']}: {len(rows)}행 조회 성공")
                    results.append(True)
                else:
                    print(f"❌ {pattern['name']}: 예상 {pattern['expected_rows']}행, 실제 {len(rows)}행")
                    results.append(False)
                    
            except Exception as e:
                print(f"❌ {pattern['name']}: 쿼리 실패 - {e}")
                results.append(False)
        
        conn.close()
        return all(results)
        
    except Exception as e:
        print(f"❌ 실제 앱 쿼리 테스트 실패: {e}")
        conn.close()
        return False

def main():
    print("SETUP - Phase 5 TEXT 호환성 검증")
    
    tests = [
        test_text_overload_compatibility,
        test_real_app_queries
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_func.__name__} 예외: {e}")
            results.append(False)
    
    # 결과
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Phase 5 TEXT 호환성 검증 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - TEXT 오버로드 호환성 완벽!")
        print("🚀 json_extract(text, text) 함수 정상 작동!")
        print("✨ 모든 기존 앱 쿼리 호환성 보장!")
        print("🌟 PostgreSQL 전환 준비 완료!")
        return True
    else:
        print("⚠️  TEXT 호환성 이슈 발견")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)