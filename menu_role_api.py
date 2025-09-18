#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
메뉴별 역할 관리 API
"""

from flask import Blueprint, jsonify, request, session
import psycopg2
from datetime import datetime
from menu_based_permission_system import MenuBasedPermissionSystem
import logging

logger = logging.getLogger(__name__)

menu_role_api_bp = Blueprint('menu_role_api', __name__, url_prefix='/api/menu-roles')

def get_db_connection():
    """데이터베이스 연결"""
    return psycopg2.connect(
        host='localhost',
        database='portal_db',
        user='postgres',
        password='postgres'
    )

@menu_role_api_bp.route('/all', methods=['GET'])
def get_all_user_menu_roles():
    """모든 사용자의 메뉴별 역할 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 사용자 정보 조회
        cursor.execute("""
            SELECT DISTINCT
                u.emp_id,
                u.emp_name,
                u.department,
                u.company
            FROM system_users u
            WHERE u.is_active = true
            ORDER BY u.emp_id
        """)

        users = {}
        for emp_id, emp_name, department, company in cursor.fetchall():
            users[emp_id] = {
                'name': emp_name,
                'department': department,
                'company': company,
                'menu_roles': {}
            }

        # 메뉴별 역할 조회
        cursor.execute("""
            SELECT emp_id, menu_code, role_for_menu
            FROM user_menu_roles
            WHERE is_active = true
        """)

        for emp_id, menu_code, role in cursor.fetchall():
            if emp_id in users:
                users[emp_id]['menu_roles'][menu_code] = role

        # 권한이 설정되지 않은 메뉴는 'none'으로 표시
        menus = ['accident', 'safety', 'follow_sop', 'full_process', 'partner', 'change_request']
        for emp_id in users:
            for menu in menus:
                if menu not in users[emp_id]['menu_roles']:
                    users[emp_id]['menu_roles'][menu] = 'none'

        cursor.close()
        conn.close()

        return jsonify(users)

    except Exception as e:
        logger.error(f"Error getting all menu roles: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/user/<emp_id>', methods=['GET'])
def get_user_menu_roles(emp_id):
    """특정 사용자의 메뉴별 역할 조회"""
    try:
        perm_system = MenuBasedPermissionSystem()
        roles = perm_system.get_user_all_menu_roles(emp_id)

        # 권한이 없는 메뉴는 'none'으로 표시
        menus = ['accident', 'safety', 'follow_sop', 'full_process', 'partner', 'change_request']
        for menu in menus:
            if menu not in roles:
                roles[menu] = 'none'

        return jsonify({
            'emp_id': emp_id,
            'menu_roles': roles
        })

    except Exception as e:
        logger.error(f"Error getting user menu roles: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/set', methods=['POST'])
def set_user_menu_role():
    """사용자의 특정 메뉴 역할 설정"""
    try:
        data = request.json
        emp_id = data.get('emp_id')
        menu_code = data.get('menu_code')
        role = data.get('role')

        if not all([emp_id, menu_code, role]):
            return jsonify({'error': 'Missing parameters'}), 400

        perm_system = MenuBasedPermissionSystem()
        success = perm_system.set_user_menu_role(emp_id, menu_code, role)

        if success:
            return jsonify({
                'success': True,
                'message': f'Set {emp_id} as {role} for menu {menu_code}'
            })
        else:
            return jsonify({'error': 'Failed to set role'}), 500

    except Exception as e:
        logger.error(f"Error setting menu role: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/batch-update', methods=['POST'])
def batch_update_menu_roles():
    """여러 메뉴 역할 일괄 업데이트"""
    try:
        data = request.json
        changes = data.get('changes', [])
        updated_by = session.get('emp_id', 'SYSTEM')

        conn = get_db_connection()
        cursor = conn.cursor()

        update_count = 0
        for change in changes:
            emp_id = change.get('emp_id')
            menu_code = change.get('menu_code')
            role = change.get('role')

            if role == 'none':
                # 'none'인 경우 권한 삭제
                cursor.execute("""
                    UPDATE user_menu_roles
                    SET is_active = false, updated_at = NOW(), updated_by = %s
                    WHERE emp_id = %s AND menu_code = %s
                """, (updated_by, emp_id, menu_code))
            else:
                # 권한 설정 또는 업데이트
                cursor.execute("""
                    INSERT INTO user_menu_roles
                    (emp_id, menu_code, role_for_menu, is_active, created_at, created_by)
                    VALUES (%s, %s, %s, true, NOW(), %s)
                    ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                        role_for_menu = EXCLUDED.role_for_menu,
                        is_active = true,
                        updated_at = NOW(),
                        updated_by = %s
                """, (emp_id, menu_code, role, updated_by, updated_by))

            update_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Updated {update_count} menu roles',
            'count': update_count
        })

    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/check-permission', methods=['POST'])
def check_permission():
    """권한 체크 API"""
    try:
        data = request.json
        emp_id = data.get('emp_id', session.get('emp_id'))
        menu_code = data.get('menu_code')
        action = data.get('action')
        target_data = data.get('target_data', {})

        if not all([emp_id, menu_code, action]):
            return jsonify({'error': 'Missing parameters'}), 400

        perm_system = MenuBasedPermissionSystem()
        has_permission = perm_system.check_permission(emp_id, menu_code, action, target_data)

        # 역할도 함께 반환
        menu_role = perm_system.get_user_menu_role(emp_id, menu_code)

        return jsonify({
            'emp_id': emp_id,
            'menu_code': menu_code,
            'action': action,
            'has_permission': has_permission,
            'menu_role': menu_role
        })

    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/data-filter/<menu_code>', methods=['GET'])
def get_data_filter(menu_code):
    """메뉴별 데이터 필터 조건 조회"""
    try:
        emp_id = session.get('emp_id')
        if not emp_id:
            return jsonify({'error': 'Not authenticated'}), 401

        perm_system = MenuBasedPermissionSystem()
        filter_conditions = perm_system.build_data_filter(emp_id, menu_code)

        return jsonify({
            'emp_id': emp_id,
            'menu_code': menu_code,
            'filter': filter_conditions
        })

    except Exception as e:
        logger.error(f"Error getting data filter: {e}")
        return jsonify({'error': str(e)}), 500

@menu_role_api_bp.route('/copy-roles', methods=['POST'])
def copy_user_roles():
    """한 사용자의 메뉴 역할을 다른 사용자에게 복사"""
    try:
        data = request.json
        source_emp_id = data.get('source_emp_id')
        target_emp_ids = data.get('target_emp_ids', [])
        updated_by = session.get('emp_id', 'SYSTEM')

        if not source_emp_id or not target_emp_ids:
            return jsonify({'error': 'Invalid parameters'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 소스 사용자의 메뉴 역할 조회
        cursor.execute("""
            SELECT menu_code, role_for_menu
            FROM user_menu_roles
            WHERE emp_id = %s AND is_active = true
        """, (source_emp_id,))

        source_roles = cursor.fetchall()

        # 타겟 사용자들에게 복사
        copy_count = 0
        for target_emp_id in target_emp_ids:
            for menu_code, role in source_roles:
                cursor.execute("""
                    INSERT INTO user_menu_roles
                    (emp_id, menu_code, role_for_menu, is_active, created_at, created_by)
                    VALUES (%s, %s, %s, true, NOW(), %s)
                    ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                        role_for_menu = EXCLUDED.role_for_menu,
                        is_active = true,
                        updated_at = NOW(),
                        updated_by = %s
                """, (target_emp_id, menu_code, role, updated_by, updated_by))
                copy_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Copied roles from {source_emp_id} to {len(target_emp_ids)} users',
            'count': copy_count
        })

    except Exception as e:
        logger.error(f"Error copying roles: {e}")
        return jsonify({'error': str(e)}), 500

# Flask app.py에 추가할 코드
"""
# app.py에 추가:

from menu_role_api import menu_role_api_bp
app.register_blueprint(menu_role_api_bp)

# 권한 설정 페이지 라우트 변경
@app.route("/admin/permission-settings")
@require_admin_auth
def admin_permission_settings():
    return render_template('admin/menu_role_management.html', menu=MENU_CONFIG)
"""