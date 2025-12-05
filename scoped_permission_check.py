#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
환경안전 특화 권한 체크 시스템
데이터 범위(Scope) 기반 권한 관리
"""

from flask import session
from db_connection import get_db_connection
import logging

logger = logging.getLogger(__name__)


def _row_value(row, index, key):
    """Helper to read value from either tuple-like or dict-like rows."""
    if row is None:
        return None
    if hasattr(row, 'keys'):
        return row.get(key)
    return row[index]


def _get_dept_info(cursor, dept_id):
    """Return (dept_code, dept_full_path) for the given dept_id."""
    if not dept_id:
        return None, None

    try:
        cursor.execute(
            """
            SELECT dept_code, COALESCE(dept_full_path, dept_code)
            FROM departments_external
            WHERE dept_id = %s AND is_active = true
            """,
            (dept_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None, None
        dept_code = _row_value(row, 0, 'dept_code')
        dept_path = _row_value(row, 1, 'coalesce')
        return dept_code, dept_path
    except Exception as exc:
        logger.debug(f"departments_external lookup failed: {exc}")
        return None, None


def _get_dept_permission_levels(cursor, menu_code, dept_id, dept_code, dept_path):
    """
    Fetch the most specific department permission row matching the user department hierarchy.
    Returns dict with keys read_level, write_level, can_delete when available.
    """
    if not menu_code or not (dept_id or dept_code):
        return None

    where_clauses = []
    params = [menu_code]

    if dept_id:
        where_clauses.append("dept_id = %s")
        params.append(dept_id)

    path_codes = []
    if dept_path:
        path_codes = [code.strip() for code in dept_path.split('|') if code.strip()]

    if dept_code and dept_code not in path_codes:
        path_codes.append(dept_code)

    if path_codes:
        where_clauses.append("dept_code = ANY(%s)")
        params.append(path_codes)

    if not where_clauses:
        return None

    where_sql = " OR ".join(where_clauses)

    # Prefer exact dept_id match, then the most specific ancestor (longer path)
    params.extend([
        dept_id if dept_id else '',
    ])

    sql = f"""
        SELECT read_level, write_level, can_delete
        FROM dept_menu_roles
        WHERE menu_code = %s
          AND is_active = true
          AND ({where_sql})
        ORDER BY
            CASE WHEN dept_id = %s THEN 0 ELSE 1,
            COALESCE(length(dept_full_path), 0) DESC,
            updated_at DESC
        LIMIT 1
    """

    try:
        cursor.execute(sql, params)
        row = cursor.fetchone()
        if not row:
            return None

        return {
            'read_level': _row_value(row, 0, 'read_level'),
            'write_level': _row_value(row, 1, 'write_level'),
            'can_delete': _row_value(row, 2, 'can_delete'),
        }
    except Exception as exc:
        logger.debug(f"dept_menu_roles lookup failed for {menu_code}: {exc}")
        return None

class PermissionLevel:
    """권한 레벨 상수"""
    NONE = 0      # 권한 없음
    SELF = 1      # 본인 관련
    DEPT = 2      # 부서 관련
    ALL = 3       # 전체

    @staticmethod
    def get_name(level, action='read'):
        """레벨 이름 반환"""
        if action == 'read':
            return {
                0: '권한없음',
                1: '본인 관련',
                2: '부서 관련',
                3: '전체 조회'
            }.get(level, '알수없음')
        else:  # write
            return {
                0: '권한없음',
                1: '본인 글만',
                2: '부서 글',
                3: '전체 수정'
            }.get(level, '알수없음')

def get_permission_level(login_id, dept_id, menu_code, action='read'):
    """
    사용자의 권한 레벨 조회

    Args:
        login_id: 사용자 ID
        dept_id: 부서 ID
        menu_code: 메뉴 코드
        action: 'read' or 'write'

    Returns:
        int: 권한 레벨 (0-3)
    """
    if not login_id or not dept_id:
        return PermissionLevel.NONE

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        column = 'read_level' if action == 'read' else 'write_level'

        # 개인 권한 레벨 (login_id 기준)
        cursor.execute(
            f"""
            SELECT {column}
            FROM user_menu_permissions
            WHERE login_id = %s AND menu_code = %s AND is_active = true
            """,
            (login_id, menu_code),
        )

        user_result = cursor.fetchone()
        user_level = _row_value(user_result, 0, column) if user_result else 0

        # 부서 권한 레벨 (SSO deptid 기준, 상위 조직 포함)
        dept_code, dept_path = _get_dept_info(cursor, dept_id)
        dept_perm = _get_dept_permission_levels(cursor, menu_code, dept_id, dept_code, dept_path)
        dept_level = 0
        if dept_perm:
            dept_level = dept_perm.get(column) or 0

        cursor.close()
        conn.close()

        # 더 높은 레벨 반환 (OR 연산)
        return max(user_level, dept_level)

    except Exception as e:
        logger.error(f"Error getting permission level: {e}")
        return PermissionLevel.NONE

def check_data_access(login_id, dept_id, menu_code, action, data_owner=None, data_dept=None):
    """
    데이터 접근 권한 체크

    Args:
        login_id: 사용자 ID
        dept_id: 사용자 부서 ID
        menu_code: 메뉴 코드
        action: 'read', 'write', or 'delete'
        data_owner: 데이터 소유자 ID
        data_dept: 데이터 소속 부서 ID

    Returns:
        bool: 접근 가능 여부
    """
    # 삭제는 별도 체크
    if action == 'delete':
        return check_delete_permission(login_id, dept_id, menu_code)

    # 권한 레벨 확인
    level = get_permission_level(login_id, dept_id, menu_code, action)

    if level == PermissionLevel.NONE:
        return False
    elif level == PermissionLevel.SELF:
        # 본인 데이터만 접근 가능
        return data_owner == login_id
    elif level == PermissionLevel.DEPT:
        # 본인 또는 부서 데이터 접근 가능
        return data_owner == login_id or data_dept == dept_id
    elif level >= PermissionLevel.ALL:
        # 모든 데이터 접근 가능
        return True

    return False

def check_delete_permission(login_id, dept_id, menu_code):
    """삭제 권한 체크 (별도 관리)"""
    if not login_id or not dept_id:
        return False

    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 개인 삭제 권한
        cursor.execute(
            """
            SELECT can_delete
            FROM user_menu_permissions
            WHERE login_id = %s AND menu_code = %s AND is_active = true
            """,
            (login_id, menu_code),
        )

        user_result = cursor.fetchone()
        user_can_delete = _row_value(user_result, 0, 'can_delete') if user_result else False

        # 부서 삭제 권한 (상위 조직 포함)
        dept_code, dept_path = _get_dept_info(cursor, dept_id)
        dept_perm = _get_dept_permission_levels(cursor, menu_code, dept_id, dept_code, dept_path)
        dept_can_delete = dept_perm.get('can_delete') if dept_perm else False

        cursor.close()
        conn.close()

        # OR 연산
        return user_can_delete or dept_can_delete

    except Exception as e:
        logger.error(f"Error checking delete permission: {e}")
        return False

def get_data_filter_condition(login_id, dept_id, menu_code):
    """
    SQL WHERE 조건 생성 (데이터 필터링용)

    Returns:
        tuple: (where_clause, params)
    """
    level = get_permission_level(login_id, dept_id, menu_code, 'read')

    if level == PermissionLevel.NONE:
        return "1=0", []  # 아무것도 볼 수 없음
    elif level == PermissionLevel.SELF:
        # 사고 테이블의 경우 reporter_id, accident_manager_id 사용
        # 다른 테이블은 created_by 사용
        if menu_code == 'ACCIDENT_MGT':
            return "(reporter_id = %s OR accident_manager_id = %s)", [login_id, login_id]
        else:
            return "(created_by = %s)", [login_id]
    elif level == PermissionLevel.DEPT:
        if menu_code == 'ACCIDENT_MGT':
            return "(reporter_id = %s OR accident_manager_id = %s OR dept_id = %s OR accident_dept_id = %s)", [login_id, login_id, dept_id, dept_id]
        else:
            return "(created_by = %s OR dept_id = %s)", [login_id, dept_id]
    else:  # ALL
        return "1=1", []  # 모든 데이터

def get_user_permission_summary(login_id, dept_id):
    """사용자의 전체 권한 요약"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 개인 권한
        cursor.execute(
            """
            SELECT menu_code, read_level, write_level, can_delete
            FROM user_menu_permissions
            WHERE login_id = %s AND is_active = true
            """,
            (login_id,),
        )
        personal = {}
        for row in cursor.fetchall():
            menu_code = _row_value(row, 0, 'menu_code')
            personal[menu_code] = {
                'read_level': _row_value(row, 1, 'read_level') or 0,
                'write_level': _row_value(row, 2, 'write_level') or 0,
                'can_delete': bool(_row_value(row, 3, 'can_delete')),
            }

        # 부서 권한 (상위 조직 포함)
        dept_code, dept_path = _get_dept_info(cursor, dept_id)
        dept_perms = {}
        if dept_code or dept_id:
            where_parts = []
            params = []
            if dept_id:
                where_parts.append("dept_id = %s")
                params.append(dept_id)

            path_codes = []
            if dept_path:
                path_codes = [code.strip() for code in dept_path.split('|') if code.strip()]

            if dept_code and dept_code not in path_codes:
                path_codes.append(dept_code)

            if where_parts or path_codes:
                if path_codes:
                    where_parts.append("dept_code = ANY(%s)")
                    params.append(path_codes)

                where_sql = " OR ".join(where_parts)
                params_extended = params + [dept_id if dept_id else '']

                cursor.execute(
                    f"""
                    SELECT menu_code, read_level, write_level, can_delete, dept_full_path, updated_at
                    FROM dept_menu_roles
                    WHERE is_active = true AND menu_code IS NOT NULL
                      AND ({where_sql})
                    ORDER BY
                        CASE WHEN dept_id = %s THEN 0 ELSE 1,
                        COALESCE(length(dept_full_path), 0) DESC,
                        updated_at DESC
                    """,
                    params_extended,
                )

                for row in cursor.fetchall():
                    menu_code = _row_value(row, 0, 'menu_code')
                    if menu_code in dept_perms:
                        continue
                    dept_perms[menu_code] = {
                        'read_level': _row_value(row, 1, 'read_level') or 0,
                        'write_level': _row_value(row, 2, 'write_level') or 0,
                        'can_delete': bool(_row_value(row, 3, 'can_delete')),
                    }

        cursor.close()
        conn.close()

        all_codes = set(personal.keys()) | set(dept_perms.keys())
        permissions = {}
        for menu_code in all_codes:
            user_perm = personal.get(menu_code, {'read_level': 0, 'write_level': 0, 'can_delete': False})
            dept_perm = dept_perms.get(menu_code, {'read_level': 0, 'write_level': 0, 'can_delete': False})

            read_level = max(user_perm['read_level'], dept_perm['read_level'])
            write_level = max(user_perm['write_level'], dept_perm['write_level'])
            can_delete = user_perm['can_delete'] or dept_perm['can_delete']

            permissions[menu_code] = {
                'read_level': read_level,
                'read_level_name': PermissionLevel.get_name(read_level, 'read'),
                'write_level': write_level,
                'write_level_name': PermissionLevel.get_name(write_level, 'write'),
                'can_delete': can_delete,
            }

        return permissions

    except Exception as e:
        logger.error(f"Error getting permission summary: {e}")
        return {}

# Flask decorator용 함수들
def require_read_permission(menu_code, level=PermissionLevel.SELF):
    """읽기 권한 체크 decorator"""
    from functools import wraps
    from flask import jsonify

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            user_level = get_permission_level(login_id, dept_id, menu_code, 'read')
            if user_level < level:
                return jsonify({'error': 'Insufficient read permission'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_write_permission(menu_code, level=PermissionLevel.SELF):
    """쓰기 권한 체크 decorator"""
    from functools import wraps
    from flask import jsonify

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            user_level = get_permission_level(login_id, dept_id, menu_code, 'write')
            if user_level < level:
                return jsonify({'error': 'Insufficient write permission'}), 403

            return f(*args, **kwargs)
        return decorated_function
    return decorator
