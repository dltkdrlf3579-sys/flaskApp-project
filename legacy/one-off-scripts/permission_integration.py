#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 시스템 통합 예시
기존 라우트에 권한 체크를 적용하는 예시 코드
"""

from flask import session, jsonify, request, abort
from functools import wraps
from scoped_permission_check import (
    get_permission_level,
    check_data_access,
    get_data_filter_condition,
    PermissionLevel
)
import logging

logger = logging.getLogger(__name__)

def apply_permission_filters_to_accident_query(query_base, login_id, dept_id):
    """
    사고 목록 쿼리에 권한 필터 적용

    Args:
        query_base: 기본 쿼리 (WHERE 절 이전까지)
        login_id: 현재 로그인 사용자 ID
        dept_id: 현재 사용자 부서 ID

    Returns:
        tuple: (filtered_query, params)
    """
    # 권한 레벨 확인
    level = get_permission_level(login_id, dept_id, 'ACCIDENT_MGT', 'read')

    if level == PermissionLevel.NONE:
        # 권한 없음 - 아무것도 보이지 않음
        return query_base + " WHERE 1=0", []

    elif level == PermissionLevel.SELF:
        # 본인 관련 데이터만
        filter_clause = """
        WHERE (
            reporter_id = %s
            OR accident_manager_id = %s
            OR investigation_manager_id = %s
        )
        """
        params = [login_id, login_id, login_id]
        return query_base + filter_clause, params

    elif level == PermissionLevel.DEPT:
        # 부서 관련 데이터까지
        filter_clause = """
        WHERE (
            reporter_id = %s
            OR accident_manager_id = %s
            OR investigation_manager_id = %s
            OR dept_id = %s
            OR accident_dept_id = %s
        )
        """
        params = [login_id, login_id, login_id, dept_id, dept_id]
        return query_base + filter_clause, params

    else:  # PermissionLevel.ALL
        # 전체 데이터 조회 가능
        return query_base + " WHERE 1=1", []


def check_accident_write_permission(accident_id, login_id, dept_id):
    """
    특정 사고에 대한 쓰기 권한 체크

    Args:
        accident_id: 사고 ID
        login_id: 현재 로그인 사용자 ID
        dept_id: 현재 사용자 부서 ID

    Returns:
        bool: 쓰기 권한 여부
    """
    from db_connection import get_db_connection

    conn = get_db_connection()
    cursor = conn.cursor()

    # 사고 정보 조회
    cursor.execute("""
        SELECT reporter_id, accident_manager_id, dept_id, accident_dept_id
        FROM accidents_cache
        WHERE accident_id = %s
    """, (accident_id,))

    result = cursor.fetchone()
    cursor.close()
    conn.close()

    if not result:
        return False

    # RowCompat 처리
    if hasattr(result, '__getitem__'):
        data_owner = result[0] or result[1]  # reporter_id or accident_manager_id
        data_dept = result[2] or result[3]    # dept_id or accident_dept_id
    else:
        data_owner, manager, data_dept, acc_dept = result
        data_owner = data_owner or manager
        data_dept = data_dept or acc_dept

    # 권한 체크
    return check_data_access(
        login_id=login_id,
        dept_id=dept_id,
        menu_code='ACCIDENT_MGT',
        action='write',
        data_owner=data_owner,
        data_dept=data_dept
    )


def require_accident_read_permission(f):
    """사고 읽기 권한 체크 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        login_id = session.get('user_id')
        dept_id = session.get('deptid')

        if not login_id:
            if request.is_json:
                return jsonify({'error': '로그인이 필요합니다'}), 401
            else:
                abort(401)

        level = get_permission_level(login_id, dept_id, 'ACCIDENT_MGT', 'read')

        if level == PermissionLevel.NONE:
            if request.is_json:
                return jsonify({'error': '사고 조회 권한이 없습니다'}), 403
            else:
                abort(403)

        # 권한 레벨을 request context에 저장
        request.permission_level = level
        return f(*args, **kwargs)

    return decorated_function


def require_accident_write_permission(f):
    """사고 쓰기 권한 체크 데코레이터"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        login_id = session.get('user_id')
        dept_id = session.get('deptid')

        if not login_id:
            if request.is_json:
                return jsonify({'error': '로그인이 필요합니다'}), 401
            else:
                abort(401)

        level = get_permission_level(login_id, dept_id, 'ACCIDENT_MGT', 'write')

        if level == PermissionLevel.NONE:
            if request.is_json:
                return jsonify({'error': '사고 등록/수정 권한이 없습니다'}), 403
            else:
                abort(403)

        # 수정의 경우 추가 체크
        if 'accident_id' in kwargs or request.form.get('accident_id'):
            accident_id = kwargs.get('accident_id') or request.form.get('accident_id')
            if accident_id and not check_accident_write_permission(accident_id, login_id, dept_id):
                if request.is_json:
                    return jsonify({'error': '해당 사고를 수정할 권한이 없습니다'}), 403
                else:
                    abort(403)

        request.permission_level = level
        return f(*args, **kwargs)

    return decorated_function


def get_accident_list_with_permissions(filters=None, page=1, per_page=10):
    """
    권한이 적용된 사고 목록 조회

    Args:
        filters: 검색 필터 딕셔너리
        page: 페이지 번호
        per_page: 페이지당 항목 수

    Returns:
        tuple: (accidents, total_count)
    """
    from db_connection import get_db_connection

    login_id = session.get('user_id')
    dept_id = session.get('deptid')

    if not login_id:
        return [], 0

    conn = get_db_connection()
    cursor = conn.cursor()

    # 기본 쿼리
    base_query = """
        SELECT *
        FROM accidents_cache
    """

    # 권한 필터 적용
    query, params = apply_permission_filters_to_accident_query(
        base_query, login_id, dept_id
    )

    # 추가 필터 적용 (날짜, 사업장 등)
    if filters:
        additional_conditions = []

        if filters.get('accident_date_start'):
            additional_conditions.append("accident_date >= %s")
            params.append(filters['accident_date_start'])

        if filters.get('accident_date_end'):
            additional_conditions.append("accident_date <= %s")
            params.append(filters['accident_date_end'])

        if filters.get('workplace'):
            additional_conditions.append("workplace LIKE %s")
            params.append(f"%{filters['workplace']}%")

        if filters.get('accident_grade'):
            additional_conditions.append("accident_grade = %s")
            params.append(filters['accident_grade'])

        if additional_conditions:
            # WHERE가 이미 있으면 AND로 연결
            if "WHERE" in query:
                query += " AND " + " AND ".join(additional_conditions)
            else:
                query += " WHERE " + " AND ".join(additional_conditions)

    # 정렬 및 페이징
    query += " ORDER BY accident_date DESC"

    # 전체 카운트
    count_query = query.replace("SELECT *", "SELECT COUNT(*)")
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # 페이징 적용
    offset = (page - 1) * per_page
    query += f" LIMIT {per_page} OFFSET {offset}"

    # 실제 데이터 조회
    cursor.execute(query, params)
    accidents = cursor.fetchall()

    cursor.close()
    conn.close()

    return accidents, total_count