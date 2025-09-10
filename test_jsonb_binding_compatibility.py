#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
JSONB 바인딩 호환성 테스트
TEXT → JSONB 마이그레이션 후 앱 코드의 파라미터 바인딩 이슈 검증
"""
import sys
import os
import psycopg
import json

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def get_config():
    """PostgreSQL 연결 설정"""
    return 'postgresql://postgres:admin123@localhost:5432/portal_dev'

def test_text_to_jsonb_binding():
    """TEXT → JSONB 파라미터 바인딩 호환성 테스트"""
    print("\n=== TEXT → JSONB 파라미터 바인딩 테스트 ===")
    
    admin_dsn = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 테스트 환경 준비
        print("--- 테스트 환경 준비 ---")
        cur.execute("DROP TABLE IF EXISTS jsonb_binding_test CASCADE")
        
        # TEXT 컬럼으로 시작
        cur.execute("""
            CREATE TABLE jsonb_binding_test (
                id SERIAL PRIMARY KEY,
                custom_data TEXT DEFAULT '{}'
            )
        """)
        
        # 기존 앱 패턴: JSON 문자열을 TEXT로 바인딩
        test_json = '{"workplace": "공장A", "type": "사고", "severity": "중"}'
        
        print("--- TEXT 컬럼에 JSON 문자열 바인딩 ---")
        cur.execute("INSERT INTO jsonb_binding_test (custom_data) VALUES (%s)", (test_json,))
        print("✅ TEXT 컬럼 바인딩 성공")
        
        # JSONB로 변환
        print("--- JSONB 변환 ---")
        cur.execute("ALTER TABLE jsonb_binding_test ALTER COLUMN custom_data TYPE JSONB USING custom_data::JSONB")
        cur.execute("ALTER TABLE jsonb_binding_test ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB")
        print("✅ JSONB 변환 완료")
        
        # 기존 앱 패턴이 여전히 작동하는지 테스트
        print("--- JSONB 컬럼에 JSON 문자열 바인딩 테스트 ---")
        test_cases = [
            {
                'name': 'INSERT with JSON string',
                'query': 'INSERT INTO jsonb_binding_test (custom_data) VALUES (%s)',
                'params': ('{"workplace": "공장B", "type": "점검"}',),
                'expected_success': True
            },
            {
                'name': 'UPDATE with JSON string',
                'query': 'UPDATE jsonb_binding_test SET custom_data = %s WHERE id = 1',
                'params': ('{"workplace": "공장C", "type": "개선", "updated": true}',),
                'expected_success': True
            },
            {
                'name': 'INSERT with invalid JSON',
                'query': 'INSERT INTO jsonb_binding_test (custom_data) VALUES (%s)',
                'params': ('invalid json string',),
                'expected_success': False
            },
            {
                'name': 'INSERT with Python dict (should fail)',
                'query': 'INSERT INTO jsonb_binding_test (custom_data) VALUES (%s)',
                'params': ({"workplace": "공장D", "type": "dict"},),
                'expected_success': False
            }
        ]
        
        results = []
        for test_case in test_cases:
            try:
                cur.execute(test_case['query'], test_case['params'])
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
            
            if success == test_case['expected_success']:
                if success:
                    print(f"✅ {test_case['name']}: 성공 (예상대로)")
                else:
                    print(f"✅ {test_case['name']}: 실패 (예상대로) - {error}")
                results.append(True)
            else:
                if success:
                    print(f"❌ {test_case['name']}: 예상외 성공")
                else:
                    print(f"❌ {test_case['name']}: 예상외 실패 - {error}")
                results.append(False)
        
        # 데이터 검증
        print("--- 저장된 데이터 검증 ---")
        cur.execute("SELECT id, custom_data, custom_data->>'workplace' FROM jsonb_binding_test ORDER BY id")
        rows = cur.fetchall()
        
        for row in rows:
            print(f"ID {row[0]}: {row[1]} → workplace: {row[2]}")
        
        conn.close()
        return all(results)
        
    except Exception as e:
        print(f"❌ JSONB 바인딩 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_app_compatibility_patterns():
    """실제 앱 코드 패턴 호환성 테스트"""
    print("\n=== 실제 앱 패턴 호환성 테스트 ===")
    
    admin_dsn = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 실제 앱에서 사용하는 패턴들 시뮬레이션
        cur.execute("DROP TABLE IF EXISTS app_pattern_test CASCADE")
        cur.execute("""
            CREATE TABLE app_pattern_test (
                id SERIAL PRIMARY KEY,
                custom_data JSONB DEFAULT '{}'::JSONB
            )
        """)
        
        # 앱 코드 패턴 시뮬레이션
        app_patterns = [
            {
                'name': 'add_page_routes.py UPDATE 패턴',
                'action': lambda: cur.execute(
                    "UPDATE app_pattern_test SET custom_data = %s WHERE id = %s",
                    (json.dumps({"workplace": "공장A", "updated_by": "user1"}), 1)
                )
            },
            {
                'name': 'app.py INSERT 패턴', 
                'action': lambda: cur.execute(
                    "INSERT INTO app_pattern_test (custom_data) VALUES (%s)",
                    (json.dumps({"accident_type": "낙하", "severity": "중"}),)
                )
            },
            {
                'name': 'board_services.py UPDATE 패턴',
                'action': lambda: cur.execute(
                    "UPDATE app_pattern_test SET custom_data = %s WHERE id = %s",
                    (json.dumps({"title": "제목", "content": "내용", "updated_at": "2025-09-06"}), 2)
                )
            },
            {
                'name': '원시 문자열 바인딩 (위험)',
                'action': lambda: cur.execute(
                    "INSERT INTO app_pattern_test (custom_data) VALUES (%s)",
                    ('{"raw": "string", "test": true}',)
                )
            }
        ]
        
        # 첫 번째 레코드 생성
        cur.execute("INSERT INTO app_pattern_test (custom_data) VALUES (%s)", (json.dumps({"init": "data"}),))
        
        results = []
        for pattern in app_patterns:
            try:
                pattern['action']()
                print(f"✅ {pattern['name']}: 성공")
                results.append(True)
            except Exception as e:
                print(f"❌ {pattern['name']}: 실패 - {e}")
                results.append(False)
        
        # 최종 데이터 확인
        cur.execute("SELECT id, custom_data FROM app_pattern_test ORDER BY id")
        rows = cur.fetchall()
        
        print("--- 저장된 데이터 확인 ---")
        for row in rows:
            print(f"ID {row[0]}: {row[1]}")
        
        conn.close()
        return all(results)
        
    except Exception as e:
        print(f"❌ 앱 패턴 테스트 실패: {e}")
        return False

def create_compatibility_guide():
    """JSONB 호환성 가이드 생성"""
    print("\n=== JSONB 호환성 가이드 생성 ===")
    
    guide_content = """# JSONB 바인딩 호환성 가이드

