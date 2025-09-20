"""SQL helper functions for boolean flags (PostgreSQL only in new architecture)."""
from __future__ import annotations

from typing import Any


def sql_is_active_true(field_expr: str, conn: Any) -> str:
    """Return SQL fragment that checks a boolean/int column is true."""
    # Postgres connection exposes is_postgres attribute in CompatConnection.
    # SQLite 지원은 제거 대상이지만, 남은 코드가 conn.is_postgres를 참고하므로
    # Postgres가 아니면 단순 비교를 사용한다.
    if getattr(conn, 'is_postgres', False):
        return f"(LOWER(COALESCE({field_expr}::text, '0')) IN ('1','t','true'))"
    return f"(COALESCE({field_expr}, 0) = 1)"


def sql_is_deleted_false(field_expr: str, conn: Any) -> str:
    """Return SQL fragment that checks a boolean/int column is false or NULL."""
    if getattr(conn, 'is_postgres', False):
        return f"(LOWER(COALESCE({field_expr}::text, '0')) NOT IN ('1','t','true'))"
    return f"(COALESCE({field_expr}, 0) = 0)"
