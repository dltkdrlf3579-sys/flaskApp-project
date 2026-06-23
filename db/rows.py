"""Small row helpers for PostgreSQL query results."""
from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import Any


class DbRow(Mapping[str, Any]):
    """Mapping row that also supports positional reads during migration.

    Runtime code should prefer key access, but positional access keeps existing
    SELECT MAX(...), COUNT(*), and small tuple-style reads stable while the
    project is being converted away from SQLite-specific row objects.
    """

    def __init__(self, values: Mapping[str, Any]):
        self._data = dict(values)
        self._keys = list(self._data.keys())

    def __getitem__(self, key: str | int) -> Any:
        if isinstance(key, int):
            return self._data[self._keys[key]]
        return self._data[key]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def keys(self):
        return self._data.keys()

    def values(self):
        return self._data.values()

    def items(self):
        return self._data.items()


def row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a DB row-like object to a plain dictionary."""

    if row is None:
        return {}
    if isinstance(row, Mapping):
        return dict(row)
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    raise TypeError(f"Cannot convert row of type {type(row)!r} to dict")

