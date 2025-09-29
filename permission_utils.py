"""
권한 시스템 유틸리티 - Day 1 구현
데코레이터와 권한 체크 로직
"""
from functools import wraps
from flask import session, abort, g, jsonify, request
from db_connection import get_db_connection
import logging

from audit_logger import record_permission_event
from datetime import datetime, timedelta
import json
import configparser

logger = logging.getLogger(__name__)

# 권한 시스템 활성화 여부 확인
def is_permission_enabled():
    """config.ini에서 권한 시스템 활성화 여부 확인"""
    try:
        config = configparser.ConfigParser()
        config.read('config.ini', encoding='utf-8')
        return config.getboolean('PERMISSION', 'enabled', fallback=True)
    except:
        return True  # 기본값은 활성화

class PermissionService:
    """권한 체크 서비스"""

    def __init__(self):
        self.cache_ttl = 300  # 5분 캐시

    def check_permission(self, menu_code, action='view'):
        """권한 체크 데코레이터"""
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                # 권한 시스템 비활성화 시 통과
                if not is_permission_enabled():
                    return f(*args, **kwargs)

                # 세션 체크
                emp_id = session.get('emp_id')
                login_id = session.get('user_id')

                # 로그인 체크
                if not emp_id and not login_id:
                    logger.warning(f"Unauthorized access attempt to {menu_code}")
                    abort(401)  # 로그인 필요

                # emp_id가 없으면 login_id 사용 (호환성)
                if not emp_id:
                    emp_id = login_id

                try:
                    # 권한 확인
                    permission = self._get_user_permission(emp_id, menu_code, action)

                    if not permission:
                        logger.warning(f"Permission denied: {emp_id} -> {menu_code}:{action}")
                        self._log_access(emp_id, action, menu_code, False, "Permission denied")
                        abort(403)  # 권한 없음

                    # g 객체에 권한 정보 저장
                    g.permission = permission
                    g.emp_id = emp_id
                    g.login_id = login_id
                    g.data_scope = permission.get('data_scope', 'none')

                    # 접근 로그 기록
                    self._log_access(emp_id, action, menu_code, True)

                    return f(*args, **kwargs)

                except Exception as e:
                    logger.error(f"Permission check error: {e}")
                    # 오류 시 기본 거부
                    abort(500)

            return wrapped
        return decorator

    def _get_user_permission(self, emp_id, menu_code, action='view'):
        """사용자 권한 조회 (캐시 포함)"""
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 1. 캐시 확인
            cursor.execute("""
                SELECT permissions_json
                FROM permission_cache
                WHERE emp_id = %s AND menu_code = %s
                AND expires_at > CURRENT_TIMESTAMP
            """, (emp_id, menu_code))

            cache_result = cursor.fetchone()
            if cache_result and cache_result[0]:
                permissions = json.loads(cache_result[0]) if isinstance(cache_result[0], str) else cache_result[0]
                if self._check_action(permissions, action):
                    return permissions

            # 2. 권한 계산 (개인 > 부서 > 역할 순)
            permissions = self._calculate_permission(cursor, emp_id, menu_code)

            # 3. 캐시 저장
            if permissions:
                self._cache_permission(cursor, emp_id, menu_code, permissions)
                conn.commit()

            # 4. 액션 체크
            if self._check_action(permissions, action):
                return permissions

            return None

        finally:
            cursor.close()
            conn.close()

    def _calculate_permission(self, cursor, emp_id, menu_code):
        """권한 계산 (우선순위: 개인 > 부서 > 역할)"""

        # 1. 개인 권한 확인 (최우선 - Day 2 추가)
        try:
            cursor.execute("""
                SELECT
                    'user' as source,
                    can_view, can_create, can_edit, can_delete, data_scope
                FROM user_menu_permissions
                WHERE emp_id = %s AND menu_code = %s
                AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)
            """, (emp_id, menu_code))

            result = cursor.fetchone()
            if result:
                return {
                    'source': result[0],
                    'can_view': result[1],
                    'can_create': result[2],
                    'can_edit': result[3],
                    'can_delete': result[4],
                    'data_scope': result[5]
                }
        except Exception as e:
            # 테이블이 없을 수 있음 (Day 2 미적용 환경)
            logger.debug(f"user_menu_permissions not available: {e}")

        # 2. 부서 권한 확인 (Day 2 추가)
        try:
            cursor.execute("""
                SELECT
                    'dept' as source,
                    dmp.can_view, dmp.can_create, dmp.can_edit, dmp.can_delete, dmp.data_scope
                FROM system_users u
                JOIN dept_menu_permissions dmp ON u.dept_id = dmp.dept_id
                WHERE u.emp_id = %s AND dmp.menu_code = %s
                AND (dmp.expires_at IS NULL OR dmp.expires_at > CURRENT_TIMESTAMP)
            """, (emp_id, menu_code))

            result = cursor.fetchone()
            if result:
                return {
                    'source': result[0],
                    'can_view': result[1],
                    'can_create': result[2],
                    'can_edit': result[3],
                    'can_delete': result[4],
                    'data_scope': result[5]
                }
        except Exception as e:
            logger.debug(f"dept_menu_permissions not available: {e}")

        # 3. 역할 기반 권한 (Day 1 기본)
        cursor.execute("""
            SELECT
                r.role_code,
                r.role_level,
                p.can_view,
                p.can_create,
                p.can_edit,
                p.can_delete,
                p.data_scope
            FROM user_role_mapping um
            JOIN system_roles r ON um.role_code = r.role_code
            LEFT JOIN role_menu_permissions p
                ON p.role_code = r.role_code AND p.menu_code = %s
            WHERE um.emp_id = %s
            ORDER BY r.role_level DESC
            LIMIT 1
        """, (menu_code, emp_id))

        result = cursor.fetchone()

        if result and result[2] is not None:  # can_view가 설정되어 있으면
            return {
                'source': 'role',
                'role_code': result[0],
                'role_level': result[1],
                'can_view': result[2],
                'can_create': result[3],
                'can_edit': result[4],
                'can_delete': result[5],
                'data_scope': result[6] or 'none'
            }

        # 기본값 반환 (권한 없음)
        return {
            'source': 'none',
            'can_view': False,
            'can_create': False,
            'can_edit': False,
            'can_delete': False,
            'data_scope': 'none'
        }

    def _check_action(self, permissions, action):
        """액션 권한 체크"""
        if not permissions:
            return False

        action_map = {
            'view': 'can_view',
            'create': 'can_create',
            'edit': 'can_edit',
            'delete': 'can_delete'
        }

        can_field = action_map.get(action, 'can_view')
        return permissions.get(can_field, False)

    def _cache_permission(self, cursor, emp_id, menu_code, permissions):
        """권한 캐시 저장"""
        try:
            expires_at = datetime.now() + timedelta(seconds=self.cache_ttl)
            permissions_json = json.dumps(permissions)

            cursor.execute("""
                INSERT INTO permission_cache (emp_id, menu_code, permissions_json, expires_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (emp_id, menu_code) DO UPDATE
                SET permissions_json = EXCLUDED.permissions_json,
                    cached_at = CURRENT_TIMESTAMP,
                    expires_at = EXCLUDED.expires_at
            """, (emp_id, menu_code, permissions_json, expires_at))

        except Exception as e:
            logger.error(f"Cache save error: {e}")

    def _log_access(self, emp_id, action, menu_code, success, error_message=None):
        """접근 로그 기록"""
        try:
            resource_id = request.args.get('id') if request else None
            details = {}
            if resource_id:
                details['resource_id'] = resource_id
            if error_message:
                details['error'] = error_message

            record_permission_event(
                action_type=action,
                menu_code=menu_code,
                permission_result='SUCCESS' if success else 'DENIED',
                success=success,
                details=details or None,
                error_message=error_message,
            )
        except Exception as e:
            logger.error(f"Access log error: {e}")

