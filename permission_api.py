#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 관리 API 엔드포인트
사용자별/부서별 권한 관리
"""

from flask import jsonify, request, session
from db_connection import get_db_connection
from permission_helpers import is_super_admin, resolve_menu_code
from config.menu import MENU_CONFIG
from functools import wraps
from typing import Any, List
import logging

logger = logging.getLogger(__name__)


def _row_value(row, index, key):
    """Helper to read from tuple-like or dict-like cursor rows."""
    if row is None:
        return None
    if hasattr(row, 'keys'):
        if hasattr(row, 'get'):
            return row.get(key)
        try:
            return row[key]
        except Exception:
            pass
    return row[index]


def _normalize_level(value, upper=4):
    """Convert arbitrary input to an integer permission level within range."""
    try:
        level = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(upper, level))


def _flatten_menu_codes():
    codes = []
    for section in MENU_CONFIG:
        for item in section.get('submenu', []):
            slug = item.get('url')
            if not slug:
                continue
            normalized = resolve_menu_code(slug)
            if normalized:
                codes.append(normalized)
    return codes


def _build_menu_title_map():
    mapping = {}
    for section in MENU_CONFIG:
        title = section.get('title', '')
        for item in section.get('submenu', []):
            slug = item.get('url')
            name = item.get('title') or title
            if not slug:
                continue
            normalized = resolve_menu_code(slug)
            if normalized:
                mapping[normalized] = name
                # 기존 슬러그로 저장된 데이터와의 호환성을 위해 슬러그도 매핑
                mapping[slug] = name
    return mapping


def _admin_required(func):
    """Ensure route is accessible only to admin-authenticated or super admin users."""

    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            if session.get('admin_authenticated') or is_super_admin():
                return func(*args, **kwargs)
        except Exception as exc:  # pragma: no cover - guard against unexpected session issues
            logger.debug("admin check failed: %s", exc)
        return jsonify({'error': '관리자 권한이 필요합니다.'}), 403

    return wrapper

def register_permission_routes(app):
    """권한 관리 API 라우트 등록"""

    menu_codes = set(_flatten_menu_codes())
    menu_title_map = _build_menu_title_map()

    @app.route('/api/menu-roles/users', methods=['GET'])
    @_admin_required
    def get_user_permissions():
        """사용자별 권한 목록 조회"""
        conn = None
        cursor = None
        try:
            try:
                page = int(request.args.get('page', 1))
            except (TypeError, ValueError):
                page = 1
            page = max(1, page)

            try:
                size = int(request.args.get('size', 500))
            except (TypeError, ValueError):
                size = 500
            size = max(1, min(500, size))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            search_login = (request.args.get('login') or '').strip().lower()
            search_name = (request.args.get('name') or '').strip().lower()
            search_dept = (request.args.get('dept') or '').strip().lower()

            where_clauses = [
                "u.is_active = TRUE",
                "u.login_id IS NOT NULL"
            ]
            params: List[Any] = []

            if search_login:
                where_clauses.append("LOWER(u.login_id) LIKE %s")
                params.append(f"%{search_login}%")

            if search_name:
                where_clauses.append("LOWER(u.user_name) LIKE %s")
                params.append(f"%{search_name}%")

            if search_dept:
                where_clauses.append("LOWER(COALESCE(d.dept_name, u.dept_name)) LIKE %s")
                params.append(f"%{search_dept}%")

            where_sql = " AND ".join(where_clauses)

            count_sql = f"""
                SELECT COUNT(*) AS total
                  FROM system_users u
                  LEFT JOIN departments_external d
                    ON d.dept_id = u.dept_id AND d.is_active = TRUE
                 WHERE {where_sql}
            """
            cursor.execute(count_sql, params)
            total_row = cursor.fetchone()
            total = _row_value(total_row, 0, 'total') or 0

            data_params = list(params)
            data_params.extend([size, offset])

            data_sql = f"""
                SELECT
                    u.login_id,
                    u.emp_id,
                    u.user_name,
                    u.dept_id,
                    u.dept_name,
                    COALESCE(d.dept_code, u.dept_id) AS dept_code,
                    d.dept_full_path
                FROM system_users u
                LEFT JOIN departments_external d
                    ON d.dept_id = u.dept_id AND d.is_active = TRUE
                WHERE {where_sql}
                ORDER BY COALESCE(u.user_name, '') ASC, u.login_id
                LIMIT %s OFFSET %s
            """
            cursor.execute(data_sql, data_params)
            rows = cursor.fetchall()

            user_map = {}
            login_ids = []
            for row in rows:
                login_id = _row_value(row, 0, 'login_id')
                if not login_id:
                    continue
                if login_id not in user_map:
                    login_ids.append(login_id)
                    user_map[login_id] = {
                        'login_id': login_id,
                        'emp_id': _row_value(row, 1, 'emp_id'),
                        'name': _row_value(row, 2, 'user_name'),
                        'dept_id': _row_value(row, 3, 'dept_id'),
                        'dept_name': _row_value(row, 4, 'dept_name'),
                        'dept_code': _row_value(row, 5, 'dept_code'),
                        'dept_full_path': _row_value(row, 6, 'dept_full_path'),
                        'permissions': {}
                    }

            if login_ids:
                params_list = list(login_ids)
                if params_list:
                    placeholders = ','.join(['%s'] * len(params_list))
                    cursor.execute(
                        f"""
                        SELECT login_id, menu_code, read_level, write_level
                        FROM user_menu_permissions
                        WHERE is_active = TRUE
                          AND login_id IN ({placeholders})
                        """,
                        params_list,
                    )
                    perm_rows = cursor.fetchall()
                else:
                    perm_rows = []
                for perm_row in perm_rows:
                    login_id = _row_value(perm_row, 0, 'login_id')
                    menu_code = _row_value(perm_row, 1, 'menu_code')
                    normalized_code = resolve_menu_code(menu_code) if menu_code else ''
                    if not login_id or not normalized_code:
                        continue
                    read_level = _normalize_level(_row_value(perm_row, 2, 'read_level'), upper=3)
                    write_level = _normalize_level(_row_value(perm_row, 3, 'write_level'))
                    user_entry = user_map.get(login_id)
                    if user_entry is None:
                        continue
                    user_entry['permissions'][normalized_code] = {
                        'read_level': read_level,
                        'write_level': write_level,
                    }

            items = list(user_map.values())
            return jsonify({
                'items': items,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as exc:
            logger.error("Error getting user permissions: %s", exc)
            return jsonify({
                'error': '권한 조회 실패',
                'message': str(exc)
            }), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/departments', methods=['GET'])
    @_admin_required
    def get_dept_permissions():
        """부서별 권한 목록 조회"""
        conn = None
        cursor = None
        try:
            try:
                page = int(request.args.get('page', 1))
            except (TypeError, ValueError):
                page = 1
            page = max(1, page)

            try:
                size = int(request.args.get('size', 500))
            except (TypeError, ValueError):
                size = 500
            size = max(1, min(500, size))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            search_name = (request.args.get('name') or '').strip().lower()

            dept_where = ["is_active = TRUE"]
            dept_params: List[Any] = []

            if search_name:
                dept_where.append("(LOWER(dept_name) LIKE %s OR LOWER(dept_code) LIKE %s)")
                dept_params.extend([f"%{search_name}%", f"%{search_name}%"])

            dept_where_sql = " AND ".join(dept_where)

            cursor.execute(
                f"""
                SELECT COUNT(*) AS total
                  FROM departments_external
                 WHERE {dept_where_sql}
                """,
                dept_params,
            )
            total_row = cursor.fetchone()
            total = _row_value(total_row, 0, 'total') or 0

            dept_params_with_limit = list(dept_params)
            dept_params_with_limit.extend([size, offset])

            cursor.execute(
                f"""
                SELECT
                    dept_id,
                    dept_code,
                    dept_name,
                    parent_dept_code,
                    dept_full_path,
                    dept_level
                FROM departments_external
                WHERE {dept_where_sql}
                ORDER BY COALESCE(dept_full_path, dept_code) ASC, dept_code
                LIMIT %s OFFSET %s
                """,
                dept_params_with_limit,
            )
            rows = cursor.fetchall()

            dept_map = {}
            dept_ids = []
            for row in rows:
                dept_id = _row_value(row, 0, 'dept_id')
                if not dept_id:
                    continue
                if dept_id not in dept_map:
                    dept_ids.append(dept_id)
                    dept_map[dept_id] = {
                        'sso_dept_id': dept_id,
                        'dept_id': dept_id,
                        'dept_code': _row_value(row, 1, 'dept_code'),
                        'dept_name': _row_value(row, 2, 'dept_name'),
                        'parent_dept_code': _row_value(row, 3, 'parent_dept_code'),
                        'dept_full_path': _row_value(row, 4, 'dept_full_path'),
                        'dept_level': _row_value(row, 5, 'dept_level'),
                        'permissions': {}
                    }

            if dept_ids:
                params_list = list(dept_ids)
                if params_list:
                    placeholders = ','.join(['%s'] * len(params_list))
                    cursor.execute(
                        f"""
                        SELECT dept_id, menu_code, read_level, write_level
                        FROM dept_menu_roles
                        WHERE is_active = TRUE
                          AND dept_id IN ({placeholders})
                        """,
                        params_list,
                    )
                    perm_rows = cursor.fetchall()
                else:
                    perm_rows = []
                for perm_row in perm_rows:
                    dept_id = _row_value(perm_row, 0, 'dept_id')
                    menu_code = _row_value(perm_row, 1, 'menu_code')
                    normalized_code = resolve_menu_code(menu_code) if menu_code else ''
                    if not dept_id or not normalized_code:
                        continue
                    read_level = _normalize_level(_row_value(perm_row, 2, 'read_level'), upper=3)
                    write_level = _normalize_level(_row_value(perm_row, 3, 'write_level'))
                    dept_entry = dept_map.get(dept_id)
                    if dept_entry is None:
                        continue
                    dept_entry['permissions'][normalized_code] = {
                        'read_level': read_level,
                        'write_level': write_level,
                    }

            items = list(dept_map.values())
            return jsonify({
                'items': items,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as exc:
            logger.error("Error getting department permissions: %s", exc)
            return jsonify({
                'error': '부서 권한 조회 실패',
                'message': str(exc)
            }), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/batch-update', methods=['POST'])
    @_admin_required
    def batch_update_user_permissions():
        """사용자 권한을 일괄 저장/업데이트"""
        payload = request.get_json(silent=True) or {}
        changes = payload.get('changes')

        if not isinstance(changes, list) or not changes:
            return jsonify({'error': '변경사항이 없습니다.'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            updated_by = session.get('user_id') or 'system'
            super_flag = False
            try:
                super_flag = is_super_admin()
            except Exception:
                super_flag = False

            affected = 0
            valid_menu_codes = menu_codes

            for change in changes:
                if not isinstance(change, dict):
                    continue
                login_id = change.get('login_id') or change.get('user_id') or ''
                raw_menu_code = change.get('menu_code') or ''
                normalized_code = resolve_menu_code(raw_menu_code)
                if not login_id or not normalized_code:
                    continue
                if valid_menu_codes and normalized_code not in valid_menu_codes:
                    continue

                read_level = _normalize_level(change.get('read_level'), upper=3)
                write_level = _normalize_level(change.get('write_level'))
                if write_level == 4 and not super_flag:
                    return jsonify({'error': '관리자(4) 권한은 슈퍼어드민만 설정할 수 있습니다.'}), 403

                cursor.execute(
                    """
                    INSERT INTO user_menu_permissions
                        (login_id, menu_code, read_level, write_level, updated_at, is_active)
                    VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                    ON CONFLICT (login_id, menu_code)
                    DO UPDATE SET
                        read_level = EXCLUDED.read_level,
                        write_level = EXCLUDED.write_level,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                    """,
                    (login_id, normalized_code, read_level, write_level),
                )
                affected += 1

            conn.commit()
            return jsonify({'success': True, 'count': affected})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error batch updating user permissions: %s", exc)
            return jsonify({'error': '사용자 권한 저장 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/users/delete', methods=['POST'])
    @_admin_required
    def delete_user_permissions_bulk():
        """선택한 사용자 권한을 비활성화"""
        payload = request.get_json(silent=True) or {}
        login_ids = payload.get('login_ids')

        if not isinstance(login_ids, list) or not login_ids:
            return jsonify({'error': 'login_ids가 필요합니다.'}), 400

        filtered_ids = [str(lid).strip() for lid in login_ids if str(lid).strip()]
        if not filtered_ids:
            return jsonify({'error': '유효한 login_ids가 없습니다.'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            placeholders = ','.join(['%s'] * len(filtered_ids))
            cursor.execute(
                f"""
                UPDATE user_menu_permissions
                   SET is_active = FALSE,
                       read_level = 0,
                       write_level = 0,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE login_id IN ({placeholders})
                """,
                filtered_ids,
            )
            affected = cursor.rowcount or 0
            conn.commit()

            logger.info(
                "User permissions deactivated: ids=%s affected=%s",
                filtered_ids,
                affected,
            )
            return jsonify({'success': True, 'affected': affected})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error deleting user permissions: %s", exc)
            return jsonify({'error': '사용자 권한 삭제 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/dept-roles/batch-update', methods=['POST'])
    @_admin_required
    def batch_update_dept_permissions():
        """부서 권한을 일괄 저장/업데이트"""
        payload = request.get_json(silent=True) or {}
        changes = payload.get('changes')

        if not isinstance(changes, list) or not changes:
            return jsonify({'error': '변경사항이 없습니다.'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            updated_by = session.get('user_id') or 'system'

            affected = 0
            valid_menu_codes = menu_codes
            dept_cache = {}

            for change in changes:
                if not isinstance(change, dict):
                    continue
                dept_id = change.get('dept_id') or change.get('sso_dept_id') or ''
                raw_menu_code = change.get('menu_code') or ''
                normalized_code = resolve_menu_code(raw_menu_code)
                if not dept_id or not normalized_code:
                    continue
                if valid_menu_codes and normalized_code not in valid_menu_codes:
                    continue

                read_level = _normalize_level(change.get('read_level'), upper=3)
                write_level = _normalize_level(change.get('write_level'))

                if dept_id not in dept_cache:
                    cursor.execute(
                        """
                        SELECT dept_code, dept_full_path
                        FROM departments_external
                        WHERE dept_id = %s AND is_active = TRUE
                        """,
                        (dept_id,),
                    )
                    dept_row = cursor.fetchone()
                    if not dept_row:
                        dept_cache[dept_id] = None
                    else:
                        dept_cache[dept_id] = (
                            _row_value(dept_row, 0, 'dept_code'),
                            _row_value(dept_row, 1, 'dept_full_path'),
                        )

                cache_entry = dept_cache.get(dept_id)
                if not cache_entry:
                    continue
                dept_code, dept_full_path = cache_entry

                cursor.execute(
                    """
                    INSERT INTO dept_menu_roles
                        (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level, updated_at, is_active)
                    VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                    ON CONFLICT (dept_id, menu_code)
                    DO UPDATE SET
                        dept_code = EXCLUDED.dept_code,
                        dept_full_path = EXCLUDED.dept_full_path,
                        read_level = EXCLUDED.read_level,
                        write_level = EXCLUDED.write_level,
                        updated_at = CURRENT_TIMESTAMP,
                        is_active = TRUE
                    """,
                    (dept_id, dept_code, dept_full_path, normalized_code, read_level, write_level),
                )
                affected += 1

            conn.commit()
            return jsonify({'success': True, 'count': affected})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error batch updating department permissions: %s", exc)
            return jsonify({'error': '부서 권한 저장 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/dept-roles/delete', methods=['POST'])
    @_admin_required
    def delete_dept_permissions_bulk():
        """선택한 부서 권한을 비활성화"""
        payload = request.get_json(silent=True) or {}
        dept_ids = payload.get('dept_ids')

        if not isinstance(dept_ids, list) or not dept_ids:
            return jsonify({'error': 'dept_ids가 필요합니다.'}), 400

        filtered_ids = [str(dept).strip() for dept in dept_ids if str(dept).strip()]
        if not filtered_ids:
            return jsonify({'error': '유효한 dept_ids가 없습니다.'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            placeholders = ','.join(['%s'] * len(filtered_ids))
            cursor.execute(
                f"""
                UPDATE dept_menu_roles
                   SET is_active = FALSE,
                       read_level = 0,
                       write_level = 0,
                       granted_by = %s,
                       updated_at = CURRENT_TIMESTAMP
                 WHERE dept_id IN ({placeholders})
                """,
                [session.get('user_id', 'system'), *filtered_ids],
            )
            affected = cursor.rowcount or 0
            conn.commit()

            logger.info(
                "Department permissions deactivated: ids=%s affected=%s",
                filtered_ids,
                affected,
            )
            return jsonify({'success': True, 'affected': affected})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error deleting department permissions: %s", exc)
            return jsonify({'error': '부서 권한 삭제 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/users/<user_id>', methods=['POST'])
    @_admin_required
    def save_user_permission(user_id):
        """사용자 권한 저장/업데이트"""
        data = request.get_json(silent=True) or {}
        raw_menu_code = (data.get('menu_code') or '').strip()
        menu_code = resolve_menu_code(raw_menu_code)
        if not menu_code:
            return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

        valid_menu_codes = menu_codes
        if valid_menu_codes and menu_code not in valid_menu_codes:
            return jsonify({'error': '알 수 없는 메뉴 코드입니다'}), 400

        read_level = _normalize_level(data.get('read_level'), upper=3)
        write_level = _normalize_level(data.get('write_level'))

        super_flag = False
        try:
            super_flag = is_super_admin()
        except Exception as exc:
            logger.debug("super admin check failed: %s", exc)
        if write_level == 4 and not super_flag:
            return jsonify({'error': '관리자(4) 권한은 슈퍼어드민만 설정할 수 있습니다.'}), 403

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, granted_by, updated_at, is_active)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                ON CONFLICT (login_id, menu_code)
                DO UPDATE SET
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    granted_by = EXCLUDED.granted_by,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = TRUE
                """,
                (user_id, menu_code, read_level, write_level, session.get('user_id', 'system')),
            )

            conn.commit()
            logger.info(
                "Permission updated: user=%s, menu=%s, read=%s, write=%s",
                user_id,
                menu_code,
                read_level,
                write_level,
            )
            return jsonify({'status': 'success', 'message': '권한이 저장되었습니다'})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error saving user permission: %s", exc)
            return jsonify({'error': '권한 저장 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/departments/<dept_id>', methods=['POST'])
    @_admin_required
    def save_dept_permission(dept_id):
        """부서 권한 저장/업데이트"""
        data = request.get_json(silent=True) or {}
        raw_menu_code = (data.get('menu_code') or '').strip()
        menu_code = resolve_menu_code(raw_menu_code)
        if not menu_code:
            return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

        valid_menu_codes = menu_codes
        if valid_menu_codes and menu_code not in valid_menu_codes:
            return jsonify({'error': '알 수 없는 메뉴 코드입니다'}), 400

        read_level = _normalize_level(data.get('read_level'), upper=3)
        write_level = _normalize_level(data.get('write_level'))

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT dept_code, dept_full_path
                FROM departments_external
                WHERE dept_id = %s AND is_active = TRUE
                """,
                (dept_id,),
            )
            dept_row = cursor.fetchone()

            dept_code = data.get('dept_code') if isinstance(data, dict) else None
            dept_full_path = data.get('dept_full_path') if isinstance(data, dict) else None

            if dept_row:
                dept_code = _row_value(dept_row, 0, 'dept_code') or dept_code
                dept_full_path = _row_value(dept_row, 1, 'dept_full_path') or dept_full_path

            if not dept_code:
                return jsonify({'error': '부서 정보를 찾을 수 없습니다'}), 404

            cursor.execute(
                """
                INSERT INTO dept_menu_roles
                    (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level, granted_by, updated_at, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                ON CONFLICT (dept_id, menu_code)
                DO UPDATE SET
                    dept_code = EXCLUDED.dept_code,
                    dept_full_path = EXCLUDED.dept_full_path,
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    granted_by = EXCLUDED.granted_by,
                    updated_at = CURRENT_TIMESTAMP,
                    is_active = TRUE
                """,
                (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level, session.get('user_id', 'system')),
            )

            conn.commit()
            logger.info(
                "Department permission updated: dept=%s, menu=%s, read=%s, write=%s",
                dept_id,
                menu_code,
                read_level,
                write_level,
            )
            return jsonify({'status': 'success', 'message': '부서 권한이 저장되었습니다'})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error saving department permission: %s", exc)
            return jsonify({'error': '부서 권한 저장 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/users/<user_id>', methods=['DELETE'])
    @_admin_required
    def delete_user_permissions(user_id):
        """사용자 권한 삭제 (soft delete)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Soft delete: is_active를 false로 설정
            cursor.execute("""
                UPDATE user_menu_permissions
                SET is_active = false,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = %s
                WHERE login_id = %s
            """, (session.get('user_id', 'system'), user_id))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"User permissions deleted (soft): user={user_id}, affected={affected}")
            return jsonify({
                'status': 'success',
                'message': f'{affected}개 권한이 삭제되었습니다'
            })

        except Exception as e:
            logger.error(f"Error deleting user permissions: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 삭제 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/departments/<dept_id>', methods=['DELETE'])
    @_admin_required
    def delete_dept_permissions(dept_id):
        """부서 권한 삭제 (soft delete)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Soft delete
            cursor.execute("""
                UPDATE dept_menu_roles
                SET is_active = false,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = %s
                WHERE dept_id = %s
            """, (session.get('user_id', 'system'), dept_id))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Department permissions deleted (soft): dept={dept_id}, affected={affected}")
            return jsonify({
                'status': 'success',
                'message': f'{affected}개 부서 권한이 삭제되었습니다'
            })

        except Exception as e:
            logger.error(f"Error deleting department permissions: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '부서 권한 삭제 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/stats', methods=['GET'])
    @_admin_required
    def get_permission_stats():
        """권한 설정 대시보드를 위한 간단한 통계"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """SELECT COUNT(*) AS total FROM system_users WHERE is_active = TRUE AND login_id IS NOT NULL"""
            )
            users_row = cursor.fetchone()
            total_users = _row_value(users_row, 0, 'total') or 0

            cursor.execute(
                """SELECT COUNT(*) AS total FROM departments_external WHERE is_active = TRUE"""
            )
            depts_row = cursor.fetchone()
            total_depts = _row_value(depts_row, 0, 'total') or 0

            total_menus = len(menu_codes)

            return jsonify({
                'users': total_users,
                'depts': total_depts,
                'menus': total_menus
            })

        except Exception as exc:
            logger.error("Error getting permission stats: %s", exc)
            return jsonify({'error': '통계 조회 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/dept-permissions/tree', methods=['GET'])
    @_admin_required
    def get_dept_tree():
        """부서 트리 구조를 계층적으로 반환"""
        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT dept_id, dept_code, dept_name, parent_dept_code, dept_full_path, dept_level
                FROM departments_external
                WHERE is_active = TRUE
                ORDER BY COALESCE(dept_full_path, dept_code)
                """
            )
            rows = cursor.fetchall()

            nodes_by_code = {}
            ordered_nodes = []

            for row in rows:
                dept_code = _row_value(row, 1, 'dept_code')
                if not dept_code:
                    continue
                node = {
                    'sso_dept_id': _row_value(row, 0, 'dept_id'),
                    'dept_id': _row_value(row, 0, 'dept_id'),
                    'dept_code': dept_code,
                    'dept_name': _row_value(row, 2, 'dept_name'),
                    'parent_dept_code': _row_value(row, 3, 'parent_dept_code'),
                    'dept_full_path': _row_value(row, 4, 'dept_full_path'),
                    'dept_level': _row_value(row, 5, 'dept_level'),
                    'children': []
                }
                nodes_by_code[dept_code] = node
                ordered_nodes.append((dept_code, node, _row_value(row, 3, 'parent_dept_code')))

            roots = []
            for dept_code, node, parent_code in ordered_nodes:
                if parent_code and parent_code in nodes_by_code:
                    nodes_by_code[parent_code]['children'].append(node)
                else:
                    roots.append(node)

            return jsonify({'success': True, 'data': roots})

        except Exception as exc:
            logger.error("Error building department tree: %s", exc)
            return jsonify({'success': False, 'error': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/dept-permissions/apply', methods=['POST'])
    @_admin_required
    def apply_dept_permissions_bulk():
        """선택한 부서 및 하위 부서에 권한을 일괄 적용"""
        payload = request.get_json(silent=True) or {}
        departments = payload.get('departments') or []
        permissions_map = payload.get('permissions') or {}
        apply_to_children = bool(payload.get('apply_to_children'))

        if not departments or not isinstance(permissions_map, dict):
            return jsonify({'error': '부서 또는 권한 정보가 부족합니다'}), 400

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            updated_by = session.get('user_id') or 'system'

            affected = 0

            for dept in departments:
                if not isinstance(dept, dict):
                    continue
                dept_id = dept.get('sso_dept_id') or dept.get('dept_id')
                if not dept_id:
                    continue

                dept_permissions = permissions_map.get(dept_id)
                if dept_permissions is None:
                    dept_permissions = permissions_map.get(str(dept_id))
                if not isinstance(dept_permissions, dict):
                    continue

                cursor.execute(
                    """
                    SELECT dept_code, dept_full_path
                    FROM departments_external
                    WHERE dept_id = %s AND is_active = TRUE
                    """,
                    (dept_id,),
                )
                dept_row = cursor.fetchone()
                if not dept_row:
                    continue

                dept_code = _row_value(dept_row, 0, 'dept_code')
                dept_full_path = _row_value(dept_row, 1, 'dept_full_path')

                child_rows = []
                if apply_to_children and dept_full_path:
                    cursor.execute(
                        """
                        SELECT dept_id, dept_code, dept_full_path
                        FROM departments_external
                        WHERE dept_full_path LIKE %s
                          AND dept_id <> %s
                          AND is_active = TRUE
                        """,
                        (f"{dept_full_path}|%", dept_id),
                    )
                    child_rows = cursor.fetchall() or []

                for menu_code, level_value in dept_permissions.items():
                    normalized_code = resolve_menu_code(menu_code)
                    if not normalized_code:
                        continue
                    if menu_codes and normalized_code not in menu_codes:
                        continue
                    level = _normalize_level(level_value)
                    cursor.execute(
                        """
                        INSERT INTO dept_menu_roles
                            (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level, granted_by,
                             updated_at, is_active)
                        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                        ON CONFLICT (dept_id, menu_code)
                        DO UPDATE SET
                            dept_code = EXCLUDED.dept_code,
                            dept_full_path = EXCLUDED.dept_full_path,
                            read_level = EXCLUDED.read_level,
                            write_level = EXCLUDED.write_level,
                            granted_by = EXCLUDED.granted_by,
                            updated_at = CURRENT_TIMESTAMP,
                            is_active = TRUE
                        """,
                        (dept_id, dept_code, dept_full_path, normalized_code, level, level, updated_by),
                    )
                    affected += 1

                    for child_row in child_rows:
                        child_id = _row_value(child_row, 0, 'dept_id')
                        child_code = _row_value(child_row, 1, 'dept_code')
                        child_path = _row_value(child_row, 2, 'dept_full_path')
                        cursor.execute(
                            """
                            INSERT INTO dept_menu_roles
                                (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level,
                                 granted_by, updated_at, is_active)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)
                            ON CONFLICT (dept_id, menu_code)
                            DO UPDATE SET
                                dept_code = EXCLUDED.dept_code,
                                dept_full_path = EXCLUDED.dept_full_path,
                                read_level = EXCLUDED.read_level,
                                write_level = EXCLUDED.write_level,
                                granted_by = EXCLUDED.granted_by,
                                updated_at = CURRENT_TIMESTAMP,
                                is_active = TRUE
                            """,
                            (child_id, child_code, child_path, normalized_code, level, level, updated_by),
                        )
                        affected += 1

            conn.commit()
            return jsonify({'success': True, 'affected_count': affected})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error applying department permissions: %s", exc)
            return jsonify({'error': '권한 적용 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/menu-roles/check', methods=['GET'])
    def check_user_permission():
        """현재 사용자의 특정 메뉴 권한 체크"""
        try:
            raw_menu_code = request.args.get('menu_code')
            menu_code = resolve_menu_code(raw_menu_code) if raw_menu_code else ''
            action = request.args.get('action', 'read')  # read or write

            if not menu_code:
                return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            # scoped_permission_check 모듈 사용
            from scoped_permission_check import get_permission_level

            level = get_permission_level(login_id, dept_id, menu_code, action)

            return jsonify({
                'has_permission': level > 0,
                'level': level,
                'action': action,
                'menu_code': menu_code
            })

        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return jsonify({
                'error': '권한 체크 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/summary', methods=['GET'])
    def get_permission_summary():
        """현재 사용자의 전체 권한 요약"""
        try:
            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            # scoped_permission_check 모듈 사용
            from scoped_permission_check import get_user_permission_summary

            permissions = get_user_permission_summary(login_id, dept_id)

            return jsonify({
                'user_id': login_id,
                'dept_id': dept_id,
                'permissions': permissions
            })

        except Exception as e:
            logger.error(f"Error getting permission summary: {e}")
            return jsonify({
                'error': '권한 요약 조회 실패',
                'message': str(e)
            }), 500

    # ==================== 권한 신청 관련 API ====================

    @app.route('/api/permission-requests', methods=['POST'])
    def create_permission_request():
        """권한 신청 생성"""
        try:
            data = request.json or {}

            login_id = session.get('user_id')
            user_name = session.get('name', '')
            deptid = session.get('deptid', '')
            dept_name = session.get('department', '')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            menu_requests = []
            permission_type = data.get('permission_type')

            if isinstance(data.get('menu_requests'), list):
                for entry in data.get('menu_requests'):
                    if not isinstance(entry, dict):
                        continue
                    code = entry.get('menu_code') or entry.get('code')
                    perm_type = entry.get('permission_type') or entry.get('permission')
                    if isinstance(code, str):
                        code = code.strip()
                    normalized = resolve_menu_code(code) if code else ''
                    if normalized:
                        menu_requests.append((normalized, perm_type))

            if not menu_requests:
                raw_codes = []
                if isinstance(data.get('menu_codes'), list):
                    raw_codes.extend(data.get('menu_codes') or [])
                if data.get('menu_code'):
                    raw_codes.append(data.get('menu_code'))

                for code in raw_codes:
                    if not isinstance(code, str):
                        continue
                    trimmed = code.strip()
                    normalized = resolve_menu_code(trimmed) if trimmed else ''
                    if normalized:
                        menu_requests.append((normalized, permission_type))

            reason = (data.get('reason') or '').strip()

            if not menu_requests:
                return jsonify({'error': '메뉴를 선택해주세요'}), 400
            if data.get('menu_requests') is None and permission_type not in ('read', 'read_write'):
                return jsonify({'error': '권한 유형을 선택해주세요'}), 400
            if not reason or len(reason) < 10:
                return jsonify({'error': '신청 사유를 10자 이상 입력해주세요'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            created_ids = []
            created_menu_codes = []
            skipped = []
            seen_codes = set()

            for menu_code, perm_type in menu_requests:
                if menu_code in seen_codes:
                    continue
                seen_codes.add(menu_code)

                if perm_type not in ('read', 'read_write'):
                    skipped.append({'menu_code': menu_code, 'reason': 'invalid_permission_type'})
                    continue

                cursor.execute("""
                    SELECT id FROM permission_requests
                    WHERE login_id = %s AND menu_code = %s AND status = 'pending'
                """, (login_id, menu_code))

                if cursor.fetchone():
                    skipped.append({'menu_code': menu_code, 'reason': 'already_pending'})
                    continue

                cursor.execute("SELECT menu_name FROM menu_names WHERE menu_code = %s", (menu_code,))
                menu_result = cursor.fetchone()
                if menu_result and menu_result[0]:
                    menu_name = menu_result[0]
                else:
                    menu_name = menu_title_map.get(menu_code, menu_code)

                cursor.execute("""
                    INSERT INTO permission_requests
                    (login_id, user_name, deptid, dept_name, menu_code, menu_name,
                     permission_type, reason, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                    RETURNING id
                """, (login_id, user_name, deptid, dept_name, menu_code, menu_name,
                      perm_type, reason))

                new_id = cursor.fetchone()[0]
                created_ids.append(new_id)
                created_menu_codes.append(menu_code)

            conn.commit()
            cursor.close()
            conn.close()

            if not created_ids:
                return jsonify({
                    'status': 'skipped',
                    'message': '이미 대기 중인 권한 신청이 있습니다.',
                    'skipped_menus': skipped
                }), 200

            logger.info(
                "Permission requests created: count=%s, user=%s, menus=%s",
                len(created_ids),
                login_id,
                created_menu_codes
            )
            return jsonify({
                'status': 'success',
                'message': f'{len(created_ids)}개 권한 신청이 등록되었습니다.',
                'created_ids': created_ids,
                'skipped_menus': skipped
            })

        except Exception as e:
            logger.error(f"Error creating permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 신청 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests', methods=['GET'])
    def get_permission_requests():
        """권한 신청 목록 조회"""
        try:
            status = request.args.get('status', 'pending')  # pending, approved, rejected, all
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 50))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            # WHERE 조건 구성
            where_clause = "WHERE is_active = true"
            params = []

            if status != 'all':
                where_clause += " AND status = %s"
                params.append(status)

            # 전체 카운트
            cursor.execute(f"""
                SELECT COUNT(*) FROM permission_requests {where_clause}
            """, params)
            total = cursor.fetchone()[0]

            # 데이터 조회
            params.extend([size, offset])
            cursor.execute(f"""
                SELECT
                    id, login_id, user_name, deptid, dept_name,
                    menu_code, menu_name, permission_type, reason,
                    status, created_at, reviewed_by, reviewed_at, review_comment
                FROM permission_requests
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)

            rows = cursor.fetchall()
            requests = []

            for row in rows:
                raw_code = row[5]
                menu_code = resolve_menu_code(raw_code) if raw_code else ''
                stored_name = row[6]
                menu_name = stored_name if stored_name else menu_title_map.get(raw_code, menu_title_map.get(menu_code, menu_code))

                requests.append({
                    'id': row[0],
                    'login_id': row[1],
                    'user_name': row[2],
                    'deptid': row[3],
                    'dept_name': row[4],
                    'menu_code': menu_code,
                    'menu_name': menu_name,
                    'permission_type': row[7],
                    'reason': row[8],
                    'status': row[9],
                    'created_at': row[10].isoformat() if row[10] else None,
                    'reviewed_by': row[11],
                    'reviewed_at': row[12].isoformat() if row[12] else None,
                    'review_comment': row[13]
                })

            cursor.close()
            conn.close()

            return jsonify({
                'data': requests,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as e:
            logger.error(f"Error getting permission requests: {e}")
            return jsonify({
                'error': '권한 신청 목록 조회 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/<int:request_id>/approve', methods=['POST'])
    def approve_permission_request(request_id):
        """권한 신청 승인"""
        try:
            data = request.json
            reviewer_id = session.get('user_id')
            review_comment = data.get('comment', '')

            if not reviewer_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            conn = get_db_connection()
            cursor = conn.cursor()

            # 신청 정보 조회
            cursor.execute("""
                SELECT login_id, menu_code, permission_type, status
                FROM permission_requests
                WHERE id = %s AND is_active = true
            """, (request_id,))

            request_row = cursor.fetchone()
            if not request_row:
                cursor.close()
                conn.close()
                logger.warning("Permission request not found: id=%s", request_id)
                return jsonify({'error': '신청을 찾을 수 없습니다'}), 404

            login_id = _row_value(request_row, 0, 'login_id')
            menu_code = _row_value(request_row, 1, 'menu_code')
            permission_type = _row_value(request_row, 2, 'permission_type')
            status = _row_value(request_row, 3, 'status')

            if status != 'pending':
                cursor.close()
                conn.close()
                logger.warning("Permission request already processed: id=%s status=%s", request_id, status)
                return jsonify({
                    'status': 'skipped',
                    'message': '이미 처리된 신청입니다.',
                    'request_id': request_id
                })

            permissions_payload = data.get('permissions') or {}
            payload_entry = permissions_payload.get(menu_code) if isinstance(permissions_payload, dict) else None

            def _sanitize_level(value):
                try:
                    return max(0, min(4, int(value)))
                except (TypeError, ValueError):
                    return 0

            if payload_entry:
                read_level = _sanitize_level(payload_entry.get('read_level'))
                write_level = _sanitize_level(payload_entry.get('write_level'))
            else:
                read_level = 3 if permission_type in ('read', 'read_write') else 0
                write_level = 3 if permission_type == 'read_write' else 0

            if write_level > 0 and read_level == 0:
                read_level = write_level

            # 사용자 권한 업데이트 (UPSERT)
            cursor.execute("""
                INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, updated_at, is_active)
                VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP, true)
                ON CONFLICT (login_id, menu_code)
                DO UPDATE SET
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    updated_at = CURRENT_TIMESTAMP
            """, (login_id, menu_code, read_level, write_level))

            # 신청 상태 업데이트
            cursor.execute("""
                UPDATE permission_requests
                SET status = 'approved',
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_comment = %s
                WHERE id = %s
            """, (reviewer_id, review_comment, request_id))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission request approved: id={request_id}, user={login_id}, menu={menu_code}")
            return jsonify({
                'status': 'success',
                'message': '권한 신청이 승인되었습니다'
            })

        except Exception as e:
            logger.error(f"Error approving permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 승인 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/<int:request_id>/reject', methods=['POST'])
    def reject_permission_request(request_id):
        """권한 신청 거절"""
        try:
            data = request.json
            reviewer_id = session.get('user_id')
            review_comment = data.get('comment', '')

            if not reviewer_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            if not review_comment:
                return jsonify({'error': '거절 사유를 입력해주세요'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # 신청 상태 확인
            cursor.execute("""
                SELECT status FROM permission_requests
                WHERE id = %s AND is_active = true
            """, (request_id,))

            result = cursor.fetchone()
            if not result:
                cursor.close()
                conn.close()
                return jsonify({'error': '신청을 찾을 수 없습니다'}), 404

            if result[0] != 'pending':
                cursor.close()
                conn.close()
                return jsonify({'error': '이미 처리된 신청입니다'}), 400

            # 신청 거절
            cursor.execute("""
                UPDATE permission_requests
                SET status = 'rejected',
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_comment = %s
                WHERE id = %s
            """, (reviewer_id, review_comment, request_id))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission request rejected: id={request_id}")
            return jsonify({
                'status': 'success',
                'message': '권한 신청이 거절되었습니다'
            })

        except Exception as e:
            logger.error(f"Error rejecting permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 거절 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/<int:request_id>/cancel', methods=['POST'])
    def cancel_permission_request(request_id):
        """사용자 본인이 대기중인 권한 신청을 취소"""
        login_id = session.get('user_id')
        if not login_id:
            return jsonify({'error': '로그인이 필요합니다'}), 401

        conn = None
        cursor = None
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT login_id, status
                FROM permission_requests
                WHERE id = %s
                """,
                (request_id,)
            )
            row = cursor.fetchone()
            if not row:
                return jsonify({'error': '신청 내역을 찾을 수 없습니다'}), 404

            owner = row[0]
            status = row[1]
            if owner != login_id:
                return jsonify({'error': '본인이 신청한 권한만 취소할 수 있습니다'}), 403
            if status != 'pending':
                return jsonify({'error': '처리 중이거나 완료된 신청은 취소할 수 없습니다'}), 400

            cursor.execute(
                """
                UPDATE permission_requests
                SET status = 'cancelled',
                    is_active = false,
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_comment = '사용자 취소'
                WHERE id = %s
                """,
                (login_id, request_id)
            )

            conn.commit()
            return jsonify({'status': 'success', 'message': '신청이 취소되었습니다.'})

        except Exception as exc:
            if conn:
                conn.rollback()
            logger.error("Error cancelling permission request: %s", exc)
            return jsonify({'error': '권한 신청 취소 실패', 'message': str(exc)}), 500
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    @app.route('/api/permission-requests/my', methods=['GET'])
    def get_my_permission_requests():
        """내 권한 신청 내역 조회"""
        try:
            login_id = session.get('user_id')
            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id, menu_code, menu_name, permission_type, reason,
                    status, created_at, reviewed_by, reviewed_at, review_comment
                FROM permission_requests
                WHERE login_id = %s AND is_active = true
                ORDER BY created_at DESC
            """, (login_id,))

            rows = cursor.fetchall()
            requests = []

            for row in rows:
                raw_code = row[1]
                menu_code = resolve_menu_code(raw_code) if raw_code else ''
                stored_name = row[2]
                menu_name = stored_name if stored_name else menu_title_map.get(raw_code, menu_title_map.get(menu_code, menu_code))

                requests.append({
                    'id': row[0],
                    'menu_code': menu_code,
                    'menu_name': menu_name,
                    'permission_type': row[3],
                    'reason': row[4],
                    'status': row[5],
                    'created_at': row[6].isoformat() if row[6] else None,
                    'reviewed_by': row[7],
                    'reviewed_at': row[8].isoformat() if row[8] else None,
                    'review_comment': row[9]
                })

            cursor.close()
            conn.close()

            return jsonify({'data': requests})

        except Exception as e:
            logger.error(f"Error getting my permission requests: {e}")
            return jsonify({
                'error': '내 신청 내역 조회 실패',
                'message': str(e)
            }), 500
