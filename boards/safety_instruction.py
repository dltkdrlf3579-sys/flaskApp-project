"""Blueprint wrappers for Safety Instruction board routes."""

from flask import Blueprint, request

safety_instruction_bp = Blueprint('safety_instruction', __name__)


@safety_instruction_bp.route("/safety-instruction")
def safety_instruction_route():
    from app import _safety_instruction_controller

    return _safety_instruction_controller.list_view(request)


@safety_instruction_bp.route(
    "/safety-instruction-register",
    endpoint="safety_instruction_register",
)
def safety_instruction_register():
    from app import _safety_instruction_controller

    return _safety_instruction_controller.register_view(request)


@safety_instruction_bp.route(
    "/safety-instruction-detail/<issue_number>",
    endpoint="safety_instruction_detail",
)
def safety_instruction_detail(issue_number):
    from app import _safety_instruction_controller

    return _safety_instruction_controller.detail_view(request, issue_number)


@safety_instruction_bp.route(
    '/update-safety-instruction',
    methods=['POST'],
    endpoint='update_safety_instruction'
)
def update_safety_instruction():
    from app import _safety_instruction_controller

    return _safety_instruction_controller.update(request)


@safety_instruction_bp.route(
    '/register-safety-instruction',
    methods=['POST'],
    endpoint='register_safety_instruction'
)
def register_safety_instruction():
    from app import _safety_instruction_controller

    return _safety_instruction_controller.save(request)
