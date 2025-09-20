"""Full Process board controller prototype for Phase 2.

The controller does not yet replace existing routes; it documents the
intended responsibilities and will be gradually wired in once the
repository layer is ready.
"""

from __future__ import annotations

from typing import Any

from controllers import BoardController, BoardControllerConfig


class FullProcessController(BoardController):
    """Pilot controller that will absorb `add_page_routes.py` logic."""

    def list_view(self, request) -> Any:
        # TODO: build filters, call repository, and render template
        raise NotImplementedError

    def detail_view(self, request, fullprocess_number: str) -> Any:
        # TODO: fetch record, attachments, and render detail template
        raise NotImplementedError

    def register_view(self, request) -> Any:
        # TODO: load dynamic sections/columns and render register template
        raise NotImplementedError

    def save(self, request) -> Any:
        # TODO: validate payload, persist through repository, and respond JSON
        raise NotImplementedError


def build_full_process_config() -> BoardControllerConfig:
    """Helper to create the config object used by the controller."""

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
        },
    )
