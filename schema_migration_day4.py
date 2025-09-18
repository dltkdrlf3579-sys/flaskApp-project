#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 1-3 스키마 불일치 수정
운영 전환 전 필수 실행
"""

import psycopg2
import configparser
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class SchemaMigration:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config.ini', encoding='utf-8')
        self.conn = None
        self.cursor = None
        self.changes = []

    def connect(self):
        """데이터베이스 연결"""
        try:
            if self.config.has_option('DATABASE', 'postgres_dsn'):
                dsn = self.config.get('DATABASE', 'postgres_dsn')
                self.conn = psycopg2.connect(dsn)
            else:
                # 기본값 사용
                self.conn = psycopg2.connect(
                    host='localhost',
                    database='portal_db',
                    user='postgres',
                    password='postgres'
                )
            self.cursor = self.conn.cursor()
            logger.info("Database connected successfully")
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            raise

    def check_column_exists(self, table, column):
        """컬럼 존재 확인"""
        self.cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
        """, (table, column))
        return self.cursor.fetchone() is not None

    def check_table_exists(self, table):
        """테이블 존재 확인"""
        self.cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = %s AND table_schema = 'public'
        """, (table,))
        return self.cursor.fetchone() is not None

    def migrate_system_users(self):
        """system_users 테이블 정합성 확인"""
        logger.info("Checking system_users table...")

        if not self.check_table_exists('system_users'):
            logger.warning("system_users table does not exist")
            return

        # user_name vs emp_name 확인
        has_emp_name = self.check_column_exists('system_users', 'emp_name')
        has_user_name = self.check_column_exists('system_users', 'user_name')

        if has_emp_name and not has_user_name:
            self.cursor.execute("""
                ALTER TABLE system_users
                ADD COLUMN IF NOT EXISTS user_name VARCHAR(100)
            """)
            self.cursor.execute("""
                UPDATE system_users
                SET user_name = emp_name
                WHERE user_name IS NULL
            """)
            self.changes.append("Added user_name column to system_users")

        elif has_user_name and not has_emp_name:
            self.cursor.execute("""
                ALTER TABLE system_users
                ADD COLUMN IF NOT EXISTS emp_name VARCHAR(100)
            """)
            self.cursor.execute("""
                UPDATE system_users
                SET emp_name = user_name
                WHERE emp_name IS NULL
            """)
            self.changes.append("Added emp_name column to system_users")

        # email 컬럼 추가 (없으면)
        if not self.check_column_exists('system_users', 'email'):
            self.cursor.execute("""
                ALTER TABLE system_users
                ADD COLUMN IF NOT EXISTS email VARCHAR(200)
            """)
            self.changes.append("Added email column to system_users")

    def migrate_role_tables(self):
        """역할 관련 테이블 정합성 확인"""
        logger.info("Checking role tables...")

        # role_menu_permissions 테이블 체크
        if self.check_table_exists('role_menu_permissions'):
            has_role_id = self.check_column_exists('role_menu_permissions', 'role_id')
            has_role_code = self.check_column_exists('role_menu_permissions', 'role_code')

            if has_role_id and not has_role_code:
                self.cursor.execute("""
                    ALTER TABLE role_menu_permissions
                    ADD COLUMN IF NOT EXISTS role_code VARCHAR(50)
                """)
                self.cursor.execute("""
                    UPDATE role_menu_permissions
                    SET role_code = role_id
                    WHERE role_code IS NULL
                """)
                self.changes.append("Added role_code to role_menu_permissions")

            elif has_role_code and not has_role_id:
                self.cursor.execute("""
                    ALTER TABLE role_menu_permissions
                    ADD COLUMN IF NOT EXISTS role_id VARCHAR(50)
                """)
                self.cursor.execute("""
                    UPDATE role_menu_permissions
                    SET role_id = role_code
                    WHERE role_id IS NULL
                """)
                self.changes.append("Added role_id to role_menu_permissions")

        # user_role_mapping 테이블 체크
        if self.check_table_exists('user_role_mapping'):
            has_role_id = self.check_column_exists('user_role_mapping', 'role_id')
            has_role_code = self.check_column_exists('user_role_mapping', 'role_code')

            if has_role_code and not has_role_id:
                self.cursor.execute("""
                    ALTER TABLE user_role_mapping
                    ADD COLUMN IF NOT EXISTS role_id VARCHAR(50)
                """)
                self.cursor.execute("""
                    UPDATE user_role_mapping
                    SET role_id = role_code
                    WHERE role_id IS NULL
                """)
                self.changes.append("Added role_id to user_role_mapping")

            elif has_role_id and not has_role_code:
                self.cursor.execute("""
                    ALTER TABLE user_role_mapping
                    ADD COLUMN IF NOT EXISTS role_code VARCHAR(50)
                """)
                self.cursor.execute("""
                    UPDATE user_role_mapping
                    SET role_code = role_id
                    WHERE role_code IS NULL
                """)
                self.changes.append("Added role_code to user_role_mapping")

    def migrate_audit_log(self):
        """감사 로그 테이블 정합성 확인"""
        logger.info("Checking audit log table...")

        if not self.check_table_exists('access_audit_log'):
            logger.warning("access_audit_log table does not exist")
            return

        # permission_result vs success 컬럼 확인
        if not self.check_column_exists('access_audit_log', 'success'):
            self.cursor.execute("""
                ALTER TABLE access_audit_log
                ADD COLUMN IF NOT EXISTS success BOOLEAN
            """)

            # permission_result 컬럼이 있으면 변환
            if self.check_column_exists('access_audit_log', 'permission_result'):
                self.cursor.execute("""
                    UPDATE access_audit_log
                    SET success = CASE
                        WHEN permission_result IN ('SUCCESS', 'GRANTED', 'ALLOWED') THEN TRUE
                        WHEN permission_result IN ('DENIED', 'FORBIDDEN', 'FAILED') THEN FALSE
                        ELSE NULL
                    END
                    WHERE success IS NULL
                """)

            self.changes.append("Added success column to access_audit_log")

        # action_type 컬럼 추가 (없으면)
        if not self.check_column_exists('access_audit_log', 'action_type'):
            self.cursor.execute("""
                ALTER TABLE access_audit_log
                ADD COLUMN IF NOT EXISTS action_type VARCHAR(50)
            """)
            self.changes.append("Added action_type column to access_audit_log")

        # ip_address 컬럼 추가 (없으면)
        if not self.check_column_exists('access_audit_log', 'ip_address'):
            self.cursor.execute("""
                ALTER TABLE access_audit_log
                ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45)
            """)
            self.changes.append("Added ip_address column to access_audit_log")

    def create_missing_indexes(self):
        """누락된 인덱스 생성"""
        logger.info("Creating missing indexes...")

        indexes = [
            ("idx_users_login_id", "system_users", "(login_id)"),
            ("idx_users_emp_id", "system_users", "(emp_id)"),
            ("idx_users_dept", "system_users", "(dept_id)"),
            ("idx_role_mapping_emp", "user_role_mapping", "(emp_id)"),
            ("idx_role_mapping_compound", "user_role_mapping", "(emp_id, role_id)"),
            ("idx_audit_log_emp", "access_audit_log", "(emp_id)"),
            ("idx_audit_log_created", "access_audit_log", "(created_at DESC)"),
            ("idx_audit_log_compound", "access_audit_log", "(emp_id, created_at DESC)"),
            ("idx_cache_expires", "permission_cache", "(expires_at)"),
            ("idx_cache_emp_menu", "permission_cache", "(emp_id, menu_code)")
        ]

        for idx_name, table_name, idx_columns in indexes:
            try:
                # 테이블 존재 확인
                if not self.check_table_exists(table_name):
                    logger.warning(f"Table {table_name} does not exist, skipping index {idx_name}")
                    continue

                # 인덱스 존재 확인
                self.cursor.execute("""
                    SELECT indexname
                    FROM pg_indexes
                    WHERE schemaname = 'public'
                    AND tablename = %s
                    AND indexname = %s
                """, (table_name, idx_name))

                if not self.cursor.fetchone():
                    self.cursor.execute(f"""
                        CREATE INDEX {idx_name} ON {table_name} {idx_columns}
                    """)
                    self.changes.append(f"Created index {idx_name} on {table_name}")
                else:
                    logger.info(f"Index {idx_name} already exists")

            except Exception as e:
                logger.warning(f"Could not create index {idx_name}: {e}")

    def backup_before_migration(self):
        """마이그레이션 전 백업"""
        logger.info("Creating backup tables...")
        backup_time = datetime.now().strftime('%Y%m%d_%H%M%S')

        tables_to_backup = [
            'system_users',
            'role_menu_permissions',
            'user_role_mapping',
            'access_audit_log',
            'permission_cache'
        ]

        for table in tables_to_backup:
            try:
                if not self.check_table_exists(table):
                    logger.warning(f"Table {table} does not exist, skipping backup")
                    continue

                backup_table = f"{table}_backup_{backup_time}"

                # 백업 테이블이 이미 존재하는지 확인
                if self.check_table_exists(backup_table):
                    logger.warning(f"Backup table {backup_table} already exists, skipping")
                    continue

                self.cursor.execute(f"""
                    CREATE TABLE {backup_table} AS
                    SELECT * FROM {table}
                """)
                self.changes.append(f"Backed up {table} to {backup_table}")

            except Exception as e:
                logger.warning(f"Could not backup {table}: {e}")

    def cleanup_test_data(self):
        """테스트 데이터 정리"""
        logger.info("Cleaning up test data...")

        test_users = [
            'test_user', 'test_partner', 'test_manager', 'admin',
            'delegator1', 'delegate1', 'staff1', 'approver1',
            'new_employee', 'manager1', 'dev_user1'
        ]

        # 테스트 사용자와 관련 데이터 삭제
        if self.check_table_exists('user_role_mapping'):
            self.cursor.execute("""
                DELETE FROM user_role_mapping
                WHERE emp_id = ANY(%s)
            """, (test_users,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} test user role mappings")

        if self.check_table_exists('user_menu_permissions'):
            self.cursor.execute("""
                DELETE FROM user_menu_permissions
                WHERE emp_id = ANY(%s)
            """, (test_users,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} test user permissions")

        if self.check_table_exists('permission_delegations'):
            self.cursor.execute("""
                DELETE FROM permission_delegations
                WHERE delegator_id = ANY(%s) OR delegate_id = ANY(%s)
            """, (test_users, test_users))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} test delegations")

        if self.check_table_exists('permission_requests'):
            self.cursor.execute("""
                DELETE FROM permission_requests
                WHERE requester_id = ANY(%s)
            """, (test_users,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} test permission requests")

        if self.check_table_exists('system_users'):
            self.cursor.execute("""
                DELETE FROM system_users
                WHERE emp_id = ANY(%s)
            """, (test_users,))
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} test users")

        # Load test 사용자 정리
        if self.check_table_exists('system_users'):
            self.cursor.execute("""
                DELETE FROM system_users
                WHERE emp_id LIKE 'load_test_user_%'
            """)
            deleted = self.cursor.rowcount
            if deleted > 0:
                self.changes.append(f"Deleted {deleted} load test users")

    def run(self):
        """전체 마이그레이션 실행"""
        try:
            self.connect()
            logger.info("=" * 60)
            logger.info("Starting schema migration for Day 4...")
            logger.info("=" * 60)

            # 1. 백업 먼저
            self.backup_before_migration()

            # 2. 각 테이블 마이그레이션
            self.migrate_system_users()
            self.migrate_role_tables()
            self.migrate_audit_log()

            # 3. 인덱스 생성
            self.create_missing_indexes()

            # 4. 테스트 데이터 정리
            self.cleanup_test_data()

            # 5. 커밋
            self.conn.commit()

            logger.info("=" * 60)
            logger.info("Migration completed successfully!")
            logger.info(f"Total changes made: {len(self.changes)}")

            if self.changes:
                logger.info("\nChanges summary:")
                for i, change in enumerate(self.changes, 1):
                    logger.info(f"  {i}. {change}")
            else:
                logger.info("No changes were necessary")

            logger.info("=" * 60)
            return True

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

    def verify_migration(self):
        """마이그레이션 결과 검증"""
        try:
            self.connect()
            logger.info("\nVerifying migration results...")

            # 필수 테이블 확인
            required_tables = [
                'system_users', 'system_roles', 'user_role_mapping',
                'menu_registry', 'role_menu_permissions', 'permission_cache',
                'access_audit_log', 'department_hierarchy'
            ]

            missing_tables = []
            for table in required_tables:
                if not self.check_table_exists(table):
                    missing_tables.append(table)

            if missing_tables:
                logger.warning(f"Missing tables: {missing_tables}")
            else:
                logger.info("✅ All required tables exist")

            # 테스트 데이터 확인
            if self.check_table_exists('system_users'):
                self.cursor.execute("""
                    SELECT COUNT(*) FROM system_users
                    WHERE emp_id LIKE 'test_%' OR emp_id LIKE 'load_test_%'
                """)
                test_count = self.cursor.fetchone()[0]

                if test_count > 0:
                    logger.warning(f"⚠️ Found {test_count} test users remaining")
                else:
                    logger.info("✅ No test users found")

            return len(missing_tables) == 0

        except Exception as e:
            logger.error(f"Verification failed: {e}")
            return False

        finally:
            if self.cursor:
                self.cursor.close()
            if self.conn:
                self.conn.close()


if __name__ == "__main__":
    migration = SchemaMigration()

    # 마이그레이션 실행
    if migration.run():
        print("\n✅ Schema migration completed successfully")

        # 결과 검증
        if migration.verify_migration():
            print("✅ Migration verification passed")
        else:
            print("⚠️ Migration verification found issues")
    else:
        print("\n❌ Schema migration failed")
        exit(1)