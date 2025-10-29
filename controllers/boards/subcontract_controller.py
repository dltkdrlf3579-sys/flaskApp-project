"""Controllers for the subcontract competency evaluation boards."""

from __future__ import annotations

from controllers import BoardControllerConfig
from controllers.dynamic_board_controller import DynamicBoardController


class SubcontractApprovalController(DynamicBoardController):
    """Controller for the 산안법 도급승인 보드."""

    pass


def build_subcontract_approval_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="subcontract_approval",
        list_template="subcontract-approval.html",
        detail_template="subcontract-approval-detail.html",
        register_template="subcontract-approval-register.html",
        attachments_enabled=True,
        scoring_enabled=False,
        per_page_default=20,
        extra_context={
            "menu_section": "competency_eval",
            "permission_code": "SUBCONTRACT_APPROVAL",
            "board_display_name": "산안법 도급승인",
            "identifier_label": "도급승인번호",
            "identifier_column": "approval_number",
            "board_slug": "subcontract-approval",
        },
        list_context_key="subcontract_approvals",
        detail_missing_message="산안법 도급승인 건을 찾을 수 없습니다.",
    )


class SubcontractReportController(DynamicBoardController):
    """Controller for the 화관법 도급신고 보드."""

    pass


def build_subcontract_report_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="subcontract_report",
        list_template="subcontract-report.html",
        detail_template="subcontract-report-detail.html",
        register_template="subcontract-report-register.html",
        attachments_enabled=True,
        scoring_enabled=False,
        per_page_default=20,
        extra_context={
            "menu_section": "competency_eval",
            "permission_code": "SUBCONTRACT_REPORT",
            "board_display_name": "화관법 도급신고",
            "identifier_label": "도급신고번호",
            "identifier_column": "report_number",
            "board_slug": "subcontract-report",
        },
        list_context_key="subcontract_reports",
        detail_missing_message="화관법 도급신고 건을 찾을 수 없습니다.",
    )
