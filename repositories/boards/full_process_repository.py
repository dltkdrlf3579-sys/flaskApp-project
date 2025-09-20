"""Repository skeleton for Full Process board.

The implementation will encapsulate SQL currently embedded in
`add_page_routes.py` so that the controller can remain storage-agnostic.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional, Tuple


class FullProcessRepository:
    """Encapsulates all DB interactions for the Full Process board."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    # --- Query helpers -------------------------------------------------

    def fetch_list(
        self,
        filters: Mapping[str, Any],
        pagination: Tuple[int, int],
        order_by: Optional[Iterable[str]] = None,
    ) -> Tuple[int, Iterable[Mapping[str, Any]]]:
        raise NotImplementedError

    def fetch_detail(self, fullprocess_number: str) -> Optional[Mapping[str, Any]]:
        raise NotImplementedError

    def save(self, payload: Mapping[str, Any]) -> Any:
        raise NotImplementedError
