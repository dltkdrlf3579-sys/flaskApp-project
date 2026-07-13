#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
emp_id 제거 및 login_id를 primary key로 변경하는 스크립트
Knox ID를 SSO 식별자로 사용
"""

import psycopg2
from psycopg2 import sql
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def remove_empid_and_setup_knox():
    """emp_id 제거 및 knox_id 설정"""

    try:
        conn = psycopg2.connect(
            host="localhost",
            database="portal_dev",
            user="postgres",
            password="admin123"
        )
        cur = conn.cursor()
        print("[OK] Database connection successful")
    except Exception as e:
        print(f"[ERROR] Database connection failed: {e}")
        return False

    operations = [
        # 1. user_menu_permissions 테이블 수정
        ("Drop user_menu_permissions constraints", """
            ALTER TABLE user_menu_permissions
            DROP CONSTRAINT IF EXISTS user_menu_permissions_pkey CASCADE;

            ALTER TABLE user_menu_permissions
            DROP CONSTRAINT IF EXISTS user_menu_permissions_emp_id_menu_code_key CASCADE;
        """),

        ("Remove emp_id from user_menu_permissions", """
            ALTER TABLE user_menu_permissions
            DROP COLUMN IF EXISTS emp_id CASCADE;
        """),

        ("Add primary key to user_menu_permissions", """
            ALTER TABLE user_menu_permissions
            ADD CONSTRAINT user_menu_permissions_pkey PRIMARY KEY (login_id, menu_code);
        """),

        # 2. user_role_mapping 테이블 수정
        ("Drop user_role_mapping constraints", """
            ALTER TABLE user_role_mapping
            DROP CONSTRAINT IF EXISTS user_role_mapping_pkey CASCADE;

            ALTER TABLE user_role_mapping
            DROP CONSTRAINT IF EXISTS user_role_mapping_emp_id_role_code_key CASCADE;
        """),

        ("Remove emp_id from user_role_mapping", """
            ALTER TABLE user_role_mapping
            DROP COLUMN IF EXISTS emp_id CASCADE;
        """),

        ("Add primary key to user_role_mapping", """
            ALTER TABLE user_role_mapping
            ADD CONSTRAINT user_role_mapping_pkey PRIMARY KEY (login_id, role_code);
        """),

        # 3. user_menu_roles 테이블 수정
        ("Drop user_menu_roles constraints", """
            ALTER TABLE user_menu_roles
            DROP CONSTRAINT IF EXISTS user_menu_roles_pkey CASCADE;

            ALTER TABLE user_menu_roles
            DROP CONSTRAINT IF EXISTS user_menu_roles_emp_id_menu_code_key CASCADE;
        """),

        ("Remove emp_id from user_menu_roles", """
            ALTER TABLE user_menu_roles
            DROP COLUMN IF EXISTS emp_id CASCADE;
        """),

        ("Add primary key to user_menu_roles", """
            ALTER TABLE user_menu_roles
            ADD CONSTRAINT user_menu_roles_pkey PRIMARY KEY (login_id, menu_code);
        """),

        # 4. system_users 테이블 수정
        ("Add knox_id column", """
            ALTER TABLE system_users
            ADD COLUMN IF NOT EXISTS knox_id VARCHAR(100);
        """),

        ("Copy login_id to knox_id", """
            UPDATE system_users SET knox_id = login_id WHERE knox_id IS NULL;
        """),

        ("Make knox_id unique", """
            ALTER TABLE system_users
            ADD CONSTRAINT system_users_knox_id_key UNIQUE (knox_id);
        """),

        ("Update system_users primary key", """
            ALTER TABLE system_users
            DROP CONSTRAINT IF EXISTS system_users_pkey CASCADE;

            ALTER TABLE system_users
            ADD CONSTRAINT system_users_pkey PRIMARY KEY (login_id);
        """),

        # 5. 인덱스 생성
        ("Create indexes", """
            CREATE INDEX IF NOT EXISTS idx_system_users_knox_id ON system_users(knox_id);
            CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_login_id ON user_menu_permissions(login_id);
            CREATE INDEX IF NOT EXISTS idx_user_role_mapping_login_id ON user_role_mapping(login_id);
            CREATE INDEX IF NOT EXISTS idx_user_menu_roles_login_id ON user_menu_roles(login_id);
        """),

        # 6. 함수 업데이트
        ("Create check_user_permission function", """
            CREATE OR REPLACE FUNCTION check_user_permission(
                p_login_id VARCHAR,
                p_menu_code VARCHAR,
                p_action VARCHAR
            ) RETURNS BOOLEAN AS $$
            DECLARE
                has_permission BOOLEAN := FALSE;
            BEGIN
                SELECT
                    CASE p_action
                        WHEN 'view' THEN can_view
                        WHEN 'create' THEN can_create
                        WHEN 'edit' THEN can_edit
                        WHEN 'delete' THEN can_delete
                        ELSE FALSE
                    END INTO has_permission
                FROM user_menu_permissions
                WHERE login_id = p_login_id
                    AND menu_code = p_menu_code
                    AND is_active = TRUE
                LIMIT 1;

                RETURN COALESCE(has_permission, FALSE);
            END;
            $$ LANGUAGE plpgsql;
        """),

        ("Create get_user_by_knox_id function", """
            CREATE OR REPLACE FUNCTION get_user_by_knox_id(
                p_knox_id VARCHAR
            ) RETURNS TABLE(
                login_id VARCHAR,
                name VARCHAR,
                dept_code VARCHAR,
                position VARCHAR
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT
                    u.login_id,
                    u.name,
                    u.dept_code,
                    u.position
                FROM system_users u
                WHERE u.knox_id = p_knox_id
                    AND u.is_active = TRUE
                LIMIT 1;
            END;
            $$ LANGUAGE plpgsql;
        """)
    ]

    for description, query in operations:
        try:
            print(f"\n[EXECUTING] {description}...")
            cur.execute(query)
            print(f"[OK] {description}")
        except psycopg2.errors.UndefinedColumn as e:
            print(f"[SKIP] {description} - Column doesn't exist: {e}")
        except psycopg2.errors.DuplicateObject as e:
            print(f"[SKIP] {description} - Already exists: {e}")
        except Exception as e:
            print(f"[ERROR] {description} failed: {e}")
            conn.rollback()
            continue

    # 통계 출력
    print("\n[STATS] Checking final state...")

    tables = ['user_menu_permissions', 'user_role_mapping', 'user_menu_roles']
    for table in tables:
        try:
            # emp_id 컬럼 존재 확인
            cur.execute(f"""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = '{table}' AND column_name = 'emp_id'
            """)

            if cur.fetchone():
                print(f"[WARNING] {table} still has emp_id column")
            else:
                print(f"[OK] {table} - emp_id removed successfully")

            # login_id로 primary key 확인
            cur.execute(f"""
                SELECT constraint_name
                FROM information_schema.table_constraints
                WHERE table_name = '{table}'
                AND constraint_type = 'PRIMARY KEY'
            """)

            constraint = cur.fetchone()
            if constraint:
                print(f"[OK] {table} has primary key: {constraint[0]}")

        except Exception as e:
            print(f"[ERROR] Failed to check {table}: {e}")

    # knox_id 확인
    try:
        cur.execute("""
            SELECT COUNT(*) FROM system_users WHERE knox_id IS NOT NULL
        """)
        knox_count = cur.fetchone()[0]
        print(f"\n[OK] {knox_count} users have knox_id assigned")
    except Exception as e:
        print(f"[ERROR] Failed to check knox_id: {e}")

    conn.commit()
    cur.close()
    conn.close()

    print("\n[COMPLETE] emp_id removal completed!")
    print("[INFO] Now using:")
    print("  - login_id as primary key for all permission tables")
    print("  - knox_id as SSO identifier")

    return True

if __name__ == "__main__":
    print("="*60)
    print("Removing emp_id and Setting up Knox ID")
    print("="*60)
    remove_empid_and_setup_knox()