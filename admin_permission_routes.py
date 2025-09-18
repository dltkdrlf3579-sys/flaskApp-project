#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 관리 시스템 Flask 라우트
기존 UI 스타일에 맞춘 새로운 버전
"""

from flask import Flask, render_template, jsonify, request, session, redirect, url_for
import psycopg2
import configparser
import json
from datetime import datetime, timedelta
from functools import wraps
import hashlib

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'

# 설정 파일 로드
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

def get_db_connection():
    """데이터베이스 연결"""
    if config.has_option('DATABASE', 'postgres_dsn'):
        return psycopg2.connect(config.get('DATABASE', 'postgres_dsn'))
    else:
        # 개발 환경 기본값
        return psycopg2.connect(
            host='localhost',
            database='portal_db',
            user='postgres',
            password='postgres'
        )

def login_required(f):
    """로그인 체크 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'emp_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    """관리자 권한 체크 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session or session['role'] not in ['super_admin', 'admin']:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated_function

# 메인 권한 관리 대시보드
@app.route('/admin/permissions')
@login_required
@admin_required
def permission_dashboard():
    """권한 관리 대시보드 v2"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 통계 데이터 조회
        stats = {}

        # 전체 사용자 수
        cursor.execute("SELECT COUNT(*) FROM system_users WHERE is_active = TRUE")
        stats['total_users'] = cursor.fetchone()[0] or 0

        # 활성 역할 수
        cursor.execute("SELECT COUNT(DISTINCT role_code) FROM system_roles WHERE is_active = TRUE")
        stats['active_roles'] = cursor.fetchone()[0] or 0

        # 권한 메뉴 수
        cursor.execute("SELECT COUNT(DISTINCT menu_code) FROM menu_registry WHERE is_active = TRUE")
        stats['total_menus'] = cursor.fetchone()[0] or 0

        # 오늘 접속 수
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_id) FROM access_audit_log
            WHERE DATE(created_at) = CURRENT_DATE
            AND action_type = 'LOGIN'
        """)
        stats['today_logins'] = cursor.fetchone()[0] or 0

        # 역할별 사용자 분포
        cursor.execute("""
            SELECT r.role_code, r.role_name, COUNT(urm.emp_id) as user_count
            FROM system_roles r
            LEFT JOIN user_role_mapping urm ON r.role_code = urm.role_id
            GROUP BY r.role_code, r.role_name
            ORDER BY r.role_level DESC
        """)
        stats['role_distribution'] = cursor.fetchall()

        # 최근 권한 변경 이력
        cursor.execute("""
            SELECT
                al.created_at,
                al.emp_id,
                u.user_name,
                al.action_type,
                al.details,
                al.permission_result
            FROM access_audit_log al
            LEFT JOIN system_users u ON al.emp_id = u.emp_id
            WHERE al.action_type IN ('PERMISSION_CHANGE', 'ROLE_CHANGE')
            ORDER BY al.created_at DESC
            LIMIT 10
        """)
        stats['recent_changes'] = cursor.fetchall()

        cursor.close()
        conn.close()

        return render_template('admin/permission_dashboard.html', **stats)

    except Exception as e:
        print(f"Error in permission_dashboard: {e}")
        cursor.close()
        conn.close()
        return render_template('admin/permission_dashboard.html', error=str(e))

