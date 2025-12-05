"""
부서 권한 관리 API
SSO deptid와 dept_code 매핑을 통한 권한 관리
"""

from flask import Blueprint, request, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from datetime import datetime

dept_permission_bp = Blueprint('dept_permission', __name__)

# 데이터베이스 연결
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="portal_dev",
        user="postgres",
        password="admin123",
        cursor_factory=RealDictCursor
    )

@dept_permission_bp.route('/api/dept-permissions/mapping', methods=['GET'])
def get_dept_mapping():
    """SSO deptid와 dept_code 매핑 정보 조회"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # SSO deptid 파라미터
        sso_dept_id = request.args.get('sso_dept_id')

        if sso_dept_id:
            # 특정 부서 조회
            cur.execute("""
                SELECT
                    dept_id as sso_dept_id,
                    dept_code,
                    dept_name,
                    dept_full_path,
                    dept_level,
                    parent_dept_code
                FROM departments_external
                WHERE dept_id = %s AND is_active = true
            """, (sso_dept_id,))
            result = cur.fetchone()
        else:
            # 전체 매핑 조회
            cur.execute("""
                SELECT
                    dept_id as sso_dept_id,
                    dept_code,
                    dept_name,
                    dept_full_path,
                    dept_level,
                    parent_dept_code
                FROM departments_external
                WHERE is_active = true
                ORDER BY dept_full_path
            """)
            result = cur.fetchall()

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': result
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dept_permission_bp.route('/api/dept-permissions/tree', methods=['GET'])
def get_dept_tree():
    """부서 트리 구조 조회 (deptid 포함)"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # 모든 부서 조회
        cur.execute("""
            SELECT
                dept_id as sso_dept_id,
                dept_code,
                dept_name,
                parent_dept_code,
                dept_full_path,
                dept_level
            FROM departments_external
            WHERE is_active = true
            ORDER BY dept_full_path
        """)

        departments = cur.fetchall()

        # 트리 구조 생성
        dept_map = {}
        roots = []

        for dept in departments:
            dept['children'] = []
            dept_map[dept['dept_code']] = dept

        for dept in departments:
            if dept['parent_dept_code']:
                parent = dept_map.get(dept['parent_dept_code'])
                if parent:
                    parent['children'].append(dept)
            else:
                roots.append(dept)

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'data': roots
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dept_permission_bp.route('/api/dept-permissions/apply', methods=['POST'])
def apply_dept_permissions():
    """부서 권한 설정 (SSO deptid 기반)"""
    try:
        data = request.get_json()
        sso_dept_id = data.get('sso_dept_id')
        permissions = data.get('permissions', {})
        apply_to_children = data.get('apply_to_children', False)

        conn = get_db_connection()
        cur = conn.cursor()

        # SSO deptid로 dept_code 조회
        cur.execute("""
            SELECT dept_code, dept_full_path
            FROM departments_external
            WHERE dept_id = %s AND is_active = true
        """, (sso_dept_id,))

        dept_info = cur.fetchone()
        if not dept_info:
            return jsonify({
                'success': False,
                'error': 'Department not found'
            }), 404

        dept_code = dept_info['dept_code']
        dept_full_path = dept_info['dept_full_path']

        # 권한 설정
        for menu_code, role in permissions.items():
            cur.execute("""
                INSERT INTO dept_menu_roles (dept_id, dept_code, dept_full_path, menu_code, role_for_menu)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (dept_id, menu_code)
                DO UPDATE SET
                    role_for_menu = EXCLUDED.role_for_menu,
                    dept_full_path = EXCLUDED.dept_full_path,
                    updated_at = CURRENT_TIMESTAMP
            """, (sso_dept_id, dept_code, dept_full_path, menu_code, role))

        affected_count = len(permissions)

        # 하위 부서에 적용
        if apply_to_children:
            # dept_full_path를 이용해 하위 부서 찾기
            cur.execute("""
                SELECT dept_id, dept_code, dept_full_path
                FROM departments_external
                WHERE dept_full_path LIKE %s
                  AND dept_id != %s
                  AND is_active = true
            """, (f"{dept_full_path}|%", sso_dept_id))

            child_departments = cur.fetchall()

            for child in child_departments:
                for menu_code, role in permissions.items():
                    cur.execute("""
                        INSERT INTO dept_menu_roles (dept_id, dept_code, dept_full_path, menu_code, role_for_menu)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (dept_id, menu_code)
                        DO UPDATE SET
                            role_for_menu = EXCLUDED.role_for_menu,
                            dept_full_path = EXCLUDED.dept_full_path,
                            updated_at = CURRENT_TIMESTAMP
                    """, (child['dept_id'], child['dept_code'], child['dept_full_path'], menu_code, role))

            affected_count += len(child_departments) * len(permissions)

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'affected_count': affected_count,
            'message': f'Permissions applied to {dept_code}' + (' and its children' if apply_to_children else '')
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dept_permission_bp.route('/api/dept-permissions/check-user', methods=['GET'])
def check_user_permissions():
    """사용자의 최종 권한 확인 (SSO deptid 기반)"""
    try:
        emp_id = request.args.get('emp_id')
        sso_dept_id = request.args.get('sso_dept_id')

        if not emp_id or not sso_dept_id:
            return jsonify({
                'success': False,
                'error': 'emp_id and sso_dept_id are required'
            }), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # 부서 정보 조회
        cur.execute("""
            SELECT dept_code, dept_full_path, dept_name
            FROM departments_external
            WHERE dept_id = %s AND is_active = true
        """, (sso_dept_id,))

        dept_info = cur.fetchone()
        if not dept_info:
            return jsonify({
                'success': False,
                'error': 'Department not found'
            }), 404

        # dept_full_path에서 모든 상위 부서 추출
        dept_codes = dept_info['dept_full_path'].split('|')

        # 개인 권한 조회
        cur.execute("""
            SELECT menu_code, role_for_menu, 'personal' as source
            FROM user_menu_roles
            WHERE emp_id = %s AND is_active = true
        """, (emp_id,))
        personal_permissions = {row['menu_code']: row for row in cur.fetchall()}

        # 부서 권한 조회 (상위 부서 포함)
        cur.execute("""
            SELECT DISTINCT ON (menu_code)
                menu_code,
                role_for_menu,
                dept_code,
                CASE
                    WHEN dept_code = %s THEN 'dept_direct'
                    ELSE 'dept_inherited'
                END as source
            FROM dept_menu_roles
            WHERE dept_code = ANY(%s) AND is_active = true
            ORDER BY menu_code,
                     CASE WHEN dept_code = %s THEN 0 ELSE 1 END,
                     updated_at DESC
        """, (dept_info['dept_code'], dept_codes, dept_info['dept_code']))

        dept_permissions = {row['menu_code']: row for row in cur.fetchall()}

        # 최종 권한 결합 (개인 권한이 우선)
        final_permissions = {}
        all_menu_codes = set(personal_permissions.keys()) | set(dept_permissions.keys())

        for menu_code in all_menu_codes:
            if menu_code in personal_permissions:
                final_permissions[menu_code] = personal_permissions[menu_code]
            elif menu_code in dept_permissions:
                final_permissions[menu_code] = dept_permissions[menu_code]
            else:
                final_permissions[menu_code] = {
                    'menu_code': menu_code,
                    'role_for_menu': 'none',
                    'source': 'default'
                }

        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'user': {
                'emp_id': emp_id,
                'sso_dept_id': sso_dept_id,
                'dept_code': dept_info['dept_code'],
                'dept_name': dept_info['dept_name'],
                'dept_path': dept_info['dept_full_path']
            },
            'permissions': final_permissions
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dept_permission_bp.route('/api/dept-permissions/sync-external', methods=['POST'])
def sync_external_departments():
    """외부 시스템과 부서 정보 동기화"""
    try:
        # 외부 시스템에서 부서 데이터 조회 (실제 구현 시 외부 API 호출)
        # 여기서는 예시 데이터 사용
        external_data = request.get_json()

        conn = get_db_connection()
        cur = conn.cursor()

        sync_count = 0
        for dept in external_data.get('departments', []):
            cur.execute("""
                INSERT INTO departments_external
                (dept_id, dept_code, dept_name, parent_dept_code, dept_full_path, dept_level)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (dept_id)
                DO UPDATE SET
                    dept_code = EXCLUDED.dept_code,
                    dept_name = EXCLUDED.dept_name,
                    parent_dept_code = EXCLUDED.parent_dept_code,
                    dept_full_path = EXCLUDED.dept_full_path,
                    dept_level = EXCLUDED.dept_level,
                    last_sync_at = CURRENT_TIMESTAMP
            """, (
                dept['deptid'],
                dept['dept_code'],
                dept['dept_name'],
                dept.get('parent_dept_code'),
                dept['dept_full_path'],
                dept.get('dept_level', 1)
            ))
            sync_count += 1

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'sync_count': sync_count,
            'message': f'Successfully synced {sync_count} departments'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@dept_permission_bp.route('/api/dept-permissions/batch-update', methods=['POST'])
