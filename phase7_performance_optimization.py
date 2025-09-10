#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 7: JSON/검색 성능 최적화 
PostgreSQL Migration v7 - 인덱스 생성 및 성능 튜닝
"""
import sys
import os
import psycopg
import configparser
import time
import json
from typing import Dict, List, Optional, Tuple

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

class IndexAnalyzer:
    """인덱스 분석 및 추천 도구"""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        # 실제 존재하는 테이블만 확인
        self.target_tables = self._get_existing_tables()
    
    def _get_existing_tables(self) -> List[str]:
        """실제 존재하는 테이블만 반환"""
        potential_tables = [
            'accidents_cache',
            'safety_instructions_cache', 
            'follow_sop',
            'full_process',
            'followsop_cache',
            'fullprocess_cache',
            'partner_change_requests'
        ]
        
        existing_tables = []
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    for table in potential_tables:
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = %s AND table_schema = 'public'
                            )
                        """, (table,))
                        
                        if cur.fetchone()[0]:
                            existing_tables.append(table)
        except Exception:
            pass
        
        return existing_tables
    
    def analyze_current_indexes(self) -> Dict[str, List]:
        """현재 인덱스 상태 분석"""
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                results = {}
                
                for table in self.target_tables:
                    # 테이블 존재 확인
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s AND table_schema = 'public'
                        )
                    """, (table,))
                    
                    if not cur.fetchone()[0]:
                        print(f"⚠️  테이블 {table}이 존재하지 않습니다")
                        continue
                    
                    # 인덱스 조회
                    cur.execute("""
                        SELECT 
                            indexname,
                            indexdef,
                            schemaname
                        FROM pg_indexes 
                        WHERE tablename = %s AND schemaname = 'public'
                        ORDER BY indexname
                    """, (table,))
                    
                    indexes = cur.fetchall()
                    results[table] = [
                        {
                            'name': idx[0],
                            'definition': idx[1],
                            'schema': idx[2]
                        }
                        for idx in indexes
                    ]
                
                return results
    
    def analyze_json_keys(self) -> Dict[str, List[str]]:
        """각 테이블의 JSON 키 사용 빈도 분석"""
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                results = {}
                
                for table in self.target_tables:
                    # 테이블 존재 및 custom_data 컬럼 확인
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = %s 
                            AND column_name = 'custom_data'
                            AND table_schema = 'public'
                        )
                    """, (table,))
                    
                    if not cur.fetchone()[0]:
                        continue
                    
                    # JSON 키 추출 (최대 1000개 샘플)
                    cur.execute(f"""
                        SELECT DISTINCT jsonb_object_keys(custom_data) as key_name, COUNT(*) as frequency
                        FROM (
                            SELECT custom_data 
                            FROM {table} 
                            WHERE custom_data IS NOT NULL 
                            AND jsonb_typeof(custom_data) = 'object'
                            LIMIT 1000
                        ) sample
                        GROUP BY jsonb_object_keys(custom_data)
                        ORDER BY frequency DESC
                        LIMIT 10
                    """)
                    
                    keys = [row[0] for row in cur.fetchall()]
                    results[table] = keys
                
                return results
    
    def get_table_stats(self) -> Dict[str, Dict]:
        """테이블 통계 정보"""
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                results = {}
                
                for table in self.target_tables:
                    try:
                        # 테이블 크기 및 행 수
                        cur.execute(f"""
                            SELECT 
                                COUNT(*) as row_count,
                                pg_size_pretty(pg_total_relation_size('{table}')) as total_size
                            FROM {table}
                        """)
                        
                        row = cur.fetchone()
                        if row:
                            results[table] = {
                                'row_count': row[0],
                                'total_size': row[1]
                            }
                    except Exception as e:
                        print(f"⚠️  {table} 통계 수집 실패: {e}")
                        continue
                
                return results

