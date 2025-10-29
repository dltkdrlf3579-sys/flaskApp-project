# ============= 필요한 imports =============
import logging
import sqlite3
import json
from flask import (
    Blueprint,
    request,
    render_template,
    jsonify,
    session,
    flash,
    redirect,
    url_for,
)
from db_connection import get_db_connection
from column_utils import normalize_column_types, determine_linked_type
from common_mapping import smart_apply_mappings
from upload_utils import validate_uploaded_files
from database_config import db_config
from utils.sql_filters import sql_is_active_true, sql_is_deleted_false
from utils.board_layout import (
    order_value as _order_value,
    sort_columns as _sort_columns,
    sort_sections as _sort_sections,
)
from controllers.boards.follow_sop_controller import (
    FollowSopController,
    build_follow_sop_config,
)
from controllers.boards.subcontract_controller import (
    SubcontractApprovalController,
    build_subcontract_approval_config,
    SubcontractReportController,
    build_subcontract_report_config,
)
from controllers.boards.safe_workplace_controller import (
    SafeWorkplaceController,
    build_safe_workplace_config,
)
from controllers.boards.full_process_controller import (
    FullProcessController,
    build_full_process_config,
)
from repositories.boards.follow_sop_repository import FollowSopRepository
from repositories.boards.subcontract_repository import (
    SubcontractApprovalRepository,
    SubcontractReportRepository,
)
from repositories.boards.safe_workplace_repository import SafeWorkplaceRepository
from repositories.boards.full_process_repository import FullProcessRepository


# 공통: fetchone() 결과 첫 번째 값 안전 추출
def _first(row, default=0):
    try:
        if row is None:
            return default
        # sqlite3.Row 또는 tuple/리스트 인덱스 0 시도
        try:
            return row[0]
        except Exception:
            pass
        # dict 계열 대응
        if hasattr(row, 'values'):
            vals = list(row.values())
            return vals[0] if vals else default
        return default
    except Exception:
        return default


from config.menu import MENU_CONFIG
from permission_helpers import enforce_permission
from audit_logger import record_board_action, record_menu_view

DB_PATH = db_config.local_db_path
pyjson = json



def _response_info(response):
    status = 200
    payload = None

    if isinstance(response, tuple):
        if response:
            payload = response[0]
        if len(response) > 1 and isinstance(response[1], int):
            status = response[1]
    else:
        status = getattr(response, 'status_code', status)
        try:
            payload = response.get_json()
        except Exception:
            payload = None

    success = status < 400
    if isinstance(payload, dict) and 'success' in payload:
        success = bool(payload['success'])

    return success, payload
follow_sop_bp = Blueprint('follow_sop', __name__)
safe_workplace_bp = Blueprint('safe_workplace', __name__)
full_process_bp = Blueprint('full_process', __name__)
subcontract_approval_bp = Blueprint('subcontract_approval', __name__)
subcontract_report_bp = Blueprint('subcontract_report', __name__)

_follow_sop_controller = FollowSopController(
    build_follow_sop_config(),
    FollowSopRepository(DB_PATH),
    menu_config=MENU_CONFIG,
)

_subcontract_approval_controller = SubcontractApprovalController(
    build_subcontract_approval_config(),
    SubcontractApprovalRepository(DB_PATH),
    menu_config=MENU_CONFIG,
)

_subcontract_report_controller = SubcontractReportController(
    build_subcontract_report_config(),
    SubcontractReportRepository(DB_PATH),
    menu_config=MENU_CONFIG,
)

_safe_workplace_controller = SafeWorkplaceController(
    build_safe_workplace_config(),
    SafeWorkplaceRepository(DB_PATH),
    menu_config=MENU_CONFIG,
)

_full_process_controller = FullProcessController(
    build_full_process_config(),
    FullProcessRepository(DB_PATH),
    menu_config=MENU_CONFIG,
)


# ============= Follow SOP 페이지 라우트 =============
@follow_sop_bp.route("/follow-sop", endpoint="follow_sop_route")
def follow_sop_route():
    """Follow SOP 목록 페이지"""
    guard = enforce_permission('FOLLOW_SOP', 'view')
    if guard:
        return guard
    response = _follow_sop_controller.list_view(request)
    record_menu_view('FOLLOW_SOP')
    return response

