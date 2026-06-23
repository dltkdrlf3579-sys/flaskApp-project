"""PostgreSQL-only connection wrapper.

This module intentionally does not translate SQLite SQL. Queries must already
use PostgreSQL syntax and `%s` placeholders before reaching this layer.
"""
from __future__ import annotations

import json
from typing import Any, Iterable

try:
    import psycopg
    from psycopg.rows import dict_row
    from psycopg.types.json import Jsonb as _JsonAdapter

    PSYCOPG_VERSION = 3
except ImportError:  # pragma: no cover - fallback for older environments
    psycopg = None
    dict_row = None
    _JsonAdapter = None
    PSYCOPG_VERSION = None

try:
    import psycopg2
    import psycopg2.extras
except ImportError:  # pragma: no cover - optional fallback
    psycopg2 = None

from db.rows import DbRow


def _json_adapter(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        if PSYCOPG_VERSION == 3 and _JsonAdapter is not None:
            return _JsonAdapter(value)
        if psycopg2 is not None:
            return psycopg2.extras.Json(value)
        return json.dumps(value, ensure_ascii=False)
    return value


def _convert_params(params: Any) -> Any:
    if params is None:
        return None
    if isinstance(params, tuple):
        return tuple(_json_adapter(value) for value in params)
    if isinstance(params, list):
        return tuple(_json_adapter(value) for value in params)
    if isinstance(params, dict):
        return {key: _json_adapter(value) for key, value in params.items()}
    return params


def _wrap_row(row: Any) -> Any:
    if row is None:
        return None
    if isinstance(row, DbRow):
        return row
    if isinstance(row, dict):
        return DbRow(row)
    if hasattr(row, "keys"):
        return DbRow({key: row[key] for key in row.keys()})
    return row


class PostgresCursor:
    """Thin cursor wrapper that returns mapping rows consistently."""

    def __init__(self, cursor: Any):
        self._cursor = cursor

    @property
    def rowcount(self) -> int:
        return self._cursor.rowcount

    @property
    def description(self):
        return self._cursor.description

    def execute(self, sql: str, params: Any = None):
        self._cursor.execute(sql, _convert_params(params))
        return self

    def executemany(self, sql: str, params_list: Iterable[Any]):
        self._cursor.executemany(sql, [_convert_params(params) for params in params_list])
        return self

    def fetchone(self):
        return _wrap_row(self._cursor.fetchone())

    def fetchall(self):
        return [_wrap_row(row) for row in self._cursor.fetchall()]

    def fetchmany(self, size: int | None = None):
        if size is None:
            return [_wrap_row(row) for row in self._cursor.fetchmany()]
        return [_wrap_row(row) for row in self._cursor.fetchmany(size)]

    def close(self):
        return self._cursor.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PostgresConnection:
    """Small PostgreSQL connection facade used by existing services."""

    is_postgres = True

    def __init__(self, dsn: str, timeout: float = 10.0):
        if psycopg is not None:
            self._conn = psycopg.connect(
                dsn,
                row_factory=dict_row,
                client_encoding="UTF8",
                connect_timeout=int(timeout),
            )
        elif psycopg2 is not None:  # pragma: no cover
            self._conn = psycopg2.connect(
                dsn,
                cursor_factory=psycopg2.extras.RealDictCursor,
                connect_timeout=int(timeout),
            )
        else:  # pragma: no cover
            raise ImportError("psycopg is required for PostgreSQL connections")

    def cursor(self) -> PostgresCursor:
        return PostgresCursor(self._conn.cursor())

    def execute(self, sql: str, params: Any = None) -> PostgresCursor:
        cursor = self.cursor()
        return cursor.execute(sql, params)

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            self.rollback()
        else:
            self.commit()
        self.close()
