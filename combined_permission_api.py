#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 권한 조회 API
"""

from flask import Blueprint, jsonify, request, session
from combined_permission_check import (
    get_max_permission,
    get_user_all_permissions,
    check_current_user_permission
)
from db_connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

combined_permission_api_bp = Blueprint('combined_permission_api', __name__, url_prefix='/api/combined-permissions')

@combined_permission_api_bp.route('/check', methods=['GET'])
def check_permission():
    """
    현재 사용자의 특정 메뉴 권한 체크
    Query params: menu_code, action (view/create/edit/delete)
    """
    menu_code = request.args.get('menu_code')
    action = request.args.get('action', 'view')

    if not menu_code:
        return jsonify({'error': 'menu_code is required'}), 400

    has_permission = check_current_user_permission(menu_code, action)

    return jsonify({
        'menu_code': menu_code,
        'action': action,
        'has_permission': has_permission,
        'user_id': session.get('user_id'),
        'dept_id': session.get('deptid')
    })

@combined_permission_api_bp.route('/all', methods=['GET'])
def get_all_permissions():
    """
    현재 사용자의 모든 메뉴 권한 조회
    """
    login_id = session.get('user_id')
    dept_id = session.get('deptid')

    if not login_id or not dept_id:
        return jsonify({'error': 'Authentication required'}), 401

    permissions = get_user_all_permissions(login_id, dept_id)

    return jsonify({
        'user_id': login_id,
        'dept_id': dept_id,
        'permissions': permissions
    })

@combined_permission_api_bp.route('/check-specific', methods=['POST'])
def check_specific_permission():
    """
    특정 사용자의 권한 체크 (관리자용)
    Body: login_id, dept_id, menu_code, action
    """
    data = request.json
    login_id = data.get('login_id')
    dept_id = data.get('dept_id')
    menu_code = data.get('menu_code')
    action = data.get('action', 'view')

    if not all([login_id, dept_id, menu_code]):
        return jsonify({'error': 'login_id, dept_id, and menu_code are required'}), 400

    has_permission = get_max_permission(login_id, dept_id, menu_code, action)

    # 개인 권한과 부서 권한 각각 조회
    conn = get_db_connection()
    cursor = conn.cursor()

    # 개인 권한
    cursor.execute(f"""
        SELECT can_view, can_create, can_edit, can_delete
        FROM user_menu_permissions
        WHERE login_id = %s AND menu_code = %s AND is_active = true
    """, (login_id, menu_code))
    personal = cursor.fetchone()

    # 부서 권한
    cursor.execute(f"""
        SELECT can_view, can_create, can_edit, can_delete
        FROM dept_menu_roles
        WHERE dept_id = %s AND menu_code = %s AND is_active = true
    """, (dept_id, menu_code))
    dept = cursor.fetchone()

    cursor.close()
    conn.close()

    return jsonify({
        'login_id': login_id,
        'dept_id': dept_id,
        'menu_code': menu_code,
        'action': action,
        'has_permission': has_permission,
        'personal_permissions': {
            'can_view': personal[0] if personal else False,
            'can_create': personal[1] if personal else False,
            'can_edit': personal[2] if personal else False,
            'can_delete': personal[3] if personal else False
        } if personal else None,
        'dept_permissions': {
            'can_view': dept[0] if dept else False,
            'can_create': dept[1] if dept else False,
            'can_edit': dept[2] if dept else False,
            'can_delete': dept[3] if dept else False
        } if dept else None,
        'combined_result': 'Personal OR Department (higher permission wins)'
    })

@combined_permission_api_bp.route('/test', methods=['GET'])
def test_permission():
    """
    권한 테스트 엔드포인트
    """
    login_id = session.get('user_id', 'test_user')
    dept_id = session.get('deptid', 'D001')

    # 테스트 시나리오
    test_cases = [
        {'menu': 'accident', 'action': 'view', 'expected': 'Should be TRUE if either personal or dept has view'},
        {'menu': 'accident', 'action': 'edit', 'expected': 'Should be TRUE if either personal or dept has edit'},
        {'menu': 'accident', 'action': 'delete', 'expected': 'Should be TRUE if either personal or dept has delete'}
    ]

    results = []
    for case in test_cases:
        has_perm = get_max_permission(login_id, dept_id, case['menu'], case['action'])
        results.append({
            'menu': case['menu'],
            'action': case['action'],
            'has_permission': has_perm,
            'expected': case['expected']
        })

    return jsonify({
        'login_id': login_id,
        'dept_id': dept_id,
        'test_results': results
    })