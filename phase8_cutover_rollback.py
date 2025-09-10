#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 8: 컷오버/롤백 시스템
PostgreSQL Migration v7 - 실제 전환 및 즉시 복귀 관리
"""
import sys
import os
import configparser
import psycopg
import sqlite3
import time
import json
from typing import Dict, List, Optional, Tuple, Any

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

class CutoverManager:
    """컷오버/롤백 관리 클래스"""
    
    def __init__(self):
        self.config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
        self.backup_config_path = self.config_path + '.phase8_backup'
        self.sqlite_path = os.path.join(os.path.dirname(__file__), 'portal.db')
    
    def get_postgres_dsn(self) -> str:
        """config.ini에서 PostgreSQL DSN 읽기"""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            return config.get('DATABASE', 'POSTGRES_DSN', 
                           fallback='postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev')
        except Exception:
            return 'postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev'
        
    def backup_current_config(self) -> bool:
        """현재 설정 백업"""
        try:
            if os.path.exists(self.config_path):
                import shutil
                shutil.copy2(self.config_path, self.backup_config_path)
                print(f"✅ 설정 백업 완료: {self.backup_config_path}")
                return True
            else:
                print("⚠️  config.ini 파일이 없습니다. 기본 설정으로 생성합니다.")
                return self.create_default_config()
        except Exception as e:
            print(f"❌ 설정 백업 실패: {e}")
            return False
    
    def create_default_config(self) -> bool:
        """기본 config.ini 생성 (앱 스키마와 일치)"""
        try:
            config_content = """[DATABASE]
DB_BACKEND = sqlite
LOCAL_DB_PATH = portal.db
POSTGRES_DSN = postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev
EXTERNAL_DB_ENABLED = false
INITIAL_SYNC_ON_FIRST_REQUEST = false
MASTER_DATA_DAILY = false
CONTENT_DATA_ONCE = false

