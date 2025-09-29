"""Blueprint wrappers for Safety Instruction board routes."""

from flask import Blueprint, request

from permission_helpers import enforce_permission
from audit_logger import record_board_action, record_menu_view

safety_instruction_bp = Blueprint('safety_instruction', __name__)



def _response_meta(response):
    status = getattr(response, 'status_code', 200)
    payload = None

    if isinstance(response, tuple):
        payload = response[0] if response else None
        if len(response) > 1 and isinstance(response[1], int):
            status = response[1]
    else:
        try:
            payload = response.get_json(silent=True)
        except Exception:
            payload = None

    success = status < 400
    if isinstance(payload, dict) and 'success' in payload:
        success = bool(payload['success'])
    return success, payload


@safety_instruction_bp.route("/safety-instruction")
def safety_instruction_route():
    from app import _safety_instruction_controller

    guard = enforce_permission('SAFETY_INSTRUCTION', 'view')
    if guard:
        return guard
    response = _safety_instruction_controller.list_view(request)
    record_menu_view('SAFETY_INSTRUCTION')
    return response


@safety_instruction_bp.route(
    "/safety-instruction-register",
    endpoint="safety_instruction_register",
)
def safety_instruction_register():
    from app import _safety_instruction_controller

    guard = enforce_permission('SAFETY_INSTRUCTION', 'write')
    if guard:
        return guard
    response = _safety_instruction_controller.register_view(request)
    record_board_action('SAFETY_INSTRUCTION', 'VIEW', object_type='SAFETY_INSTRUCTION', object_name='register')
    return response


@safety_instruction_bp.route(
    "/safety-instruction-detail/<issue_number>",
    endpoint="safety_instruction_detail",
)
def safety_instruction_detail(issue_number):
    from app import _safety_instruction_controller

    guard = enforce_permission('SAFETY_INSTRUCTION', 'view')
    if guard:
        return guard
    response = _safety_instruction_controller.detail_view(request, issue_number)
    success, _ = _response_meta(response)
    record_board_action(
        'SAFETY_INSTRUCTION',
        'VIEW',
        object_type='SAFETY_INSTRUCTION',
        object_id=issue_number,
        success=success,
    )
    return response


@safety_instruction_bp.route(
    '/update-safety-instruction',
    methods=['POST'],
    endpoint='update_safety_instruction'
)
def update_safety_instruction():
    from app import _safety_instruction_controller

    guard = enforce_permission('SAFETY_INSTRUCTION', 'write', response_type='json')
    if guard:
        return guard
    response = _safety_instruction_controller.update(request)
    success, payload = _response_meta(response)
    record_board_action(
        'SAFETY_INSTRUCTION',
        'UPDATE',
        object_type='SAFETY_INSTRUCTION',
        object_id=(payload.get('issue_number') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response


@safety_instruction_bp.route(
    '/register-safety-instruction',
    methods=['POST'],
    endpoint='register_safety_instruction'
)
def register_safety_instruction():
    from app import _safety_instruction_controller

    guard = enforce_permission('SAFETY_INSTRUCTION', 'write', response_type='json')
    if guard:
        return guard
    response = _safety_instruction_controller.save(request)
    success, payload = _response_meta(response)
    record_board_action(
        'SAFETY_INSTRUCTION',
        'CREATE',
        object_type='SAFETY_INSTRUCTION',
        object_id=(payload.get('issue_number') if isinstance(payload, dict) else None),
        success=success,
        details=payload if isinstance(payload, dict) else None,
        error_message=(payload.get('message') if isinstance(payload, dict) and not success else None),
    )
    return response
