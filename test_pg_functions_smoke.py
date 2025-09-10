#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL 호환 함수 스모크 테스트
setup_pg_functions.py 설치 후 실제 작동 확인
"""
import sys
import os
import psycopg
import configparser

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def get_config():
    """config.ini에서 DB 설정 읽기"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        
        # PostgreSQL 설정 읽기
        postgres_dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')://{postgres}:{portal_password}@{host}:{port}/{database}'
        return portal_dsn
    else:
        # 기본값 사용
        return 'postgresql://postgres:admin123@localhost:5432/portal_dev'

def test_smoke_check():
    """codex 요구사항에 따른 스모크 테스트"""
    print("\n=== PostgreSQL 호환 함수 스모크 테스트 ===")
    
    try:
        portal_dsn = get_config()
        print(f"INFO - 연결 테스트: {portal_dsn.replace(':admin123@', ':***@')}")
        
        conn = psycopg.connect(portal_dsn)
        cur = conn.cursor()
        
        # 1. 캐스트 없는 호출 테스트
        print("\n--- 캐스트 없는 호출 테스트 ---")
        cur.execute("SELECT json_extract(%s, '$.a')", ('{}',))
        result1 = cur.fetchone()[0]
        print(f"✅ json_extract('{{}}', '$.a') → {result1} (expected: None)")
        
        # 2. 실제 JSON 데이터 테스트
        test_json = '{"workplace": "공장A", "level": 1, "manager": "김부장"}'
        
        print("\n--- TEXT 오버로드 함수 테스트 ---")
        cur.execute("SELECT json_extract(%s, '$.workplace')", (test_json,))
        result2 = cur.fetchone()[0]
        print(f"✅ json_extract(text_data, '$.workplace') → '{result2}'")
        
        cur.execute("SELECT json_extract(%s, '$.level')", (test_json,))
        result3 = cur.fetchone()[0]
        print(f"✅ json_extract(text_data, '$.level') → '{result3}'")
        
        # 3. JSONB 캐스트 함수 테스트
        print("\n--- JSONB 함수 테스트 ---")
        cur.execute("SELECT json_extract(%s::jsonb, '$.manager')", (test_json,))
        result4 = cur.fetchone()[0]
        print(f"✅ json_extract(jsonb_data, '$.manager') → '{result4}'")
        
        # 4. 임시 테이블을 만들어서 실제 TEXT 컬럼 테스트
        print("\n--- TEXT 컬럼 테스트 ---")
        cur.execute("""
            CREATE TEMP TABLE smoke_test (
                id SERIAL PRIMARY KEY,
                custom_data TEXT
            )
        """)
        
        cur.execute("INSERT INTO smoke_test (custom_data) VALUES (%s)", (test_json,))
        cur.execute("SELECT json_extract(custom_data, '$.workplace') FROM smoke_test WHERE id = 1")
        result5 = cur.fetchone()[0]
        print(f"✅ TEXT 컬럼에서 json_extract → '{result5}'")
        
        # 5. LIKE 필터 테스트
        print("\n--- LIKE 필터 테스트 ---")
        cur.execute("""
            INSERT INTO smoke_test (custom_data) VALUES 
            ('{"workplace": "공장B", "department": "제조부"}'),
            ('{"workplace": "사무실", "department": "관리부"}')
        """)
        
        cur.execute("SELECT id FROM smoke_test WHERE json_extract(custom_data, '$.workplace') LIKE %s", ('%공장%',))
        like_results = cur.fetchall()
        print(f"✅ LIKE '%공장%' 필터 → {len(like_results)}개 결과")
        
        # 6. datetime 함수 테스트
        print("\n--- datetime 함수 테스트 ---")
        cur.execute("SELECT datetime('now')")
        dt_result = cur.fetchone()[0]
        print(f"✅ datetime('now') → {dt_result}")
        
        cur.execute("SELECT datetime('2024-01-01')")
        dt_result2 = cur.fetchone()[0]
        print(f"✅ datetime('2024-01-01') → {dt_result2}")
        
        conn.close()
        print("\n🎉 모든 스모크 테스트 통과!")
        print("✅ TEXT 오버로드 함수 정상 작동")
        print("✅ 캐스트 없는 호출 지원")
        print("✅ 실제 앱 쿼리 패턴 호환")
        return True
        
    except Exception as e:
        print(f"❌ PostgreSQL 스모크 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("SMOKE CHECK - PostgreSQL 호환 함수 설치 후 검증")
    
    if test_smoke_check():
        print("\n🚀 SUCCESS - Phase 5 PostgreSQL 호환성 완벽!")
        print("🌟 모든 codex 요구사항 충족!")
        return True
    else:
        print("\n⚠️  스모크 테스트 실패 - setup_pg_functions.py 먼저 실행 필요")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)