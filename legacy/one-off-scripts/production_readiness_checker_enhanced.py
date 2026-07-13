#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Enhanced Production Readiness Checker - Day 4
Comprehensive validation of production environment
"""

import psycopg2
import configparser
import logging
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import subprocess
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ReadinessChecker:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self.conn = None
        self.cursor = None
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'checks': {},
            'score': 0,
            'status': 'UNKNOWN',
            'critical_issues': [],
            'warnings': [],
            'recommendations': []
        }

    def connect(self):
        """데이터베이스 연결"""
        try:
            if self.config.has_option('DATABASE', 'postgres_dsn'):
                dsn = self.config.get('DATABASE', 'postgres_dsn')
                self.conn = psycopg2.connect(dsn)
            else:
                self.conn = psycopg2.connect(
                    host='localhost',
                    database='portal_db',
                    user='postgres',
                    password='postgres'
                )
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            self.report['critical_issues'].append(f"Database connection failed: {e}")
            return False

    def check_database_schema(self) -> Tuple[bool, int]:
        """데이터베이스 스키마 체크"""
        logger.info("Checking database schema...")
        check_name = "Database Schema"
        score = 0
        passed = True
        issues = []

        required_tables = [
            'system_users', 'system_roles', 'user_role_mapping',
            'menu_registry', 'role_menu_permissions', 'permission_cache',
            'access_audit_log', 'department_hierarchy', 'permission_delegations',
            'permission_requests', 'menu_departments', 'user_menu_permissions'
        ]

        try:
            # 테이블 존재 여부 확인
            for table in required_tables:
                self.cursor.execute("""
                    SELECT table_name FROM information_schema.tables
                    WHERE table_name = %s AND table_schema = 'public'
                """, (table,))
                if not self.cursor.fetchone():
                    issues.append(f"Missing table: {table}")
                    passed = False
                else:
                    score += 5

            # 중요 컬럼 일치 여부 확인
            column_checks = [
                ('system_users', ['emp_id', 'login_id', 'user_name', 'emp_name']),
                ('user_role_mapping', ['emp_id', 'role_id', 'role_code']),
                ('access_audit_log', ['emp_id', 'success', 'action_type'])
            ]

            for table, columns in column_checks:
                for column in columns:
                    self.cursor.execute("""
                        SELECT column_name FROM information_schema.columns
                        WHERE table_name = %s AND column_name = %s
                    """, (table, column))
                    if self.cursor.fetchone():
                        score += 2
                    else:
                        issues.append(f"Missing column: {table}.{column}")
                        if column in ['emp_id', 'role_id', 'login_id']:
                            passed = False  # Critical columns

            # 인덱스 확인
            critical_indexes = [
                ('idx_users_emp_id', 'system_users'),
                ('idx_role_mapping_compound', 'user_role_mapping'),
                ('idx_audit_log_compound', 'access_audit_log')
            ]

            for idx_name, table_name in critical_indexes:
                self.cursor.execute("""
                    SELECT indexname FROM pg_indexes
                    WHERE schemaname = 'public' AND tablename = %s AND indexname = %s
                """, (table_name, idx_name))
                if self.cursor.fetchone():
                    score += 3
                else:
                    issues.append(f"Missing index: {idx_name}")

        except Exception as e:
            logger.error(f"Schema check failed: {e}")
            passed = False
            issues.append(str(e))

        self.report['checks'][check_name] = {
            'passed': passed,
            'score': min(score, 100),
            'issues': issues
        }

        if issues:
            if passed:
                self.report['warnings'].extend(issues)
            else:
                self.report['critical_issues'].extend(issues)

        return passed, min(score, 100)

    def check_data_integrity(self) -> Tuple[bool, int]:
        """데이터 무결성 체크"""
        logger.info("Checking data integrity...")
        check_name = "Data Integrity"
        score = 100
        passed = True
        issues = []

        try:
            # 1. 고아 레코드 체크
            self.cursor.execute("""
                SELECT COUNT(*) FROM user_role_mapping urm
                LEFT JOIN system_users su ON urm.emp_id = su.emp_id
                WHERE su.emp_id IS NULL
            """)
            orphan_roles = self.cursor.fetchone()[0]
            if orphan_roles > 0:
                issues.append(f"Found {orphan_roles} orphan role mappings")
                score -= 20
                passed = False

            # 2. 중복 데이터 체크
            self.cursor.execute("""
                SELECT emp_id, role_id, COUNT(*)
                FROM user_role_mapping
                GROUP BY emp_id, role_id
                HAVING COUNT(*) > 1
            """)
            duplicates = self.cursor.fetchall()
            if duplicates:
                issues.append(f"Found {len(duplicates)} duplicate role assignments")
                score -= 15
                passed = False

            # 3. 테스트 데이터 잔존 체크
            self.cursor.execute("""
                SELECT COUNT(*) FROM system_users
                WHERE emp_id LIKE 'test_%' OR emp_id LIKE 'load_test_%'
            """)
            test_users = self.cursor.fetchone()[0]
            if test_users > 0:
                issues.append(f"Found {test_users} test users in production")
                score -= 25
                passed = False

            # 4. NULL 체크
            self.cursor.execute("""
                SELECT COUNT(*) FROM system_users
                WHERE emp_id IS NULL OR login_id IS NULL
            """)
            null_critical = self.cursor.fetchone()[0]
            if null_critical > 0:
                issues.append(f"Found {null_critical} users with NULL critical fields")
                score -= 30
                passed = False

            # 5. 참조 무결성
            self.cursor.execute("""
                SELECT COUNT(*) FROM role_menu_permissions rmp
                LEFT JOIN system_roles sr ON rmp.role_id = sr.role_id
                WHERE sr.role_id IS NULL
            """)
            invalid_perms = self.cursor.fetchone()[0]
            if invalid_perms > 0:
                issues.append(f"Found {invalid_perms} permissions with invalid roles")
                score -= 10

        except Exception as e:
            logger.error(f"Data integrity check failed: {e}")
            passed = False
            score = 0
            issues.append(str(e))

        self.report['checks'][check_name] = {
            'passed': passed,
            'score': max(score, 0),
            'issues': issues
        }

        if issues:
            if score >= 70:
                self.report['warnings'].extend(issues)
            else:
                self.report['critical_issues'].extend(issues)

        return passed, max(score, 0)

    def check_performance(self) -> Tuple[bool, int]:
        """성능 체크"""
        logger.info("Checking performance metrics...")
        check_name = "Performance"
        score = 100
        passed = True
        issues = []

        try:
            # 1. 테이블 크기 체크
            self.cursor.execute("""
                SELECT
                    relname as table_name,
                    pg_size_pretty(pg_total_relation_size(relid)) as size,
                    n_tup_ins + n_tup_upd + n_tup_del as total_writes
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 10
            """)
            table_stats = self.cursor.fetchall()

            for table, size, writes in table_stats:
                logger.info(f"  Table {table}: {size}, {writes} writes")
                # Large table without proper indexing warning
                if 'GB' in size:
                    self.cursor.execute("""
                        SELECT COUNT(*) FROM pg_indexes
                        WHERE schemaname = 'public' AND tablename = %s
                    """, (table,))
                    idx_count = self.cursor.fetchone()[0]
                    if idx_count < 3:
                        issues.append(f"Large table {table} ({size}) has only {idx_count} indexes")
                        score -= 10

            # 2. 슬로우 쿼리 체크 (권한 확인 성능)
            self.cursor.execute("""
                SELECT COUNT(*) FROM access_audit_log
                WHERE created_at > NOW() - INTERVAL '24 hours'
            """)
            recent_logs = self.cursor.fetchone()[0]

            # 3. 캐시 효율성
            self.cursor.execute("""
                SELECT
                    COUNT(*) as total,
                    COUNT(CASE WHEN expires_at > NOW() THEN 1 END) as valid,
                    COUNT(CASE WHEN expires_at <= NOW() THEN 1 END) as expired
                FROM permission_cache
            """)
            cache_stats = self.cursor.fetchone()
            if cache_stats[0] > 0:
                cache_efficiency = (cache_stats[1] / cache_stats[0]) * 100
                if cache_efficiency < 50:
                    issues.append(f"Low cache efficiency: {cache_efficiency:.1f}%")
                    score -= 15

            # 4. 인덱스 사용률
            self.cursor.execute("""
                SELECT
                    schemaname,
                    tablename,
                    indexname,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public' AND idx_scan = 0
            """)
            unused_indexes = self.cursor.fetchall()
            if len(unused_indexes) > 5:
                issues.append(f"Found {len(unused_indexes)} unused indexes")
                score -= 5

        except Exception as e:
            logger.error(f"Performance check failed: {e}")
            issues.append(str(e))
            score -= 20

        self.report['checks'][check_name] = {
            'passed': score >= 70,
            'score': max(score, 0),
            'issues': issues
        }

        if issues and score >= 70:
            self.report['warnings'].extend(issues)
        elif issues:
            self.report['critical_issues'].extend(issues)

        return score >= 70, max(score, 0)

    def check_security(self) -> Tuple[bool, int]:
        """보안 체크"""
        logger.info("Checking security configuration...")
        check_name = "Security"
        score = 100
        passed = True
        issues = []

        try:
            # 1. 비밀번호 정책 체크
            self.cursor.execute("""
                SELECT COUNT(*) FROM system_users
                WHERE password IS NOT NULL AND LENGTH(password) < 8
            """)
            weak_passwords = self.cursor.fetchone()[0]
            if weak_passwords > 0:
                issues.append(f"Found {weak_passwords} users with weak passwords")
                score -= 30
                passed = False

            # 2. 과도한 권한 체크
            self.cursor.execute("""
                SELECT emp_id, COUNT(DISTINCT role_id) as role_count
                FROM user_role_mapping
                GROUP BY emp_id
                HAVING COUNT(DISTINCT role_id) > 3
            """)
            over_privileged = self.cursor.fetchall()
            if over_privileged:
                issues.append(f"Found {len(over_privileged)} users with excessive roles")
                score -= 15

            # 3. 만료된 위임 체크
            self.cursor.execute("""
                SELECT COUNT(*) FROM permission_delegations
                WHERE end_date < CURRENT_DATE AND is_active = true
            """)
            expired_delegations = self.cursor.fetchone()[0]
            if expired_delegations > 0:
                issues.append(f"Found {expired_delegations} expired but active delegations")
                score -= 10

            # 4. 감사 로그 보존
            self.cursor.execute("""
                SELECT
                    MIN(created_at) as oldest,
                    MAX(created_at) as newest,
                    COUNT(*) as total
                FROM access_audit_log
            """)
            audit_stats = self.cursor.fetchone()
            if audit_stats[2] > 0:
                retention_days = (datetime.now() - audit_stats[0]).days
                if retention_days < 90:
                    issues.append(f"Audit log retention only {retention_days} days")
                    score -= 5

            # 5. 실패한 접근 시도 체크
            self.cursor.execute("""
                SELECT emp_id, COUNT(*) as fail_count
                FROM access_audit_log
                WHERE success = false
                AND created_at > NOW() - INTERVAL '1 hour'
                GROUP BY emp_id
                HAVING COUNT(*) > 5
            """)
            suspicious_activity = self.cursor.fetchall()
            if suspicious_activity:
                issues.append(f"Found {len(suspicious_activity)} users with suspicious activity")
                score -= 20
                passed = False

        except Exception as e:
            logger.error(f"Security check failed: {e}")
            issues.append(str(e))
            score = 0
            passed = False

        self.report['checks'][check_name] = {
            'passed': passed,
            'score': max(score, 0),
            'issues': issues
        }

        if issues:
            if score >= 70:
                self.report['warnings'].extend(issues)
            else:
                self.report['critical_issues'].extend(issues)

        return passed, max(score, 0)

    def check_configuration(self) -> Tuple[bool, int]:
        """설정 파일 체크"""
        logger.info("Checking configuration...")
        check_name = "Configuration"
        score = 100
        passed = True
        issues = []

        try:
            # 1. config.ini 체크
            if not os.path.exists('config.ini'):
                issues.append("config.ini not found")
                score -= 50
                passed = False
            else:
                # 필수 섹션 체크
                required_sections = ['APPLICATION', 'DATABASE', 'SECURITY']
                for section in required_sections:
                    if not self.config.has_section(section):
                        issues.append(f"Missing config section: {section}")
                        score -= 15
                    else:
                        score += 5

                # 중요 설정 체크
                if self.config.has_option('APPLICATION', 'debug'):
                    if self.config.getboolean('APPLICATION', 'debug'):
                        issues.append("Debug mode is enabled in production")
                        score -= 30
                        passed = False

                if self.config.has_option('SECURITY', 'secret_key'):
                    secret_key = self.config.get('SECURITY', 'secret_key')
                    if len(secret_key) < 32:
                        issues.append("Secret key is too short")
                        score -= 20
                        passed = False

            # 2. 로그 설정 체크
            log_level = logging.getLogger().getEffectiveLevel()
            if log_level > logging.INFO:
                issues.append(f"Log level too high: {logging.getLevelName(log_level)}")
                score -= 10

            # 3. 백업 디렉토리 체크
            backup_dir = 'backups'
            if not os.path.exists(backup_dir):
                issues.append("Backup directory not found")
                score -= 15
                self.report['recommendations'].append(f"Create {backup_dir} directory")

        except Exception as e:
            logger.error(f"Configuration check failed: {e}")
            issues.append(str(e))
            score = 0
            passed = False

        self.report['checks'][check_name] = {
            'passed': passed,
            'score': max(score, 0),
            'issues': issues
        }

        if issues:
            if score >= 70:
                self.report['warnings'].extend(issues)
            else:
                self.report['critical_issues'].extend(issues)

        return passed, max(score, 0)

    def check_dependencies(self) -> Tuple[bool, int]:
        """의존성 체크"""
        logger.info("Checking dependencies...")
        check_name = "Dependencies"
        score = 100
        passed = True
        issues = []

        try:
            # requirements.txt 체크
            if not os.path.exists('requirements.txt'):
                issues.append("requirements.txt not found")
                score -= 50
                passed = False
            else:
                with open('requirements.txt', 'r') as f:
                    requirements = f.read()

                    # 보안 취약점 있는 패키지 버전 체크
                    vulnerable_packages = {
                        'flask<2.0': 'Flask should be >= 2.0',
                        'jinja2<3.0': 'Jinja2 should be >= 3.0',
                        'werkzeug<2.0': 'Werkzeug should be >= 2.0'
                    }

                    for pattern, message in vulnerable_packages.items():
                        if pattern.split('<')[0] in requirements.lower():
                            # 간단한 버전 체크 (실제로는 더 정교해야 함)
                            issues.append(message)
                            score -= 10

            # Python 버전 체크
            python_version = sys.version_info
            if python_version.major < 3 or (python_version.major == 3 and python_version.minor < 8):
                issues.append(f"Python version {python_version.major}.{python_version.minor} is outdated")
                score -= 20
                passed = False

        except Exception as e:
            logger.error(f"Dependencies check failed: {e}")
            issues.append(str(e))
            score -= 30

        self.report['checks'][check_name] = {
            'passed': passed,
            'score': max(score, 0),
            'issues': issues
        }

        if issues:
            if score >= 70:
                self.report['warnings'].extend(issues)
            else:
                self.report['critical_issues'].extend(issues)

        return passed, max(score, 0)

    def generate_recommendations(self):
        """개선 권장사항 생성"""
        logger.info("Generating recommendations...")

        # 점수 기반 권장사항
        for check_name, check_data in self.report['checks'].items():
            if check_data['score'] < 70:
                if check_name == "Database Schema":
                    self.report['recommendations'].append(
                        "Run schema_migration_day4.py to fix schema issues"
                    )
                elif check_name == "Data Integrity":
                    self.report['recommendations'].append(
                        "Clean up test data and fix orphan records"
                    )
                elif check_name == "Performance":
                    self.report['recommendations'].append(
                        "Add missing indexes and optimize slow queries"
                    )
                elif check_name == "Security":
                    self.report['recommendations'].append(
                        "Implement password policy and review user permissions"
                    )
                elif check_name == "Configuration":
                    self.report['recommendations'].append(
                        "Review and update configuration for production"
                    )

        # 일반 권장사항
        if self.report['score'] < 80:
            self.report['recommendations'].extend([
                "Set up automated monitoring and alerting",
                "Implement regular backup schedule",
                "Create disaster recovery plan",
                "Schedule security audit"
            ])

    def run(self):
        """전체 체크 실행"""
        logger.info("=" * 70)
        logger.info("Production Readiness Check - Starting...")
        logger.info("=" * 70)

        total_score = 0
        check_count = 0
        all_passed = True

        # 데이터베이스 연결
        if not self.connect():
            self.report['status'] = 'FAILED'
            self.report['score'] = 0
            return self.report

        # 각 체크 실행
        checks = [
            ('Database Schema', self.check_database_schema),
            ('Data Integrity', self.check_data_integrity),
            ('Performance', self.check_performance),
            ('Security', self.check_security),
            ('Configuration', self.check_configuration),
            ('Dependencies', self.check_dependencies)
        ]

        for check_name, check_func in checks:
            try:
                passed, score = check_func()
                total_score += score
                check_count += 1
                if not passed:
                    all_passed = False
                logger.info(f"  {check_name}: {'PASS' if passed else 'FAIL'} (Score: {score}/100)")
            except Exception as e:
                logger.error(f"  {check_name}: ERROR - {e}")
                self.report['checks'][check_name] = {
                    'passed': False,
                    'score': 0,
                    'issues': [str(e)]
                }
                all_passed = False
                check_count += 1

        # 전체 점수 계산
        if check_count > 0:
            self.report['score'] = total_score // check_count
        else:
            self.report['score'] = 0

        # 상태 결정
        if all_passed and self.report['score'] >= 90:
            self.report['status'] = 'READY'
        elif self.report['score'] >= 70:
            self.report['status'] = 'READY_WITH_WARNINGS'
        elif self.report['score'] >= 50:
            self.report['status'] = 'NOT_READY'
        else:
            self.report['status'] = 'CRITICAL'

        # 권장사항 생성
        self.generate_recommendations()

        # 연결 종료
        if self.cursor:
            self.cursor.close()
        if self.conn:
            self.conn.close()

        logger.info("=" * 70)
        logger.info(f"Overall Score: {self.report['score']}/100")
        logger.info(f"Status: {self.report['status']}")
        logger.info("=" * 70)

        return self.report

    def save_report(self, filename=None):
        """리포트 저장"""
        if filename is None:
            filename = f"readiness_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Report saved to {filename}")
        return filename

    def print_summary(self):
        """요약 출력"""
        print("\n" + "=" * 70)
        print("PRODUCTION READINESS SUMMARY")
        print("=" * 70)
        print(f"Overall Score: {self.report['score']}/100")
        print(f"Status: {self.report['status']}")
        print("\nCheck Results:")
        print("-" * 40)

        for check_name, check_data in self.report['checks'].items():
            status = "PASS" if check_data['passed'] else "FAIL"
            print(f"  {check_name:<20} {status:>6} ({check_data['score']}/100)")

        if self.report['critical_issues']:
            print("\nCRITICAL ISSUES:")
            print("-" * 40)
            for issue in self.report['critical_issues'][:5]:  # Top 5
                print(f"  - {issue}")

        if self.report['warnings']:
            print("\nWARNINGS:")
            print("-" * 40)
            for warning in self.report['warnings'][:5]:  # Top 5
                print(f"  - {warning}")

        if self.report['recommendations']:
            print("\nRECOMMENDATIONS:")
            print("-" * 40)
            for rec in self.report['recommendations'][:5]:  # Top 5
                print(f"  - {rec}")

        print("\n" + "=" * 70)

        # 상태별 메시지
        if self.report['status'] == 'READY':
            print("System is READY for production!")
        elif self.report['status'] == 'READY_WITH_WARNINGS':
            print("System is ready for production with minor issues to address.")
        elif self.report['status'] == 'NOT_READY':
            print("System is NOT ready for production. Address critical issues first.")
        else:  # CRITICAL
            print("System has CRITICAL issues. Do not proceed to production!")

        print("=" * 70 + "\n")


if __name__ == "__main__":
    checker = ReadinessChecker()

    # 체크 실행
    report = checker.run()

    # 리포트 저장
    report_file = checker.save_report()

    # 요약 출력
    checker.print_summary()

    # Exit code 설정
    if report['status'] in ['READY', 'READY_WITH_WARNINGS']:
        exit(0)
    else:
        exit(1)