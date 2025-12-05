"""
권한 시스템 헬퍼 함수
실제 권한 체크 및 레벨별 데이터 필터링
"""
from db_connection import get_db_connection
from flask import session, render_template, jsonify
import logging
import configparser
import copy

from config.menu import MENU_CONFIG

logger = logging.getLogger(__name__)

# Config 파일에서 슈퍼어드민 목록 읽기
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')
PERMISSION_ENABLED = config.getboolean('PERMISSION', 'enabled', fallback=True)
SUPER_ADMIN_USERS = config.get('PERMISSION', 'super_admin_users', fallback='').split(',')
SUPER_ADMIN_USERS = [u.strip() for u in SUPER_ADMIN_USERS if u.strip()]

MENU_PERMISSION_MAP = {
    'partner-standards': 'VENDOR_MGT',
    'partner-change-request': 'REFERENCE_CHANGE',
    'partner-change-request-detail': 'REFERENCE_CHANGE',
    'accident': 'ACCIDENT_MGT',
    'accident-register': 'ACCIDENT_MGT',
    'accident-detail': 'ACCIDENT_MGT',
    'accident-update': 'ACCIDENT_MGT',
    'partner-accident': 'ACCIDENT_MGT',
    'safety-instruction': 'SAFETY_INSTRUCTION',
    'safety-instruction-register': 'SAFETY_INSTRUCTION',
    'safety-instruction-detail': 'SAFETY_INSTRUCTION',
    'safety-instruction-update': 'SAFETY_INSTRUCTION',
    'follow-sop': 'FOLLOW_SOP',
    'follow-sop-register': 'FOLLOW_SOP',
    'follow-sop-detail': 'FOLLOW_SOP',
    'follow-sop-update': 'FOLLOW_SOP',
    'subcontract-approval': 'SUBCONTRACT_APPROVAL',
    'subcontract-approval-register': 'SUBCONTRACT_APPROVAL',
    'subcontract-approval-detail': 'SUBCONTRACT_APPROVAL',
    'subcontract-approval-update': 'SUBCONTRACT_APPROVAL',
    'subcontract-report': 'SUBCONTRACT_REPORT',
    'subcontract-report-register': 'SUBCONTRACT_REPORT',
    'subcontract-report-detail': 'SUBCONTRACT_REPORT',
    'subcontract-report-update': 'SUBCONTRACT_REPORT',
    'safe-workplace': 'SAFE_WORKPLACE',
    'safe-workplace-register': 'SAFE_WORKPLACE',
    'safe-workplace-detail': 'SAFE_WORKPLACE',
    'safe-workplace-update': 'SAFE_WORKPLACE',
    'full-process': 'FULL_PROCESS',
    'full-process-register': 'FULL_PROCESS',
    'full-process-detail': 'FULL_PROCESS',
    'full-process-update': 'FULL_PROCESS',
    'safety-council': 'SAFETY_COUNCIL',
}

_SUFFIXES = (
    '-register',
    '-detail',
    '-update',
    '-create',
    '-edit',
    '-view',
    '-list',
    '-delete',
)

def resolve_menu_code(slug: str) -> str:
    if not slug:
        return ''
    key = slug.strip('/').lower()
    if key in MENU_PERMISSION_MAP:
        return MENU_PERMISSION_MAP[key]

    trimmed = key
    for suffix in _SUFFIXES:
        if trimmed.endswith(suffix):
            base = trimmed[: -len(suffix)]
            if base in MENU_PERMISSION_MAP:
                return MENU_PERMISSION_MAP[base]
            trimmed = base
            if trimmed in MENU_PERMISSION_MAP:
                return MENU_PERMISSION_MAP[trimmed]
    if trimmed in MENU_PERMISSION_MAP:
        return MENU_PERMISSION_MAP[trimmed]

    fallback = trimmed.replace('-', '_').upper()
    if fallback == '':
        return 'HOME'
    return fallback