def get_data_filter(menu_code=None):
    """데이터 접근 범위에 따른 필터 조건 반환"""
    scope = g.get('data_scope', 'none')
    emp_id = g.get('emp_id')
    login_id = g.get('login_id', session.get('user_id'))

    # 권한 시스템 비활성화 시
    if not is_permission_enabled():
        return "1=1", []

    if scope == 'all':
        # 모든 데이터 접근 가능
        return "1=1", []

    elif scope == 'own':
        # 본인 데이터만
        if login_id:
            return "(created_by = %s OR modified_by = %s OR updated_by = %s)", [login_id, login_id, login_id]
        return "1=0", []

    elif scope == 'dept':
        # 부서 데이터 (Day 2에서 구현)
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 같은 부서 사용자들의 login_id 목록
            cursor.execute("""
                SELECT DISTINCT s2.login_id
                FROM system_users s1
                JOIN system_users s2 ON s1.dept_id = s2.dept_id
                WHERE s1.emp_id = %s AND s2.dept_id IS NOT NULL
            """, (emp_id,))

            dept_users = [r[0] for r in cursor.fetchall()]

            if dept_users:
                placeholders = ','.join(['%s'] * len(dept_users))
                return f"(created_by IN ({placeholders}) OR modified_by IN ({placeholders}))", dept_users + dept_users

        finally:
            cursor.close()
            conn.close()

    elif scope == 'company':
        # 회사 데이터
        conn = get_db_connection()
        cursor = conn.cursor()

        try:
            # 같은 회사 사용자들의 login_id 목록
            cursor.execute("""
                SELECT DISTINCT s2.login_id
                FROM system_users s1
                JOIN system_users s2 ON s1.company_id = s2.company_id
                WHERE s1.emp_id = %s AND s2.company_id IS NOT NULL
            """, (emp_id,))

            company_users = [r[0] for r in cursor.fetchall()]

            if company_users:
                placeholders = ','.join(['%s'] * len(company_users))
                return f"(created_by IN ({placeholders}) OR modified_by IN ({placeholders}))", company_users + company_users

        finally:
            cursor.close()
            conn.close()

    # 기본값: 데이터 접근 불가
    return "1=0", []