[LOGGING]
LOG_DB_BACKEND = true
"""
            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(config_content)
            
            print(f"✅ 기본 config.ini 생성: {self.config_path}")
            return True
            
        except Exception as e:
            print(f"❌ 기본 설정 생성 실패: {e}")
            return False
    
    def read_current_backend(self) -> str:
        """현재 DB 백엔드 확인"""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            return config.get('DATABASE', 'DB_BACKEND', fallback='sqlite')
        except Exception as e:
            print(f"❌ 설정 읽기 실패: {e}")
            return 'sqlite'  # 기본값
    
    def switch_to_postgres(self) -> bool:
        """PostgreSQL로 전환 (DSN 덮어쓰지 않음)"""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            
            # DATABASE 섹션이 없으면 생성
            if 'DATABASE' not in config:
                config.add_section('DATABASE')
            
            # DB_BACKEND만 변경 (DSN은 보존)
            config.set('DATABASE', 'DB_BACKEND', 'postgres')
            
            # POSTGRES_DSN이 없는 경우에만 기본값 설정
            if not config.has_option('DATABASE', 'POSTGRES_DSN'):
                config.set('DATABASE', 'POSTGRES_DSN', 
                          'postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev')
            
            # 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            print("✅ PostgreSQL 백엔드로 전환 완료 (DSN 보존)")
            return True
            
        except Exception as e:
            print(f"❌ PostgreSQL 전환 실패: {e}")
            return False
    
    def switch_to_sqlite(self) -> bool:
        """SQLite로 롤백 (DSN 보존)"""
        try:
            config = configparser.ConfigParser()
            config.read(self.config_path, encoding='utf-8')
            
            # DATABASE 섹션이 없으면 생성
            if 'DATABASE' not in config:
                config.add_section('DATABASE')
            
            # DB_BACKEND만 변경 (다른 설정 보존)
            config.set('DATABASE', 'DB_BACKEND', 'sqlite')
            
            # LOCAL_DB_PATH가 없는 경우에만 기본값 설정
            if not config.has_option('DATABASE', 'LOCAL_DB_PATH'):
                config.set('DATABASE', 'LOCAL_DB_PATH', 'portal.db')
            
            # 파일 저장
            with open(self.config_path, 'w', encoding='utf-8') as f:
                config.write(f)
            
            print("✅ SQLite 백엔드로 롤백 완료 (설정 보존)")
            return True
            
        except Exception as e:
            print(f"❌ SQLite 롤백 실패: {e}")
            return False
    
    def restore_config_backup(self) -> bool:
        """백업 설정 복원"""
        try:
            if os.path.exists(self.backup_config_path):
                import shutil
                shutil.copy2(self.backup_config_path, self.config_path)
                print("✅ 백업 설정 복원 완료")
                return True
            else:
                print("⚠️  백업 파일이 없습니다")
                return False
        except Exception as e:
            print(f"❌ 설정 복원 실패: {e}")
            return False

class SmokeTestRunner:
    """스모크 테스트 실행기"""
    
    def __init__(self):
        self.test_scenarios = [
            {
                'name': '데이터베이스 연결 테스트',
                'function': self.test_database_connection,
                'critical': True
            },
            {
                'name': '테이블 존재 확인',
                'function': self.test_tables_exist,
                'critical': True
            },
            {
                'name': '기본 CRUD 작업',
                'function': self.test_basic_crud,
                'critical': True
            },
            {
                'name': 'JSON 데이터 검색',
                'function': self.test_json_search,
                'critical': False
            },
            {
                'name': '인덱스 활용 확인',
                'function': self.test_index_usage,
                'critical': False
            },
            {
                'name': '성능 기본 검증',
                'function': self.test_basic_performance,
                'critical': False
            }
        ]
    
    def get_current_backend(self) -> str:
        """현재 백엔드 확인"""
        try:
            config = configparser.ConfigParser()
            config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
            config.read(config_path, encoding='utf-8')
            return config.get('DATABASE', 'DB_BACKEND', fallback='sqlite')
        except:
            return 'sqlite'
    
    def get_connection(self):
        """현재 백엔드에 따른 연결 반환 (config에서 DSN 읽기)"""
        backend = self.get_current_backend()
        
        if backend == 'postgres':
            # config.ini에서 PostgreSQL DSN 읽기
            try:
                config = configparser.ConfigParser()
                config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
                config.read(config_path, encoding='utf-8')
                dsn = config.get('DATABASE', 'POSTGRES_DSN', 
                               fallback='postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev')
                return psycopg.connect(dsn)
            except Exception as e:
                print(f"⚠️  PostgreSQL DSN 읽기 실패, 기본 DSN 사용: {e}")
                return psycopg.connect('postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev')
        else:
            db_path = os.path.join(os.path.dirname(__file__), 'portal.db')
            return sqlite3.connect(db_path)
    
    def test_database_connection(self) -> Dict[str, Any]:
        """데이터베이스 연결 테스트"""
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            backend = self.get_current_backend()
            if backend == 'postgres':
                cur.execute("SELECT version()")
                version_info = cur.fetchone()[0]
            else:
                cur.execute("SELECT sqlite_version()")
                version_info = f"SQLite {cur.fetchone()[0]}"
            
            conn.close()
            
            elapsed = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'message': f'{backend} 연결 성공',
                'details': f'버전: {version_info}',
                'elapsed_ms': elapsed
            }
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': '데이터베이스 연결 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def test_tables_exist(self) -> Dict[str, Any]:
        """테이블 존재 확인"""
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            backend = self.get_current_backend()
            expected_tables = ['accidents_cache', 'safety_instructions_cache', 'follow_sop', 'full_process']
            
            existing_tables = []
            for table in expected_tables:
                if backend == 'postgres':
                    cur.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.tables 
                            WHERE table_name = %s AND table_schema = 'public'
                        )
                    """, (table,))
                else:
                    cur.execute("""
                        SELECT name FROM sqlite_master 
                        WHERE type='table' AND name=?
                    """, (table,))
                
                if backend == 'postgres':
                    if cur.fetchone()[0]:
                        existing_tables.append(table)
                else:
                    if cur.fetchone():
                        existing_tables.append(table)
            
            conn.close()
            elapsed = (time.time() - start_time) * 1000
            
            if len(existing_tables) == len(expected_tables):
                return {
                    'success': True,
                    'message': f'모든 테이블 존재 확인 ({len(existing_tables)}개)',
                    'details': ', '.join(existing_tables),
                    'elapsed_ms': elapsed
                }
            else:
                missing = set(expected_tables) - set(existing_tables)
                return {
                    'success': False,
                    'message': f'일부 테이블 누락 ({len(missing)}개)',
                    'details': f'누락: {", ".join(missing)}',
                    'elapsed_ms': elapsed
                }
                
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': '테이블 확인 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def test_basic_crud(self) -> Dict[str, Any]:
        """기본 CRUD 작업 테스트"""
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            # PostgreSQL psycopg에만 autocommit 설정 적용
            if hasattr(conn, 'autocommit'):
                conn.autocommit = True
            cur = conn.cursor()
            
            backend = self.get_current_backend()
            test_table = 'accidents_cache'
            test_data = {
                'workplace': 'Phase8테스트',
                'test_id': f'TEST_{int(time.time())}',
                'status': '테스트중'
            }
            
            # CREATE (INSERT) - 안전한 임시 테스트 테이블 사용
            test_table_safe = f"{test_table}_phase8_test"
            
            # 임시 테스트 테이블 생성
            if backend == 'postgres':
                cur.execute(f"""
                    CREATE TEMP TABLE {test_table_safe} (
                        id SERIAL PRIMARY KEY,
                        test_name TEXT,
                        custom_data JSONB DEFAULT '{{}}'::jsonb
                    )
                """)
                
                cur.execute(f"""
                    INSERT INTO {test_table_safe} (test_name, custom_data) 
                    VALUES (%s, %s::jsonb)
                """, ('Phase8-테스트', json.dumps(test_data, ensure_ascii=False)))
                
                # RETURNING으로 ID 획득
                cur.execute(f"""
                    INSERT INTO {test_table_safe} (test_name, custom_data) 
                    VALUES (%s, %s::jsonb) RETURNING id
                """, ('Phase8-테스트2', json.dumps(test_data, ensure_ascii=False)))
                test_id = cur.fetchone()[0]
            else:
                cur.execute(f"""
                    CREATE TEMP TABLE {test_table_safe} (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        test_name TEXT,
                        custom_data TEXT DEFAULT '{{}}'
                    )
                """)
                
                cur.execute(f"""
                    INSERT INTO {test_table_safe} (test_name, custom_data) 
                    VALUES (?, ?)
                """, ('Phase8-테스트', json.dumps(test_data, ensure_ascii=False)))
                test_id = cur.lastrowid
            
            # READ (SELECT) - 임시 테이블에서 조회
            if backend == 'postgres':
                cur.execute(f"""
                    SELECT COUNT(*) FROM {test_table_safe} 
                    WHERE custom_data->>'workplace' = %s
                """, ('Phase8테스트',))
            else:
                cur.execute(f"""
                    SELECT COUNT(*) FROM {test_table_safe} 
                    WHERE json_extract(custom_data, '$.workplace') = ?
                """, ('Phase8테스트',))
            
            count = cur.fetchone()[0]
            
            # UPDATE - 임시 테이블 업데이트
            updated_data = test_data.copy()
            updated_data['status'] = '업데이트됨'
            
            if backend == 'postgres':
                cur.execute(f"""
                    UPDATE {test_table_safe} 
                    SET custom_data = %s::jsonb 
                    WHERE id = %s
                """, (json.dumps(updated_data, ensure_ascii=False), test_id))
            else:
                cur.execute(f"""
                    UPDATE {test_table_safe} 
                    SET custom_data = ? 
                    WHERE id = ?
                """, (json.dumps(updated_data, ensure_ascii=False), test_id))
            
            # DELETE (정리) - 임시 테이블에서만 삭제
            if backend == 'postgres':
                cur.execute(f"""
                    DELETE FROM {test_table_safe} 
                    WHERE custom_data->>'workplace' = %s
                """, ('Phase8테스트',))
            else:
                cur.execute(f"""
                    DELETE FROM {test_table_safe} 
                    WHERE json_extract(custom_data, '$.workplace') = ?
                """, ('Phase8테스트',))
            
            deleted_count = cur.rowcount if hasattr(cur, 'rowcount') else 0
            
            # 임시 테이블 자동 정리 (TEMP 테이블이므로 세션 종료 시 자동 삭제됨)
            
            conn.close()
            elapsed = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'message': 'CRUD 작업 성공',
                'details': f'생성/조회({count}개)/수정/삭제({deleted_count}개) 완료',
                'elapsed_ms': elapsed
            }
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': 'CRUD 작업 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def test_json_search(self) -> Dict[str, Any]:
        """JSON 검색 테스트"""
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            backend = self.get_current_backend()
            
            # JSON 키 존재 확인
            if backend == 'postgres':
                cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE custom_data ? 'workplace'")
            else:
                cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE json_extract(custom_data, '$.workplace') IS NOT NULL")
            
            json_count = cur.fetchone()[0]
            
            # 특정 값 검색
            if backend == 'postgres':
                cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'workplace' = '공장A'")
            else:
                cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE json_extract(custom_data, '$.workplace') = '공장A'")
            
            specific_count = cur.fetchone()[0]
            
            conn.close()
            elapsed = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'message': 'JSON 검색 성공',
                'details': f'JSON 키 보유: {json_count}개, 특정값: {specific_count}개',
                'elapsed_ms': elapsed
            }
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': 'JSON 검색 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def test_index_usage(self) -> Dict[str, Any]:
        """인덱스 활용 확인 (PostgreSQL만)"""
        start_time = time.time()
        
        backend = self.get_current_backend()
        if backend != 'postgres':
            return {
                'success': True,
                'message': 'SQLite - 인덱스 테스트 생략',
                'details': 'PostgreSQL에서만 테스트',
                'elapsed_ms': 0
            }
        
        try:
            # config에서 PostgreSQL DSN 읽기
            try:
                config = configparser.ConfigParser()
                config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
                config.read(config_path, encoding='utf-8')
                dsn = config.get('DATABASE', 'POSTGRES_DSN', 
                               fallback='postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev')
            except Exception:
                dsn = 'postgresql://postgres:강력한_비밀번호@localhost:5432/portal_dev'
                
            conn = psycopg.connect(dsn)
            cur = conn.cursor()
            
            # 실행계획 확인
            cur.execute("""
                EXPLAIN (FORMAT JSON) 
                SELECT COUNT(*) FROM accidents_cache 
                WHERE custom_data->>'workplace' = '공장A'
            """)
            
            plan = cur.fetchone()[0][0]
            uses_index = 'Index' in str(plan)
            
            conn.close()
            elapsed = (time.time() - start_time) * 1000
            
            return {
                'success': True,
                'message': f'인덱스 활용: {"✅ Yes" if uses_index else "❌ No"}',
                'details': 'workplace 검색 실행계획 확인',
                'elapsed_ms': elapsed
            }
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': '인덱스 확인 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def test_basic_performance(self) -> Dict[str, Any]:
        """기본 성능 테스트"""
        start_time = time.time()
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            backend = self.get_current_backend()
            
            # 간단한 성능 테스트
            times = []
            for _ in range(3):
                query_start = time.time()
                
                if backend == 'postgres':
                    cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE custom_data->>'workplace' = '공장A'")
                else:
                    cur.execute("SELECT COUNT(*) FROM accidents_cache WHERE json_extract(custom_data, '$.workplace') = '공장A'")
                
                result = cur.fetchone()[0]
                query_end = time.time()
                times.append((query_end - query_start) * 1000)
            
            avg_time = sum(times) / len(times)
            conn.close()
            elapsed = (time.time() - start_time) * 1000
            
            # 성능 기준은 정보성 로그만 (개발환경 변동폭 고려)
            performance_info = "양호" if avg_time < 50 else "주의"
            
            return {
                'success': True,  # 성능은 실패 기준이 아닌 정보성
                'message': f'평균 응답시간: {avg_time:.2f}ms ({performance_info})',
                'details': f'3회 측정, 결과: {result}개, 기준: <50ms는 참고용',
                'elapsed_ms': elapsed
            }
            
        except Exception as e:
            elapsed = (time.time() - start_time) * 1000
            return {
                'success': False,
                'message': '성능 테스트 실패',
                'details': str(e),
                'elapsed_ms': elapsed
            }
    
    def run_all_tests(self) -> Dict[str, Any]:
        """모든 스모크 테스트 실행"""
        print("=== 스모크 테스트 실행 ===")
        
        results = []
        critical_failures = 0
        total_time = 0
        
        for scenario in self.test_scenarios:
            print(f"\n🔄 {scenario['name']} 실행 중...")
            
            result = scenario['function']()
            result['name'] = scenario['name']
            result['critical'] = scenario['critical']
            
            if result['success']:
                print(f"✅ {scenario['name']}: {result['message']} ({result['elapsed_ms']:.1f}ms)")
            else:
                status = "🚨" if scenario['critical'] else "⚠️"
                print(f"{status} {scenario['name']}: {result['message']}")
                print(f"   상세: {result['details']}")
                
                if scenario['critical']:
                    critical_failures += 1
            
            results.append(result)
            total_time += result['elapsed_ms']
        
        # 결과 요약
        passed = sum(1 for r in results if r['success'])
        total = len(results)
        critical_passed = sum(1 for r in results if r['success'] and r['critical'])
        critical_total = sum(1 for r in results if r['critical'])
        
        summary = {
            'total_tests': total,
            'passed_tests': passed,
            'critical_tests': critical_total,
            'critical_passed': critical_passed,
            'critical_failures': critical_failures,
            'total_time_ms': total_time,
            'results': results,
            'overall_success': critical_failures == 0
        }
        
        return summary

