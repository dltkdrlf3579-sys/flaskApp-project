#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 5 실제 CompatConnection 테스트
db/compat.py의 실제 구현 검증
"""
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(__file__))

def test_real_compat_logic():
    """실제 CompatConnection의 변환 로직 검증"""
    print("\n=== 실제 CompatConnection 로직 검증 ===")
    
    # 실제 CompatConnection import
    from db.compat import CompatConnection
    
    # 더미 PostgreSQL 연결 생성 (실제 연결 없이 변환만 테스트)
    class TestCompatConnection(CompatConnection):
        def __init__(self):
            # 부모 생성자 우회하고 필요한 속성만 설정
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestCompatConnection()
    
    # 실제 변환 로직 테스트
    test_cases = [
        {
            'name': '기본 변환',
            'input': 'SELECT * FROM users WHERE id = ?',
            'expected': 'SELECT * FROM users WHERE id = %s'
        },
        {
            'name': '다중 파라미터',
            'input': 'INSERT INTO users (name, email) VALUES (?, ?)',
            'expected': 'INSERT INTO users (name, email) VALUES (%s, %s)'
        },
        {
            'name': '문자열 보호',
            'input': "SELECT * FROM test WHERE col = ? AND note = 'contains ? here'",
            'expected': "SELECT * FROM test WHERE col = %s AND note = 'contains ? here'"
        },
        {
            'name': '복합 케이스',
            'input': "UPDATE users SET name = ? WHERE id = ? AND status = 'active'",
            'expected': "UPDATE users SET name = %s WHERE id = %s AND status = 'active'"
        }
    ]
    
    results = []
    for case in test_cases:
        try:
            converted = compat_conn._convert_sql(case['input'])
            
            if converted == case['expected']:
                print(f"✅ {case['name']}: 실제 로직 성공")
                results.append(True)
            else:
                print(f"❌ {case['name']}: 실제 로직 실패")
                print(f"   입력: {case['input']}")
                print(f"   예상: {case['expected']}")
                print(f"   실제: {converted}")
                results.append(False)
        except Exception as e:
            print(f"❌ {case['name']}: 예외 - {e}")
            import traceback
            traceback.print_exc()
            results.append(False)
    
    return all(results)

def test_placeholder_conversion_method():
    """_safe_placeholder_conversion 메서드 직접 테스트"""
    print("\n=== _safe_placeholder_conversion 메서드 직접 테스트 ===")
    
    from db.compat import CompatConnection
    
    class TestCompatConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = True
            self._conn = None
    
    compat_conn = TestCompatConnection()
    
    # placeholder 변환만 테스트
    placeholder_cases = [
        {
            'name': '단순 변환',
            'input': 'SELECT * FROM test WHERE id = ?',
            'expected': 'SELECT * FROM test WHERE id = %s'
        },
        {
            'name': '문자열 내 ? 보호',
            'input': "SELECT * FROM test WHERE data = 'value?' AND col = ?",
            'expected': "SELECT * FROM test WHERE data = 'value?' AND col = %s"
        },
        {
            'name': '이스케이프 처리',
            'input': "SELECT * FROM test WHERE msg = 'can''t find ?' AND id = ?",
            'expected': "SELECT * FROM test WHERE msg = 'can''t find ?' AND id = %s"
        }
    ]
    
    results = []
    for case in placeholder_cases:
        try:
            converted = compat_conn._safe_placeholder_conversion(case['input'])
            
            if converted == case['expected']:
                print(f"✅ {case['name']}: placeholder 변환 성공")
                results.append(True)
            else:
                print(f"❌ {case['name']}: placeholder 변환 실패")
                print(f"   입력: {case['input']}")
                print(f"   예상: {case['expected']}")
                print(f"   실제: {converted}")
                results.append(False)
        except Exception as e:
            print(f"❌ {case['name']}: placeholder 변환 예외 - {e}")
            results.append(False)
    
    return all(results)

def test_sqlite_mode_no_conversion():
    """SQLite 모드에서는 변환하지 않는지 확인"""
    print("\n=== SQLite 모드 변환 없음 확인 ===")
    
    from db.compat import CompatConnection
    
    class TestSQLiteConnection(CompatConnection):
        def __init__(self):
            self.is_postgres = False  # SQLite 모드
            self._conn = None
    
    compat_conn = TestSQLiteConnection()
    
    # SQLite 모드에서는 변환하지 않아야 함
    test_sql = "SELECT * FROM users WHERE name = ? AND age > ?"
    converted = compat_conn._convert_sql(test_sql)
    
    if converted == test_sql:
        print("✅ SQLite 모드: 변환하지 않음 (정상)")
        return True
    else:
        print(f"❌ SQLite 모드: 불필요한 변환 발생 - {converted}")
        return False

def main():
    print("SETUP - Phase 5 실제 CompatConnection 로직 검증")
    
    tests = [
        test_real_compat_logic,
        test_placeholder_conversion_method,
        test_sqlite_mode_no_conversion
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
    
    print(f"\n=== Phase 5 실제 구현 검증 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 5 실제 구현 완벽!")
        print("🚀 CompatConnection의 placeholder 변환 시스템 검증 완료!")
        print("✨ SQLite ↔ PostgreSQL 호환성 완성!")
        return True
    else:
        print("⚠️  실제 구현에 이슈가 있음")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)