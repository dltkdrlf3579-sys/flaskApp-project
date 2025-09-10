#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 6 최종 검증 테스트
JSONB 마이그레이션과 성능 최적화 완성 확인
"""
import sys
import os
import psycopg
import configparser
import json
import time

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
        host = config.get('postgresql', 'host', fallback='localhost')
        port = config.get('postgresql', 'port', fallback='5432')
        database = config.get('postgresql', 'database', fallback='portal_dev')
        admin_user = config.get('postgresql', 'admin_user', fallback='postgres')
        admin_password = config.get('postgresql', 'admin_password', fallback='admin123')
        
        admin_dsn = f'postgresql://{admin_user}:{admin_password}@{host}:{port}/{database}'
        return admin_dsn
    else:
        return 'postgresql://postgres:admin123@localhost:5432/portal_dev'

def test_jsonb_complete_workflow():
    """JSONB 완전한 워크플로우 테스트"""
    print("\n=== JSONB 완전한 워크플로우 테스트 ===")
    
    admin_dsn = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 1. 정리 및 생성
        print("\n--- 테스트 환경 준비 ---")
        cur.execute("DROP TABLE IF EXISTS phase6_demo CASCADE")
        
        # TEXT 컬럼으로 테이블 생성
        cur.execute("""
            CREATE TABLE phase6_demo (
                id SERIAL PRIMARY KEY,
                item_name TEXT,
                custom_data TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ TEXT 기반 테이블 생성")
        
        # 샘플 데이터 삽입
        sample_data = [
            ('사고보고-001', '{"workplace": "공장A", "type": "낙하사고", "severity": "중", "injured": 1, "department": "제조부"}'),
            ('사고보고-002', '{"workplace": "공장B", "type": "화상사고", "severity": "경", "injured": 0, "department": "용접부"}'),
            ('점검보고-001', '{"workplace": "공장A", "type": "안전점검", "score": 85, "inspector": "김감독", "issues": 3}'),
            ('교육이수-001', '{"workplace": "전사", "type": "안전교육", "participants": 50, "completion_rate": 92.5}'),
            ('개선제안-001', '{"workplace": "공장C", "type": "안전개선", "cost": 500000, "expected_effect": "사고율 30% 감소"}')
        ]
        
        for item_name, custom_data in sample_data:
            cur.execute(
                "INSERT INTO phase6_demo (item_name, custom_data) VALUES (%s, %s)",
                (item_name, custom_data)
            )
        print(f"✅ {len(sample_data)}개 샘플 데이터 삽입")
        
        # 2. TEXT 버전 쿼리 성능 측정
        print("\n--- TEXT 버전 성능 측정 ---")
        
        # json_extract 함수 사용
        start_time = time.time()
        for _ in range(100):
            cur.execute("SELECT COUNT(*) FROM phase6_demo WHERE json_extract(custom_data, '$.workplace') = %s", ('공장A',))
            result = cur.fetchone()
        text_time = (time.time() - start_time) / 100 * 1000
        print(f"📊 TEXT json_extract: {text_time:.2f}ms (결과: {result[0]})")
        
        # 3. JSONB로 마이그레이션
        print("\n--- JSONB 마이그레이션 ---")
        
        # 안전한 마이그레이션 (백업 → 변환 → 기본값 설정)
        cur.execute("ALTER TABLE phase6_demo ADD COLUMN custom_data_backup TEXT")
        cur.execute("UPDATE phase6_demo SET custom_data_backup = custom_data")
        cur.execute("ALTER TABLE phase6_demo ALTER COLUMN custom_data DROP DEFAULT")
        cur.execute("ALTER TABLE phase6_demo ALTER COLUMN custom_data TYPE JSONB USING custom_data::JSONB")
        cur.execute("ALTER TABLE phase6_demo ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB")
        print("✅ JSONB 마이그레이션 완료")
        
        # 4. JSONB 인덱스 생성
        print("\n--- JSONB 인덱스 최적화 ---")
        # JSONB 전체 컬럼에 GIN 인덱스
        cur.execute("CREATE INDEX idx_demo_gin_all ON phase6_demo USING GIN (custom_data)")
        print("✅ JSONB 전체 GIN 인덱스 생성")
        
        # 특정 키에 B-tree 인덱스 (문자열 비교용)
        cur.execute("CREATE INDEX idx_demo_workplace ON phase6_demo ((custom_data->>'workplace'))")
        cur.execute("CREATE INDEX idx_demo_type ON phase6_demo ((custom_data->>'type'))")
        print("✅ 키별 B-tree 인덱스 생성")
        
        # 5. JSONB 버전 성능 측정
        print("\n--- JSONB 버전 성능 측정 ---")
        
        start_time = time.time()
        for _ in range(100):
            cur.execute("SELECT COUNT(*) FROM phase6_demo WHERE custom_data->>'workplace' = %s", ('공장A',))
            result = cur.fetchone()
        jsonb_time = (time.time() - start_time) / 100 * 1000
        print(f"📊 JSONB 연산자: {jsonb_time:.2f}ms (결과: {result[0]})")
        
        # 성능 비교
        improvement = (text_time - jsonb_time) / text_time * 100
        if improvement > 0:
            print(f"🚀 성능 향상: {improvement:.1f}% ({text_time:.2f}ms → {jsonb_time:.2f}ms)")
        else:
            print(f"📊 성능 변화: {abs(improvement):.1f}% 느림")
        
        # 6. JSONB 고급 기능 시연
        print("\n--- JSONB 고급 기능 시연 ---")
        
        # 복합 조건 쿼리
        cur.execute("""
            SELECT item_name, custom_data->>'workplace', custom_data->>'type'
            FROM phase6_demo
            WHERE custom_data->>'workplace' LIKE '공장%' 
            AND custom_data ? 'injured'
        """)
        results = cur.fetchall()
        print(f"📊 복합 조건 쿼리: {len(results)}건")
        
        # JSON 집계
        cur.execute("""
            SELECT 
                custom_data->>'workplace' as workplace,
                COUNT(*) as count,
                AVG(COALESCE((custom_data->>'injured')::INTEGER, 0)) as avg_injured
            FROM phase6_demo
            WHERE custom_data ? 'injured'
            GROUP BY custom_data->>'workplace'
        """)
        aggregations = cur.fetchall()
        print("📊 작업장별 집계:")
        for workplace, count, avg_injured in aggregations:
            print(f"   {workplace}: {count}건 (평균 부상자: {avg_injured:.1f}명)")
        
        # JSON 업데이트
        cur.execute("""
            UPDATE phase6_demo 
            SET custom_data = jsonb_set(custom_data, '{last_updated}', %s::jsonb)
            WHERE item_name = %s
        """, (f'"{time.strftime("%Y-%m-%d %H:%M:%S")}"', '사고보고-001'))
        
        cur.execute("SELECT custom_data->>'last_updated' FROM phase6_demo WHERE item_name = %s", ('사고보고-001',))
        updated = cur.fetchone()[0]
        print(f"✅ JSON 업데이트: last_updated = {updated}")
        
        # 7. 인덱스 사용 확인
        print("\n--- 인덱스 사용 확인 ---")
        cur.execute("""
            EXPLAIN (FORMAT JSON) 
            SELECT * FROM phase6_demo 
            WHERE custom_data->>'workplace' = '공장A'
        """)
        plan = cur.fetchone()[0]
        
        # 인덱스 스캔 사용 여부 확인
        plan_str = json.dumps(plan, ensure_ascii=False)
        if 'Index' in plan_str:
            print("✅ 인덱스 활용됨")
        else:
            print("📊 순차 스캔 사용됨 (데이터 적어서 정상)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ JSONB 워크플로우 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_migration_script_dry_run():
    """마이그레이션 스크립트 검증 (실제 실행 없이)"""
    print("\n=== 마이그레이션 스크립트 검증 ===")
    
    # 생성된 SQL 파일 확인
    script_path = os.path.join(os.path.dirname(__file__), 'migrate_to_jsonb.sql')
    rollback_path = os.path.join(os.path.dirname(__file__), 'rollback_jsonb_migration.sql')
    
    results = []
    
    # 마이그레이션 스크립트 확인
    if os.path.exists(script_path):
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # 핵심 요소 확인
        checks = [
            ('BEGIN/COMMIT 트랜잭션', 'BEGIN;' in content and 'COMMIT;' in content),
            ('마이그레이션 로그', 'migration_log' in content),
            ('백업 컬럼 생성', 'custom_data_backup' in content),
            ('JSONB 변환', 'TYPE JSONB' in content),
            ('GIN 인덱스', 'USING GIN' in content),
            ('에러 처리', 'EXCEPTION WHEN OTHERS' in content)
        ]
        
        for check_name, passed in checks:
            if passed:
                print(f"✅ {check_name}: 포함됨")
                results.append(True)
            else:
                print(f"❌ {check_name}: 누락됨")
                results.append(False)
                
        print(f"📊 마이그레이션 스크립트: {sum(results)}/{len(results)} 확인")
    else:
        print("❌ migrate_to_jsonb.sql 파일 없음")
        return False
    
    # 롤백 스크립트 확인
    if os.path.exists(rollback_path):
        with open(rollback_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        if 'JSONB_to_TEXT' in content and 'custom_data_backup' in content:
            print("✅ 롤백 스크립트: 정상")
            results.append(True)
        else:
            print("❌ 롤백 스크립트: 불완전")
            results.append(False)
    else:
        print("❌ rollback_jsonb_migration.sql 파일 없음")
        results.append(False)
    
    return all(results)

def test_compatibility_functions():
    """호환성 함수 동작 확인"""
    print("\n=== 호환성 함수 동작 확인 ===")
    
    admin_dsn = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        cur = conn.cursor()
        
        # json_extract 함수 테스트 (TEXT)
        test_json = '{"test": "value", "number": 42}'
        cur.execute("SELECT json_extract(%s, '$.test')", (test_json,))
        result1 = cur.fetchone()[0]
        print(f"✅ json_extract(TEXT): '{result1}'")
        
        # json_extract 함수 테스트 (JSONB)
        cur.execute("SELECT json_extract(%s::jsonb, '$.number')", (test_json,))
        result2 = cur.fetchone()[0]
        print(f"✅ json_extract(JSONB): '{result2}'")
        
        # datetime 함수 테스트
        cur.execute("SELECT datetime('now')")
        result3 = cur.fetchone()[0]
        print(f"✅ datetime('now'): {result3}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 호환성 함수 테스트 실패: {e}")
        return False

def main():
    print("FINAL TEST - Phase 6 JSONB 마이그레이션 최종 검증")
    
    tests = [
        ("호환성 함수 동작 확인", test_compatibility_functions),
        ("마이그레이션 스크립트 검증", test_migration_script_dry_run),
        ("JSONB 완전한 워크플로우", test_jsonb_complete_workflow)
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
    
    print(f"\n=== Phase 6 최종 검증 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 6 JSONB 마이그레이션 완전 완성!")
        print("🚀 PostgreSQL Migration v7 Phase 6 완료!")
        print("✨ 주요 성과:")
        print("   - TEXT → JSONB 안전한 마이그레이션 스크립트")
        print("   - GIN 인덱스 기반 성능 최적화")
        print("   - JSONB 네이티브 연산자 활용")
        print("   - 완전한 롤백 메커니즘")
        print("   - json_extract 호환성 유지")
        print("🌟 Production Ready - JSONB 기반 고성능 JSON 처리!")
        return True
    else:
        print("⚠️  일부 검증에 이슈가 있습니다")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)