# API: 사용자 목록 조회
@app.route('/api/admin/users')
@login_required
@admin_required
def get_users():
    """사용자 목록 API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search = request.args.get('search', '')
    role = request.args.get('role', '')
    dept = request.args.get('dept', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    # 기본 쿼리
    query = """
        SELECT
            u.emp_id,
            u.user_name,
            u.login_id,
            u.dept_id,
            u.is_active,
            u.last_login,
            urm.role_id,
            r.role_name,
            r.role_level
        FROM system_users u
        LEFT JOIN user_role_mapping urm ON u.emp_id = urm.emp_id
        LEFT JOIN system_roles r ON urm.role_id = r.role_code
        WHERE 1=1
    """

    params = []

    # 검색 조건 추가
    if search:
        query += " AND (u.user_name LIKE %s OR u.login_id LIKE %s OR u.emp_id LIKE %s)"
        params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    if role:
        query += " AND urm.role_id = %s"
        params.append(role)

    if dept:
        query += " AND u.dept_id = %s"
        params.append(dept)

    # 정렬
    query += " ORDER BY u.created_at DESC"

    # 페이지네이션
    query += " LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    users = cursor.fetchall()

    # 전체 개수 조회
    count_query = "SELECT COUNT(*) FROM system_users u WHERE 1=1"
    count_params = []

    if search:
        count_query += " AND (u.user_name LIKE %s OR u.login_id LIKE %s OR u.emp_id LIKE %s)"
        count_params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])

    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return jsonify({
        'users': [{
            'emp_id': u[0],
            'user_name': u[1],
            'login_id': u[2],
            'dept_id': u[3],
            'is_active': u[4],
            'last_login': u[5].isoformat() if u[5] else None,
            'role_id': u[6],
            'role_name': u[7],
            'role_level': u[8]
        } for u in users],
        'total': total_count,
        'page': page,
        'per_page': per_page,
        'total_pages': (total_count + per_page - 1) // per_page
    })

# API: 역할 목록 조회
@app.route('/api/admin/roles')
@login_required
@admin_required
def get_roles():
    """역할 목록 API"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            r.role_code,
            r.role_name,
            r.description,
            r.role_level,
            r.is_active,
            COUNT(urm.emp_id) as user_count
        FROM system_roles r
        LEFT JOIN user_role_mapping urm ON r.role_code = urm.role_id
        GROUP BY r.role_code, r.role_name, r.description, r.role_level, r.is_active
        ORDER BY r.role_level DESC
    """)

    roles = cursor.fetchall()

    cursor.close()
    conn.close()

    return jsonify([{
        'role_code': r[0],
        'role_name': r[1],
        'description': r[2],
        'role_level': r[3],
        'is_active': r[4],
        'user_count': r[5]
    } for r in roles])

# API: 권한 매트릭스 조회
@app.route('/api/admin/permission-matrix')
@login_required
@admin_required
def get_permission_matrix():
    """권한 매트릭스 API"""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            rmp.role_code,
            r.role_name,
            r.role_level,
            rmp.menu_code,
            m.menu_name,
            rmp.can_view,
            rmp.can_create,
            rmp.can_edit,
            rmp.can_delete,
            rmp.data_scope
        FROM role_menu_permissions rmp
        JOIN system_roles r ON rmp.role_code = r.role_code
        JOIN menu_registry m ON rmp.menu_code = m.menu_code
        WHERE r.is_active = TRUE AND m.is_active = TRUE
        ORDER BY r.role_level DESC, m.display_order
    """)

    permissions = cursor.fetchall()

    cursor.close()
    conn.close()

    # 매트릭스 형태로 재구성
    matrix = {}
    menus = set()

    for perm in permissions:
        role_code = perm[0]
        menu_code = perm[3]

        if role_code not in matrix:
            matrix[role_code] = {
                'role_name': perm[1],
                'role_level': perm[2],
                'permissions': {}
            }

        matrix[role_code]['permissions'][menu_code] = {
            'menu_name': perm[4],
            'can_view': perm[5],
            'can_create': perm[6],
            'can_edit': perm[7],
            'can_delete': perm[8],
            'data_scope': perm[9]
        }

        menus.add((menu_code, perm[4]))

    return jsonify({
        'matrix': matrix,
        'menus': sorted(list(menus), key=lambda x: x[0])
    })

