"""Follow SOP board controller built on the dynamic board base."""

from controllers import BoardControllerConfig
from controllers.dynamic_board_controller import DynamicBoardController


class FollowSopController(DynamicBoardController):
    """Follow SOP controller leveraging the shared dynamic board implementation."""

    pass


def build_follow_sop_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="follow_sop",
        list_template="follow-sop.html",
        detail_template="follow-sop-detail.html",
        register_template="follow-sop-register.html",
        attachments_enabled=True,
        scoring_enabled=True,
        per_page_default=20,
        extra_context={
            "menu_section": "follow_sop",
            "permission_code": "FOLLOW_SOP",
            "board_display_name": "Follow SOP",
            "identifier_label": "점검번호",
            "identifier_column": "work_req_no",
            "board_slug": "follow-sop",
        },
        list_context_key="followsops",
        detail_missing_message="Follow SOP를 찾을 수 없습니다.",
    )
