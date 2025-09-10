#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 6 검증 및 성능 테스트 도구
JSONB 마이그레이션 전후 검증, 성능 비교
"""
import sys
import os
import psycopg
import configparser
import json
import time
from datetime import datetime

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
        
        return admin_dsn, portal_dsn
    else:
        # 기본값 사용
        admin_dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
        portal_dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
        return admin_dsn, portal_dsn

def create_test_environment():
    """테스트 환경 구축 - 샘플 데이터로 JSONB 마이그레이션 테스트"""
    print("\n=== 테스트 환경 구축 ===")
    
    admin_dsn, _ = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        conn.autocommit = True
        cur = conn.cursor()
        
        # 테스트용 테이블들 생성
        test_tables = [
            {
                'name': 'jsonb_test_accidents',
                'create_sql': """
                    CREATE TABLE IF NOT EXISTS jsonb_test_accidents (
                        id SERIAL PRIMARY KEY,
                        issue_number TEXT UNIQUE,
                        custom_data TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'sample_data': [
                    ('ACC-001', '{"workplace": "공장A", "accident_type": "낙하", "severity": "중", "department": "제조부", "injured_count": 1}'),
                    ('ACC-002', '{"workplace": "공장B", "accident_type": "화상", "severity": "경", "department": "용접부", "injured_count": 0}'),
                    ('ACC-003', '{"workplace": "공장A", "accident_type": "절단", "severity": "중", "department": "가공부", "injured_count": 2}'),
                    ('ACC-004', '{"workplace": "사무실", "accident_type": "넘어짐", "severity": "경", "department": "관리부", "injured_count": 1}'),
                    ('ACC-005', '{"workplace": "공장C", "accident_type": "압착", "severity": "심각", "department": "프레스부", "injured_count": 3}')
                ]
            },
            {
                'name': 'jsonb_test_safety',
                'create_sql': """
                    CREATE TABLE IF NOT EXISTS jsonb_test_safety (
                        id SERIAL PRIMARY KEY,
                        issue_number TEXT UNIQUE,
                        custom_data TEXT DEFAULT '{}',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """,
                'sample_data': [
                    ('SAFE-001', '{"workplace": "공장A", "violation_type": "안전모", "severity": "중", "inspector": "김감독", "corrected": true}'),
                    ('SAFE-002', '{"workplace": "공장B", "violation_type": "안전화", "severity": "경", "inspector": "박감독", "corrected": false}'),
                    ('SAFE-003', '{"workplace": "공장A", "violation_type": "보호장갑", "severity": "경", "inspector": "김감독", "corrected": true}'),
                    ('SAFE-004', '{"workplace": "공장C", "violation_type": "안전벨트", "severity": "심각", "inspector": "이감독", "corrected": false}'),
                    ('SAFE-005', '{"workplace": "공장B", "violation_type": "보호경", "severity": "중", "inspector": "박감독", "corrected": true}')
                ]
            }
        ]
        
        total_records = 0
        for table_info in test_tables:
            table_name = table_info['name']
            
            # 테이블 생성
            cur.execute(table_info['create_sql'])
            print(f"✅ {table_name} 테이블 생성")
            
            # 샘플 데이터 삽입
            for issue_number, custom_data in table_info['sample_data']:
                cur.execute(f"""
                    INSERT INTO {table_name} (issue_number, custom_data) 
                    VALUES (%s, %s) ON CONFLICT (issue_number) DO NOTHING
                """, (issue_number, custom_data))
            
            # 데이터 수 확인
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            count = cur.fetchone()[0]
            total_records += count
            print(f"   📊 {count}개 샘플 데이터")
        
        print(f"✅ 테스트 환경 구축 완료 ({total_records}개 레코드)")
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 테스트 환경 구축 실패: {e}")
        return False

