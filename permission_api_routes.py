#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 관리 API 라우트
사용자별 메뉴별 세밀한 CRUD 권한 관리
"""

from flask import Blueprint, jsonify, request, session
import psycopg2
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

# Blueprint 생성
permission_api_bp = Blueprint('permission_api', __name__, url_prefix='/api/permissions')

def get_db_connection():
    """데이터베이스 연결"""
    return psycopg2.connect(
        host='localhost',
        database='portal_db',
        user='postgres',
        password='postgres'
    )

@permission_api_bp.route('/all', methods=['GET'])
def get_all_permissions():
    """모든 사용자의 권한 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 사용자 정보와 권한 조회
        cursor.execute("""
            SELECT
                u.emp_id,
                u.emp_name,
                u.department,
                u.role,
                p.menu_code,
                p.can_create,
                p.can_read,
                p.can_edit,
                p.can_delete
            FROM system_users u
            LEFT JOIN user_menu_permissions p ON u.emp_id = p.emp_id
            WHERE u.is_active = true
            ORDER BY u.emp_id, p.menu_code
        """)

        # 데이터 구조화
        users = {}
        for row in cursor.fetchall():
            emp_id = row[0]
            if emp_id not in users:
                users[emp_id] = {
                    'emp_id': emp_id,
                    'emp_name': row[1],
                    'department': row[2],
                    'role': row[3],
                    'permissions': {}
                }

            if row[4]:  # menu_code가 있는 경우
                menu_code = row[4]
                users[emp_id]['permissions'][menu_code] = {
                    'create': row[5] or False,
                    'read': row[6] or False,
                    'update': row[7] or False,
                    'delete': row[8] or False
                }

        cursor.close()
        conn.close()

        return jsonify(list(users.values()))

    except Exception as e:
        logger.error(f"Error getting all permissions: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/user/<emp_id>', methods=['GET'])
def get_user_permissions(emp_id):
    """특정 사용자의 권한 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                menu_code,
                can_create,
                can_read,
                can_edit,
                can_delete
            FROM user_menu_permissions
            WHERE emp_id = %s
        """, (emp_id,))

        permissions = {}
        for menu_code, create, read, edit, delete in cursor.fetchall():
            permissions[menu_code] = {
                'create': create or False,
                'read': read or False,
                'update': edit or False,
                'delete': delete or False
            }

        cursor.close()
        conn.close()

        return jsonify({'emp_id': emp_id, 'permissions': permissions})

    except Exception as e:
        logger.error(f"Error getting user permissions: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/user/<emp_id>', methods=['POST'])
def update_user_permissions(emp_id):
    """특정 사용자의 권한 업데이트"""
    try:
        data = request.json
        permissions = data.get('permissions', {})
        updated_by = session.get('emp_id', 'SYSTEM')

        conn = get_db_connection()
        cursor = conn.cursor()

        # 각 메뉴별로 권한 업데이트
        for menu_code, perm in permissions.items():
            cursor.execute("""
                INSERT INTO user_menu_permissions
                (emp_id, menu_code, can_view, can_create, can_edit, can_delete,
                 created_at, created_by, updated_at, updated_by)
                VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), %s)
                ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                    can_view = EXCLUDED.can_view,
                    can_create = EXCLUDED.can_create,
                    can_edit = EXCLUDED.can_edit,
                    can_delete = EXCLUDED.can_delete,
                    updated_at = NOW(),
                    updated_by = EXCLUDED.updated_by
            """, (
                emp_id, menu_code,
                perm.get('read', False),  # can_view = read
                perm.get('create', False),
                perm.get('update', False),  # can_edit = update
                perm.get('delete', False),
                updated_by, updated_by
            ))

        conn.commit()
        cursor.close()
        conn.close()

        # 캐시 정리 (선택사항)
        try:
            from simple_cache import get_cache
            cache = get_cache()
            cache.clear_user(emp_id)
        except:
            pass

        return jsonify({'success': True, 'message': f'Permissions updated for {emp_id}'})

    except Exception as e:
        logger.error(f"Error updating user permissions: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/batch', methods=['POST'])
def batch_update_permissions():
    """여러 사용자의 권한 일괄 업데이트"""
    try:
        data = request.json
        users = data.get('users', [])
        updated_by = session.get('emp_id', 'SYSTEM')

        conn = get_db_connection()
        cursor = conn.cursor()

        update_count = 0
        for user_data in users:
            emp_id = user_data.get('emp_id')
            permissions = user_data.get('permissions', {})

            for menu_code, perm in permissions.items():
                cursor.execute("""
                    INSERT INTO user_menu_permissions
                    (emp_id, menu_code, can_view, can_create, can_edit, can_delete,
                     created_at, created_by, updated_at, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), %s)
                    ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                        can_view = EXCLUDED.can_view,
                        can_create = EXCLUDED.can_create,
                        can_edit = EXCLUDED.can_edit,
                        can_delete = EXCLUDED.can_delete,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """, (
                    emp_id, menu_code,
                    perm.get('read', False),
                    perm.get('create', False),
                    perm.get('update', False),
                    perm.get('delete', False),
                    updated_by, updated_by
                ))
                update_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Updated {update_count} permissions',
            'count': update_count
        })

    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/copy', methods=['POST'])
