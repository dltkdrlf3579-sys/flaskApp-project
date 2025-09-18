"""
권한 시스템 유틸리티 - 운영환경 안전 버전
개발/운영 환경을 자동 감지하고 안전하게 동작
"""
from functools import wraps
from flask import session, abort, g, jsonify, request
from db_connection import get_db_connection
import logging
import os
import configparser
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

# 환경 감지
def get_environment():
    """현재 환경 감지 (개발/운영)"""
    env = os.getenv('ENVIRONMENT', 'DEVELOPMENT')
    config_file = 'config.ini.prod' if env == 'PRODUCTION' else 'config.ini'

    config = configparser.ConfigParser()
    config.read(config_file, encoding='utf-8')

    return {
        'env': env,
        'config': config,
        'is_production': env == 'PRODUCTION',
        'is_development': env == 'DEVELOPMENT'
    }

# 권한 시스템 활성화 여부 확인 (환경별)
def is_permission_enabled():
    """권한 시스템 활성화 여부 (환경별 설정)"""
    env_info = get_environment()
    config = env_info['config']

    # 운영환경에서는 더 신중하게
    if env_info['is_production']:
        # 다중 체크
        enabled = config.getboolean('PERMISSION', 'enabled', fallback=False)
        confirmed = config.getboolean('PERMISSION', 'confirmed', fallback=False)

        # 두 플래그 모두 true여야 활성화
        return enabled and confirmed

    # 개발환경
    return config.getboolean('PERMISSION', 'enabled', fallback=True)

class SafePermissionService:
    """운영환경 안전 권한 서비스"""

    def __init__(self):
        env_info = get_environment()
        self.env = env_info['env']
        self.config = env_info['config']
        self.is_production = env_info['is_production']

        # 환경별 캐시 TTL
        self.cache_ttl = self.config.getint('PERMISSION', 'cache_ttl',
                                           fallback=3600 if self.is_production else 300)

        # 로그 레벨 설정
        log_level = logging.ERROR if self.is_production else logging.DEBUG
        logger.setLevel(log_level)

    def check_permission(self, menu_code, action='view'):
        """권한 체크 데코레이터 (안전 버전)"""
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                # 권한 시스템 비활성화 시 통과
                if not is_permission_enabled():
                    logger.debug(f"Permission system disabled, allowing {menu_code}:{action}")
                    return f(*args, **kwargs)

                # LOG_ONLY 모드 체크 (운영 초기)
                log_only = self.config.getboolean('PERMISSION', 'log_only', fallback=False)

                # 활성 메뉴 체크 (단계적 적용)
                active_menus = self.config.get('PERMISSION', 'active_menus', fallback='all')
                if active_menus != 'all':
                    active_list = [m.strip() for m in active_menus.split(',')]
                    if menu_code not in active_list:
                        logger.debug(f"Menu {menu_code} not in active list, allowing")
                        return f(*args, **kwargs)

                # 세션 체크
                emp_id = session.get('emp_id')
                login_id = session.get('user_id')

                # 로그인 체크
                if not emp_id and not login_id:
                    logger.warning(f"Unauthorized access attempt to {menu_code}")

                    if log_only:
                        # 로그만 남기고 허용 (운영 초기)
                        self._log_access('ANONYMOUS', action, menu_code, True,
                                       "LOG_ONLY mode - would deny")
                        return f(*args, **kwargs)
                    else:
                        abort(401)  # 로그인 필요

                # emp_id가 없으면 login_id 사용 (호환성)
                if not emp_id:
                    emp_id = login_id

                try:
                    # 권한 확인
                    permission = self._get_user_permission_safe(emp_id, menu_code, action)

                    if not permission:
                        msg = f"Permission denied: {emp_id} -> {menu_code}:{action}"
                        logger.warning(msg)

                        # 운영환경 알림
                        if self.is_production:
                            self._send_permission_alert(emp_id, menu_code, action)

                        if log_only:
                            self._log_access(emp_id, action, menu_code, True,
                                           "LOG_ONLY mode - would deny")
                            return f(*args, **kwargs)
                        else:
                            self._log_access(emp_id, action, menu_code, False, "Permission denied")
                            abort(403)

                    # 권한 정보 저장
                    g.permission = permission
                    g.emp_id = emp_id
                    g.login_id = login_id
                    g.data_scope = permission.get('data_scope', 'none')

                    # 성공 로그
                    self._log_access(emp_id, action, menu_code, True)

                    return f(*args, **kwargs)

                except Exception as e:
                    logger.error(f"Permission check error: {e}")

                    # 운영환경에서는 안전하게 거부
                    if self.is_production:
                        self._send_error_alert(str(e))
                        abort(500)
                    else:
                        # 개발환경에서는 상세 에러
                        raise

            return wrapped
        return decorator

    def _get_user_permission_safe(self, emp_id, menu_code, action='view'):
        """사용자 권한 조회 (안전 버전)"""
        conn = None
        cursor = None

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 테이블 존재 확인 (운영 초기)
            if self.is_production:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_name = 'system_users'
                    )
                """)
                if not cursor.fetchone()[0]:
                    logger.error("system_users table not found!")
                    return None

            # Day 1의 기존 로직 사용
            return self._calculate_permission(cursor, emp_id, menu_code)

        except Exception as e:
            logger.error(f"Permission query error: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _calculate_permission(self, cursor, emp_id, menu_code):
        """권한 계산 (Day 2 확장 버전 포함)"""

        # 1. 개인 권한 확인 (Day 2 추가)
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
            # 테이블이 없을 수 있음 (Day 2 미적용)
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
        if result and result[2] is not None:
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

        # 기본값
        return {
            'source': 'none',
            'can_view': False,
            'can_create': False,
            'can_edit': False,
            'can_delete': False,
            'data_scope': 'none'
        }

    def _log_access(self, emp_id, action, menu_code, success, error_message=None):
        """접근 로그 기록 (운영환경 강화)"""
        # 테스트 사용자는 로그 제외 옵션
        if not self.is_production:
            test_users = ['admin', 'test_user', 'test_partner']
            if emp_id in test_users:
                return

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_name = 'access_audit_log'
                )
            """)

            if not cursor.fetchone()[0]:
                logger.debug("access_audit_log table not found, skipping log")
                return

            ip_address = request.remote_addr if request else None
            resource_id = request.args.get('id') if request else None

            cursor.execute("""
                INSERT INTO access_audit_log
                (emp_id, login_id, action, menu_code, resource_id, ip_address, success, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                emp_id,
                session.get('user_id'),
                action,
                menu_code,
                resource_id,
                ip_address,
                success,
                error_message
            ))

            conn.commit()

        except Exception as e:
            logger.error(f"Access log error: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _send_permission_alert(self, emp_id, menu_code, action):
        """운영환경 권한 거부 알림"""
        if self.is_production:
            # 실제 구현 시 이메일/SMS 발송
            logger.critical(f"PERMISSION DENIED: {emp_id} tried {action} on {menu_code}")

    def _send_error_alert(self, error_msg):
        """운영환경 에러 알림"""
        if self.is_production:
            logger.critical(f"PERMISSION SYSTEM ERROR: {error_msg}")

# 안전한 인스턴스 생성
safe_permission_service = SafePermissionService()
check_permission = safe_permission_service.check_permission

# 기존 코드 호환성을 위한 별칭
permission_service = safe_permission_service