## 🚨 중요: JSONB 마이그레이션 후 앱 코드 수정 필요

### 문제점
TEXT → JSONB 마이그레이션 후, 기존 앱 코드의 파라미터 바인딩에 타입 불일치 가능성

### 해결책

#### ✅ 권장 방법 1: json.dumps() 사용
```python
# 기존 (TEXT 시절)
custom_data = '{"workplace": "공장A", "type": "사고"}'
cursor.execute("UPDATE table SET custom_data = %s", (custom_data,))

# 수정 (JSONB 호환)
import json
custom_data_dict = {"workplace": "공장A", "type": "사고"}
cursor.execute("UPDATE table SET custom_data = %s", (json.dumps(custom_data_dict),))
```

#### ✅ 권장 방법 2: 명시적 캐스팅
```python
# JSONB 명시적 캐스팅
cursor.execute("UPDATE table SET custom_data = %s::jsonb", (json_string,))
```

#### ✅ 권장 방법 3: CompatConnection 확장
db/compat.py의 _convert_params() 메서드에서 자동 변환 처리

### 수정 대상 파일
- add_page_routes.py: SET custom_data = %s (2곳)
- app.py: custom_data = %s (3곳)  
- board_services.py: custom_data = %s (1곳)
- fix_list_field.py: SET custom_data = %s (1곳)

### 검증 방법
python test_jsonb_binding_compatibility.py 실행

### 주의사항
- Python dict 직접 바인딩 불가
- 무효한 JSON 문자열 → 오류
- json.dumps() 사용으로 안전 보장
"""
    
    guide_path = os.path.join(os.path.dirname(__file__), 'JSONB_BINDING_COMPATIBILITY.md')
    with open(guide_path, 'w', encoding='utf-8') as f:
        f.write(guide_content)
    
    print(f"✅ 호환성 가이드 생성: {guide_path}")
    return guide_path

def main():
    print("COMPATIBILITY CHECK - JSONB 바인딩 호환성 검증")
    
    tests = [
        ("TEXT → JSONB 바인딩 테스트", test_text_to_jsonb_binding),
        ("실제 앱 패턴 호환성", test_app_compatibility_patterns),
        ("호환성 가이드 생성", lambda: create_compatibility_guide() is not None)
    ]
    
    results = []
    for test_name, test_func in tests:
        try:
            print(f"\n🔄 {test_name} 시작...")
            result = test_func()
            results.append(result)
            if result:
                print(f"✅ {test_name} 완료")
            else:
                print(f"⚠️  {test_name} 부분 실패")
        except Exception as e:
            print(f"❌ {test_name} 실패: {e}")
            results.append(False)
    
    # 결과
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n=== JSONB 바인딩 호환성 검증 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - JSONB 바인딩 호환성 확인!")
        print("✅ 기존 앱 코드와 JSONB 호환 가능")
        print("📋 주의사항: json.dumps() 사용 권장")
        return True
    else:
        print("⚠️  JSONB 바인딩 이슈 발견")
        print("🔧 수정 필요: 앱 코드에서 json.dumps() 활용")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)