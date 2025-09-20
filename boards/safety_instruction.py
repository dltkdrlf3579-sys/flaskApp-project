"""Blueprint wrappers for Safety Instruction board routes."""

from flask import Blueprint

safety_instruction_bp = Blueprint('safety_instruction', __name__)


@safety_instruction_bp.route("/safety-instruction")
def safety_instruction_route():
    from app import safety_instruction_route_logic

    return safety_instruction_route_logic()


@safety_instruction_bp.route(
    "/safety-instruction-register",
    endpoint="safety_instruction_register",
)
def safety_instruction_register():
    from app import safety_instruction_register_logic

    return safety_instruction_register_logic()


@safety_instruction_bp.route(
    "/safety-instruction-detail/<issue_number>",
    endpoint="safety_instruction_detail",
)
def safety_instruction_detail(issue_number):
    from app import safety_instruction_detail_logic

    return safety_instruction_detail_logic(issue_number)


@safety_instruction_bp.route(
    '/update-safety-instruction',
    methods=['POST'],
    endpoint='update_safety_instruction'
)
def update_safety_instruction():
    from app import update_safety_instruction_logic

    return update_safety_instruction_logic()


@safety_instruction_bp.route(
    '/register-safety-instruction',
    methods=['POST'],
    endpoint='register_safety_instruction'
)
def register_safety_instruction():
    from app import register_safety_instruction_logic

    return register_safety_instruction_logic()