def has_permission(menu_code, action='view'):
    """권한 체크 (Boolean 반환)"""
    emp_id = session.get('emp_id', session.get('user_id'))

    if not emp_id:
        return False

    if not is_permission_enabled():
        return True

    service = PermissionService()
    permission = service._get_user_permission(emp_id, menu_code, action)

    return permission is not None

def get_user_menus():
    """사용자가 접근 가능한 메뉴 목록 반환"""
    emp_id = session.get('emp_id', session.get('user_id'))

    if not emp_id:
        return []

    if not is_permission_enabled():
        # 권한 시스템 비활성화 시 모든 메뉴 반환
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT menu_code, menu_name, menu_path
            FROM menu_registry
            WHERE is_active = TRUE
            ORDER BY display_order
        """)
        menus = cursor.fetchall()
        cursor.close()
        conn.close()
        return menus

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT DISTINCT
                m.menu_code,
                m.menu_name,
                m.menu_path,
                m.display_order
            FROM menu_registry m
            JOIN role_menu_permissions p ON m.menu_code = p.menu_code
            JOIN user_role_mapping um ON p.role_code = um.role_code
            WHERE um.emp_id = %s
            AND m.is_active = TRUE
            AND p.can_view = TRUE
            ORDER BY m.display_order
        """, (emp_id,))

        return cursor.fetchall()

    finally:
        cursor.close()
        conn.close()

def clear_user_cache(emp_id=None):
    """사용자 권한 캐시 클리어"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if emp_id:
            cursor.execute("DELETE FROM permission_cache WHERE emp_id = %s", (emp_id,))
        else:
            cursor.execute("DELETE FROM permission_cache")

        conn.commit()
        return True

    except Exception as e:
        logger.error(f"Cache clear error: {e}")
        return False

    finally:
        cursor.close()
        conn.close()

# 권한 체크 인스턴스 생성
permission_service = PermissionService()
check_permission = permission_service.check_permission