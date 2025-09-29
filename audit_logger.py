"""통합 감사 로그 유틸리티.

access_audit_log 테이블에 한국어 레이블로 주요 활동을 기록한다.
"""
from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Optional, Dict

from flask import Request, request, session

from db_connection import get_db_connection

logger = logging.getLogger(__name__)

# 한국어 레이블 매핑
def _normalize_key(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


_SCOPE_LABELS: Dict[str, str] = {
    "MENU": "메뉴",
    "BOARD": "게시판",
    "PERMISSION": "권한",
    "SYSTEM": "시스템",
    "AUTH": "권한",
    "COLUMN": "컬럼",
    "API": "API",
    "FILE": "파일",
}

_ACTION_LABELS: Dict[str, str] = {
    "VIEW": "조회",
    "GET": "조회",
    "READ": "조회",
    "LIST": "목록 조회",
    "INDEX": "목록 조회",
    "REGISTER": "등록",
    "CREATE": "등록",
    "POST": "등록",
    "WRITE": "등록",
    "SAVE": "등록",
    "UPDATE": "업데이트",
    "PUT": "업데이트",
    "PATCH": "업데이트",
    "EDIT": "업데이트",
    "DETAIL": "수정",
    "DELETE": "삭제",
    "REMOVE": "삭제",
    "DESTROY": "삭제",
    "REQUEST_APPROVE": "요청 승인",
    "REQUEST_REJECT": "요청 거부",
    "REQUEST_CANCEL": "요청 취소",
    "PERMISSION_REQUEST": "권한 요청",
    "PERMISSION_UPDATE": "권한 변경",
    "ROLE_CHANGE": "역할 변경",
    "MENU_ACCESS": "메뉴 접근",
    "LOGIN": "로그인",
    "LOGOUT": "로그아웃",
    "REQUEST": "요청",
    "COLUMN_UPDATE": "컬럼 설정 수정",
    "COLUMN_PRESET": "컬럼 프리셋 적용",
    "VIEW_DETAIL": "상세 조회",
    "DOWNLOAD": "다운로드",
    "UPLOAD": "업로드",
    "ACCESS": "접근",
}

_RESULT_LABELS: Dict[str, str] = {
    "SUCCESS": "성공",
    "GRANTED": "허용",
    "ALLOWED": "허용",
    "TRUE": "성공",
    "DENIED": "거부",
    "FORBIDDEN": "거부",
    "FAILED": "실패",
    "ERROR": "오류",
    "REJECTED": "거부",
    "FALSE": "실패",
}


def _localized(mapping: Dict[str, str], value: Any) -> Optional[str]:
    key = _normalize_key(value)
    if key is None:
        return None
    return mapping.get(key.upper(), key)


@contextmanager
def _db_cursor():
    """DB 커서 헬퍼."""
    conn = None
    cursor = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        if conn:
            conn.rollback()
        raise
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


def _coerce_details(details: Any) -> Optional[str]:
    if details is None:
        return None
    if isinstance(details, (dict, list)):
        try:
            return json.dumps(details, ensure_ascii=False)
        except Exception as exc:
            logger.debug("Failed to json encode details: %s", exc)
            return None
    if isinstance(details, str):
        return details
    try:
        return json.dumps(details, ensure_ascii=False)
    except Exception:
        return str(details)


def record_audit_log(
    action_scope: str,
    action_type: str,
    *,
    action: Optional[str] = None,
    menu_code: Optional[str] = None,
    request_path: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    object_name: Optional[str] = None,
    resource_id: Optional[str] = None,
    permission_result: Optional[str] = None,
    success: Optional[bool] = True,
    details: Any = None,
    error_message: Optional[str] = None,
    custom_request: Optional[Request] = None,
    emp_id_override: Optional[str] = None,
    login_id_override: Optional[str] = None,
    ip_address_override: Optional[str] = None,
    user_agent_override: Optional[str] = None,
) -> None:
    """access_audit_log에 감사 로그를 적재한다."""

    scope_value = _localized(_SCOPE_LABELS, action_scope)
    action_label = _localized(_ACTION_LABELS, action_type)
    action_display = _localized(_ACTION_LABELS, action or action_type)

    result_value = _localized(_RESULT_LABELS, permission_result)
    if result_value is None and success is not None:
        result_value = "성공" if success else "실패"

    req = custom_request or (request if request else None)

    try:
        emp_id = emp_id_override or session.get('emp_id') or session.get('user_id')
        login_id = login_id_override or session.get('user_id')
        ip_address = ip_address_override or (req.remote_addr if req else None)
        user_agent = user_agent_override or (req.headers.get('User-Agent') if req else None)
        path = request_path or (req.path if req else None)
        res_id = resource_id
        if res_id is None and req and 'id' in req.args:
            res_id = req.args.get('id')

        details_payload = _coerce_details(details)

        with _db_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO access_audit_log (
                    emp_id,
                    login_id,
                    action_scope,
                    action_type,
                    action,
                    menu_code,
                    request_path,
                    object_type,
                    object_id,
                    object_name,
                    resource_id,
                    permission_result,
                    success,
                    ip_address,
                    user_agent,
                    details,
                    error_message
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    emp_id,
                    login_id,
                    scope_value,
                    action_label,
                    action_display,
                    menu_code,
                    path,
                    _localized(_ACTION_LABELS, object_type) if object_type else object_type,
                    object_id,
                    object_name,
                    res_id,
                    result_value,
                    success,
                    ip_address,
                    user_agent,
                    details_payload,
                    error_message,
                ),
            )
    except Exception as exc:
        logger.warning("Failed to record audit log: %s", exc)


