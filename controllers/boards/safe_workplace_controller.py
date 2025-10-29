"""Safe Workplace board controller built on the dynamic board base."""

from controllers import BoardControllerConfig
from controllers.dynamic_board_controller import DynamicBoardController


class SafeWorkplaceController(DynamicBoardController):
    """Safe Workplace controller leveraging the shared dynamic implementation."""

    pass


def build_safe_workplace_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="safe_workplace",
        list_template="safe-workplace.html",
        detail_template="safe-workplace-detail.html",
        register_template="safe-workplace-register.html",
        attachments_enabled=True,
        scoring_enabled=True,
        per_page_default=20,
        extra_context={
            "menu_section": "safe_workplace",
            "permission_code": "SAFE_WORKPLACE",
        },
        list_context_key="workplaces",
        detail_missing_message="Safe Workplace를 찾을 수 없습니다.",
    )