@follow_sop_bp.route("/follow-sop-register", endpoint="follow_sop_register")
def follow_sop_register():
    """Follow SOP 등록 페이지"""
    guard = enforce_permission('FOLLOW_SOP', 'write')
    if guard:
        return guard
    response = _follow_sop_controller.register_view(request)
    record_board_action('FOLLOW_SOP', 'VIEW', object_type='FOLLOW_SOP', object_name='register')
    return response

@follow_sop_bp.route(
    "/follow-sop-detail/<work_req_no>",
    endpoint="follow_sop_detail",
)
def follow_sop_detail(work_req_no):
    """Follow SOP 상세정보 페이지"""
    guard = enforce_permission('FOLLOW_SOP', 'view')
    if guard:
        return guard
    response = _follow_sop_controller.detail_view(request, work_req_no)
    success, _ = _response_info(response)
    record_board_action(
        'FOLLOW_SOP',
        'VIEW',
        object_type='FOLLOW_SOP',
        object_id=work_req_no,
        success=success,
    )
    return response

@follow_sop_bp.route(
    '/register-follow-sop',
    methods=['POST'],
    endpoint='register_follow_sop'
)
def register_follow_sop():
    """새 Follow SOP 등록"""
    guard = enforce_permission('FOLLOW_SOP', 'write', response_type='json')
    if guard:
        return guard
    response = _follow_sop_controller.save(request)
    success, payload = _response_info(response)
    work_req_no = None
    error_message = None
    if isinstance(payload, dict):
        work_req_no = payload.get('work_req_no') or payload.get('id')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'FOLLOW_SOP',
        'CREATE',
        object_type='FOLLOW_SOP',
        object_id=work_req_no,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response


@follow_sop_bp.route(
    '/update-follow-sop',
    methods=['POST'],
    endpoint='update_follow_sop'
)
def update_follow_sop():
    """Follow SOP 수정"""
    guard = enforce_permission('FOLLOW_SOP', 'write', response_type='json')
    if guard:
        return guard
    response = _follow_sop_controller.update(request)
    success, payload = _response_info(response)
    work_req_no = None
    error_message = None
    if isinstance(payload, dict):
        work_req_no = payload.get('work_req_no') or payload.get('id')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'FOLLOW_SOP',
        'UPDATE',
        object_type='FOLLOW_SOP',
        object_id=work_req_no,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response

# ============= Subcontract Approval 라우트 =============
@subcontract_approval_bp.route("/subcontract-approval", endpoint="subcontract_approval_route")
def subcontract_approval_route():
    """산안법 도급승인 목록 페이지"""
    guard = enforce_permission('SUBCONTRACT_APPROVAL', 'view')
    if guard:
        return guard
    response = _subcontract_approval_controller.list_view(request)
    record_menu_view('SUBCONTRACT_APPROVAL')
    return response


@subcontract_approval_bp.route("/subcontract-approval-register", endpoint="subcontract_approval_register")
def subcontract_approval_register():
    """산안법 도급승인 등록 페이지"""
    guard = enforce_permission('SUBCONTRACT_APPROVAL', 'write')
    if guard:
        return guard
    response = _subcontract_approval_controller.register_view(request)
    record_board_action(
        'SUBCONTRACT_APPROVAL',
        'VIEW',
        object_type='SUBCONTRACT_APPROVAL',
        object_name='register',
    )
    return response


@subcontract_approval_bp.route(
    "/subcontract-approval-detail/<approval_number>",
    endpoint="subcontract_approval_detail",
)
def subcontract_approval_detail(approval_number: str):
    """산안법 도급승인 상세 페이지"""
    guard = enforce_permission('SUBCONTRACT_APPROVAL', 'view')
    if guard:
        return guard
    response = _subcontract_approval_controller.detail_view(request, approval_number)
    success, _ = _response_info(response)
    record_board_action(
        'SUBCONTRACT_APPROVAL',
        'VIEW',
        object_type='SUBCONTRACT_APPROVAL',
        object_id=approval_number,
        success=success,
    )
    return response


@subcontract_approval_bp.route(
    "/register-subcontract-approval",
    methods=['POST'],
    endpoint="register_subcontract_approval",
)
def register_subcontract_approval():
    """산안법 도급승인 신규 등록"""
    guard = enforce_permission('SUBCONTRACT_APPROVAL', 'write', response_type='json')
    if guard:
        return guard
    response = _subcontract_approval_controller.save(request)
    success, payload = _response_info(response)
    approval_number = None
    error_message = None
    if isinstance(payload, dict):
        approval_number = payload.get('approval_number') or payload.get('identifier_value')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'SUBCONTRACT_APPROVAL',
        'CREATE',
        object_type='SUBCONTRACT_APPROVAL',
        object_id=approval_number,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response


