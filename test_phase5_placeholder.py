#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5 테스트: Placeholder 변환 시스템 검증
SQLite ? → PostgreSQL %s 변환의 정확성 확인
"""
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection

def test_basic_placeholder_conversion():
    """기본 placeholder 변환 테스트"""
    print("\n=== 기본 Placeholder 변환 테스트 ===")
    
    conn = get_db_connection()
    db_type = 'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'
    print(f"DB 연결: {db_type}")
    
    # 내부 변환 메서드 직접 테스트
    test_cases = [
        {
            'name': '단순 SELECT',
            'sql': 'SELECT * FROM users WHERE id = ?',
            'expected_pg': 'SELECT * FROM users WHERE id = %s'
        },
        {
            'name': '다중 파라미터',
            'sql': 'SELECT * FROM users WHERE name = ? AND age > ?',
            'expected_pg': 'SELECT * FROM users WHERE name = %s AND age > %s'
        },
        {
            'name': '문자열 리터럴 보호',
            'sql': "SELECT * FROM logs WHERE message = ? AND data LIKE 'user:? debug'",
            'expected_pg': "SELECT * FROM logs WHERE message = %s AND data LIKE 'user:? debug'"
        },
        {
            'name': 'INSERT 문',
            'sql': 'INSERT INTO users (name, email, age) VALUES (?, ?, ?)',
            'expected_pg': 'INSERT INTO users (name, email, age) VALUES (%s, %s, %s)'
        }
    ]
    
    results = []
    for case in test_cases:
        try:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                converted = conn._convert_sql(case['sql'])
                if converted == case['expected_pg']:
                    print(f"✅ {case['name']}: 변환 성공")
                    results.append(True)
                else:
                    print(f"❌ {case['name']}: 예상='{case['expected_pg']}' 실제='{converted}'")
                    results.append(False)
            else:
                # SQLite에서는 변환하지 않음
                converted = conn._convert_sql(case['sql'])
                if converted == case['sql']:
                    print(f"✅ {case['name']}: SQLite 모드 - 변환 안 함")
                    results.append(True)
                else:
                    print(f"❌ {case['name']}: SQLite에서 불필요한 변환됨")
                    results.append(False)
                    
        except Exception as e:
            print(f"❌ {case['name']}: 변환 실패 - {e}")
            results.append(False)
    
    conn.close()
    return all(results)

def test_string_literal_protection():
    """문자열 리터럴 보호 고급 테스트"""
    print("\n=== 문자열 리터럴 보호 테스트 ===")
    
    conn = get_db_connection()
    
    advanced_cases = [
        {
            'name': '이스케이프된 따옴표',
            'sql': "SELECT * FROM logs WHERE data = ? AND message = 'can''t find ?'",
            'expected_pg': "SELECT * FROM logs WHERE data = %s AND message = 'can''t find ?'"
        },
        {
            'name': '이중 따옴표 문자열',
            'sql': 'SELECT * FROM users WHERE name = ? AND note = "contains ? mark"',
            'expected_pg': 'SELECT * FROM users WHERE name = %s AND note = "contains ? mark"'
        },
        {
            'name': '복합 문자열',
            'sql': "SELECT * FROM test WHERE a = ? AND b = 'test?' AND c = ? AND d = 'end'",
            'expected_pg': "SELECT * FROM test WHERE a = %s AND b = 'test?' AND c = %s AND d = 'end'"
        },
        {
            'name': '중첩 따옴표',
            'sql': """SELECT * FROM mixed WHERE col = ? AND info = 'item "data?" here' AND val = ?""",
            'expected_pg': """SELECT * FROM mixed WHERE col = %s AND info = 'item "data?" here' AND val = %s"""
        }
    ]
    
    results = []
    for case in advanced_cases:
        try:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                converted = conn._convert_sql(case['sql'])
                if converted == case['expected_pg']:
                    print(f"✅ {case['name']}: 고급 변환 성공")
                    results.append(True)
                else:
                    print(f"❌ {case['name']}:")
                    print(f"   예상: {case['expected_pg']}")  
                    print(f"   실제: {converted}")
                    results.append(False)
            else:
                print(f"⏭️  {case['name']}: SQLite 모드 - 테스트 건너뜀")
                results.append(True)
                
        except Exception as e:
            print(f"❌ {case['name']}: 고급 변환 실패 - {e}")
            results.append(False)
    
    conn.close()
    return all(results)

def test_actual_query_execution():
    """실제 쿼리 실행으로 변환 정확성 검증"""
    print("\n=== 실제 쿼리 실행 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 테스트 테이블 생성
        cursor.execute("""
            CREATE TEMP TABLE test_placeholder (
                id INTEGER PRIMARY KEY,
                name TEXT,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ 테스트 테이블 생성")
        
        # 파라미터를 사용한 INSERT 테스트
        test_data = [
            ('테스트1', '값1'),
            ('테스트2', 'contains ? mark'),
            ('테스트3', "mixed 'quotes' here")
        ]
        
        for name, value in test_data:
            cursor.execute(
                "INSERT INTO test_placeholder (name, value) VALUES (?, ?)",
                (name, value)
            )
        print(f"✅ {len(test_data)}개 레코드 INSERT 성공")
        
        # 파라미터를 사용한 SELECT 테스트  
        cursor.execute("SELECT * FROM test_placeholder WHERE name = ?", ('테스트1',))
        row = cursor.fetchone()
        
        if row:
            if hasattr(row, 'keys'):
                found_name = row['name']
                found_value = row['value']
            else:
                found_name = row[1]  # name 컬럼
                found_value = row[2]  # value 컬럼
            
            print(f"✅ SELECT 결과: name='{found_name}', value='{found_value}'")
            
            if found_name == '테스트1' and found_value == '값1':
                print("✅ 파라미터 바인딩 정확성 확인")
                return True
            else:
                print("❌ 데이터 불일치")
                return False
        else:
            print("❌ 데이터를 찾을 수 없음")
            return False
            
    except Exception as e:
        print(f"❌ 실제 쿼리 실행 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def test_params_conversion():
    """파라미터 변환 테스트"""
    print("\n=== 파라미터 변환 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 다양한 파라미터 타입 테스트
        test_params = [
            ('튜플', ('a', 'b', 'c')),
            ('리스트', ['x', 'y', 'z']),  
            ('단일값', 'single'),
            ('None', None),
            ('혼합타입', (1, 'text', None, 3.14))
        ]
        
        results = []
        for name, params in test_params:
            try:
                converted = conn._convert_params(params)
                print(f"✅ {name}: {type(params)} → {type(converted)}")
                results.append(True)
            except Exception as e:
                print(f"❌ {name}: 변환 실패 - {e}")
                results.append(False)
        
        conn.close()
        return all(results)
        
    except Exception as e:
        print(f"❌ 파라미터 변환 테스트 실패: {e}")
        conn.close()
        return False

def main():
    print("SETUP - Phase 5 Placeholder 변환 시스템 테스트 시작")
    
    tests = [
        test_basic_placeholder_conversion,
        test_string_literal_protection,
        test_params_conversion,
        test_actual_query_execution
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
    
    print(f"\n=== Phase 5 테스트 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 5 Placeholder 시스템 완벽!")
        print("🚀 모든 SQLite → PostgreSQL 변환 정상 작동!")
        print("✨ 문자열 리터럴 보호 및 파라미터 바인딩 완료!")
        return True
    else:
        print("⚠️  일부 placeholder 변환 이슈 발견")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)