def build_user_menu_config():
    try:
        if not PERMISSION_ENABLED or is_super_admin():
            return copy.deepcopy(MENU_CONFIG)

        accessible = get_user_accessible_menus()
        allowed_codes = {entry.get('code') for entry in accessible if entry.get('code')}

        filtered = []
        for section in MENU_CONFIG:
            sub_filtered = []
            for item in section.get('submenu', []):
                slug = item.get('url') or ''
                code = resolve_menu_code(slug)
                if code in allowed_codes:
                    sub_filtered.append(dict(item))
            if sub_filtered:
                filtered.append({'title': section.get('title'), 'submenu': sub_filtered})
        return filtered
    except Exception as exc:
        logger.debug("build_user_menu_config failed: %s", exc)
        return copy.deepcopy(MENU_CONFIG)

def is_super_admin():
    """현재 사용자가 슈퍼어드민인지 확인"""
    login_id = session.get('user_id')
    return login_id in SUPER_ADMIN_USERS

def get_user_permission_level(menu_code, permission_type='read'):
    """
    사용자의 권한 레벨 조회 (0-3)
    개인 권한과 부서 권한 중 높은 것을 반환
    슈퍼어드민은 항상 레벨 3 반환
    """
    try:
        if not PERMISSION_ENABLED:
            return 3

        login_id = session.get('user_id')

        # 슈퍼어드민 체크
        if is_super_admin():
            return 3  # 슈퍼어드민은 항상 최고 권한

        conn = get_db_connection()
        cursor = conn.cursor()

        dept_id = session.get('deptid')

        if not login_id:
            return 0

        # 개인 권한 확인
        cursor.execute("""
            SELECT read_level, write_level
            FROM user_menu_permissions
            WHERE login_id = %s AND menu_code = %s
            AND is_active = true
        """, (login_id, menu_code))

        user_perm = cursor.fetchone()

        # 부서 권한 확인
        dept_perm = None
        if dept_id:
            cursor.execute("""
                SELECT read_level, write_level
                FROM dept_menu_permissions
                WHERE dept_id = %s AND menu_code = %s
                AND is_active = true
            """, (dept_id, menu_code))

            dept_perm = cursor.fetchone()

        # OR 연산 (높은 권한 우선)
        if permission_type == 'read':
            user_level = user_perm[0] if user_perm else 0
            dept_level = dept_perm[0] if dept_perm else 0
        else:  # write
            user_level = user_perm[1] if user_perm else 0
            dept_level = dept_perm[1] if dept_perm else 0

        cursor.close()
        conn.close()

        return max(user_level, dept_level)

    except Exception as e:
        logger.error(f"Error getting permission level: {e}")
        return 0

def check_menu_permission(menu_code, action='view'):
    """
    메뉴 접근 권한 체크
    권한이 없으면 팝업 메시지 후 이전 페이지로
    슈퍼어드민은 항상 통과
    """
    if not PERMISSION_ENABLED:
        return True, None, None

    # 슈퍼어드민은 모든 권한 통과
    if is_super_admin():
        return True, None, None

    if action == 'view':
        level = get_user_permission_level(menu_code, 'read')
    else:
        level = get_user_permission_level(menu_code, 'write')

    if level == 0:
        # 간단한 팝업 메시지
        error_html = """
        <!DOCTYPE html>
        <html>
        <head><meta charset="UTF-8"></head>
        <body>
        <script>
            (function() {
                alert('접근 권한이 없습니다\\n\\n요청하신 페이지에 접근할 수 있는 권한이 없습니다.\\n이 페이지를 보려면 적절한 권한이 필요합니다.\\n\\n권한이 필요하신가요?\\n관리자에게 권한을 요청하세요\\n권한 신청 버튼을 통해 직접 신청할 수 있습니다\\n신청 후 승인까지 대기해 주세요');
                try {
                    if (window.opener && !window.opener.closed) {
                        window.close();
                        return;
                    }
                } catch (err) {
                    console.warn('권한 팝업 닫기 실패:', err);
                }
                if (window.history.length > 1) {
                    window.history.back();
                } else {
                    window.location.href = '/';
                }
            })();
        </script>
        </body>
        </html>
        """
        return False, error_html, 403

    return True, None, None

def enforce_permission(menu_code, action='view', response_type='html'):
    allowed, error_html, status = check_menu_permission(menu_code, action)
    if allowed:
        return None

    status_code = status or 403
    if response_type == 'json':
        return jsonify({'error': '권한이 없습니다.'}), status_code
    return (error_html or '권한이 없습니다.'), status_code