@subcontract_approval_bp.route(
    "/update-subcontract-approval",
    methods=['POST'],
    endpoint="update_subcontract_approval",
)
def update_subcontract_approval():
    """산안법 도급승인 수정"""
    guard = enforce_permission('SUBCONTRACT_APPROVAL', 'write', response_type='json')
    if guard:
        return guard
    response = _subcontract_approval_controller.update(request)
    success, payload = _response_info(response)
    approval_number = None
    error_message = None
    if isinstance(payload, dict):
        approval_number = payload.get('approval_number') or payload.get('identifier_value')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'SUBCONTRACT_APPROVAL',
        'UPDATE',
        object_type='SUBCONTRACT_APPROVAL',
        object_id=approval_number,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response


# ============= Subcontract Report 라우트 =============
@subcontract_report_bp.route("/subcontract-report", endpoint="subcontract_report_route")
def subcontract_report_route():
    """화관법 도급신고 목록 페이지"""
    guard = enforce_permission('SUBCONTRACT_REPORT', 'view')
    if guard:
        return guard
    response = _subcontract_report_controller.list_view(request)
    record_menu_view('SUBCONTRACT_REPORT')
    return response


@subcontract_report_bp.route("/subcontract-report-register", endpoint="subcontract_report_register")
def subcontract_report_register():
    """화관법 도급신고 등록 페이지"""
    guard = enforce_permission('SUBCONTRACT_REPORT', 'write')
    if guard:
        return guard
    response = _subcontract_report_controller.register_view(request)
    record_board_action(
        'SUBCONTRACT_REPORT',
        'VIEW',
        object_type='SUBCONTRACT_REPORT',
        object_name='register',
    )
    return response


@subcontract_report_bp.route(
    "/subcontract-report-detail/<report_number>",
    endpoint="subcontract_report_detail",
)
def subcontract_report_detail(report_number: str):
    """화관법 도급신고 상세 페이지"""
    guard = enforce_permission('SUBCONTRACT_REPORT', 'view')
    if guard:
        return guard
    response = _subcontract_report_controller.detail_view(request, report_number)
    success, _ = _response_info(response)
    record_board_action(
        'SUBCONTRACT_REPORT',
        'VIEW',
        object_type='SUBCONTRACT_REPORT',
        object_id=report_number,
        success=success,
    )
    return response


@subcontract_report_bp.route(
    "/register-subcontract-report",
    methods=['POST'],
    endpoint="register_subcontract_report",
)
def register_subcontract_report():
    """화관법 도급신고 신규 등록"""
    guard = enforce_permission('SUBCONTRACT_REPORT', 'write', response_type='json')
    if guard:
        return guard
    response = _subcontract_report_controller.save(request)
    success, payload = _response_info(response)
    report_number = None
    error_message = None
    if isinstance(payload, dict):
        report_number = payload.get('report_number') or payload.get('identifier_value')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'SUBCONTRACT_REPORT',
        'CREATE',
        object_type='SUBCONTRACT_REPORT',
        object_id=report_number,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response


@subcontract_report_bp.route(
    "/update-subcontract-report",
    methods=['POST'],
    endpoint="update_subcontract_report",
)
def update_subcontract_report():
    """화관법 도급신고 수정"""
    guard = enforce_permission('SUBCONTRACT_REPORT', 'write', response_type='json')
    if guard:
        return guard
    response = _subcontract_report_controller.update(request)
    success, payload = _response_info(response)
    report_number = None
    error_message = None
    if isinstance(payload, dict):
        report_number = payload.get('report_number') or payload.get('identifier_value')
        error_message = payload.get('message') if not success else None
    record_board_action(
        'SUBCONTRACT_REPORT',
        'UPDATE',
        object_type='SUBCONTRACT_REPORT',
        object_id=report_number,
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=error_message,
    )
    return response

# ============= Safe-Workplace 관련 라우트 =============
@safe_workplace_bp.route("/safe-workplace", endpoint="safe_workplace_route")
def safe_workplace_route():
    """Safe Workplace 목록 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'view')
    if guard:
        return guard
    response = _safe_workplace_controller.list_view(request)
    record_menu_view('SAFE_WORKPLACE')
    return response

@safe_workplace_bp.route("/safe-workplace-register", endpoint="safe_workplace_register")
def safe_workplace_register():
    """Safe Workplace 등록 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'write')
    if guard:
        return guard
    response = _safe_workplace_controller.register_view(request)
    record_board_action('SAFE_WORKPLACE', 'VIEW', object_type='SAFE_WORKPLACE', object_name='register')
    return response

