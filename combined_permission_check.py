#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 권한 체크 시스템
부서 권한과 개인 권한을 OR 연산으로 처리
더 높은 권한이 적용됨
"""

from flask import session
from db_connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

def get_max_permission(login_id, dept_id, menu_code, action='view'):
    """
    개인 권한과 부서 권한 중 더 높은 권한 반환

    권한 우선순위:
    1. delete (최고)
    2. edit
    3. create
    4. view
    5. none (최저)
    """
    if not login_id or not dept_id:
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

        # 1. 개인 권한 확인
        cursor.execute(f"""
            SELECT can_view, can_create, can_edit, can_delete
            FROM user_menu_permissions
            WHERE login_id = %s
                AND menu_code = %s
                AND is_active = true
            LIMIT 1
        """, (login_id, menu_code))

        personal_perms = cursor.fetchone()

        # 2. 부서 권한 확인 (dept_id 사용)
        cursor.execute(f"""
            SELECT can_view, can_create, can_edit, can_delete
            FROM dept_menu_roles
            WHERE dept_id = %s
                AND menu_code = %s
                AND is_active = true
            LIMIT 1
        """, (dept_id, menu_code))

        dept_perms = cursor.fetchone()

        cursor.close()
        conn.close()

        # 3. OR 연산으로 최대 권한 계산
        has_permission = False

        # 개인 권한 체크
        if personal_perms:
            if action == 'view' and personal_perms[0]:
                has_permission = True
            elif action == 'create' and personal_perms[1]:
                has_permission = True
            elif action == 'edit' and personal_perms[2]:
                has_permission = True
            elif action == 'delete' and personal_perms[3]:
                has_permission = True

        # 부서 권한 체크 (OR 연산)
        if dept_perms and not has_permission:
            if action == 'view' and dept_perms[0]:
                has_permission = True
            elif action == 'create' and dept_perms[1]:
                has_permission = True
            elif action == 'edit' and dept_perms[2]:
                has_permission = True
            elif action == 'delete' and dept_perms[3]:
                has_permission = True

        # 더 높은 권한이 있는지 추가 체크 (예: view만 요청했지만 edit 권한이 있는 경우)
        if action == 'view' and not has_permission:
            # 개인이나 부서에 더 높은 권한(create/edit/delete)이 있으면 view도 가능
            if personal_perms and (personal_perms[1] or personal_perms[2] or personal_perms[3]):
                has_permission = True
            elif dept_perms and (dept_perms[1] or dept_perms[2] or dept_perms[3]):
                has_permission = True

        return has_permission

    except Exception as e:
        logger.error(f"Error checking combined permission: {e}")
        return False

def get_user_all_permissions(login_id, dept_id):
    """
    사용자의 모든 메뉴에 대한 통합 권한 조회
    """
    if not login_id or not dept_id:
        return {}

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 모든 메뉴 목록
        cursor.execute("""
            SELECT DISTINCT menu_code
            FROM (
                SELECT menu_code FROM user_menu_permissions WHERE login_id = %s AND is_active = true
                UNION
                SELECT menu_code FROM dept_menu_roles WHERE dept_id = %s AND is_active = true
            ) as menus
        """, (login_id, dept_id))

        menu_codes = [row[0] for row in cursor.fetchall()]

        permissions = {}
        for menu_code in menu_codes:
            # 개인 권한
            cursor.execute("""
                SELECT can_view, can_create, can_edit, can_delete
                FROM user_menu_permissions
                WHERE login_id = %s AND menu_code = %s AND is_active = true
            """, (login_id, menu_code))
            personal = cursor.fetchone()

            # 부서 권한
            cursor.execute("""
                SELECT can_view, can_create, can_edit, can_delete
                FROM dept_menu_roles
                WHERE dept_id = %s AND menu_code = %s AND is_active = true
            """, (dept_id, menu_code))
            dept = cursor.fetchone()

            # OR 연산으로 통합
            permissions[menu_code] = {
                'can_view': (personal and personal[0]) or (dept and dept[0]) or False,
                'can_create': (personal and personal[1]) or (dept and dept[1]) or False,
                'can_edit': (personal and personal[2]) or (dept and dept[2]) or False,
                'can_delete': (personal and personal[3]) or (dept and dept[3]) or False
            }

        cursor.close()
        conn.close()

        return permissions

    except Exception as e:
        logger.error(f"Error getting all permissions: {e}")
        return {}

def check_current_user_permission(menu_code, action='view'):
    """
    현재 세션 사용자의 권한 체크 (SSO 인증 기반)
    """
    login_id = session.get('user_id')  # Knox ID
    dept_id = session.get('deptid')    # SSO dept_id

    if not login_id or not dept_id:
        logger.warning(f"Missing session data: login_id={login_id}, dept_id={dept_id}")
        return False

    return get_max_permission(login_id, dept_id, menu_code, action)

# 간편 함수들
def can_view(menu_code):
    """현재 사용자의 조회 권한 체크"""
    return check_current_user_permission(menu_code, 'view')

def can_create(menu_code):
    """현재 사용자의 생성 권한 체크"""
    return check_current_user_permission(menu_code, 'create')

def can_edit(menu_code):
    """현재 사용자의 편집 권한 체크"""
    return check_current_user_permission(menu_code, 'edit')

def can_delete(menu_code):
    """현재 사용자의 삭제 권한 체크"""
    return check_current_user_permission(menu_code, 'delete')