class PerformanceIndexCreator:
    """성능 최적화 인덱스 생성기"""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
        
        # 실제 존재하는 테이블만 확인
        self.existing_tables = self._get_existing_tables()
        
        # 테이블별 핵심 검색 키 (실사용 패턴 기반)
        all_patterns = {
            'accidents_cache': ['workplace', 'accident_type', 'severity', 'department'],
            'safety_instructions_cache': ['workplace', 'violation_type', 'severity', 'inspector'],
            'follow_sop': ['workplace', 'process_type', 'status', 'department'],
            'full_process': ['workplace', 'process_name', 'status', 'department'],
            'followsop_cache': ['workplace', 'process_type', 'status'],
            'fullprocess_cache': ['workplace', 'process_name', 'status'],
            'partner_change_requests': ['requester_name', 'company_name', 'status', 'department']
        }
        
        # 존재하는 테이블만 필터링
        self.key_patterns = {
            table: keys for table, keys in all_patterns.items() 
            if table in self.existing_tables
        }
    
    def _get_existing_tables(self) -> List[str]:
        """실제 존재하는 테이블만 반환"""
        potential_tables = [
            'accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process',
            'followsop_cache', 'fullprocess_cache', 'partner_change_requests'
        ]
        
        existing_tables = []
        try:
            with psycopg.connect(self.dsn) as conn:
                with conn.cursor() as cur:
                    for table in potential_tables:
                        cur.execute("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_name = %s AND table_schema = 'public'
                            )
                        """, (table,))
                        
                        if cur.fetchone()[0]:
                            existing_tables.append(table)
        except Exception:
            pass
        
        return existing_tables
    
    def create_expression_indexes(self, table: str, keys: List[str]) -> List[str]:
        """표현식 인덱스 생성 (정확 매칭 최적화)"""
        created_indexes = []
        
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                for key in keys:
                    index_name = f"idx_{table}_{key}_expr"
                    
                    try:
                        # 기존 인덱스 확인
                        cur.execute("""
                            SELECT indexname FROM pg_indexes 
                            WHERE indexname = %s AND tablename = %s
                        """, (index_name, table))
                        
                        if cur.fetchone():
                            print(f"✅ {index_name} 이미 존재")
                            continue
                        
                        # 표현식 인덱스 생성
                        create_sql = f"""
                            CREATE INDEX {index_name} 
                            ON {table} ((custom_data->>'{key}'))
                        """
                        
                        cur.execute(create_sql)
                        conn.commit()
                        
                        print(f"✅ 생성: {index_name}")
                        created_indexes.append(index_name)
                        
                    except Exception as e:
                        print(f"❌ {index_name} 생성 실패: {e}")
                        continue
        
        return created_indexes
    
    def create_composite_indexes(self, table: str, key_combinations: List[Tuple[str, str]]) -> List[str]:
        """복합 인덱스 생성 (다중 조건 검색 최적화)"""
        created_indexes = []
        
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                for key1, key2 in key_combinations:
                    index_name = f"idx_{table}_{key1}_{key2}_composite"
                    
                    try:
                        # 기존 인덱스 확인
                        cur.execute("""
                            SELECT indexname FROM pg_indexes 
                            WHERE indexname = %s AND tablename = %s
                        """, (index_name, table))
                        
                        if cur.fetchone():
                            print(f"✅ {index_name} 이미 존재")
                            continue
                        
                        # 복합 인덱스 생성
                        create_sql = f"""
                            CREATE INDEX {index_name} 
                            ON {table} ((custom_data->>'{key1}'), (custom_data->>'{key2}'))
                        """
                        
                        cur.execute(create_sql)
                        conn.commit()
                        
                        print(f"✅ 생성: {index_name}")
                        created_indexes.append(index_name)
                        
                    except Exception as e:
                        print(f"❌ {index_name} 생성 실패: {e}")
                        continue
        
        return created_indexes
    
    def create_gin_indexes(self, table: str, selective: bool = True) -> List[str]:
        """GIN 인덱스 생성 (광범위 JSON 검색용)"""
        created_indexes = []
        
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                # 테이블 크기 확인 (GIN은 대용량에만 적용)
                cur.execute(f"SELECT COUNT(*) FROM {table}")
                row_count = cur.fetchone()[0]
                
                # GIN 인덱스는 더 큰 데이터에서만 효용성 있음
                gin_threshold = 10000  # codex 권장: 더 높은 임계치
                if selective and row_count < gin_threshold:
                    print(f"📊 {table}: 행 수 {row_count:,} < {gin_threshold:,}, GIN 인덱스 생략 (광범위 검색 시에만 유효)")
                    return created_indexes
                
                index_name = f"idx_{table}_custom_data_gin"
                
                try:
                    # 기존 GIN 인덱스 확인
                    cur.execute("""
                        SELECT indexname FROM pg_indexes 
                        WHERE indexname = %s AND tablename = %s
                    """, (index_name, table))
                    
                    if cur.fetchone():
                        print(f"✅ {index_name} 이미 존재")
                        return created_indexes
                    
                    # GIN 인덱스 생성
                    create_sql = f"""
                        CREATE INDEX {index_name} 
                        ON {table} USING GIN (custom_data)
                    """
                    
                    cur.execute(create_sql)
                    conn.commit()
                    
                    print(f"✅ 생성: {index_name} (행 수: {row_count:,})")
                    created_indexes.append(index_name)
                    
                except Exception as e:
                    print(f"❌ {index_name} 생성 실패: {e}")
        
        return created_indexes

class PerformanceTester:
    """성능 테스트 도구"""
    
    def __init__(self, dsn: str):
        self.dsn = dsn
    
    def test_query_performance(self, table: str, queries: List[Dict]) -> List[Dict]:
        """쿼리 성능 측정"""
        results = []
        
        with psycopg.connect(self.dsn) as conn:
            with conn.cursor() as cur:
                for query_info in queries:
                    name = query_info['name']
                    sql = query_info['sql']
                    params = query_info.get('params', ())
                    
                    try:
                        # 여러 번 실행하여 평균 측정
                        times = []
                        for _ in range(5):
                            start_time = time.time()
                            cur.execute(sql, params)
                            result = cur.fetchall()
                            end_time = time.time()
                            times.append(end_time - start_time)
                        
                        avg_time = sum(times) / len(times)
                        
                        # 실행 계획 조회
                        explain_sql = f"EXPLAIN (FORMAT JSON) {sql}"
                        cur.execute(explain_sql, params)
                        plan = cur.fetchone()[0][0]
                        
                        results.append({
                            'table': table,
                            'name': name,
                            'avg_time_ms': avg_time * 1000,
                            'result_count': len(result),
                            'execution_plan': plan,
                            'uses_index': 'Index' in str(plan)
                        })
                        
                    except Exception as e:
                        print(f"❌ {name} 성능 테스트 실패: {e}")
                        continue
        
        return results
    
    def generate_test_queries(self, table: str, keys: List[str]) -> List[Dict]:
        """테스트 쿼리 생성"""
        queries = []
        
        # 정확 매칭 테스트
        if 'workplace' in keys:
            queries.append({
                'name': f'{table} - 정확 매칭 (workplace)',
                'sql': f"SELECT COUNT(*) FROM {table} WHERE custom_data->>'workplace' = %s",
                'params': ('공장A',)
            })
        
        # LIKE 검색 테스트
        if 'workplace' in keys:
            queries.append({
                'name': f'{table} - LIKE 검색 (workplace)',
                'sql': f"SELECT COUNT(*) FROM {table} WHERE custom_data->>'workplace' LIKE %s",
                'params': ('%공장%',)
            })
        
        # 복합 조건 테스트 (안전한 SQL 포맷)
        if len(keys) >= 2:
            key1, key2 = keys[0], keys[1]
            queries.append({
                'name': f'{table} - 복합 조건 ({key1} + {key2})',
                'sql': f"SELECT COUNT(*) FROM {table} WHERE custom_data->>'{key1}' = %s AND custom_data->>'{key2}' IS NOT NULL",
                'params': ('공장A',)  # 실제 테스트 값 사용
            })
        
        # JSON 키 존재 확인
        if keys:
            queries.append({
                'name': f'{table} - 키 존재 확인 ({keys[0]})',
                'sql': f"SELECT COUNT(*) FROM {table} WHERE custom_data ? %s",
                'params': (keys[0],)
            })
        
        return queries

def analyze_current_state():
    """현재 상태 분석"""
    print("=== Phase 7: JSON/검색 성능 최적화 시작 ===")
    
    dsn = get_config()
    analyzer = IndexAnalyzer(dsn)
    
    print("\n--- 현재 인덱스 상태 ---")
    current_indexes = analyzer.analyze_current_indexes()
    for table, indexes in current_indexes.items():
        print(f"\n📊 {table}:")
        if indexes:
            for idx in indexes:
                print(f"  ✅ {idx['name']}")
        else:
            print("  ⚠️  인덱스 없음")
    
    print("\n--- JSON 키 분석 ---")
    json_keys = analyzer.analyze_json_keys()
    for table, keys in json_keys.items():
        if keys:
            print(f"📊 {table}: {', '.join(keys[:5])}")
    
    print("\n--- 테이블 통계 ---")
    table_stats = analyzer.get_table_stats()
    for table, stats in table_stats.items():
        print(f"📊 {table}: {stats['row_count']:,}행, {stats['total_size']}")
    
    return current_indexes, json_keys, table_stats

def create_performance_indexes():
    """성능 최적화 인덱스 생성"""
    print("\n=== 성능 인덱스 생성 ===")
    
    dsn = get_config()
    creator = PerformanceIndexCreator(dsn)
    
    total_created = []
    
    for table, keys in creator.key_patterns.items():
        print(f"\n--- {table} 최적화 ---")
        
        # 표현식 인덱스 생성 (상위 2개 키만으로 제한 - codex 권장)
        print("1. 표현식 인덱스:")
        priority_keys = keys[:2]  # 인덱스 폭증 방지
        print(f"   대상 키: {priority_keys}")
        expr_indexes = creator.create_expression_indexes(table, priority_keys)
        total_created.extend(expr_indexes)
        
        # 복합 인덱스 생성 (주요 조합만)
        if len(keys) >= 2:
            print("2. 복합 인덱스:")
            composite_combinations = [(keys[0], keys[1])]  # workplace + type/status 조합
            comp_indexes = creator.create_composite_indexes(table, composite_combinations)
            total_created.extend(comp_indexes)
        
        # GIN 인덱스 (선별적)
        print("3. GIN 인덱스:")
        gin_indexes = creator.create_gin_indexes(table, selective=True)
        total_created.extend(gin_indexes)
    
    # 인덱스 생성 후 통계 정보 업데이트 (codex 권장)
    if total_created:
        print(f"\n--- 통계 정보 업데이트 ---")
        try:
            with psycopg.connect(dsn) as conn:
                with conn.cursor() as cur:
                    cur.execute("ANALYZE")
                    print("✅ 전체 테이블 통계 정보 갱신 완료")
        except Exception as e:
            print(f"⚠️  통계 정보 업데이트 실패: {e}")
    
    print(f"\n✅ 총 {len(total_created)}개 인덱스 생성 완료")
    return total_created

def test_performance_improvements():
    """성능 개선 효과 측정"""
    print("\n=== 성능 개선 효과 측정 ===")
    
    dsn = get_config()
    tester = PerformanceTester(dsn)
    creator = PerformanceIndexCreator(dsn)
    
    all_results = []
    
    for table, keys in creator.key_patterns.items():
        print(f"\n--- {table} 성능 테스트 ---")
        
        queries = tester.generate_test_queries(table, keys)
        results = tester.test_query_performance(table, queries)
        
        for result in results:
            print(f"📊 {result['name']}: {result['avg_time_ms']:.2f}ms "
                  f"({result['result_count']}건) "
                  f"{'🚀 인덱스' if result['uses_index'] else '🐌 풀스캔'}")
        
        all_results.extend(results)
    
    return all_results

def generate_performance_report(results: List[Dict]):
    """성능 보고서 생성"""
    report_path = os.path.join(os.path.dirname(__file__), 'PHASE7_PERFORMANCE_REPORT.md')
    
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("# Phase 7 성능 최적화 보고서\n\n")
        f.write("## 📊 실행 요약\n\n")
        f.write(f"- 테스트 시간: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"- 총 쿼리 테스트: {len(results)}개\n")
        
        indexed_queries = [r for r in results if r['uses_index']]
        f.write(f"- 인덱스 활용: {len(indexed_queries)}/{len(results)}개\n\n")
        
        f.write("## 🎯 성능 결과\n\n")
        
        # 테이블별 결과
        tables = set(r['table'] for r in results)
        for table in sorted(tables):
            table_results = [r for r in results if r['table'] == table]
            if not table_results:
                continue
                
            f.write(f"### {table}\n\n")
            f.write("| 쿼리 유형 | 응답시간 | 결과 수 | 인덱스 활용 |\n")
            f.write("|----------|---------|---------|-------------|\n")
            
            for result in table_results:
                index_status = "✅" if result['uses_index'] else "❌"
                f.write(f"| {result['name'].split(' - ')[1]} | "
                       f"{result['avg_time_ms']:.2f}ms | "
                       f"{result['result_count']:,} | "
                       f"{index_status} |\n")
            
            f.write("\n")
        
        f.write("## 📈 최적화 권장사항\n\n")
        
        slow_queries = [r for r in results if r['avg_time_ms'] > 100]  # 100ms 초과
        if slow_queries:
            f.write("### 🐌 느린 쿼리 (100ms 초과)\n\n")
            for query in slow_queries:
                f.write(f"- **{query['name']}**: {query['avg_time_ms']:.2f}ms\n")
                if not query['uses_index']:
                    f.write("  - 권장: 추가 인덱스 생성 검토\n")
                f.write("\n")
        
        no_index_queries = [r for r in results if not r['uses_index']]
        if no_index_queries:
            f.write("### 📋 인덱스 미활용 쿼리\n\n")
            for query in no_index_queries:
                f.write(f"- **{query['name']}**: 풀 테이블 스캔\n")
            f.write("\n")
        
        f.write("## ✅ 성능 기준 평가\n\n")
        f.write("- 🎯 목표: 주요 검색 쿼리 < 50ms\n")
        
        fast_queries = [r for r in results if r['avg_time_ms'] <= 50]
        f.write(f"- ✅ 기준 달성: {len(fast_queries)}/{len(results)}개 쿼리\n")
        
        if len(fast_queries) == len(results):
            f.write("\n🎉 **모든 쿼리가 성능 기준을 달성했습니다!**\n")
        else:
            f.write(f"\n⚠️  {len(results) - len(fast_queries)}개 쿼리가 성능 기준 미달성\n")
    
    print(f"\n📋 성능 보고서 생성: {report_path}")
    return report_path

def main():
    """Phase 7 메인 실행"""
    try:
        # 1. 현재 상태 분석
        current_indexes, json_keys, table_stats = analyze_current_state()
        
        # 2. 성능 인덱스 생성
        created_indexes = create_performance_indexes()
        
        # 3. 성능 테스트
        performance_results = test_performance_improvements()
        
        # 4. 보고서 생성
        report_path = generate_performance_report(performance_results)
        
        # 5. 결과 요약
        print("\n" + "="*60)
        print("🎉 Phase 7: JSON/검색 성능 최적화 완료!")
        print("="*60)
        print(f"✅ 생성된 인덱스: {len(created_indexes)}개")
        print(f"📊 테스트된 쿼리: {len(performance_results)}개")
        
        indexed_count = sum(1 for r in performance_results if r['uses_index'])
        print(f"🚀 인덱스 활용률: {indexed_count}/{len(performance_results)}개")
        
        fast_count = sum(1 for r in performance_results if r['avg_time_ms'] <= 50)
        print(f"⚡ 성능 기준 달성: {fast_count}/{len(performance_results)}개 (< 50ms)")
        
        print(f"📋 상세 보고서: {os.path.basename(report_path)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Phase 7 실행 중 오류: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)