@safe_workplace_bp.route(
    "/safe-workplace-detail/<safeplace_no>",
    endpoint="safe_workplace_detail",
)
def safe_workplace_detail(safeplace_no):
    """Safe Workplace 상세 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'view')
    if guard:
        return guard
    response = _safe_workplace_controller.detail_view(request, safeplace_no)
    success, _ = _response_info(response)
    record_board_action(
        'SAFE_WORKPLACE',
        'VIEW',
        object_type='SAFE_WORKPLACE',
        object_id=safeplace_no,
        success=success,
    )
    return response

@safe_workplace_bp.route(
    '/register-safe-workplace',
    methods=['POST'],
    endpoint='register_safe_workplace'
)
def register_safe_workplace():
    """Safe Workplace 신규 등록"""
    guard = enforce_permission('SAFE_WORKPLACE', 'write', response_type='json')
    if guard:
        return guard
    response = _safe_workplace_controller.save(request)
    success, payload = _response_info(response)
    record_board_action(
        'SAFE_WORKPLACE',
        'CREATE',
        object_type='SAFE_WORKPLACE',
        object_id=(payload.get('safeplace_no') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response


@safe_workplace_bp.route(
    '/update-safe-workplace',
    methods=['POST'],
    endpoint='update_safe_workplace'
)
def update_safe_workplace():
    """Safe Workplace 수정"""
    guard = enforce_permission('SAFE_WORKPLACE', 'write', response_type='json')
    if guard:
        return guard
    response = _safe_workplace_controller.update(request)
    success, payload = _response_info(response)
    record_board_action(
        'SAFE_WORKPLACE',
        'UPDATE',
        object_type='SAFE_WORKPLACE',
        object_id=(payload.get('safeplace_no') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response

# ============= Full Process 페이지 라우트 =============
@full_process_bp.route("/full-process", endpoint="full_process_route")
def full_process_route():
    """Full Process 페이지 라우트"""
    guard = enforce_permission('FULL_PROCESS', 'view')
    if guard:
        return guard
    response = _full_process_controller.list_view(request)
    record_menu_view('FULL_PROCESS')
    return response

@full_process_bp.route("/full-process-register", endpoint="full_process_register")
def full_process_register():
    """Full Process 등록 페이지"""
    guard = enforce_permission('FULL_PROCESS', 'write')
    if guard:
        return guard
    response = _full_process_controller.register_view(request)
    record_board_action('FULL_PROCESS', 'VIEW', object_type='FULL_PROCESS', object_name='register')
    return response

@full_process_bp.route(
    "/full-process-detail/<fullprocess_number>",
    endpoint="full_process_detail",
)
def full_process_detail(fullprocess_number):
    """Full Process 상세정보 페이지"""
    guard = enforce_permission('FULL_PROCESS', 'view')
    if guard:
        return guard
    response = _full_process_controller.detail_view(request, fullprocess_number)
    success, _ = _response_info(response)
    record_board_action(
        'FULL_PROCESS',
        'VIEW',
        object_type='FULL_PROCESS',
        object_id=fullprocess_number,
        success=success,
    )
    return response

@full_process_bp.route(
    '/register-full-process',
    methods=['POST'],
    endpoint='register_full_process'
)
def register_full_process():
    """새 Full Process 등록"""
    guard = enforce_permission('FULL_PROCESS', 'write', response_type='json')
    if guard:
        return guard
    response = _full_process_controller.save(request)
    success, payload = _response_info(response)
    record_board_action(
        'FULL_PROCESS',
        'CREATE',
        object_type='FULL_PROCESS',
        object_id=(payload.get('fullprocess_number') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response

@full_process_bp.route(
    '/update-full-process',
    methods=['POST'],
    endpoint='update_full_process'
)
def update_full_process():
    """Full Process 수정"""
    guard = enforce_permission('FULL_PROCESS', 'write', response_type='json')
    if guard:
        return guard
    response = _full_process_controller.update(request)
    success, payload = _response_info(response)
    record_board_action(
        'FULL_PROCESS',
        'UPDATE',
        object_type='FULL_PROCESS',
        object_id=(payload.get('fullprocess_number') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response
