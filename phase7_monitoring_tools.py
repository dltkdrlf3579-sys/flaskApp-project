#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 7 운영 모니터링 도구
codex 권장사항 반영: 실제 서비스 쿼리 성능 모니터링
"""
import psycopg
import sys
import os
from typing import Dict, List

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def get_config():
    """PostgreSQL 연결 설정"""
    return 'postgresql://postgres:admin123@localhost:5432/portal_dev'

def monitor_index_usage():
    """인덱스 사용률 모니터링"""
    print("=== 인덱스 사용률 모니터링 ===")
    
    dsn = get_config()
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                # 인덱스 사용 통계 조회
                cur.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        indexname,
                        idx_tup_read,
                        idx_tup_fetch,
                        CASE 
                            WHEN idx_tup_read = 0 THEN 0 
                            ELSE round((idx_tup_fetch::numeric / idx_tup_read * 100), 2)
                        END as efficiency_percent
                    FROM pg_stat_user_indexes 
                    WHERE schemaname = 'public'
                    AND tablename IN ('accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process')
                    ORDER BY tablename, idx_tup_read DESC
                """)
                
                results = cur.fetchall()
                
                print("\n📊 인덱스 사용 통계")
                print("=" * 80)
                print(f"{'테이블':<25} {'인덱스명':<35} {'읽기':<10} {'페치':<10} {'효율%':<8}")
                print("-" * 80)
                
                for row in results:
                    schema, table, index, reads, fetches, efficiency = row
                    print(f"{table:<25} {index:<35} {reads:<10} {fetches:<10} {efficiency or 0:<8}")
                
                # 사용되지 않는 인덱스 찾기
                print("\n⚠️  사용되지 않는 인덱스 (읽기 = 0)")
                unused_indexes = [row for row in results if row[3] == 0]  # idx_tup_read = 0
                
                if unused_indexes:
                    for row in unused_indexes:
                        print(f"  - {row[1]}.{row[2]}")
                    
                    print("\n💡 권장사항: 사용되지 않는 인덱스는 제거를 고려하세요.")
                    print("   DROP INDEX IF EXISTS <인덱스명>;")
                else:
                    print("  모든 인덱스가 사용되고 있습니다. ✅")
                
    except Exception as e:
        print(f"❌ 인덱스 모니터링 실패: {e}")

def analyze_table_bloat():
    """테이블/인덱스 bloat 분석"""
    print("\n=== 테이블/인덱스 공간 사용량 분석 ===")
    
    dsn = get_config()
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                # 테이블 크기 분석
                cur.execute("""
                    SELECT 
                        t.table_name,
                        pg_size_pretty(pg_total_relation_size(t.table_name::regclass)) as total_size,
                        pg_size_pretty(pg_relation_size(t.table_name::regclass)) as table_size,
                        pg_size_pretty(pg_indexes_size(t.table_name::regclass)) as indexes_size,
                        (SELECT COUNT(*) FROM pg_stat_user_indexes WHERE tablename = t.table_name) as index_count
                    FROM information_schema.tables t
                    WHERE t.table_schema = 'public' 
                    AND t.table_name IN ('accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process')
                    ORDER BY pg_total_relation_size(t.table_name::regclass) DESC
                """)
                
                results = cur.fetchall()
                
                print("\n📊 공간 사용량")
                print("=" * 70)
                print(f"{'테이블':<25} {'전체크기':<12} {'테이블':<12} {'인덱스':<12} {'개수':<6}")
                print("-" * 70)
                
                for row in results:
                    table, total, table_size, index_size, count = row
                    print(f"{table:<25} {total:<12} {table_size:<12} {index_size:<12} {count:<6}")
                
    except Exception as e:
        print(f"❌ 공간 분석 실패: {e}")