def copy_permissions():
    """한 사용자의 권한을 다른 사용자에게 복사"""
    try:
        data = request.json
        source_emp_id = data.get('source_emp_id')
        target_emp_ids = data.get('target_emp_ids', [])
        updated_by = session.get('emp_id', 'SYSTEM')

        if not source_emp_id or not target_emp_ids:
            return jsonify({'error': 'Invalid parameters'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 소스 사용자의 권한 조회
        cursor.execute("""
            SELECT menu_code, can_view, can_create, can_edit, can_delete
            FROM user_menu_permissions
            WHERE emp_id = %s
        """, (source_emp_id,))

        source_permissions = cursor.fetchall()

        # 타겟 사용자들에게 권한 복사
        copy_count = 0
        for target_emp_id in target_emp_ids:
            for menu_code, view, create, edit, delete in source_permissions:
                cursor.execute("""
                    INSERT INTO user_menu_permissions
                    (emp_id, menu_code, can_view, can_create, can_edit, can_delete,
                     created_at, created_by, updated_at, updated_by)
                    VALUES (%s, %s, %s, %s, %s, %s, NOW(), %s, NOW(), %s)
                    ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                        can_view = EXCLUDED.can_view,
                        can_create = EXCLUDED.can_create,
                        can_edit = EXCLUDED.can_edit,
                        can_delete = EXCLUDED.can_delete,
                        updated_at = NOW(),
                        updated_by = EXCLUDED.updated_by
                """, (
                    target_emp_id, menu_code,
                    view, create, edit, delete,
                    updated_by, updated_by
                ))
                copy_count += 1

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Copied permissions from {source_emp_id} to {len(target_emp_ids)} users',
            'count': copy_count
        })

    except Exception as e:
        logger.error(f"Error copying permissions: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/menu/<menu_code>', methods=['GET'])
def get_menu_permissions(menu_code):
    """특정 메뉴에 대한 모든 사용자의 권한 조회"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                u.emp_id,
                u.emp_name,
                u.department,
                u.role,
                p.can_create,
                p.can_read,
                p.can_edit,
                p.can_delete
            FROM system_users u
            LEFT JOIN user_menu_permissions p
                ON u.emp_id = p.emp_id AND p.menu_code = %s
            WHERE u.is_active = true
            ORDER BY u.department, u.emp_name
        """, (menu_code,))

        users = []
        for row in cursor.fetchall():
            users.append({
                'emp_id': row[0],
                'emp_name': row[1],
                'department': row[2],
                'role': row[3],
                'permissions': {
                    'create': row[4] or False,
                    'read': row[5] or False,
                    'update': row[6] or False,
                    'delete': row[7] or False
                }
            })

        cursor.close()
        conn.close()

        return jsonify({'menu_code': menu_code, 'users': users})

    except Exception as e:
        logger.error(f"Error getting menu permissions: {e}")
        return jsonify({'error': str(e)}), 500

@permission_api_bp.route('/check', methods=['POST'])
def check_permission():
    """권한 체크 API"""
    try:
        data = request.json
        emp_id = data.get('emp_id', session.get('emp_id'))
        menu_code = data.get('menu_code')
        action = data.get('action')  # create, read, update, delete

        if not emp_id or not menu_code or not action:
            return jsonify({'error': 'Missing parameters'}), 400

        conn = get_db_connection()
        cursor = conn.cursor()

        # 권한 확인
        action_column = {
            'create': 'can_create',
            'read': 'can_view',
            'update': 'can_edit',
            'delete': 'can_delete'
        }.get(action, 'can_view')

        cursor.execute(f"""
            SELECT {action_column}
            FROM user_menu_permissions
            WHERE emp_id = %s AND menu_code = %s
        """, (emp_id, menu_code))

        result = cursor.fetchone()
        has_permission = result[0] if result else False

        cursor.close()
        conn.close()

        return jsonify({
            'emp_id': emp_id,
            'menu_code': menu_code,
            'action': action,
            'has_permission': has_permission
        })

    except Exception as e:
        logger.error(f"Error checking permission: {e}")
        return jsonify({'error': str(e)}), 500

# Flask app.py에 추가할 코드
"""
# app.py에 추가:

from permission_api_routes import permission_api_bp
app.register_blueprint(permission_api_bp)
"""