def batch_update_dept_permissions():
    """부서 권한 일괄 업데이트"""
    try:
        data = request.get_json()
        changes = data.get('changes', [])

        conn = get_db_connection()
        cur = conn.cursor()

        update_count = 0
        for change in changes:
            sso_dept_id = change.get('sso_dept_id')
            menu_code = change.get('menu_code')
            role = change.get('role')

            # SSO deptid로 dept_code와 dept_full_path 조회
            cur.execute("""
                SELECT dept_code, dept_full_path
                FROM departments_external
                WHERE dept_id = %s AND is_active = true
            """, (sso_dept_id,))

            dept_info = cur.fetchone()
            if dept_info:
                cur.execute("""
                    INSERT INTO dept_menu_roles
                    (dept_id, dept_code, dept_full_path, menu_code, role_for_menu)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (dept_id, menu_code)
                    DO UPDATE SET
                        role_for_menu = EXCLUDED.role_for_menu,
                        dept_full_path = EXCLUDED.dept_full_path,
                        updated_at = CURRENT_TIMESTAMP
                """, (sso_dept_id, dept_info['dept_code'], dept_info['dept_full_path'], menu_code, role))
                update_count += 1

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({
            'success': True,
            'count': update_count,
            'message': f'{update_count} permissions updated'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    # Flask app에 Blueprint 등록
    from flask import Flask
    app = Flask(__name__)
    app.register_blueprint(dept_permission_bp)
    app.run(debug=True, port=5001)