# API: 감사 로그 조회
@app.route('/api/admin/audit-logs')
@login_required
@admin_required
def get_audit_logs():
    """감사 로그 API"""
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    action_type = request.args.get('action_type', '')
    user = request.args.get('user', '')

    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT
            al.created_at,
            al.emp_id,
            u.user_name,
            al.action_type,
            al.menu_code,
            al.request_path,
            al.details,
            al.ip_address,
            al.permission_result
        FROM access_audit_log al
        LEFT JOIN system_users u ON al.emp_id = u.emp_id
        WHERE 1=1
    """

    params = []

    if start_date:
        query += " AND al.created_at >= %s"
        params.append(start_date)

    if end_date:
        query += " AND al.created_at <= %s"
        params.append(f"{end_date} 23:59:59")

    if action_type:
        query += " AND al.action_type = %s"
        params.append(action_type)

    if user:
        query += " AND (al.emp_id LIKE %s OR u.user_name LIKE %s)"
        params.extend([f'%{user}%', f'%{user}%'])

    query += " ORDER BY al.created_at DESC LIMIT %s OFFSET %s"
    params.extend([per_page, (page - 1) * per_page])

    cursor.execute(query, params)
    logs = cursor.fetchall()

    # 전체 개수 조회
    count_query = "SELECT COUNT(*) FROM access_audit_log al WHERE 1=1"
    count_params = []

    if start_date:
        count_query += " AND al.created_at >= %s"
        count_params.append(start_date)

    if end_date:
        count_query += " AND al.created_at <= %s"
        count_params.append(f"{end_date} 23:59:59")

    if action_type:
        count_query += " AND al.action_type = %s"
        count_params.append(action_type)

    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]

    cursor.close()
    conn.close()

    return jsonify({
        'logs': [{
            'created_at': log[0].isoformat() if log[0] else None,
            'emp_id': log[1],
            'user_name': log[2],
            'action_type': log[3],
            'menu_code': log[4],
            'request_path': log[5],
            'details': log[6],
            'ip_address': log[7],
            'permission_result': log[8]
        } for log in logs],
        'total': total_count,
        'page': page,
        'per_page': per_page,
        'total_pages': (total_count + per_page - 1) // per_page
    })

# API: 사용자 역할 변경
@app.route('/api/admin/user/<emp_id>/role', methods=['POST'])
@login_required
@admin_required
def change_user_role(emp_id):
    """사용자 역할 변경 API"""
    data = request.json
    new_role = data.get('role_id')

    if not new_role:
        return jsonify({'error': 'Role ID is required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 기존 역할 조회
        cursor.execute("""
            SELECT role_id FROM user_role_mapping WHERE emp_id = %s
        """, (emp_id,))
        old_role = cursor.fetchone()

        if old_role:
            # 업데이트
            cursor.execute("""
                UPDATE user_role_mapping
                SET role_id = %s, updated_at = CURRENT_TIMESTAMP
                WHERE emp_id = %s
            """, (new_role, emp_id))
        else:
            # 새로 추가
            cursor.execute("""
                INSERT INTO user_role_mapping (emp_id, role_id)
                VALUES (%s, %s)
            """, (emp_id, new_role))

        # 감사 로그 기록
        cursor.execute("""
            INSERT INTO access_audit_log
            (emp_id, action_type, menu_code, request_path, permission_result, details)
            VALUES (%s, 'ROLE_CHANGE', 'permission_admin', '/api/admin/user/role',
                    'SUCCESS', %s)
        """, (session.get('emp_id'), json.dumps({
            'target_user': emp_id,
            'old_role': old_role[0] if old_role else None,
            'new_role': new_role
        })))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Role updated successfully'})

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

# API: 권한 매트릭스 업데이트
@app.route('/api/admin/permissions', methods=['POST'])
@login_required
@admin_required
def update_permissions():
    """권한 매트릭스 업데이트 API"""
    data = request.json
    role_code = data.get('role_code')
    menu_code = data.get('menu_code')
    permissions = data.get('permissions', {})

    if not role_code or not menu_code:
        return jsonify({'error': 'Role and menu codes are required'}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 권한 업데이트
        cursor.execute("""
            UPDATE role_menu_permissions
            SET can_view = %s,
                can_create = %s,
                can_edit = %s,
                can_delete = %s,
                data_scope = %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE role_code = %s AND menu_code = %s
        """, (
            permissions.get('can_view', False),
            permissions.get('can_create', False),
            permissions.get('can_edit', False),
            permissions.get('can_delete', False),
            permissions.get('data_scope', 'own'),
            role_code,
            menu_code
        ))

        # 권한이 없으면 새로 생성
        if cursor.rowcount == 0:
            cursor.execute("""
                INSERT INTO role_menu_permissions
                (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            """, (
                role_code,
                menu_code,
                permissions.get('can_view', False),
                permissions.get('can_create', False),
                permissions.get('can_edit', False),
                permissions.get('can_delete', False),
                permissions.get('data_scope', 'own')
            ))

        # 감사 로그
        cursor.execute("""
            INSERT INTO access_audit_log
            (emp_id, action_type, menu_code, request_path, permission_result, details)
            VALUES (%s, 'PERMISSION_CHANGE', %s, '/api/admin/permissions',
                    'SUCCESS', %s)
        """, (session.get('emp_id'), menu_code, json.dumps({
            'role': role_code,
            'permissions': permissions
        })))

        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({'success': True, 'message': 'Permissions updated successfully'})

    except Exception as e:
        conn.rollback()
        cursor.close()
        conn.close()
        return jsonify({'error': str(e)}), 500

# API: 대시보드 통계
@app.route('/api/admin/dashboard-stats')
@login_required
@admin_required
def get_dashboard_stats():
    """대시보드 통계 API"""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}

    # 일일 접속 통계 (최근 7일)
    cursor.execute("""
        SELECT
            DATE(created_at) as date,
            COUNT(DISTINCT emp_id) as unique_users,
            COUNT(*) as total_actions
        FROM access_audit_log
        WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
        GROUP BY DATE(created_at)
        ORDER BY date
    """)
    stats['daily_access'] = [{
        'date': row[0].isoformat(),
        'unique_users': row[1],
        'total_actions': row[2]
    } for row in cursor.fetchall()]

    # 시간대별 접속 패턴 (오늘)
    cursor.execute("""
        SELECT
            EXTRACT(HOUR FROM created_at) as hour,
            COUNT(DISTINCT emp_id) as users
        FROM access_audit_log
        WHERE DATE(created_at) = CURRENT_DATE
        GROUP BY EXTRACT(HOUR FROM created_at)
        ORDER BY hour
    """)
    stats['hourly_pattern'] = [{
        'hour': int(row[0]),
        'users': row[1]
    } for row in cursor.fetchall()]

    # 메뉴별 접근 통계
    cursor.execute("""
        SELECT
            menu_code,
            COUNT(*) as access_count
        FROM access_audit_log
        WHERE menu_code IS NOT NULL
        AND created_at >= CURRENT_DATE - INTERVAL '30 days'
        GROUP BY menu_code
        ORDER BY access_count DESC
        LIMIT 10
    """)
    stats['menu_access'] = [{
        'menu': row[0],
        'count': row[1]
    } for row in cursor.fetchall()]

    cursor.close()
    conn.close()

    return jsonify(stats)

if __name__ == '__main__':
    app.run(debug=True, port=5000)