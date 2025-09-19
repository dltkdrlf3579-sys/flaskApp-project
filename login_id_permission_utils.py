#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
login_id 기반 권한 관리 유틸리티
emp_id 대신 login_id를 primary identifier로 사용
"""

from flask import session
from db_connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

def get_current_login_id():
    """현재 세션에서 login_id 가져오기"""
    # session['user_id']에는 SSO 로그인 시 login_id가 저장됨
    return session.get('user_id')

def get_emp_id_from_login_id(login_id):
    """login_id로 emp_id 조회 (legacy 시스템 호환용)"""
    if not login_id:
        return None

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT emp_id
            FROM system_users
            WHERE login_id = %s AND is_active = true
        """, (login_id,))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return result[0] if result else None
    except Exception as e:
        logger.error(f"Error getting emp_id from login_id: {e}")
        return None

def check_delete_permission_by_login(login_id, menu_code):
    """login_id 기반 삭제 권한 체크"""
    if not login_id:
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 1. user_menu_permissions에서 직접 권한 확인 (login_id 사용)
        cursor.execute("""
            SELECT can_delete
            FROM user_menu_permissions
            WHERE login_id = %s
                AND menu_code = %s
                AND is_active = true
            LIMIT 1
        """, (login_id, menu_code))

        result = cursor.fetchone()
        if result and result[0]:
            cursor.close()
            conn.close()
            return True

        # 2. user_menu_roles에서 역할 기반 권한 확인 (login_id 사용)
        cursor.execute("""
            SELECT role_for_menu
            FROM user_menu_roles
            WHERE login_id = %s
                AND menu_code = %s
                AND is_active = true
            LIMIT 1
        """, (login_id, menu_code))

        result = cursor.fetchone()
        if result:
            role = result[0]
            # admin, super_admin은 삭제 권한 있음
            if role in ('admin', 'super_admin'):
                cursor.close()
                conn.close()
                return True

        # 3. 역할 기반 권한 확인 (login_id 사용)
        cursor.execute("""
            SELECT rmp.can_delete
            FROM user_role_mapping urm
            JOIN role_menu_permissions rmp
                ON urm.role_code = rmp.role_code
            WHERE urm.login_id = %s
                AND rmp.menu_code = %s
                AND urm.is_active = true
                AND rmp.is_active = true
            ORDER BY rmp.can_delete DESC
            LIMIT 1
        """, (login_id, menu_code))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return result[0] if result else False

    except Exception as e:
        logger.error(f"Error checking delete permission: {e}")
        return False

def check_permission_by_login(login_id, menu_code, action='view'):
    """login_id 기반 일반 권한 체크"""
    if not login_id:
        return False

    action_column = {
        'view': 'can_view',
        'create': 'can_create',
        'edit': 'can_edit',
        'delete': 'can_delete'
    }.get(action, 'can_view')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # PostgreSQL 함수 사용 (이미 생성된 경우)
        cursor.execute("""
            SELECT check_user_permission_by_login(%s, %s, %s)
        """, (login_id, menu_code, action))

        result = cursor.fetchone()
        if result:
            cursor.close()
            conn.close()
            return result[0]

        # 함수가 없으면 직접 쿼리
        cursor.execute(f"""
            SELECT {action_column}
            FROM user_menu_permissions
            WHERE login_id = %s
                AND menu_code = %s
                AND is_active = true
            LIMIT 1
        """, (login_id, menu_code))

        result = cursor.fetchone()
        cursor.close()
        conn.close()

        return result[0] if result else False

    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        return False

def grant_permission_by_login(login_id, menu_code, permissions):
    """login_id 기반으로 권한 부여"""
    if not login_id:
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # emp_id도 함께 저장 (호환성 유지)
        emp_id = get_emp_id_from_login_id(login_id)

        cursor.execute("""
            INSERT INTO user_menu_permissions
            (login_id, emp_id, menu_code, can_view, can_create, can_edit, can_delete, granted_by, granted_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (emp_id, menu_code)
            DO UPDATE SET
                login_id = EXCLUDED.login_id,
                can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                updated_at = CURRENT_TIMESTAMP
        """, (
            login_id,
            emp_id,
            menu_code,
            permissions.get('can_view', False),
            permissions.get('can_create', False),
            permissions.get('can_edit', False),
            permissions.get('can_delete', False),
            get_current_login_id()
        ))

        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Granted permissions to {login_id} for menu {menu_code}")
        return True

    except Exception as e:
        logger.error(f"Error granting permission: {e}")
        return False

def revoke_permission_by_login(login_id, menu_code):
    """login_id 기반으로 권한 회수"""
    if not login_id:
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE user_menu_permissions
            SET is_active = false,
                updated_at = CURRENT_TIMESTAMP
            WHERE login_id = %s
                AND menu_code = %s
        """, (login_id, menu_code))

        affected = cursor.rowcount
        conn.commit()
        cursor.close()
        conn.close()

        logger.info(f"Revoked permissions from {login_id} for menu {menu_code}")
        return affected > 0

    except Exception as e:
        logger.error(f"Error revoking permission: {e}")
        return False

# 삭제 권한 체크를 위한 헬퍼 함수 (가장 많이 사용될 것으로 예상)
def can_delete(menu_code):
    """현재 사용자의 삭제 권한 체크 (간편 함수)"""
    login_id = get_current_login_id()
    if not login_id:
        return False
    return check_delete_permission_by_login(login_id, menu_code)

def can_edit(menu_code):
    """현재 사용자의 편집 권한 체크 (간편 함수)"""
    login_id = get_current_login_id()
    if not login_id:
        return False
    return check_permission_by_login(login_id, menu_code, 'edit')

def can_create(menu_code):
    """현재 사용자의 생성 권한 체크 (간편 함수)"""
    login_id = get_current_login_id()
    if not login_id:
        return False
    return check_permission_by_login(login_id, menu_code, 'create')

def can_view(menu_code):
    """현재 사용자의 조회 권한 체크 (간편 함수)"""
    login_id = get_current_login_id()
    if not login_id:
        return False
    return check_permission_by_login(login_id, menu_code, 'view')