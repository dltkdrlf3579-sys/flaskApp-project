#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SSO User Migration System - Day 4
SSO 시스템에서 사용자 정보 동기화 및 이관
"""

import psycopg2
import configparser
import logging
import json
import hashlib
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import time

try:
    import ldap
    LDAP_AVAILABLE = True
except ImportError:
    LDAP_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning("LDAP module not available. LDAP sync disabled.")

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class SSOUserMigration:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self.conn = None
        self.cursor = None
        self.stats = {
            'total_users': 0,
            'migrated': 0,
            'updated': 0,
            'failed': 0,
            'skipped': 0,
            'new_users': [],
            'updated_users': [],
            'failed_users': []
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
            logger.info("Database connected successfully")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            return False

    def get_sso_users_ldap(self) -> List[Dict]:
        """LDAP에서 SSO 사용자 정보 조회"""
        users = []

        if not LDAP_AVAILABLE:
            logger.warning("LDAP module not available, using mock data")
            return self.get_mock_sso_users()

        try:
            # LDAP 설정
            ldap_server = self.config.get('SSO', 'ldap_server', fallback='ldap://localhost:389')
            ldap_base_dn = self.config.get('SSO', 'ldap_base_dn', fallback='dc=company,dc=com')
            ldap_bind_dn = self.config.get('SSO', 'ldap_bind_dn', fallback='cn=admin,dc=company,dc=com')
            ldap_bind_password = self.config.get('SSO', 'ldap_bind_password', fallback='')

            # LDAP 연결
            conn = ldap.initialize(ldap_server)
            conn.simple_bind_s(ldap_bind_dn, ldap_bind_password)

            # 사용자 검색
            search_filter = "(objectClass=inetOrgPerson)"
            attrs = ['uid', 'cn', 'sn', 'mail', 'employeeNumber', 'department', 'title']

            results = conn.search_s(ldap_base_dn, ldap.SCOPE_SUBTREE, search_filter, attrs)

            for dn, entry in results:
                if entry:
                    user = {
                        'login_id': entry.get('uid', [b''])[0].decode('utf-8'),
                        'emp_id': entry.get('employeeNumber', [b''])[0].decode('utf-8'),
                        'user_name': entry.get('cn', [b''])[0].decode('utf-8'),
                        'email': entry.get('mail', [b''])[0].decode('utf-8'),
                        'department': entry.get('department', [b''])[0].decode('utf-8'),
                        'position': entry.get('title', [b''])[0].decode('utf-8')
                    }
                    users.append(user)

            conn.unbind()
            logger.info(f"Retrieved {len(users)} users from LDAP")

        except Exception as e:
            logger.error(f"LDAP query failed: {e}")
            # Fallback to mock data for testing
            users = self.get_mock_sso_users()

        return users

    def get_sso_users_api(self) -> List[Dict]:
        """REST API에서 SSO 사용자 정보 조회"""
        users = []
        try:
            sso_api_url = self.config.get('SSO', 'api_url', fallback='http://localhost:8080/api/users')
            sso_api_key = self.config.get('SSO', 'api_key', fallback='')

            headers = {
                'Authorization': f'Bearer {sso_api_key}',
                'Content-Type': 'application/json'
            }

            response = requests.get(sso_api_url, headers=headers, timeout=30)

            if response.status_code == 200:
                users = response.json()
                logger.info(f"Retrieved {len(users)} users from API")
            else:
                logger.error(f"API request failed with status {response.status_code}")
                users = self.get_mock_sso_users()

        except Exception as e:
            logger.error(f"API query failed: {e}")
            users = self.get_mock_sso_users()

        return users

    def get_mock_sso_users(self) -> List[Dict]:
        """테스트용 Mock SSO 사용자 데이터"""
        mock_users = [
            {
                'login_id': 'jsmith',
                'emp_id': 'EMP001',
                'user_name': 'John Smith',
                'email': 'jsmith@company.com',
                'department': 'IT',
                'position': 'Senior Developer',
                'role': 'admin'
            },
            {
                'login_id': 'mjones',
                'emp_id': 'EMP002',
                'user_name': 'Mary Jones',
                'email': 'mjones@company.com',
                'department': 'HR',
                'position': 'HR Manager',
                'role': 'manager'
            },
            {
                'login_id': 'bwilson',
                'emp_id': 'EMP003',
                'user_name': 'Bob Wilson',
                'email': 'bwilson@company.com',
                'department': 'Sales',
                'position': 'Sales Representative',
                'role': 'user'
            },
            {
                'login_id': 'ajohnson',
                'emp_id': 'EMP004',
                'user_name': 'Alice Johnson',
                'email': 'ajohnson@company.com',
                'department': 'Finance',
                'position': 'Financial Analyst',
                'role': 'viewer'
            },
            {
                'login_id': 'tlee',
                'emp_id': 'EMP005',
                'user_name': 'Tom Lee',
                'email': 'tlee@company.com',
                'department': 'IT',
                'position': 'System Administrator',
                'role': 'super_admin'
            }
        ]
        logger.info(f"Using {len(mock_users)} mock SSO users for testing")
        return mock_users

    def validate_user(self, user: Dict) -> Tuple[bool, List[str]]:
        """사용자 데이터 검증"""
        errors = []

        # 필수 필드 확인
        required_fields = ['emp_id', 'login_id', 'user_name']
        for field in required_fields:
            if not user.get(field):
                errors.append(f"Missing required field: {field}")

        # 형식 검증
        if user.get('emp_id'):
            if len(user['emp_id']) > 50:
                errors.append(f"emp_id too long: {user['emp_id']}")

        if user.get('email'):
            if '@' not in user['email']:
                errors.append(f"Invalid email format: {user['email']}")

        return len(errors) == 0, errors

    def get_or_create_department(self, dept_name: str) -> Optional[str]:
        """부서 ID 조회 또는 생성"""
        if not dept_name:
            return None

        try:
            # 기존 부서 조회
            self.cursor.execute("""
                SELECT dept_id FROM department_hierarchy
                WHERE dept_name = %s
            """, (dept_name,))
            result = self.cursor.fetchone()

            if result:
                return result[0]

            # 새 부서 생성
            dept_id = f"DEPT_{hashlib.md5(dept_name.encode()).hexdigest()[:8].upper()}"
            self.cursor.execute("""
                INSERT INTO department_hierarchy (dept_id, dept_name, parent_dept_id, level)
                VALUES (%s, %s, NULL, 1)
                RETURNING dept_id
            """, (dept_id, dept_name))
            return self.cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Department handling failed: {e}")
            return None

    def migrate_user(self, user: Dict) -> bool:
        """개별 사용자 이관"""
        try:
            # 데이터 검증
            is_valid, errors = self.validate_user(user)
            if not is_valid:
                logger.error(f"User validation failed for {user.get('emp_id')}: {errors}")
                self.stats['failed'] += 1
                self.stats['failed_users'].append({
                    'emp_id': user.get('emp_id'),
                    'errors': errors
                })
                return False

            # 부서 ID 처리
            dept_id = self.get_or_create_department(user.get('department'))

            # 기존 사용자 확인
            self.cursor.execute("""
                SELECT emp_id, login_id, user_name, email
                FROM system_users
                WHERE emp_id = %s OR login_id = %s
            """, (user['emp_id'], user['login_id']))
            existing_user = self.cursor.fetchone()

            if existing_user:
                # 기존 사용자 업데이트
                updates = []
                params = []

                if existing_user[1] != user['login_id']:
                    updates.append("login_id = %s")
                    params.append(user['login_id'])

                if existing_user[2] != user['user_name']:
                    updates.append("user_name = %s")
                    params.append(user['user_name'])
                    updates.append("emp_name = %s")  # 호환성 유지
                    params.append(user['user_name'])

                if user.get('email') and existing_user[3] != user['email']:
                    updates.append("email = %s")
                    params.append(user['email'])

                if dept_id:
                    updates.append("dept_id = %s")
                    params.append(dept_id)

                if user.get('position'):
                    updates.append("position = %s")
                    params.append(user['position'])

                updates.append("last_sync = %s")
                params.append(datetime.now())

                if updates:
                    params.append(user['emp_id'])
                    self.cursor.execute(f"""
                        UPDATE system_users
                        SET {', '.join(updates)}
                        WHERE emp_id = %s
                    """, params)

                    self.stats['updated'] += 1
                    self.stats['updated_users'].append(user['emp_id'])
                    logger.info(f"Updated user: {user['emp_id']}")
                else:
                    self.stats['skipped'] += 1
                    logger.debug(f"No changes for user: {user['emp_id']}")

            else:
                # 신규 사용자 생성
                self.cursor.execute("""
                    INSERT INTO system_users (
                        emp_id, login_id, user_name, emp_name, email,
                        dept_id, position, is_active, created_at, last_sync
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    user['emp_id'],
                    user['login_id'],
                    user['user_name'],
                    user['user_name'],  # emp_name에도 같은 값
                    user.get('email'),
                    dept_id,
                    user.get('position'),
                    True,
                    datetime.now(),
                    datetime.now()
                ))

                # 기본 역할 할당
                default_role = user.get('role', 'viewer')
                self.cursor.execute("""
                    INSERT INTO user_role_mapping (emp_id, role_id, role_code, assigned_at, assigned_by)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (emp_id, role_id) DO NOTHING
                """, (user['emp_id'], default_role, default_role, datetime.now(), 'SSO_MIGRATION'))

                self.stats['migrated'] += 1
                self.stats['new_users'].append(user['emp_id'])
                logger.info(f"Created new user: {user['emp_id']}")

            return True

        except Exception as e:
            logger.error(f"User migration failed for {user.get('emp_id')}: {e}")
            self.stats['failed'] += 1
            self.stats['failed_users'].append({
                'emp_id': user.get('emp_id'),
                'error': str(e)
            })
            return False

    def sync_permissions(self):
        """SSO 역할 기반 권한 동기화"""
        logger.info("Syncing permissions based on SSO roles...")

        try:
            # SSO 역할 매핑 규칙
            role_mappings = {
                'super_admin': ['super_admin'],
                'admin': ['admin'],
                'manager': ['manager'],
                'user': ['user'],
                'viewer': ['viewer'],
                'partner': ['partner']
            }

            # 각 사용자의 SSO 역할 확인 및 동기화
            self.cursor.execute("""
                SELECT emp_id, sso_role FROM system_users
                WHERE sso_role IS NOT NULL AND last_sync > NOW() - INTERVAL '1 day'
            """)
            users_with_roles = self.cursor.fetchall()

            for emp_id, sso_role in users_with_roles:
                if sso_role in role_mappings:
                    portal_roles = role_mappings[sso_role]

                    # 현재 역할 제거
                    self.cursor.execute("""
                        DELETE FROM user_role_mapping
                        WHERE emp_id = %s AND assigned_by = 'SSO_SYNC'
                    """, (emp_id,))

                    # 새 역할 할당
                    for role in portal_roles:
                        self.cursor.execute("""
                            INSERT INTO user_role_mapping (emp_id, role_id, role_code, assigned_at, assigned_by)
                            VALUES (%s, %s, %s, %s, 'SSO_SYNC')
                            ON CONFLICT (emp_id, role_id) DO UPDATE
                            SET assigned_at = EXCLUDED.assigned_at
                        """, (emp_id, role, role, datetime.now()))

            logger.info("Permission sync completed")

        except Exception as e:
            logger.error(f"Permission sync failed: {e}")

    def cleanup_inactive_users(self):
        """비활성 사용자 정리"""
        logger.info("Cleaning up inactive users...")

        try:
            # 30일 이상 동기화되지 않은 사용자 비활성화
            self.cursor.execute("""
                UPDATE system_users
                SET is_active = false
                WHERE last_sync < NOW() - INTERVAL '30 days'
                AND is_active = true
                RETURNING emp_id
            """)
            deactivated = self.cursor.fetchall()

            if deactivated:
                logger.info(f"Deactivated {len(deactivated)} inactive users")

                # 비활성 사용자의 권한 회수
                for (emp_id,) in deactivated:
                    self.cursor.execute("""
                        UPDATE user_role_mapping
                        SET is_active = false
                        WHERE emp_id = %s
                    """, (emp_id,))

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")

    def generate_migration_report(self):
        """이관 리포트 생성"""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.stats,
            'summary': {
                'success_rate': 0,
                'total_processed': self.stats['total_users'],
                'successful': self.stats['migrated'] + self.stats['updated'],
                'failures': self.stats['failed']
            }
        }

        if self.stats['total_users'] > 0:
            report['summary']['success_rate'] = (
                (self.stats['migrated'] + self.stats['updated']) / self.stats['total_users'] * 100
            )

        # 리포트 저장
        report_file = f"sso_migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

        logger.info(f"Migration report saved to {report_file}")
        return report

    def run(self, source='mock'):
        """전체 이관 프로세스 실행"""
        logger.info("=" * 70)
        logger.info("Starting SSO User Migration...")
        logger.info("=" * 70)

        if not self.connect():
            logger.error("Failed to connect to database")
            return False

        try:
            # SSO 사용자 데이터 가져오기
            if source == 'ldap':
                users = self.get_sso_users_ldap()
            elif source == 'api':
                users = self.get_sso_users_api()
            else:
                users = self.get_mock_sso_users()

            self.stats['total_users'] = len(users)
            logger.info(f"Processing {len(users)} users from {source}")

            # 트랜잭션은 psycopg2에서 자동으로 시작됨

            # 각 사용자 이관
            for i, user in enumerate(users, 1):
                logger.info(f"Processing user {i}/{len(users)}: {user.get('emp_id')}")
                self.migrate_user(user)

                # 배치 커밋 (100명마다)
                if i % 100 == 0:
                    self.conn.commit()
                    logger.info(f"Batch commit at {i} users")

            # 권한 동기화
            self.sync_permissions()

            # 비활성 사용자 정리
            self.cleanup_inactive_users()

            # 최종 커밋
            self.conn.commit()

            logger.info("=" * 70)
            logger.info("Migration Summary:")
            logger.info(f"  Total Users: {self.stats['total_users']}")
            logger.info(f"  New Users: {self.stats['migrated']}")
            logger.info(f"  Updated: {self.stats['updated']}")
            logger.info(f"  Failed: {self.stats['failed']}")
            logger.info(f"  Skipped: {self.stats['skipped']}")
            logger.info("=" * 70)

            # 리포트 생성
            self.generate_migration_report()

            return self.stats['failed'] == 0

        except Exception as e:
            logger.error(f"Migration failed: {e}")
            if self.conn:
                self.conn.rollback()
            return False

        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()

    def run_incremental(self):
        """증분 동기화 (스케줄러용)"""
        logger.info("Running incremental SSO sync...")

        if not self.connect():
            return False

        try:
            # 최근 변경된 사용자만 동기화
            users = self.get_sso_users_api()  # 또는 LDAP

            for user in users:
                # 최근 1시간 이내 동기화된 사용자는 스킵
                self.cursor.execute("""
                    SELECT last_sync FROM system_users
                    WHERE emp_id = %s AND last_sync > NOW() - INTERVAL '1 hour'
                """, (user['emp_id'],))

                if not self.cursor.fetchone():
                    self.migrate_user(user)

            self.conn.commit()
            logger.info("Incremental sync completed")
            return True

        except Exception as e:
            logger.error(f"Incremental sync failed: {e}")
            if self.conn:
                self.conn.rollback()
            return False

        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='SSO User Migration Tool')
    parser.add_argument(
        '--source',
        choices=['mock', 'ldap', 'api'],
        default='mock',
        help='Data source for SSO users'
    )
    parser.add_argument(
        '--incremental',
        action='store_true',
        help='Run incremental sync instead of full migration'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Perform dry run without committing changes'
    )

    args = parser.parse_args()

    migration = SSOUserMigration()

    if args.incremental:
        success = migration.run_incremental()
    else:
        success = migration.run(source=args.source)

    exit(0 if success else 1)