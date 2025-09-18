#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
통합 권한 시스템 - 핵심 모듈
기존 permission_utils.py를 기반으로 정리된 단일 진입점
"""

import psycopg2
from flask import session, abort, g
from functools import wraps
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

class UnifiedPermissionSystem:
    """통합 권한 관리 시스템"""

    def __init__(self):
        self.cache = {}
        self.cache_expiry = {}
        self.cache_ttl = 300  # 5분

    def get_db_connection(self):
        """데이터베이스 연결 - db_connection.py 사용"""
        from db_connection import get_db_connection
        return get_db_connection()

    def check_permission(self, emp_id, menu_code, action):
        """
        권한 체크 - 3단계 우선순위
        1. 개인별 권한
        2. 부서별 권한
        3. 역할별 권한
        """
        # 캐시 확인
        cache_key = f"{emp_id}:{menu_code}"
        if cache_key in self.cache:
            if datetime.now() < self.cache_expiry.get(cache_key, datetime.min):
                cached = self.cache[cache_key]
                return cached.get(action, False)

        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # 1. 개인별 권한 확인
            cursor.execute("""
                SELECT can_view, can_create, can_edit, can_delete
                FROM user_menu_permissions
                WHERE emp_id = %s AND menu_code = %s
            """, (emp_id, menu_code))

            result = cursor.fetchone()
            if result:
                permissions = {
                    'read': result[0],
                    'create': result[1],
                    'update': result[2],
                    'delete': result[3]
                }
                self._cache_permissions(cache_key, permissions)
                cursor.close()
                conn.close()
                return permissions.get(action, False)

            # 2. 부서별 권한 확인
            cursor.execute("""
                SELECT d.can_view, d.can_create, d.can_edit, d.can_delete
                FROM system_users u
                JOIN dept_menu_permissions d ON u.department = d.department_name
                WHERE u.emp_id = %s AND d.menu_code = %s
            """, (emp_id, menu_code))

            result = cursor.fetchone()
            if result:
                permissions = {
                    'read': result[0],
                    'create': result[1],
                    'update': result[2],
                    'delete': result[3]
                }
                self._cache_permissions(cache_key, permissions)
                cursor.close()
                conn.close()
                return permissions.get(action, False)

            # 3. 역할별 권한 확인
            cursor.execute("""
                SELECT r.can_view, r.can_create, r.can_edit, r.can_delete
                FROM system_users u
                JOIN role_menu_permissions r ON u.role = r.role_id
                WHERE u.emp_id = %s AND r.menu_code = %s
            """, (emp_id, menu_code))

            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if result:
                permissions = {
                    'read': result[0],
                    'create': result[1],
                    'update': result[2],
                    'delete': result[3]
                }
                self._cache_permissions(cache_key, permissions)
                return permissions.get(action, False)

            return False

        except Exception as e:
            logger.error(f"Permission check error: {e}")
            return False

    def _cache_permissions(self, key, permissions):
        """권한 캐싱"""
        self.cache[key] = permissions
        self.cache_expiry[key] = datetime.now() + timedelta(seconds=self.cache_ttl)

    def clear_cache(self, emp_id=None):
        """캐시 정리"""
        if emp_id:
            keys_to_remove = [k for k in self.cache if k.startswith(f"{emp_id}:")]
            for key in keys_to_remove:
                self.cache.pop(key, None)
                self.cache_expiry.pop(key, None)
        else:
            self.cache.clear()
            self.cache_expiry.clear()

    def get_user_menus(self, emp_id):
        """사용자가 접근 가능한 메뉴 목록"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            # 개인, 부서, 역할 권한 통합 조회
            cursor.execute("""
                WITH user_accessible_menus AS (
                    -- 개인별 권한
                    SELECT DISTINCT menu_code
                    FROM user_menu_permissions
                    WHERE emp_id = %s AND can_view = true

                    UNION

                    -- 부서별 권한
                    SELECT DISTINCT d.menu_code
                    FROM system_users u
                    JOIN dept_menu_permissions d ON u.department = d.department_name
                    WHERE u.emp_id = %s AND d.can_view = true

                    UNION

                    -- 역할별 권한
                    SELECT DISTINCT r.menu_code
                    FROM system_users u
                    JOIN role_menu_permissions r ON u.role = r.role_id
                    WHERE u.emp_id = %s AND r.can_view = true
                )
                SELECT menu_code FROM user_accessible_menus
                ORDER BY menu_code
            """, (emp_id, emp_id, emp_id))

            menus = [row[0] for row in cursor.fetchall()]
            cursor.close()
            conn.close()

            return menus

        except Exception as e:
            logger.error(f"Error getting user menus: {e}")
            return []

    def log_access(self, emp_id, menu_code, action, success, ip_address=None):
        """접근 로그 기록"""
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO access_audit_log
                (emp_id, accessed_menu, action, success, ip_address, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (emp_id, menu_code, action, success, ip_address))

            conn.commit()
            cursor.close()
            conn.close()

        except Exception as e:
            logger.error(f"Error logging access: {e}")

# 싱글톤 인스턴스
_permission_system = None

def get_permission_system():
    """권한 시스템 싱글톤 인스턴스"""
    global _permission_system
    if _permission_system is None:
        _permission_system = UnifiedPermissionSystem()
    return _permission_system

# Flask 데코레이터
def require_permission(menu_code, action='read'):
    """
    권한 체크 데코레이터

    사용법:
    @app.route('/accident/delete/<id>')
    @require_permission('accident', 'delete')
    def delete_accident(id):
        pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            emp_id = session.get('emp_id')
            if not emp_id:
                abort(401)  # Unauthorized

            perm_system = get_permission_system()

            if not perm_system.check_permission(emp_id, menu_code, action):
                # 로그 기록
                ip = request.remote_addr if 'request' in globals() else None
                perm_system.log_access(emp_id, menu_code, action, False, ip)
                abort(403)  # Forbidden

            # 성공 로그
            ip = request.remote_addr if 'request' in globals() else None
            perm_system.log_access(emp_id, menu_code, action, True, ip)

            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 편의 함수들 (기존 permission_utils.py 호환성)
def check_permission(emp_id, menu_code, action):
    """권한 체크 - 기존 코드 호환용"""
    system = get_permission_system()
    return system.check_permission(emp_id, menu_code, action)

def get_user_menus(emp_id):
    """사용자 메뉴 조회 - 기존 코드 호환용"""
    system = get_permission_system()
    return system.get_user_menus(emp_id)

def clear_user_cache(emp_id=None):
    """캐시 정리 - 기존 코드 호환용"""
    system = get_permission_system()
    system.clear_cache(emp_id)