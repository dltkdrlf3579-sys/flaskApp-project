#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
user_menu_roles 테이블 생성 스크립트
menu_role_api.py에서 필요한 테이블 생성
"""
import psycopg2
from psycopg2.extras import RealDictCursor

# PostgreSQL 연결
conn = psycopg2.connect(
    host="localhost",
    database="portal_dev",
    user="postgres",
    password="admin123",
    port=5432
)
cursor = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("user_menu_roles 테이블 생성")
print("=" * 80)

try:
    # 1. 기존 테이블 확인
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = 'user_menu_roles'
        )
    """)
    exists = cursor.fetchone()

    if exists['exists']:
        print("user_menu_roles 테이블이 이미 존재합니다.")
        print("기존 테이블을 삭제하시겠습니까? (y/n): ", end="")
        response = input().lower()
        if response == 'y':
            cursor.execute("DROP TABLE IF EXISTS user_menu_roles CASCADE")
            print("기존 테이블을 삭제했습니다.")
        else:
            print("작업을 중단합니다.")
            conn.close()
            exit()

    # 2. user_menu_roles 테이블 생성
    print("\n테이블 생성 중...")
    cursor.execute("""
        CREATE TABLE user_menu_roles (
            id SERIAL PRIMARY KEY,
            emp_id VARCHAR(50) NOT NULL,
            menu_code VARCHAR(100) NOT NULL,
            role_for_menu VARCHAR(50) NOT NULL,
            is_active BOOLEAN DEFAULT true,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by VARCHAR(50),
            updated_at TIMESTAMP,
            updated_by VARCHAR(50),
            UNIQUE(emp_id, menu_code)
        )
    """)

    print("테이블이 생성되었습니다.")

    # 3. 인덱스 생성
    print("\n인덱스 생성 중...")
    cursor.execute("""
        CREATE INDEX idx_user_menu_roles_emp_id ON user_menu_roles(emp_id);
    """)
    cursor.execute("""
        CREATE INDEX idx_user_menu_roles_menu_code ON user_menu_roles(menu_code);
    """)
    cursor.execute("""
        CREATE INDEX idx_user_menu_roles_active ON user_menu_roles(is_active);
    """)

    print("인덱스가 생성되었습니다.")

    # 4. 초기 데이터 삽입 (기존 user_role_mapping 기반)
    print("\n초기 데이터 생성 중...")

    # 기존 user_role_mapping에서 super_admin 사용자 확인
    cursor.execute("""
        SELECT DISTINCT emp_id, role_code
        FROM user_role_mapping
        WHERE role_code = 'super_admin'
    """)
    super_admins = cursor.fetchall()

    menus = ['accident', 'safety_instruction', 'follow_sop', 'full_process', 'partners', 'change_request']

    for admin in super_admins:
        for menu in menus:
            cursor.execute("""
                INSERT INTO user_menu_roles (emp_id, menu_code, role_for_menu, is_active, created_by, created_at)
                VALUES (%s, %s, 'admin', true, 'SYSTEM', CURRENT_TIMESTAMP)
                ON CONFLICT (emp_id, menu_code) DO NOTHING
            """, (admin['emp_id'], menu))

    print(f"super_admin 사용자 {len(super_admins)}명에 대한 메뉴 권한이 설정되었습니다.")

    # 5. 일반 사용자를 위한 기본 권한 설정
    cursor.execute("""
        SELECT DISTINCT emp_id
        FROM system_users
        WHERE is_active = true
          AND emp_id NOT IN (SELECT emp_id FROM user_role_mapping WHERE role_code = 'super_admin')
        LIMIT 5
    """)
    users = cursor.fetchall()

    for user in users:
        # 기본적으로 일부 메뉴에 viewer 권한 부여
        for menu in ['accident', 'safety_instruction']:
            cursor.execute("""
                INSERT INTO user_menu_roles (emp_id, menu_code, role_for_menu, is_active, created_by, created_at)
                VALUES (%s, %s, 'viewer', true, 'SYSTEM', CURRENT_TIMESTAMP)
                ON CONFLICT (emp_id, menu_code) DO NOTHING
            """, (user['emp_id'], menu))

    print(f"일반 사용자 {len(users)}명에 대한 기본 권한이 설정되었습니다.")

    # 6. 결과 확인
    print("\n생성된 데이터 확인:")
    print("-" * 60)

    cursor.execute("""
        SELECT
            role_for_menu,
            COUNT(DISTINCT emp_id) as user_count,
            COUNT(DISTINCT menu_code) as menu_count
        FROM user_menu_roles
        WHERE is_active = true
        GROUP BY role_for_menu
    """)

    stats = cursor.fetchall()
    for stat in stats:
        print(f"역할: {stat['role_for_menu']:10} | 사용자: {stat['user_count']:3}명 | 메뉴: {stat['menu_count']:2}개")

    # 7. 샘플 데이터 출력
    print("\n샘플 데이터 (상위 5개):")
    print("-" * 60)
    cursor.execute("""
        SELECT emp_id, menu_code, role_for_menu
        FROM user_menu_roles
        WHERE is_active = true
        ORDER BY emp_id, menu_code
        LIMIT 5
    """)

    samples = cursor.fetchall()
    for sample in samples:
        print(f"  {sample['emp_id']:15} | {sample['menu_code']:20} | {sample['role_for_menu']}")

    # 트랜잭션 커밋
    conn.commit()
    print("\n" + "=" * 80)
    print("user_menu_roles 테이블이 성공적으로 생성되었습니다!")
    print("=" * 80)

except Exception as e:
    conn.rollback()
    print(f"\n오류 발생: {e}")
    print("트랜잭션이 롤백되었습니다.")

finally:
    cursor.close()
    conn.close()