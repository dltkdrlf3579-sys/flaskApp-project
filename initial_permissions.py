#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 7: 초기 권한 데이터 설정
기본 역할, 테스트 사용자, 초기 권한 설정
"""

import psycopg2
from datetime import datetime
import logging
import hashlib

logging.basicConfig(level=logging.INFO, format='%(message)s')
logger = logging.getLogger(__name__)

def get_db_connection():
    """데이터베이스 연결"""
    return psycopg2.connect(
        host='localhost',
        database='portal_db',
        user='postgres',
        password='postgres'
    )

def setup_initial_roles():
    """기본 역할 설정"""
    logger.info("\n1. Setting up initial roles...")

    roles = [
        ('super_admin', '최고 관리자', 'SUPER_ADMIN', '모든 권한을 가진 최고 관리자', 100, True),
        ('admin', '관리자', 'ADMIN', '시스템 관리 권한', 80, True),
        ('manager', '매니저', 'MANAGER', '승인 및 관리 권한', 60, True),
        ('user', '일반 사용자', 'USER', '기본 사용 권한', 40, True),
        ('viewer', '읽기 전용', 'VIEWER', '조회만 가능', 20, True),
        ('partner', '협력사', 'PARTNER', '협력사 사용자', 30, False)
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for role_id, role_name, role_code, desc, priority, is_system in roles:
            cursor.execute("""
                INSERT INTO system_roles
                (role_id, role_name, role_code, description, priority, is_system, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT (role_id) DO UPDATE
                SET role_name = EXCLUDED.role_name,
                    role_code = EXCLUDED.role_code,
                    description = EXCLUDED.description,
                    priority = EXCLUDED.priority
            """, (role_id, role_name, role_code, desc, priority, is_system))

            logger.info(f"  ✓ Role created/updated: {role_id} ({role_name})")

        conn.commit()
        logger.info("  ✓ All roles configured")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error setting up roles: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()

def create_test_users():
    """테스트 사용자 생성"""
    logger.info("\n2. Creating test users...")

    # 간단한 비밀번호 해싱 (실제로는 더 안전한 방법 사용)
    def hash_password(password):
        return hashlib.sha256(password.encode()).hexdigest()

    test_users = [
        ('ADMIN001', '관리자1', 'admin1@company.com', 'super_admin', '정보시스템팀', hash_password('admin123')),
        ('ADMIN002', '관리자2', 'admin2@company.com', 'admin', '정보시스템팀', hash_password('admin123')),
        ('MGR001', '매니저1', 'manager1@company.com', 'manager', '안전관리팀', hash_password('mgr123')),
        ('MGR002', '매니저2', 'manager2@company.com', 'manager', '시설관리팀', hash_password('mgr123')),
        ('USER001', '사용자1', 'user1@company.com', 'user', '생산1팀', hash_password('user123')),
        ('USER002', '사용자2', 'user2@company.com', 'user', '생산2팀', hash_password('user123')),
        ('VIEW001', '조회자1', 'viewer1@company.com', 'viewer', '품질관리팀', hash_password('view123')),
        ('PARTNER001', '협력사1', 'partner1@partner.com', 'partner', '외부협력사', hash_password('partner123'))
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        for emp_id, name, email, role, dept, password in test_users:
            # system_users 테이블에 사용자 추가
            cursor.execute("""
                INSERT INTO system_users
                (emp_id, emp_name, email, role, department, password_hash, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, true, NOW())
                ON CONFLICT (emp_id) DO UPDATE
                SET emp_name = EXCLUDED.emp_name,
                    email = EXCLUDED.email,
                    role = EXCLUDED.role,
                    department = EXCLUDED.department,
                    is_active = true
            """, (emp_id, name, email, role, dept, password))

            # user_role_mapping 테이블에 역할 매핑
            cursor.execute("""
                INSERT INTO user_role_mapping
                (emp_id, role_id, is_active, assigned_at, assigned_by)
                VALUES (%s, %s, true, NOW(), 'SYSTEM')
                ON CONFLICT (emp_id, role_id) DO UPDATE
                SET is_active = true,
                    assigned_at = NOW()
            """, (emp_id, role))

            logger.info(f"  ✓ User created: {emp_id} ({name}) - Role: {role}")

        conn.commit()
        logger.info("  ✓ All test users created")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error creating users: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()

def assign_initial_permissions():
    """초기 권한 할당"""
    logger.info("\n3. Assigning initial permissions...")

    # 메뉴별 역할 권한 매핑
    menu_permissions = [
        # menu_code, role, view, create, edit, delete
        # 관리자 메뉴
        ('admin', 'super_admin', True, True, True, True),
        ('admin', 'admin', True, True, True, False),

        # 사고 관리
        ('accident', 'super_admin', True, True, True, True),
        ('accident', 'admin', True, True, True, True),
        ('accident', 'manager', True, True, True, False),
        ('accident', 'user', True, True, False, False),
        ('accident', 'viewer', True, False, False, False),

        # 안전 관리
        ('safety', 'super_admin', True, True, True, True),
        ('safety', 'admin', True, True, True, True),
        ('safety', 'manager', True, True, True, False),
        ('safety', 'user', True, False, False, False),
        ('safety', 'viewer', True, False, False, False),

        # 변경 요청
        ('change-request', 'super_admin', True, True, True, True),
        ('change-request', 'admin', True, True, True, True),
        ('change-request', 'manager', True, True, True, False),
        ('change-request', 'user', True, True, False, False),
        ('change-request', 'partner', True, True, False, False),

        # 협력사 관리
        ('partner', 'super_admin', True, True, True, True),
        ('partner', 'admin', True, True, True, True),
        ('partner', 'manager', True, True, True, False),
        ('partner', 'partner', True, False, True, False),

        # 마스터 데이터
        ('masterdata', 'super_admin', True, True, True, True),
        ('masterdata', 'admin', True, True, True, False),

        # 보고서
        ('reports', 'super_admin', True, True, True, True),
        ('reports', 'admin', True, True, True, False),
        ('reports', 'manager', True, True, False, False),
        ('reports', 'user', True, False, False, False),
        ('reports', 'viewer', True, False, False, False),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 먼저 역할별 사용자 조회
        cursor.execute("""
            SELECT DISTINCT emp_id, role
            FROM system_users
            WHERE is_active = true
        """)
        users = cursor.fetchall()

        permission_count = 0
        for emp_id, user_role in users:
            for menu_code, role, view, create, edit, delete in menu_permissions:
                if user_role == role:
                    cursor.execute("""
                        INSERT INTO user_menu_permissions
                        (emp_id, menu_code, can_view, can_create, can_edit, can_delete,
                         created_at, created_by)
                        VALUES (%s, %s, %s, %s, %s, %s, NOW(), 'SYSTEM')
                        ON CONFLICT (emp_id, menu_code) DO UPDATE
                        SET can_view = EXCLUDED.can_view,
                            can_create = EXCLUDED.can_create,
                            can_edit = EXCLUDED.can_edit,
                            can_delete = EXCLUDED.can_delete
                    """, (emp_id, menu_code, view, create, edit, delete))
                    permission_count += 1

        conn.commit()
        logger.info(f"  ✓ {permission_count} permissions assigned")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error assigning permissions: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()

def create_menu_structure():
    """메뉴 구조 생성 (menu_permissions 테이블용)"""
    logger.info("\n4. Creating menu structure...")

    menus = [
        ('admin', '관리자', '/admin', 1, True),
        ('accident', '사고 관리', '/accident', 2, True),
        ('safety', '안전 관리', '/safety', 3, True),
        ('change-request', '변경 요청', '/change-request', 4, True),
        ('partner', '협력사 관리', '/partner', 5, True),
        ('masterdata', '마스터 데이터', '/masterdata', 6, True),
        ('reports', '보고서', '/reports', 7, True),
        ('monitoring', '모니터링', '/monitoring', 8, True),
    ]

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # menu_permissions 테이블이 있는지 확인
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_permissions (
                menu_code VARCHAR(50) PRIMARY KEY,
                menu_name VARCHAR(100) NOT NULL,
                menu_url VARCHAR(200),
                menu_order INTEGER,
                is_active BOOLEAN DEFAULT true,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        for menu_code, menu_name, menu_url, menu_order, is_active in menus:
            cursor.execute("""
                INSERT INTO menu_permissions
                (menu_code, menu_name, menu_url, menu_order, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (menu_code) DO UPDATE
                SET menu_name = EXCLUDED.menu_name,
                    menu_url = EXCLUDED.menu_url,
                    menu_order = EXCLUDED.menu_order,
                    is_active = EXCLUDED.is_active
            """, (menu_code, menu_name, menu_url, menu_order, is_active))

            logger.info(f"  ✓ Menu created: {menu_code} ({menu_name})")

        conn.commit()
        logger.info("  ✓ Menu structure created")
        return True

    except Exception as e:
        logger.error(f"  ✗ Error creating menu structure: {e}")
        conn.rollback()
        return False

    finally:
        cursor.close()
        conn.close()

def verify_setup():
    """설정 검증"""
    logger.info("\n5. Verifying setup...")

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 역할 수 확인
        cursor.execute("SELECT COUNT(*) FROM system_roles")
        role_count = cursor.fetchone()[0]
        logger.info(f"  • Roles: {role_count}")

        # 사용자 수 확인
        cursor.execute("SELECT COUNT(*) FROM system_users WHERE is_active = true")
        user_count = cursor.fetchone()[0]
        logger.info(f"  • Active users: {user_count}")

        # 권한 수 확인
        cursor.execute("SELECT COUNT(*) FROM user_menu_permissions")
        permission_count = cursor.fetchone()[0]
        logger.info(f"  • Permissions: {permission_count}")

        # 각 역할별 사용자 수
        cursor.execute("""
            SELECT role, COUNT(*) as count
            FROM system_users
            WHERE is_active = true
            GROUP BY role
            ORDER BY role
        """)

        logger.info("\n  Role Distribution:")
        for role, count in cursor.fetchall():
            logger.info(f"    • {role}: {count} users")

        logger.info("\n  ✓ Setup verification complete")
        return True

    except Exception as e:
        logger.error(f"  ✗ Verification failed: {e}")
        return False

    finally:
        cursor.close()
        conn.close()

def print_test_credentials():
    """테스트 계정 정보 출력"""
    print("\n" + "="*60)
    print("TEST USER CREDENTIALS")
    print("="*60)
    print("\nSuper Admin:")
    print("  ID: ADMIN001  |  Password: admin123")
    print("\nAdmin:")
    print("  ID: ADMIN002  |  Password: admin123")
    print("\nManager:")
    print("  ID: MGR001    |  Password: mgr123")
    print("  ID: MGR002    |  Password: mgr123")
    print("\nUser:")
    print("  ID: USER001   |  Password: user123")
    print("  ID: USER002   |  Password: user123")
    print("\nViewer:")
    print("  ID: VIEW001   |  Password: view123")
    print("\nPartner:")
    print("  ID: PARTNER001 | Password: partner123")
    print("="*60)

def main():
    """메인 실행 함수"""
    print("\n" + "="*60)
    print("INITIAL PERMISSION SETUP")
    print("="*60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    steps = [
        ("Setting up roles", setup_initial_roles),
        ("Creating test users", create_test_users),
        ("Assigning permissions", assign_initial_permissions),
        ("Creating menu structure", create_menu_structure),
        ("Verifying setup", verify_setup)
    ]

    success = True
    for step_name, step_func in steps:
        if not step_func():
            logger.error(f"\n✗ Failed at: {step_name}")
            success = False
            break

    if success:
        print("\n" + "="*60)
        print("✅ INITIAL SETUP COMPLETE!")
        print("="*60)
        print_test_credentials()
        print("\n📋 Next Steps:")
        print("1. Restart Flask application")
        print("2. Login with test credentials")
        print("3. Access /admin/dashboard for administration")
        print("4. Test permission controls on protected routes")
    else:
        print("\n" + "="*60)
        print("❌ SETUP FAILED")
        print("="*60)
        print("Please check the error messages above and try again")

    return success

if __name__ == "__main__":
    main()