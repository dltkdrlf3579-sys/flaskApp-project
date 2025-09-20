"""Common controller skeleton for board-style pages.

This layer will gradually absorb duplicated list/register/detail logic
from individual board blueprints (accident, follow SOP, full process, etc.).
The goal in Phase 2 is to have each board supply only configuration and
small hook implementations, while the heavy lifting remains here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Mapping, Optional, Protocol, Tuple


class BoardRepository(Protocol):
    """Minimal contract the controller expects from a board repository."""

    def fetch_list(
        self,
        filters: Mapping[str, Any],
        pagination: Tuple[int, int],
        order_by: Optional[Iterable[str]] = None,
    ) -> Tuple[int, Iterable[Mapping[str, Any]]]:
        ...

    def fetch_detail(self, identifier: Any) -> Optional[Mapping[str, Any]]:
        ...

    def save(self, payload: Mapping[str, Any]) -> Any:
        ...


@dataclass
class BoardControllerConfig:
    """Static metadata for a board controller instance."""

    board_type: str
    list_template: str
    detail_template: str
    register_template: str
    per_page_default: int = 20
    attachments_enabled: bool = True
    scoring_enabled: bool = False
    extra_context: Dict[str, Any] = field(default_factory=dict)


class BoardController:
    """Base controller that orchestrates board CRUD flows.

    Concrete controllers provide board-specific hooks by overriding
    the protected methods. Routes simply forward Flask requests to the
    corresponding public methods (`list_view`, `detail_view`, etc.).
    """

    def __init__(
        self,
        config: BoardControllerConfig,
        repository: BoardRepository,
        *,
        menu_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.config = config
        self.repository = repository
        self.menu_config = menu_config or {}

    # --- Public API -----------------------------------------------------

    def list_view(self, request) -> Any:
        """Render the list page (GET)."""
        raise NotImplementedError("list_view must be implemented by subclasses")

    def detail_view(self, request, identifier: Any) -> Any:
        """Render the detail page (GET)."""
        raise NotImplementedError("detail_view must be implemented by subclasses")

    def register_view(self, request) -> Any:
        """Render the register page (GET)."""
        raise NotImplementedError("register_view must be implemented by subclasses")

    def save(self, request) -> Any:
        """Handle POST for creating or updating entries."""
        raise NotImplementedError("save must be implemented by subclasses")

    # --- Utility helpers for subclasses --------------------------------

    def _default_pagination(self, request) -> Tuple[int, int]:
        """Extract (page, per_page) from the request with sane defaults."""
        try:
            page = int(request.args.get("page", 1))
        except (TypeError, ValueError):
            page = 1
        try:
            per_page = int(
                request.args.get("per_page", self.config.per_page_default)
            )
        except (TypeError, ValueError):
            per_page = self.config.per_page_default
        per_page = max(1, min(per_page, 200))  # guard against abuse
        return page, per_page

    def _build_template_context(self, **kwargs: Any) -> Dict[str, Any]:
        """Merge common board metadata with view-specific context."""
        context = dict(self.config.extra_context)
        context.update(kwargs)
        context.setdefault("menu", self.menu_config)
        context.setdefault("board_type", self.config.board_type)
        return context