def check_slow_queries():
    """느린 쿼리 패턴 체크"""
    print("\n=== 실제 쿼리 성능 체크 ===")
    
    dsn = get_config()
    
    # 실제 사용 패턴에 가까운 테스트 쿼리들
    test_queries = [
        {
            'name': '정확 매칭 - workplace',
            'sql': "SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'workplace' = %s",
            'params': ('공장A',)
        },
        {
            'name': 'LIKE 검색 - workplace',
            'sql': "SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'workplace' LIKE %s",
            'params': ('%공장%',)
        },
        {
            'name': '복합 조건 - workplace + severity',
            'sql': "SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'workplace' = %s AND custom_data->>'severity' = %s",
            'params': ('공장A', '높음')
        },
        {
            'name': 'JSON 키 존재 확인',
            'sql': "SELECT COUNT(*) FROM accidents_cache WHERE custom_data ? %s",
            'params': ('accident_type',)
        },
        {
            'name': '날짜 범위 검색',
            'sql': "SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'date' >= %s",
            'params': ('2024-06-01',)
        }
    ]
    
    try:
        with psycopg.connect(dsn) as conn:
            with conn.cursor() as cur:
                print("\n📊 쿼리별 성능 및 실행계획")
                print("=" * 100)
                
                for query in test_queries:
                    # 실행 시간 측정
                    import time
                    times = []
                    for _ in range(3):  # 3회 평균
                        start = time.time()
                        cur.execute(query['sql'], query['params'])
                        result = cur.fetchone()[0]
                        end = time.time()
                        times.append((end - start) * 1000)  # ms 변환
                    
                    avg_time = sum(times) / len(times)
                    
                    # 실행 계획 조회
                    explain_sql = f"EXPLAIN (FORMAT TEXT, ANALYZE TRUE, BUFFERS TRUE) {query['sql']}"
                    cur.execute(explain_sql, query['params'])
                    plan = cur.fetchall()
                    
                    # 인덱스 사용 여부 확인
                    plan_text = '\n'.join([row[0] for row in plan])
                    uses_index = 'Index Scan' in plan_text or 'Bitmap Index Scan' in plan_text
                    
                    print(f"\n🔍 {query['name']}")
                    print(f"   평균 시간: {avg_time:.2f}ms")
                    print(f"   결과 수: {result:,}개")
                    print(f"   인덱스 사용: {'✅ Yes' if uses_index else '❌ No'}")
                    
                    # 너무 느린 쿼리는 실행계획 출력
                    if avg_time > 10:  # 10ms 초과
                        print("   실행계획:")
                        for line in plan[:5]:  # 상위 5줄만
                            print(f"     {line[0]}")
                        if len(plan) > 5:
                            print("     ...")
                
    except Exception as e:
        print(f"❌ 쿼리 성능 체크 실패: {e}")

def generate_maintenance_script():
    """운영 유지보수 스크립트 생성"""
    script_path = os.path.join(os.path.dirname(__file__), 'phase7_maintenance.sql')
    
    script_content = """-- Phase 7 운영 유지보수 스크립트
-- 정기적으로 실행하여 성능 최적화 상태 유지

-- 1. 통계 정보 갱신 (주간 권장)
ANALYZE accidents_cache;
ANALYZE safety_instructions_cache;
ANALYZE follow_sop;
ANALYZE full_process;

-- 2. 인덱스 사용률 확인
SELECT 
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    CASE 
        WHEN idx_tup_read = 0 THEN '미사용'
        WHEN idx_tup_read < 100 THEN '저사용'
        ELSE '정상'
    END as status
FROM pg_stat_user_indexes 
WHERE schemaname = 'public'
AND tablename IN ('accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process')
ORDER BY idx_tup_read DESC;

-- 3. 테이블 크기 모니터링
SELECT 
    tablename,
    pg_size_pretty(pg_total_relation_size(tablename::regclass)) as total_size,
    pg_size_pretty(pg_indexes_size(tablename::regclass)) as indexes_size
FROM information_schema.tables
WHERE table_schema = 'public'
AND tablename IN ('accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process')
ORDER BY pg_total_relation_size(tablename::regclass) DESC;

-- 4. 느린 쿼리 패턴 테스트
-- (실제 값으로 교체하여 사용)
EXPLAIN ANALYZE 
SELECT COUNT(*) FROM accidents_cache 
WHERE custom_data->>'workplace' = '공장A';

-- 5. JSON 키 분포 확인 (새로운 키 패턴 발견)
SELECT 
    jsonb_object_keys(custom_data) as key_name,
    COUNT(*) as frequency
FROM accidents_cache 
GROUP BY jsonb_object_keys(custom_data)
ORDER BY frequency DESC
LIMIT 10;

-- 6. 사용되지 않는 인덱스 식별 및 제거 고려
-- (idx_tup_read = 0인 인덱스들)
/*
예시: 
DROP INDEX IF EXISTS idx_unused_index_name;
*/
"""
    
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"\n📋 운영 유지보수 스크립트 생성: {script_path}")
    return script_path

def main():
    """메인 모니터링 실행"""
    print("MONITORING - Phase 7 운영 모니터링 도구")
    
    try:
        # 1. 인덱스 사용률 모니터링
        monitor_index_usage()
        
        # 2. 테이블/인덱스 공간 분석
        analyze_table_bloat()
        
        # 3. 실제 쿼리 성능 체크
        check_slow_queries()
        
        # 4. 유지보수 스크립트 생성
        maintenance_script = generate_maintenance_script()
        
        print("\n" + "="*60)
        print("🎯 Phase 7 모니터링 완료")
        print("="*60)
        print("💡 권장사항:")
        print("  - 인덱스 사용률 정기 모니터링")
        print("  - 느린 쿼리(>10ms) 패턴 개선")
        print("  - 미사용 인덱스 제거 고려")
        print("  - 주간 ANALYZE 실행")
        
        return True
        
    except Exception as e:
        print(f"❌ 모니터링 실행 실패: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)