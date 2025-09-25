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
from controllers.boards.safe_workplace_controller import (
    SafeWorkplaceController,
    build_safe_workplace_config,
)
from controllers.boards.full_process_controller import (
    FullProcessController,
    build_full_process_config,
)
from repositories.boards.follow_sop_repository import FollowSopRepository
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

DB_PATH = db_config.local_db_path
pyjson = json

follow_sop_bp = Blueprint('follow_sop', __name__)
safe_workplace_bp = Blueprint('safe_workplace', __name__)
full_process_bp = Blueprint('full_process', __name__)

_follow_sop_controller = FollowSopController(
    build_follow_sop_config(),
    FollowSopRepository(DB_PATH),
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
    return _follow_sop_controller.list_view(request)

@follow_sop_bp.route("/follow-sop-register", endpoint="follow_sop_register")
def follow_sop_register():
    """Follow SOP 등록 페이지"""
    guard = enforce_permission('FOLLOW_SOP', 'write')
    if guard:
        return guard
    return _follow_sop_controller.register_view(request)

@follow_sop_bp.route(
    "/follow-sop-detail/<work_req_no>",
    endpoint="follow_sop_detail",
)
def follow_sop_detail(work_req_no):
    """Follow SOP 상세정보 페이지"""
    guard = enforce_permission('FOLLOW_SOP', 'view')
    if guard:
        return guard
    return _follow_sop_controller.detail_view(request, work_req_no)

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
    return _follow_sop_controller.save(request)


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
    return _follow_sop_controller.update(request)

# ============= Safe-Workplace 관련 라우트 =============
@safe_workplace_bp.route("/safe-workplace", endpoint="safe_workplace_route")
def safe_workplace_route():
    """Safe Workplace 목록 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'view')
    if guard:
        return guard
    return _safe_workplace_controller.list_view(request)

@safe_workplace_bp.route("/safe-workplace-register", endpoint="safe_workplace_register")
def safe_workplace_register():
    """Safe Workplace 등록 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'write')
    if guard:
        return guard
    return _safe_workplace_controller.register_view(request)

@safe_workplace_bp.route(
    "/safe-workplace-detail/<safeplace_no>",
    endpoint="safe_workplace_detail",
)
def safe_workplace_detail(safeplace_no):
    """Safe Workplace 상세 페이지"""
    guard = enforce_permission('SAFE_WORKPLACE', 'view')
    if guard:
        return guard
    return _safe_workplace_controller.detail_view(request, safeplace_no)

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
    return _safe_workplace_controller.save(request)


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
    return _safe_workplace_controller.update(request)

# ============= Full Process 페이지 라우트 =============
@full_process_bp.route("/full-process", endpoint="full_process_route")
def full_process_route():
    """Full Process 페이지 라우트"""
    guard = enforce_permission('FULL_PROCESS', 'view')
    if guard:
        return guard
    return _full_process_controller.list_view(request)

@full_process_bp.route("/full-process-register", endpoint="full_process_register")
def full_process_register():
    """Full Process 등록 페이지"""
    guard = enforce_permission('FULL_PROCESS', 'write')
    if guard:
        return guard
    return _full_process_controller.register_view(request)

@full_process_bp.route(
    "/full-process-detail/<fullprocess_number>",
    endpoint="full_process_detail",
)
def full_process_detail(fullprocess_number):
    """Full Process 상세정보 페이지"""
    guard = enforce_permission('FULL_PROCESS', 'view')
    if guard:
        return guard
    return _full_process_controller.detail_view(request, fullprocess_number)

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
    return _full_process_controller.save(request)

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
    return _full_process_controller.update(request)