def execute_cutover():
    """컷오버 실행"""
    print("=== Phase 8: 컷오버 시작 ===")
    
    manager = CutoverManager()
    tester = SmokeTestRunner()
    
    # 1. 현재 상태 확인
    current_backend = manager.read_current_backend()
    print(f"📊 현재 백엔드: {current_backend}")
    
    if current_backend == 'postgres':
        print("⚠️  이미 PostgreSQL 백엔드입니다.")
        return True
    
    # 2. 설정 백업
    if not manager.backup_current_config():
        print("❌ 설정 백업 실패 - 컷오버 중단")
        return False
    
    # 3. PostgreSQL로 전환
    print("\n--- PostgreSQL 전환 ---")
    if not manager.switch_to_postgres():
        print("❌ PostgreSQL 전환 실패 - 롤백 시도")
        manager.restore_config_backup()
        return False
    
    # 4. 스모크 테스트 실행
    print("\n--- 스모크 테스트 ---")
    test_results = tester.run_all_tests()
    
    # 5. 결과 평가
    print(f"\n=== 컷오버 결과 ===")
    print(f"전체 테스트: {test_results['passed_tests']}/{test_results['total_tests']} 통과")
    print(f"핵심 테스트: {test_results['critical_passed']}/{test_results['critical_tests']} 통과")
    print(f"전체 소요시간: {test_results['total_time_ms']:.1f}ms")
    
    if test_results['overall_success']:
        print("🎉 컷오버 성공! PostgreSQL 백엔드로 전환 완료")
        return True
    else:
        print(f"❌ 핵심 테스트 실패 ({test_results['critical_failures']}개) - 자동 롤백 시도")
        
        # 자동 롤백
        if manager.switch_to_sqlite():
            print("✅ 자동 롤백 완료 - SQLite로 복귀")
        else:
            print("❌ 자동 롤백 실패 - 수동 복구 필요")
            print("   수동 복구: config.ini에서 DB_BACKEND=sqlite로 설정")
        
        return False

