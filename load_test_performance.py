#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load Testing and Performance Optimization - Day 4
부하 테스트 및 성능 최적화 도구
"""

import psycopg2
import configparser
import logging
import time
import json
import threading
import random
import statistics
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import matplotlib.pyplot as plt
import numpy as np

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LoadTester:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self.results = {
            'timestamp': datetime.now().isoformat(),
            'tests': {},
            'summary': {},
            'recommendations': []
        }
        self.lock = threading.Lock()

    def create_connection(self):
        """데이터베이스 연결 생성"""
        if self.config.has_option('DATABASE', 'postgres_dsn'):
            dsn = self.config.get('DATABASE', 'postgres_dsn')
            return psycopg2.connect(dsn)
        else:
            return psycopg2.connect(
                host='localhost',
                database='portal_db',
                user='postgres',
                password='postgres'
            )

    def test_permission_check(self, emp_id: str, menu_code: str) -> float:
        """권한 체크 성능 테스트"""
        conn = self.create_connection()
        cursor = conn.cursor()

        start_time = time.time()

        try:
            # 1. 캐시 확인
            cursor.execute("""
                SELECT permission_result
                FROM permission_cache
                WHERE emp_id = %s AND menu_code = %s
                AND expires_at > NOW()
            """, (emp_id, menu_code))

            cache_result = cursor.fetchone()

            if not cache_result:
                # 2. 실제 권한 체크
                cursor.execute("""
                    WITH user_roles AS (
                        SELECT role_id FROM user_role_mapping
                        WHERE emp_id = %s AND is_active = true
                    )
                    SELECT EXISTS(
                        SELECT 1 FROM role_menu_permissions rmp
                        JOIN user_roles ur ON rmp.role_id = ur.role_id
                        WHERE rmp.menu_code = %s
                        AND rmp.can_read = true
                    )
                """, (emp_id, menu_code))

                has_permission = cursor.fetchone()[0]

                # 3. 캐시 업데이트
                cursor.execute("""
                    INSERT INTO permission_cache (emp_id, menu_code, permission_result, expires_at)
                    VALUES (%s, %s, %s, NOW() + INTERVAL '1 hour')
                    ON CONFLICT (emp_id, menu_code) DO UPDATE
                    SET permission_result = EXCLUDED.permission_result,
                        expires_at = EXCLUDED.expires_at
                """, (emp_id, menu_code, 'GRANTED' if has_permission else 'DENIED'))

                conn.commit()

        except Exception as e:
            logger.error(f"Permission check failed: {e}")
            conn.rollback()

        finally:
            cursor.close()
            conn.close()

        return time.time() - start_time

    def test_audit_log_insert(self, emp_id: str) -> float:
        """감사 로그 입력 성능 테스트"""
        conn = self.create_connection()
        cursor = conn.cursor()

        start_time = time.time()

        try:
            cursor.execute("""
                INSERT INTO access_audit_log (
                    emp_id, menu_code, action_type, success,
                    ip_address, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                emp_id,
                f'MENU_{random.randint(1, 100):03d}',
                random.choice(['READ', 'WRITE', 'DELETE']),
                random.choice([True, False]),
                f'192.168.1.{random.randint(1, 255)}',
                datetime.now()
            ))
            conn.commit()

        except Exception as e:
            logger.error(f"Audit log insert failed: {e}")
            conn.rollback()

        finally:
            cursor.close()
            conn.close()

        return time.time() - start_time

    def test_user_role_query(self, emp_id: str) -> float:
        """사용자 역할 조회 성능 테스트"""
        conn = self.create_connection()
        cursor = conn.cursor()

        start_time = time.time()

        try:
            cursor.execute("""
                SELECT
                    u.emp_id,
                    u.user_name,
                    array_agg(DISTINCT r.role_name) as roles,
                    COUNT(DISTINCT rmp.menu_code) as accessible_menus
                FROM system_users u
                LEFT JOIN user_role_mapping urm ON u.emp_id = urm.emp_id
                LEFT JOIN system_roles r ON urm.role_id = r.role_id
                LEFT JOIN role_menu_permissions rmp ON r.role_id = rmp.role_id
                WHERE u.emp_id = %s
                GROUP BY u.emp_id, u.user_name
            """, (emp_id,))

            cursor.fetchone()

        except Exception as e:
            logger.error(f"User role query failed: {e}")

        finally:
            cursor.close()
            conn.close()

        return time.time() - start_time

    def test_department_hierarchy(self) -> float:
        """부서 계층 조회 성능 테스트"""
        conn = self.create_connection()
        cursor = conn.cursor()

        start_time = time.time()

        try:
            cursor.execute("""
                WITH RECURSIVE dept_tree AS (
                    SELECT dept_id, dept_name, parent_dept_id, 1 as level
                    FROM department_hierarchy
                    WHERE parent_dept_id IS NULL

                    UNION ALL

                    SELECT d.dept_id, d.dept_name, d.parent_dept_id, dt.level + 1
                    FROM department_hierarchy d
                    JOIN dept_tree dt ON d.parent_dept_id = dt.dept_id
                )
                SELECT * FROM dept_tree
                ORDER BY level, dept_name
            """)

            cursor.fetchall()

        except Exception as e:
            logger.error(f"Department hierarchy query failed: {e}")

        finally:
            cursor.close()
            conn.close()

        return time.time() - start_time

    def concurrent_load_test(self, test_func, num_threads: int, num_requests: int) -> Dict:
        """동시 부하 테스트"""
        results = []
        errors = 0

        def worker():
            emp_id = f'EMP_{random.randint(1, 1000):05d}'
            menu_code = f'MENU_{random.randint(1, 100):03d}'

            try:
                if test_func.__name__ == 'test_permission_check':
                    duration = test_func(emp_id, menu_code)
                else:
                    duration = test_func(emp_id)

                with self.lock:
                    results.append(duration)
            except Exception as e:
                logger.error(f"Worker error: {e}")
                with self.lock:
                    nonlocal errors
                    errors += 1

        start_time = time.time()

        with ThreadPoolExecutor(max_workers=num_threads) as executor:
            futures = [executor.submit(worker) for _ in range(num_requests)]
            for future in as_completed(futures):
                pass  # Wait for completion

        total_time = time.time() - start_time

        if results:
            return {
                'total_requests': num_requests,
                'successful_requests': len(results),
                'failed_requests': errors,
                'total_time': total_time,
                'avg_response_time': statistics.mean(results),
                'min_response_time': min(results),
                'max_response_time': max(results),
                'median_response_time': statistics.median(results),
                'std_dev': statistics.stdev(results) if len(results) > 1 else 0,
                'requests_per_second': len(results) / total_time if total_time > 0 else 0,
                'percentile_95': np.percentile(results, 95) if results else 0,
                'percentile_99': np.percentile(results, 99) if results else 0
            }
        else:
            return {
                'total_requests': num_requests,
                'successful_requests': 0,
                'failed_requests': errors,
                'error': 'All requests failed'
            }

    def stress_test(self):
        """점진적 부하 증가 테스트"""
        logger.info("Starting stress test...")
        stress_results = []

        thread_counts = [1, 5, 10, 20, 50, 100]
        requests_per_thread = 10

        for threads in thread_counts:
            logger.info(f"Testing with {threads} concurrent threads...")
            result = self.concurrent_load_test(
                self.test_permission_check,
                threads,
                threads * requests_per_thread
            )
            result['concurrent_threads'] = threads
            stress_results.append(result)
            time.sleep(2)  # Cool down between tests

        self.results['tests']['stress_test'] = stress_results
        return stress_results

    def analyze_bottlenecks(self):
        """성능 병목 분석"""
        logger.info("Analyzing performance bottlenecks...")

        conn = self.create_connection()
        cursor = conn.cursor()
        bottlenecks = []

        try:
            # 1. 느린 쿼리 분석
            cursor.execute("""
                SELECT
                    query,
                    calls,
                    total_time,
                    mean_time,
                    max_time
                FROM pg_stat_statements
                WHERE mean_time > 10  -- 10ms 이상
                ORDER BY mean_time DESC
                LIMIT 10
            """)
            slow_queries = cursor.fetchall()

            if slow_queries:
                bottlenecks.append({
                    'type': 'slow_queries',
                    'count': len(slow_queries),
                    'recommendation': 'Optimize slow queries or add indexes'
                })

            # 2. 인덱스 사용 분석
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                AND idx_scan = 0
            """)
            unused_indexes = cursor.fetchall()

            if len(unused_indexes) > 5:
                bottlenecks.append({
                    'type': 'unused_indexes',
                    'count': len(unused_indexes),
                    'recommendation': 'Remove unused indexes to improve write performance'
                })

            # 3. 테이블 블로트 확인
            cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    n_dead_tup,
                    n_live_tup,
                    CASE WHEN n_live_tup > 0
                         THEN n_dead_tup::float / n_live_tup
                         ELSE 0 END as dead_ratio
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                AND n_dead_tup > 1000
                ORDER BY dead_ratio DESC
            """)
            bloated_tables = cursor.fetchall()

            if bloated_tables:
                bottlenecks.append({
                    'type': 'table_bloat',
                    'count': len(bloated_tables),
                    'recommendation': 'Run VACUUM on bloated tables'
                })

            # 4. 캐시 히트율 확인
            cursor.execute("""
                SELECT
                    sum(heap_blks_read) as heap_read,
                    sum(heap_blks_hit) as heap_hit,
                    CASE WHEN sum(heap_blks_hit) + sum(heap_blks_read) > 0
                         THEN sum(heap_blks_hit)::float / (sum(heap_blks_hit) + sum(heap_blks_read))
                         ELSE 0 END as cache_hit_ratio
                FROM pg_statio_user_tables
            """)
            cache_stats = cursor.fetchone()

            if cache_stats and cache_stats[2] < 0.9:
                bottlenecks.append({
                    'type': 'low_cache_hit_ratio',
                    'value': cache_stats[2],
                    'recommendation': 'Increase shared_buffers or optimize queries'
                })

        except Exception as e:
            logger.error(f"Bottleneck analysis failed: {e}")

        finally:
            cursor.close()
            conn.close()

        self.results['bottlenecks'] = bottlenecks
        return bottlenecks

    def optimize_database(self):
        """데이터베이스 최적화 실행"""
        logger.info("Executing database optimizations...")

        conn = self.create_connection()
        cursor = conn.cursor()
        optimizations = []

        try:
            # 1. VACUUM ANALYZE 실행
            tables = [
                'system_users', 'user_role_mapping', 'role_menu_permissions',
                'permission_cache', 'access_audit_log'
            ]

            for table in tables:
                try:
                    cursor.execute(f"VACUUM ANALYZE {table}")
                    conn.commit()
                    optimizations.append(f"VACUUM ANALYZE {table} completed")
                except Exception as e:
                    logger.error(f"VACUUM failed for {table}: {e}")

            # 2. 통계 업데이트
            cursor.execute("ANALYZE")
            conn.commit()
            optimizations.append("Statistics updated")

            # 3. 캐시 정리
            cursor.execute("""
                DELETE FROM permission_cache
                WHERE expires_at < NOW() - INTERVAL '7 days'
            """)
            deleted = cursor.rowcount
            conn.commit()
            optimizations.append(f"Deleted {deleted} expired cache entries")

            # 4. 오래된 감사 로그 아카이브 (30일 이상)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS access_audit_log_archive
                (LIKE access_audit_log INCLUDING ALL)
            """)

            cursor.execute("""
                INSERT INTO access_audit_log_archive
                SELECT * FROM access_audit_log
                WHERE created_at < NOW() - INTERVAL '30 days'
            """)
            archived = cursor.rowcount

            cursor.execute("""
                DELETE FROM access_audit_log
                WHERE created_at < NOW() - INTERVAL '30 days'
            """)
            conn.commit()
            optimizations.append(f"Archived {archived} old audit log entries")

        except Exception as e:
            logger.error(f"Optimization failed: {e}")
            conn.rollback()

        finally:
            cursor.close()
            conn.close()

        self.results['optimizations'] = optimizations
        return optimizations

    def generate_report(self):
        """성능 테스트 리포트 생성"""
        logger.info("Generating performance report...")

        # 요약 통계 계산
        if 'stress_test' in self.results['tests']:
            stress_results = self.results['tests']['stress_test']
            if stress_results:
                self.results['summary'] = {
                    'max_throughput': max(r['requests_per_second'] for r in stress_results),
                    'optimal_threads': None,
                    'breaking_point': None
                }

                # 최적 스레드 수 찾기
                best_rps = 0
                for result in stress_results:
                    if result.get('requests_per_second', 0) > best_rps:
                        best_rps = result['requests_per_second']
                        self.results['summary']['optimal_threads'] = result['concurrent_threads']

                # Breaking point 찾기 (성능이 급격히 떨어지는 지점)
                for i in range(1, len(stress_results)):
                    if stress_results[i].get('requests_per_second', 0) < stress_results[i-1].get('requests_per_second', 0) * 0.8:
                        self.results['summary']['breaking_point'] = stress_results[i]['concurrent_threads']
                        break

        # 권장사항 생성
        self.generate_recommendations()

        # 리포트 저장
        report_file = f"performance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.results, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Report saved to {report_file}")
        return self.results

    def generate_recommendations(self):
        """성능 개선 권장사항 생성"""
        recommendations = []

        # 스트레스 테스트 기반 권장사항
        if 'summary' in self.results:
            summary = self.results['summary']
            if summary.get('max_throughput', 0) < 100:
                recommendations.append({
                    'priority': 'HIGH',
                    'area': 'Throughput',
                    'recommendation': 'Consider connection pooling and query optimization'
                })

            if summary.get('breaking_point') and summary['breaking_point'] < 50:
                recommendations.append({
                    'priority': 'HIGH',
                    'area': 'Concurrency',
                    'recommendation': 'Increase max_connections and implement rate limiting'
                })

        # 병목 기반 권장사항
        if 'bottlenecks' in self.results:
            for bottleneck in self.results['bottlenecks']:
                if bottleneck['type'] == 'slow_queries':
                    recommendations.append({
                        'priority': 'HIGH',
                        'area': 'Query Performance',
                        'recommendation': bottleneck['recommendation']
                    })
                elif bottleneck['type'] == 'low_cache_hit_ratio':
                    recommendations.append({
                        'priority': 'MEDIUM',
                        'area': 'Cache',
                        'recommendation': bottleneck['recommendation']
                    })

        self.results['recommendations'] = recommendations

    def plot_results(self):
        """결과 시각화"""
        if 'stress_test' not in self.results['tests']:
            return

        stress_results = self.results['tests']['stress_test']
        if not stress_results:
            return

        threads = [r['concurrent_threads'] for r in stress_results]
        rps = [r.get('requests_per_second', 0) for r in stress_results]
        avg_response = [r.get('avg_response_time', 0) * 1000 for r in stress_results]  # Convert to ms

        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 8))

        # Throughput plot
        ax1.plot(threads, rps, 'b-o')
        ax1.set_xlabel('Concurrent Threads')
        ax1.set_ylabel('Requests per Second')
        ax1.set_title('Throughput vs Concurrency')
        ax1.grid(True)

        # Response time plot
        ax2.plot(threads, avg_response, 'r-o')
        ax2.set_xlabel('Concurrent Threads')
        ax2.set_ylabel('Average Response Time (ms)')
        ax2.set_title('Response Time vs Concurrency')
        ax2.grid(True)

        plt.tight_layout()
        plot_file = f"performance_plot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        plt.savefig(plot_file)
        logger.info(f"Performance plot saved to {plot_file}")

    def run(self):
        """전체 성능 테스트 실행"""
        logger.info("=" * 70)
        logger.info("Starting Performance Testing Suite...")
        logger.info("=" * 70)

        # 1. 단일 요청 성능 테스트
        logger.info("\n1. Single Request Performance Tests")
        logger.info("-" * 40)

        single_tests = [
            ('Permission Check', self.test_permission_check, ('EMP001', 'MENU_001')),
            ('Audit Log Insert', self.test_audit_log_insert, ('EMP001',)),
            ('User Role Query', self.test_user_role_query, ('EMP001',)),
            ('Department Hierarchy', self.test_department_hierarchy, ())
        ]

        for test_name, test_func, args in single_tests:
            try:
                duration = test_func(*args)
                logger.info(f"  {test_name}: {duration*1000:.2f}ms")
                self.results['tests'][test_name.lower().replace(' ', '_')] = duration
            except Exception as e:
                logger.error(f"  {test_name}: FAILED - {e}")

        # 2. 부하 테스트
        logger.info("\n2. Load & Stress Testing")
        logger.info("-" * 40)
        self.stress_test()

        # 3. 병목 분석
        logger.info("\n3. Bottleneck Analysis")
        logger.info("-" * 40)
        bottlenecks = self.analyze_bottlenecks()
        for bottleneck in bottlenecks:
            logger.info(f"  Found: {bottleneck['type']}")

        # 4. 최적화 실행
        logger.info("\n4. Database Optimization")
        logger.info("-" * 40)
        optimizations = self.optimize_database()
        for optimization in optimizations:
            logger.info(f"  {optimization}")

        # 5. 리포트 생성
        report = self.generate_report()

        # 6. 결과 시각화
        try:
            self.plot_results()
        except Exception as e:
            logger.error(f"Plotting failed: {e}")

        logger.info("\n" + "=" * 70)
        logger.info("Performance Testing Complete")
        logger.info("=" * 70)

        # 요약 출력
        if 'summary' in report:
            logger.info(f"\nPerformance Summary:")
            logger.info(f"  Max Throughput: {report['summary'].get('max_throughput', 0):.2f} req/s")
            logger.info(f"  Optimal Threads: {report['summary'].get('optimal_threads')}")
            logger.info(f"  Breaking Point: {report['summary'].get('breaking_point')}")

        if 'recommendations' in report and report['recommendations']:
            logger.info(f"\nTop Recommendations:")
            for rec in report['recommendations'][:3]:
                logger.info(f"  [{rec['priority']}] {rec['area']}: {rec['recommendation']}")

        return report


if __name__ == "__main__":
    tester = LoadTester()
    report = tester.run()

    # Exit code based on performance
    if report.get('summary', {}).get('max_throughput', 0) > 50:
        exit(0)  # Good performance
    else:
        exit(1)  # Poor performance