def get_user_accessible_menus():
    """
    사용자가 접근 가능한 메뉴 목록 반환
    권한 레벨이 1 이상인 메뉴만 반환
    슈퍼어드민은 모든 메뉴 반환
    """
    try:
        login_id = session.get('user_id')

        # 권한 체크 비활성화 시 전체 메뉴 반환
        if not PERMISSION_ENABLED or is_super_admin():
            return [
                {'code': 'VENDOR_MGT', 'name': '협력사 기준정보', 'url': '/vendor-management', 'icon': 'fas fa-building', 'read_level': 3, 'write_level': 3},
                {'code': 'REFERENCE_CHANGE', 'name': '기준정보 변경요청', 'url': '/reference-change', 'icon': 'fas fa-exchange-alt', 'read_level': 3, 'write_level': 3},
                {'code': 'ACCIDENT_MGT', 'name': '협력사 사고', 'url': '/accident-management', 'icon': 'fas fa-exclamation-triangle', 'read_level': 3, 'write_level': 3},
                {'code': 'SAFETY_INSTRUCTION', 'name': '환경안전 지시서', 'url': '/safety-instruction', 'icon': 'fas fa-clipboard-check', 'read_level': 3, 'write_level': 3},
                {'code': 'FOLLOW_SOP', 'name': 'Follow SOP', 'url': '/follow-sop', 'icon': 'fas fa-tasks', 'read_level': 3, 'write_level': 3},
                {'code': 'FULL_PROCESS', 'name': 'FullProcess', 'url': '/full-process', 'icon': 'fas fa-project-diagram', 'read_level': 3, 'write_level': 3},
                {'code': 'SAFE_WORKPLACE', 'name': '안전한 일터', 'url': '/safe-workplace', 'icon': 'fas fa-hard-hat', 'read_level': 3, 'write_level': 3},
                {'code': 'SUBCONTRACT_APPROVAL', 'name': '산안법 도급승인', 'url': '/subcontract-approval', 'icon': 'fas fa-file-signature', 'read_level': 3, 'write_level': 3},
                {'code': 'SUBCONTRACT_REPORT', 'name': '화관법 도급신고', 'url': '/subcontract-report', 'icon': 'fas fa-file-alt', 'read_level': 3, 'write_level': 3},
                {'code': 'SAFETY_COUNCIL', 'name': '안전보건 협의체', 'url': '/safety-council', 'icon': 'fas fa-users', 'read_level': 3, 'write_level': 3},
            ]

        conn = get_db_connection()
        cursor = conn.cursor()

        dept_id = session.get('deptid')

        if not login_id:
            return []

        # 모든 메뉴와 권한 조회
        cursor.execute("""
            WITH user_perms AS (
                SELECT menu_code, read_level, write_level
                FROM user_menu_permissions
                WHERE login_id = %s AND is_active = true
            ),
            dept_perms AS (
                SELECT menu_code, read_level, write_level
                FROM dept_menu_permissions
                WHERE dept_id = %s AND is_active = true
            ),
            all_menus AS (
                SELECT 'VENDOR_MGT' as code, '협력사 기준정보' as name, '/vendor-management' as url, 'fas fa-building' as icon
                UNION ALL
                SELECT 'REFERENCE_CHANGE', '기준정보 변경요청', '/reference-change', 'fas fa-exchange-alt'
                UNION ALL
                SELECT 'ACCIDENT_MGT', '협력사 사고', '/accident-management', 'fas fa-exclamation-triangle'
                UNION ALL
                SELECT 'SAFETY_INSTRUCTION', '환경안전 지시서', '/safety-instruction', 'fas fa-clipboard-check'
                UNION ALL
                SELECT 'FOLLOW_SOP', 'Follow SOP', '/follow-sop', 'fas fa-tasks'
                UNION ALL
                SELECT 'FULL_PROCESS', 'FullProcess', '/full-process', 'fas fa-project-diagram'
                UNION ALL
                SELECT 'SAFE_WORKPLACE', '안전한 일터', '/safe-workplace', 'fas fa-hard-hat'
                UNION ALL
                SELECT 'SUBCONTRACT_APPROVAL', '산안법 도급승인', '/subcontract-approval', 'fas fa-file-signature'
                UNION ALL
                SELECT 'SUBCONTRACT_REPORT', '화관법 도급신고', '/subcontract-report', 'fas fa-file-alt'
                UNION ALL
                SELECT 'SAFETY_COUNCIL', '안전보건 협의체', '/safety-council', 'fas fa-users'
            )
            SELECT
                m.code,
                m.name,
                m.url,
                m.icon,
                GREATEST(
                    COALESCE(up.read_level, 0),
                    COALESCE(dp.read_level, 0)
                ) as read_level,
                GREATEST(
                    COALESCE(up.write_level, 0),
                    COALESCE(dp.write_level, 0)
                ) as write_level
            FROM all_menus m
            LEFT JOIN user_perms up ON m.code = up.menu_code
            LEFT JOIN dept_perms dp ON m.code = dp.menu_code
            WHERE GREATEST(
                COALESCE(up.read_level, 0),
                COALESCE(dp.read_level, 0)
            ) > 0
            ORDER BY
                CASE m.code
                    WHEN 'VENDOR_MGT' THEN 1
                    WHEN 'REFERENCE_CHANGE' THEN 2
                    WHEN 'ACCIDENT_MGT' THEN 3
                    WHEN 'SAFETY_INSTRUCTION' THEN 4
                    WHEN 'FOLLOW_SOP' THEN 5
                    WHEN 'FULL_PROCESS' THEN 6
                    WHEN 'SAFE_WORKPLACE' THEN 7
                    WHEN 'SUBCONTRACT_APPROVAL' THEN 8
                    WHEN 'SUBCONTRACT_REPORT' THEN 9
                    WHEN 'SAFETY_COUNCIL' THEN 10
                END
        """, (login_id, dept_id or ''))

        menus = []
        for row in cursor.fetchall():
            menus.append({
                'code': row[0],
                'name': row[1],
                'url': row[2],
                'icon': row[3],
                'read_level': row[4],
                'write_level': row[5]
            })

        cursor.close()
        conn.close()

        return menus

    except Exception as e:
        logger.error(f"Error getting user menus: {e}")
        return []