def execute_rollback():
    """롤백 실행"""
    print("=== Phase 8: 롤백 시작 ===")
    
    manager = CutoverManager()
    tester = SmokeTestRunner()
    
    # 1. 현재 상태 확인
    current_backend = manager.read_current_backend()
    print(f"📊 현재 백엔드: {current_backend}")
    
    if current_backend == 'sqlite':
        print("✅ 이미 SQLite 백엔드입니다.")
        return True
    
    # 2. SQLite로 롤백
    print("\n--- SQLite 롤백 ---")
    if not manager.switch_to_sqlite():
        print("❌ SQLite 롤백 실패")
        return False
    
    # 3. 롤백 후 검증
    print("\n--- 롤백 검증 ---")
    test_results = tester.run_all_tests()
    
    # 4. 결과 평가
    print(f"\n=== 롤백 결과 ===")
    print(f"전체 테스트: {test_results['passed_tests']}/{test_results['total_tests']} 통과")
    print(f"핵심 테스트: {test_results['critical_passed']}/{test_results['critical_tests']} 통과")
    
    if test_results['overall_success']:
        print("✅ 롤백 성공! SQLite 백엔드로 복귀 완료")
        return True
    else:
        print("❌ 롤백 후 검증 실패")
        return False

def status_check():
    """현재 상태 확인"""
    print("=== Phase 8: 상태 확인 ===")
    
    manager = CutoverManager()
    tester = SmokeTestRunner()
    
    # 설정 확인
    current_backend = manager.read_current_backend()
    print(f"📊 현재 백엔드: {current_backend}")
    
    # 간단한 연결 테스트
    connection_test = tester.test_database_connection()
    if connection_test['success']:
        print(f"✅ {connection_test['message']}")
        print(f"   {connection_test['details']}")
    else:
        print(f"❌ {connection_test['message']}")
        print(f"   {connection_test['details']}")
    
    return connection_test['success']