def record_menu_view(menu_code: str, *, details: Any = None) -> None:
    record_audit_log(
        action_scope="MENU",
        action_type="VIEW",
        menu_code=menu_code,
        details=details,
    )


def record_board_action(
    menu_code: str,
    action_type: str,
    *,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    object_name: Optional[str] = None,
    success: bool = True,
    details: Any = None,
    error_message: Optional[str] = None,
    **kwargs,
) -> None:
    record_audit_log(
        action_scope="BOARD",
        action_type=action_type,
        action=action_type,
        menu_code=menu_code,
        object_type=object_type,
        object_id=object_id,
        object_name=object_name,
        success=success,
        details=details,
        error_message=error_message,
        **kwargs,
    )


def record_permission_event(
    action_type: str,
    *,
    menu_code: Optional[str] = None,
    permission_result: Optional[str] = None,
    success: bool = True,
    details: Any = None,
    error_message: Optional[str] = None,
    action_scope: str = "PERMISSION",
    **kwargs,
) -> None:
    record_audit_log(
        action_scope=action_scope,
        action_type=action_type,
        action=action_type,
        menu_code=menu_code,
        permission_result=permission_result,
        success=success,
        details=details,
        error_message=error_message,
        **kwargs,
    )


def record_system_event(
    action_type: str,
    *,
    action_scope: str = "SYSTEM",
    menu_code: Optional[str] = None,
    object_type: Optional[str] = None,
    object_id: Optional[str] = None,
    object_name: Optional[str] = None,
    success: bool = True,
    details: Any = None,
    error_message: Optional[str] = None,
    **kwargs,
) -> None:
    """시스템/관리 영역 이벤트 기록."""
    record_audit_log(
        action_scope=action_scope,
        action_type=action_type,
        menu_code=menu_code,
        object_type=object_type,
        object_id=object_id,
        object_name=object_name,
        success=success,
        details=details,
        error_message=error_message,
        **kwargs,
    )


def normalize_scope(scope: Optional[str]) -> Optional[str]:
    return _localized(_SCOPE_LABELS, scope)


def normalize_action(action: Optional[str]) -> Optional[str]:
    return _localized(_ACTION_LABELS, action)


def normalize_result(result: Optional[str]) -> Optional[str]:
    return _localized(_RESULT_LABELS, result)
