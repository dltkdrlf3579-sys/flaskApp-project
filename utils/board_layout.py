"""Shared helpers for board section/column ordering."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List


def order_value(value: Any, default: float = float("inf")) -> float:
    """Convert section/column order values to a numeric form for sorting."""
    try:
        if value is None:
            return default
        if isinstance(value, (int, float)):
            return float(value)
        text = str(value).strip()
        if not text:
            return default
        return float(text)
    except (TypeError, ValueError):
        return default


def sort_sections(section_list: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return sections ordered by section_order ASC then key name."""
    return sorted(
        list(section_list or []),
        key=lambda item: (
            order_value(item.get("section_order")),
            item.get("section_key") or "",
        ),
    )


def sort_columns(
    column_list: Iterable[Dict[str, Any]],
    section_order_map: Dict[str, float] | None = None,
) -> List[Dict[str, Any]]:
    """Return columns ordered by section order then column order."""
    section_order_map = section_order_map or {}
    return sorted(
        list(column_list or []),
        key=lambda item: (
            order_value(section_order_map.get(item.get("tab"))),
            order_value(item.get("column_order")),
            item.get("column_key") or "",
        ),
    )