def main():
    """메인 실행"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Phase 8: 컷오버/롤백 시스템')
    parser.add_argument('action', choices=['cutover', 'rollback', 'status', 'test'], 
                       help='실행할 작업')
    
    try:
        args = parser.parse_args()
    except:
        # 인자가 없으면 대화형 모드
        print("Phase 8: 컷오버/롤백 시스템")
        print("1. cutover  - PostgreSQL로 전환")
        print("2. rollback - SQLite로 롤백") 
        print("3. status   - 현재 상태 확인")
        print("4. test     - 스모크 테스트만 실행")
        
        choice = input("\n선택하세요 (1-4): ").strip()
        
        if choice == '1':
            args_action = 'cutover'
        elif choice == '2':
            args_action = 'rollback'
        elif choice == '3':
            args_action = 'status'
        elif choice == '4':
            args_action = 'test'
        else:
            print("잘못된 선택입니다.")
            return False
    else:
        args_action = args.action
    
    # 작업 실행
    if args_action == 'cutover':
        return execute_cutover()
    elif args_action == 'rollback':
        return execute_rollback()
    elif args_action == 'status':
        return status_check()
    elif args_action == 'test':
        tester = SmokeTestRunner()
        results = tester.run_all_tests()
        return results['overall_success']
    else:
        print(f"알 수 없는 작업: {args_action}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)