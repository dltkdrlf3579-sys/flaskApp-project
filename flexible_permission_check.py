#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
유연한 권한 체크 시스템
config.ini 설정에 따라 각 메뉴별로 권한 체크 방식을 다르게 적용
"""

from flask import session
from db_connection import get_db_connection
import logging
import configparser
import os

logger = logging.getLogger(__name__)

class FlexiblePermissionChecker:
    """유연한 권한 체크 클래스"""

    def __init__(self, config_path='config.ini'):
        """초기화 및 설정 로드"""
        self.config = configparser.ConfigParser()
        self.config.read(config_path, encoding='utf-8')
        self.permission_columns = {}
        self._load_permission_columns()

    def _load_permission_columns(self):
        """config.ini에서 권한 체크 컬럼 설정 로드"""
        if not self.config.has_section('PERMISSION_COLUMNS'):
            # 섹션이 없으면 기본값 사용
            logger.info("PERMISSION_COLUMNS 섹션이 없음. 모든 메뉴에서 레벨 3만 체크합니다.")
            return

        for key, value in self.config.items('PERMISSION_COLUMNS'):
            # 예: ACCIDENT_MGT_owner_column = reporter_id
            # 예: ACCIDENT_MGT_dept_column = dept_id
            if key.endswith('_owner_column') or key.endswith('_dept_column'):
                parts = key.rsplit('_', 2)  # ['ACCIDENT_MGT', 'owner', 'column']
                if len(parts) >= 3:
                    menu_code = parts[0].upper()
                    column_type = parts[1]  # 'owner' or 'dept'

                    if menu_code not in self.permission_columns:
                        self.permission_columns[menu_code] = {}

                    self.permission_columns[menu_code][column_type] = value.strip() if value else None

        logger.info(f"권한 컬럼 설정 로드됨: {self.permission_columns}")

    def get_permission_level(self, login_id, dept_id, menu_code, action='read'):
        """
        사용자의 권한 레벨 조회

        Returns:
            int: 권한 레벨 (0-3)
        """
        if not login_id or not dept_id:
            return 0

        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 개인 권한 레벨
            column = 'read_level' if action == 'read' else 'write_level'
            cursor.execute(f"""
                SELECT {column}
                FROM user_menu_permissions
                WHERE login_id = %s AND menu_code = %s AND is_active = true
            """, (login_id, menu_code))

            user_result = cursor.fetchone()
            user_level = user_result[0] if user_result else 0

            # 부서 권한 레벨
            cursor.execute(f"""
                SELECT {column}
                FROM dept_menu_roles
                WHERE dept_id = %s AND menu_code = %s AND is_active = true
            """, (dept_id, menu_code))

            dept_result = cursor.fetchone()
            dept_level = dept_result[0] if dept_result else 0

            cursor.close()
            conn.close()

            # 더 높은 레벨 반환
            return max(user_level, dept_level)

        except Exception as e:
            logger.error(f"Error getting permission level: {e}")
            return 0

    def check_data_access(self, login_id, dept_id, menu_code, action, data_record=None):
        """
        데이터 접근 권한 체크

        Args:
            login_id: 사용자 ID
            dept_id: 사용자 부서 ID
            menu_code: 메뉴 코드
            action: 'read', 'write', or 'delete'
            data_record: 데이터 레코드 (dict or Row object)

        Returns:
            bool: 접근 가능 여부
        """
        # 권한 레벨 확인
        level = self.get_permission_level(login_id, dept_id, menu_code, action)

        # 레벨 0: 권한 없음
        if level == 0:
            return False

        # 레벨 3: 전체 권한
        if level >= 3:
            return True

        # 해당 메뉴의 컬럼 설정 확인
        menu_columns = self.permission_columns.get(menu_code, {})

        # 컬럼 설정이 없으면 레벨 3만 허용 (현재 대부분의 메뉴)
        if not menu_columns.get('owner') and not menu_columns.get('dept'):
            logger.debug(f"{menu_code}에 컬럼 설정이 없음. 레벨 3만 허용")
            return level >= 3

        # data_record가 없으면 권한 체크 불가
        if not data_record:
            logger.debug(f"데이터 레코드가 없어 권한 체크 불가")
            return False

        # 데이터에서 값 추출
        if hasattr(data_record, '__getitem__'):
            # dict 또는 Row 객체
            owner_column = menu_columns.get('owner')
            dept_column = menu_columns.get('dept')

            data_owner = None
            data_dept = None

            if owner_column:
                if hasattr(data_record, 'get'):  # dict
                    data_owner = data_record.get(owner_column)
                else:  # Row object - 인덱스로 접근 필요
                    try:
                        # 컬럼명으로 접근 시도
                        data_owner = data_record[owner_column]
                    except:
                        pass

            if dept_column:
                if hasattr(data_record, 'get'):  # dict
                    data_dept = data_record.get(dept_column)
                else:  # Row object
                    try:
                        data_dept = data_record[dept_column]
                    except:
                        pass
        else:
            logger.warning(f"알 수 없는 데이터 타입: {type(data_record)}")
            return False

        # 레벨별 권한 체크
        if level == 1:
            # 본인 데이터만 접근 가능
            return data_owner == login_id if data_owner else False
        elif level == 2:
            # 본인 또는 부서 데이터 접근 가능
            if data_owner and data_owner == login_id:
                return True
            if data_dept and data_dept == dept_id:
                return True
            return False

        return False

    def get_data_filter_condition(self, login_id, dept_id, menu_code):
        """
        SQL WHERE 조건 생성

        Returns:
            tuple: (where_clause, params)
        """
        level = self.get_permission_level(login_id, dept_id, menu_code, 'read')

        # 레벨 0: 권한 없음
        if level == 0:
            return "1=0", []

        # 레벨 3: 전체 조회
        if level >= 3:
            return "1=1", []

        # 메뉴별 컬럼 설정 확인
        menu_columns = self.permission_columns.get(menu_code, {})

        # 컬럼 설정이 없으면 레벨 3만 허용
        if not menu_columns.get('owner') and not menu_columns.get('dept'):
            if level >= 3:
                return "1=1", []
            else:
                return "1=0", []  # 레벨 3 미만은 조회 불가

        owner_column = menu_columns.get('owner')
        dept_column = menu_columns.get('dept')

        # 레벨별 필터 생성
        if level == 1:
            # 본인 데이터만
            if owner_column:
                return f"({owner_column} = %s)", [login_id]
            else:
                return "1=0", []  # owner 컬럼이 없으면 조회 불가

        elif level == 2:
            # 본인 또는 부서 데이터
            conditions = []
            params = []

            if owner_column:
                conditions.append(f"{owner_column} = %s")
                params.append(login_id)

            if dept_column:
                if conditions:
                    conditions.append(f"{dept_column} = %s")
                else:
                    conditions = [f"{dept_column} = %s"]
                params.append(dept_id)

            if conditions:
                return f"({' OR '.join(conditions)})", params
            else:
                return "1=0", []

        return "1=0", []


# 전역 인스턴스
permission_checker = FlexiblePermissionChecker()


# 편의 함수들 (기존 인터페이스와 호환)
def get_permission_level(login_id, dept_id, menu_code, action='read'):
    """권한 레벨 조회"""
    return permission_checker.get_permission_level(login_id, dept_id, menu_code, action)


def check_data_access(login_id, dept_id, menu_code, action, data_record=None):
    """데이터 접근 권한 체크"""
    return permission_checker.check_data_access(login_id, dept_id, menu_code, action, data_record)


def get_data_filter_condition(login_id, dept_id, menu_code):
    """SQL WHERE 조건 생성"""
    return permission_checker.get_data_filter_condition(login_id, dept_id, menu_code)


def require_permission(menu_code, action='read', min_level=1):
    """권한 체크 데코레이터"""
    from functools import wraps
    from flask import jsonify, request, abort

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            if not login_id:
                if request.is_json:
                    return jsonify({'error': '로그인이 필요합니다'}), 401
                else:
                    abort(401)

            level = get_permission_level(login_id, dept_id, menu_code, action)

            if level < min_level:
                if request.is_json:
                    return jsonify({'error': f'권한이 부족합니다. (필요 레벨: {min_level}, 현재: {level})'}), 403
                else:
                    abort(403)

            # 권한 레벨을 request context에 저장
            request.permission_level = level
            return f(*args, **kwargs)

        return decorated_function
    return decorator