def filter_data_by_permission(data, menu_code, created_by_field='created_by', dept_field='dept_id'):
    """
    권한 레벨에 따라 데이터 필터링

    Level 0: 빈 리스트
    Level 1: 본인 데이터만
    Level 2: 부서 데이터만
    Level 3: 전체 데이터
    슈퍼어드민: 전체 데이터
    """
    # 슈퍼어드민은 전체 데이터 반환
    if is_super_admin():
        return data

    level = get_user_permission_level(menu_code, 'read')

    if level == 0:
        return []
    elif level == 1:
        # 본인 데이터만
        user_id = session.get('user_id')
        return [d for d in data if d.get(created_by_field) == user_id]
    elif level == 2:
        # 부서 데이터
        dept_id = session.get('deptid')
        return [d for d in data if d.get(dept_field) == dept_id]
    else:
        # 전체 데이터
        return data

def can_edit_data(data_item, menu_code, created_by_field='created_by', dept_field='dept_id'):
    """
    특정 데이터를 수정할 수 있는지 체크
    슈퍼어드민은 항상 수정 가능
    """
    # 슈퍼어드민은 항상 수정 가능
    if is_super_admin():
        return True

    level = get_user_permission_level(menu_code, 'write')

    if level == 0:
        return False
    elif level == 1:
        # 본인이 작성한 것만 수정 가능
        return data_item.get(created_by_field) == session.get('user_id')
    elif level == 2:
        # 같은 부서 데이터만 수정 가능
        return data_item.get(dept_field) == session.get('deptid')
    else:
        # 모두 수정 가능
        return True

def log_permission_access(menu_code, action, success, reason=None):
    """
    권한 접근 로그 기록
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO permission_access_log
            (login_id, menu_code, action, success, reason, accessed_at)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        """, (
            session.get('user_id'),
            menu_code,
            action,
            success,
            reason
        ))

        conn.commit()
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error logging permission access: {e}")
