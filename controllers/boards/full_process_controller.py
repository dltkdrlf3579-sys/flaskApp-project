"""Full Process board controller built on the dynamic board base."""

from controllers import BoardControllerConfig
from controllers.dynamic_board_controller import DynamicBoardController


class FullProcessController(DynamicBoardController):
    """Full Process controller leveraging the shared dynamic implementation."""

    pass


def build_full_process_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="full_process",
        list_template="full-process.html",
        detail_template="full-process-detail.html",
        register_template="full-process-register.html",
        attachments_enabled=True,
        scoring_enabled=True,
        per_page_default=20,
        extra_context={
            "menu_section": "full_process",
            "permission_code": "FULL_PROCESS",
        },
        list_context_key="fullprocesses",
        detail_missing_message="Full Process를 찾을 수 없습니다.",
    )