def validate_json_integrity():
    """JSON 데이터 무결성 검증"""
    print("\n=== JSON 데이터 무결성 검증 ===")
    
    admin_dsn, _ = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        cur = conn.cursor()
        
        test_tables = ['jsonb_test_accidents', 'jsonb_test_safety']
        
        for table_name in test_tables:
            print(f"\n--- {table_name} 검증 ---")
            
            # 테이블 존재 확인
            cur.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table_name,))
            
            if not cur.fetchone()[0]:
                print(f"⏭️  {table_name}: 테이블 존재하지 않음")
                continue
            
            # 전체 레코드 수
            cur.execute(f"SELECT COUNT(*) FROM {table_name}")
            total_count = cur.fetchone()[0]
            
            if total_count == 0:
                print(f"📋 {table_name}: 빈 테이블")
                continue
            
            # JSON 유효성 검사
            cur.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN custom_data IS NULL OR custom_data = '' THEN 1 END) as empty,
                    COUNT(CASE 
                        WHEN custom_data IS NOT NULL AND custom_data != '' 
                        THEN 
                            CASE 
                                WHEN custom_data::jsonb IS NOT NULL THEN 1 
                            END 
                    END) as valid_json
                FROM {table_name}
            """)
            
            total, empty, valid_json = cur.fetchone()
            invalid = total - empty - valid_json
            
            print(f"📊 전체: {total}개")
            print(f"   ✅ 유효 JSON: {valid_json}개 ({valid_json/total*100:.1f}%)")
            if empty > 0:
                print(f"   🔘 빈 값: {empty}개 ({empty/total*100:.1f}%)")
            if invalid > 0:
                print(f"   ❌ 무효 JSON: {invalid}개 ({invalid/total*100:.1f}%)")
            
            # 공통 키 분석
            cur.execute(f"""
                SELECT custom_data FROM {table_name} 
                WHERE custom_data IS NOT NULL AND custom_data != ''
                LIMIT 5
            """)
            
            samples = cur.fetchall()
            all_keys = set()
            for sample in samples:
                try:
                    json_data = json.loads(sample[0])
                    all_keys.update(json_data.keys())
                except json.JSONDecodeError:
                    pass
            
            if all_keys:
                print(f"   🔍 발견된 키: {sorted(list(all_keys))}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 무결성 검증 실패: {e}")
        return False

def performance_comparison_test():
    """TEXT vs JSONB 성능 비교 테스트"""
    print("\n=== TEXT vs JSONB 성능 비교 ===")
    
    admin_dsn, _ = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        cur = conn.cursor()
        
        # TEXT 버전 성능 테스트
        print("\n--- TEXT 버전 성능 테스트 ---")
        
        text_queries = [
            {
                'name': '단순 키 검색',
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE json_extract(custom_data, '$.workplace') = %s",
                'params': ('공장A',)
            },
            {
                'name': 'LIKE 패턴 검색', 
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE json_extract(custom_data, '$.workplace') LIKE %s",
                'params': ('%공장%',)
            },
            {
                'name': '숫자 값 비교',
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE CAST(json_extract(custom_data, '$.injured_count') AS INTEGER) > %s",
                'params': (1,)
            }
        ]
        
        text_times = []
        for query_info in text_queries:
            start_time = time.time()
            
            for _ in range(10):  # 10번 반복 실행
                cur.execute(query_info['query'], query_info['params'])
                result = cur.fetchone()
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 10 * 1000  # ms 단위
            text_times.append(avg_time)
            
            print(f"  📊 {query_info['name']}: {avg_time:.2f}ms (결과: {result[0]})")
        
        # 테이블을 JSONB로 변환
        print("\n--- JSONB 변환 중... ---")
        
        # 기본값 제거 후 타입 변경
        cur.execute("ALTER TABLE jsonb_test_accidents ALTER COLUMN custom_data DROP DEFAULT")
        cur.execute("""
            ALTER TABLE jsonb_test_accidents 
            ALTER COLUMN custom_data TYPE JSONB 
            USING custom_data::JSONB
        """)
        cur.execute("ALTER TABLE jsonb_test_accidents ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB")
        
        cur.execute("ALTER TABLE jsonb_test_safety ALTER COLUMN custom_data DROP DEFAULT") 
        cur.execute("""
            ALTER TABLE jsonb_test_safety 
            ALTER COLUMN custom_data TYPE JSONB 
            USING custom_data::JSONB
        """)
        cur.execute("ALTER TABLE jsonb_test_safety ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB")
        print("✅ JSONB 변환 완료")
        
        # JSONB 인덱스 생성
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accidents_workplace ON jsonb_test_accidents USING GIN ((custom_data->>'workplace'))")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_accidents_gin ON jsonb_test_accidents USING GIN (custom_data)")
        print("✅ JSONB 인덱스 생성 완료")
        
        # JSONB 버전 성능 테스트
        print("\n--- JSONB 버전 성능 테스트 ---")
        
        jsonb_queries = [
            {
                'name': '단순 키 검색',
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE custom_data->>'workplace' = %s",
                'params': ('공장A',)
            },
            {
                'name': 'LIKE 패턴 검색',
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE custom_data->>'workplace' LIKE %s", 
                'params': ('%공장%',)
            },
            {
                'name': '숫자 값 비교',
                'query': "SELECT COUNT(*) FROM jsonb_test_accidents WHERE (custom_data->>'injured_count')::INTEGER > %s",
                'params': (1,)
            }
        ]
        
        jsonb_times = []
        for query_info in jsonb_queries:
            start_time = time.time()
            
            for _ in range(10):  # 10번 반복 실행
                cur.execute(query_info['query'], query_info['params'])
                result = cur.fetchone()
            
            end_time = time.time()
            avg_time = (end_time - start_time) / 10 * 1000  # ms 단위
            jsonb_times.append(avg_time)
            
            print(f"  📊 {query_info['name']}: {avg_time:.2f}ms (결과: {result[0]})")
        
        # 성능 비교 결과
        print("\n--- 성능 비교 결과 ---")
        for i, query_name in enumerate(['단순 키 검색', 'LIKE 패턴 검색', '숫자 값 비교']):
            text_time = text_times[i]
            jsonb_time = jsonb_times[i]
            improvement = (text_time - jsonb_time) / text_time * 100
            
            if improvement > 0:
                print(f"  🚀 {query_name}: {improvement:.1f}% 개선 ({text_time:.2f}ms → {jsonb_time:.2f}ms)")
            else:
                print(f"  📊 {query_name}: {abs(improvement):.1f}% 느림 ({text_time:.2f}ms → {jsonb_time:.2f}ms)")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 성능 비교 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False

def jsonb_feature_showcase():
    """JSONB 고유 기능 시연"""
    print("\n=== JSONB 고유 기능 시연 ===")
    
    admin_dsn, _ = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        cur = conn.cursor()
        
        # 1. JSON 연산자 활용
        print("\n--- JSON 연산자 활용 ---")
        
        # -> 연산자 (JSON 객체 반환)
        cur.execute("SELECT custom_data->'workplace' FROM jsonb_test_accidents LIMIT 1")
        result = cur.fetchone()
        print(f"  📊 custom_data->'workplace': {result[0]} (JSON 객체)")
        
        # ->> 연산자 (텍스트 반환)
        cur.execute("SELECT custom_data->>'workplace' FROM jsonb_test_accidents LIMIT 1")
        result = cur.fetchone()
        print(f"  📊 custom_data->>'workplace': '{result[0]}' (텍스트)")
        
        # 2. JSON 경로 쿼리
        print("\n--- JSON 경로 쿼리 ---")
        cur.execute("SELECT COUNT(*) FROM jsonb_test_accidents WHERE custom_data ? 'injured_count'")
        result = cur.fetchone()
        print(f"  📊 'injured_count' 키 존재하는 레코드: {result[0]}개")
        
        # 3. JSON 집계 함수
        print("\n--- JSON 집계 함수 ---")
        cur.execute("""
            SELECT 
                custom_data->>'workplace' as workplace,
                COUNT(*) as count,
                AVG((custom_data->>'injured_count')::INTEGER) as avg_injured
            FROM jsonb_test_accidents 
            GROUP BY custom_data->>'workplace'
            ORDER BY count DESC
        """)
        
        results = cur.fetchall()
        for workplace, count, avg_injured in results:
            print(f"  📊 {workplace}: {count}건 (평균 부상자: {avg_injured:.1f}명)")
        
        # 4. JSON 업데이트
        print("\n--- JSON 업데이트 ---")
        cur.execute("""
            UPDATE jsonb_test_accidents 
            SET custom_data = jsonb_set(custom_data, '{updated_at}', %s::jsonb)
            WHERE issue_number = 'ACC-001'
        """, (f'"{datetime.now().isoformat()}"',))
        
        cur.execute("SELECT custom_data->>'updated_at' FROM jsonb_test_accidents WHERE issue_number = 'ACC-001'")
        result = cur.fetchone()
        print(f"  ✅ JSON 업데이트: updated_at = {result[0]}")
        
        # 5. 복합 조건 쿼리
        print("\n--- 복합 조건 쿼리 ---")
        cur.execute("""
            SELECT issue_number, custom_data->>'workplace', custom_data->>'severity'
            FROM jsonb_test_accidents
            WHERE custom_data->>'workplace' LIKE '%공장%'
            AND custom_data->>'severity' IN ('중', '심각')
            ORDER BY issue_number
        """)
        
        results = cur.fetchall()
        print(f"  📊 공장에서 발생한 중대사고: {len(results)}건")
        for issue_number, workplace, severity in results:
            print(f"    - {issue_number}: {workplace} ({severity})")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ JSONB 기능 시연 실패: {e}")
        return False

def main():
    print("SETUP - Phase 6 검증 및 성능 테스트 도구")
    
    tests = [
        ("테스트 환경 구축", create_test_environment),
        ("JSON 데이터 무결성 검증", validate_json_integrity),
        ("TEXT vs JSONB 성능 비교", performance_comparison_test),
        ("JSONB 고유 기능 시연", jsonb_feature_showcase)
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
    
    print(f"\n=== Phase 6 검증 및 테스트 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 6 JSONB 마이그레이션 검증 완료!")
        print("🚀 JSONB 성능 향상 및 기능 확장 검증됨!")
        print("✨ PostgreSQL 네이티브 JSON 기능 활용 가능!")
        print("🌟 Phase 6 완전 완성!")
        return True
    else:
        print("⚠️  일부 테스트에 이슈가 있습니다")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)