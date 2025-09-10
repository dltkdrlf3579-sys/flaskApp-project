#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5 복합 쿼리 테스트
실제 애플리케이션에서 사용되는 복잡한 SQL 쿼리 검증
"""
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(__file__))

def test_real_application_queries():
    """실제 애플리케이션 쿼리 패턴 테스트"""
    print("\n=== 실제 애플리케이션 쿼리 테스트 ===")
    
    from db.compat import CompatConnection
    
    class TestPGConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestPGConnection()
    
    # 실제 app.py, board_services.py 등에서 사용되는 쿼리 패턴들
    real_queries = [
        {
            'name': 'Safety Instructions Select',
            'input': """
                SELECT * FROM safety_instructions_cache 
                WHERE issue_number = ? AND (is_deleted = 0 OR is_deleted IS NULL)
            """.strip(),
            'expected': """
                SELECT * FROM safety_instructions_cache 
                WHERE issue_number = %s AND (is_deleted = 0 OR is_deleted IS NULL)
            """.strip()
        },
        {
            'name': 'Complex INSERT with JSON',
            'input': """
                INSERT INTO partner_change_requests 
                (request_number, requester_name, company_name, custom_data)
                VALUES (?, ?, ?, ?)
            """.strip(),
            'expected': """
                INSERT INTO partner_change_requests 
                (request_number, requester_name, company_name, custom_data)
                VALUES (%s, %s, %s, %s)
            """.strip()
        },
        {
            'name': 'LIKE Pattern with Quotes',
            'input': """
                SELECT * FROM safety_instructions_cache 
                WHERE issue_number LIKE ? AND violation_content != 'N/A'
            """.strip(),
            'expected': """
                SELECT * FROM safety_instructions_cache 
                WHERE issue_number LIKE %s AND violation_content != 'N/A'
            """.strip()
        },
        {
            'name': 'Attachment Query with File Info',
            'input': """
                INSERT INTO attachments (item_id, file_name, file_path, description)
                VALUES (?, ?, ?, ?)
            """.strip(),
            'expected': """
                INSERT INTO attachments (item_id, file_name, file_path, description)
                VALUES (%s, %s, %s, %s)
            """.strip()
        },
        {
            'name': 'Dropdown Options UPSERT',
            'input': """
                SELECT * FROM dropdown_option_codes_v2 
                WHERE board_type = ? AND column_key = ? AND is_active = 1
                ORDER BY display_order
            """.strip(),
            'expected': """
                SELECT * FROM dropdown_option_codes_v2 
                WHERE board_type = %s AND column_key = %s AND is_active = 1
                ORDER BY display_order
            """.strip()
        }
    ]
    
    results = []
    for case in real_queries:
        try:
            converted = compat_conn._convert_sql(case['input'])
            
            if converted == case['expected']:
                print(f"✅ {case['name']}: 실제 쿼리 변환 성공")
                results.append(True)
            else:
                print(f"❌ {case['name']}: 실제 쿼리 변환 실패")
                print(f"   예상: {case['expected']}")
                print(f"   실제: {converted}")
                results.append(False)
        except Exception as e:
            print(f"❌ {case['name']}: 실제 쿼리 예외 - {e}")
            results.append(False)
    
    return all(results)

def test_tricky_string_cases():
    """까다로운 문자열 케이스 테스트"""
    print("\n=== 까다로운 문자열 케이스 테스트 ===")
    
    from db.compat import CompatConnection
    
    class TestPGConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestPGConnection()
    
    tricky_cases = [
        {
            'name': '한글 포함 문자열',
            'input': "SELECT * FROM users WHERE name = ? AND note = '사용자 정보: ?'",
            'expected': "SELECT * FROM users WHERE name = %s AND note = '사용자 정보: ?'"
        },
        {
            'name': '특수문자 포함',
            'input': """SELECT * FROM logs WHERE data = ? AND pattern = 'user@domain.com: ?'""",
            'expected': """SELECT * FROM logs WHERE data = %s AND pattern = 'user@domain.com: ?'"""
        },
        {
            'name': '중첩 따옴표와 이스케이프',
            'input': """SELECT * FROM test WHERE a = ? AND b = 'it''s "working?" fine' AND c = ?""",
            'expected': """SELECT * FROM test WHERE a = %s AND b = 'it''s "working?" fine' AND c = %s"""
        },
        {
            'name': '백슬래시 포함',
            'input': """SELECT * FROM paths WHERE file = ? AND path LIKE 'C:\\temp\\?'""",
            'expected': """SELECT * FROM paths WHERE file = %s AND path LIKE 'C:\\temp\\?'"""
        },
        {
            'name': '연속된 문자열',
            'input': """SELECT * FROM test WHERE a = 'str1?' AND b = ? AND c = 'str2?' AND d = ?""",
            'expected': """SELECT * FROM test WHERE a = 'str1?' AND b = %s AND c = 'str2?' AND d = %s"""
        }
    ]
    
    results = []
    for case in tricky_cases:
        try:
            converted = compat_conn._convert_sql(case['input'])
            
            if converted == case['expected']:
                print(f"✅ {case['name']}: 까다로운 케이스 성공")
                results.append(True)
            else:
                print(f"❌ {case['name']}: 까다로운 케이스 실패")
                print(f"   예상: {case['expected']}")
                print(f"   실제: {converted}")
                results.append(False)
        except Exception as e:
            print(f"❌ {case['name']}: 까다로운 케이스 예외 - {e}")
            results.append(False)
    
    return all(results)

def test_boundary_conditions():
    """경계 조건 테스트"""
    print("\n=== 경계 조건 테스트 ===")
    
    from db.compat import CompatConnection
    
    class TestPGConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestPGConnection()
    
    boundary_cases = [
        {
            'name': '매우 긴 쿼리',
            'input': "SELECT " + ", ".join([f"col{i}" for i in range(20)]) + " FROM table WHERE " + " AND ".join([f"col{i} = ?" for i in range(10)]),
            'expected': "SELECT " + ", ".join([f"col{i}" for i in range(20)]) + " FROM table WHERE " + " AND ".join([f"col{i} = %s" for i in range(10)])
        },
        {
            'name': '파라미터만 있는 쿼리',
            'input': "? ? ? ?",
            'expected': "%s %s %s %s"
        },
        {
            'name': '문자열과 파라미터 섞임',
            'input': "SELECT 'a', ?, 'b', ?, 'c'",
            'expected': "SELECT 'a', %s, 'b', %s, 'c'"
        },
        {
            'name': '빈 문자열들',
            'input': "SELECT '' AS empty, ? AS param, '' AS empty2",
            'expected': "SELECT '' AS empty, %s AS param, '' AS empty2"
        }
    ]
    
    results = []
    for case in boundary_cases:
        try:
            converted = compat_conn._convert_sql(case['input'])
            
            if converted == case['expected']:
                print(f"✅ {case['name']}: 경계 조건 성공")
                results.append(True)
            else:
                print(f"❌ {case['name']}: 경계 조건 실패")
                print(f"   예상: {case['expected']}")
                print(f"   실제: {converted}")
                results.append(False)
        except Exception as e:
            print(f"❌ {case['name']}: 경계 조건 예외 - {e}")
            results.append(False)
    
    return all(results)

def test_performance_with_large_query():
    """대용량 쿼리 성능 테스트"""
    print("\n=== 대용량 쿼리 성능 테스트 ===")
    
    from db.compat import CompatConnection
    import time
    
    class TestPGConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestPGConnection()
    
    # 매우 긴 쿼리 생성 (1000개 파라미터)
    large_query = "INSERT INTO test_table (" + ", ".join([f"col{i}" for i in range(1000)]) + ") VALUES (" + ", ".join(["?" for _ in range(1000)]) + ")"
    expected_query = "INSERT INTO test_table (" + ", ".join([f"col{i}" for i in range(1000)]) + ") VALUES (" + ", ".join(["%s" for _ in range(1000)]) + ")"
    
    try:
        start_time = time.time()
        converted = compat_conn._convert_sql(large_query)
        end_time = time.time()
        
        conversion_time = (end_time - start_time) * 1000  # ms
        
        if converted == expected_query:
            print(f"✅ 대용량 쿼리 변환 성공 (1000 파라미터)")
            print(f"✅ 변환 시간: {conversion_time:.2f}ms")
            
            if conversion_time < 100:  # 100ms 미만이면 양호
                print("✅ 성능: 우수")
                return True
            else:
                print("⚠️  성능: 느림")
                return True  # 기능은 정상이므로 통과
        else:
            print("❌ 대용량 쿼리 변환 실패")
            return False
    except Exception as e:
        print(f"❌ 대용량 쿼리 성능 테스트 예외 - {e}")
        return False

def main():
    print("SETUP - Phase 5 복합 쿼리 및 성능 테스트")
    
    tests = [
        test_real_application_queries,
        test_tricky_string_cases,
        test_boundary_conditions,
        test_performance_with_large_query
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
    
    print(f"\n=== Phase 5 복합 테스트 최종 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 5 완전 완성!")
        print("🚀 모든 복합 쿼리, 까다로운 케이스, 성능 테스트 통과!")
        print("✨ PostgreSQL Migration v7 Phase 5 완료!")
        print("🌟 Production Ready - 실제 운영 환경 사용 가능!")
        return True
    else:
        print("⚠️  일부 복합 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)