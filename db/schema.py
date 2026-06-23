"""PostgreSQL schema inspection helpers."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True)
class TableName:
    schema: str
    name: str


def split_table_name(table_name: str, default_schema: str = "public") -> TableName:
    """Split an optional schema-qualified table name."""

    raw = (table_name or "").strip().strip('"')
    if "." in raw:
        schema, name = raw.split(".", 1)
        schema = schema.strip().strip('"') or default_schema
        name = name.strip().strip('"')
    else:
        schema = default_schema
        name = raw
    return TableName(schema=schema, name=name)


def quote_identifier(identifier: str) -> str:
    """Quote a PostgreSQL identifier after basic validation."""

    if not _IDENT_RE.match(identifier or ""):
        raise ValueError(f"Invalid SQL identifier: {identifier!r}")
    return f'"{identifier}"'


def table_exists(conn: Any, table_name: str) -> bool:
    """Return whether a table exists in PostgreSQL."""

    parsed = split_table_name(table_name)
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_name = %s
        ) AS exists
        """,
        (parsed.schema, parsed.name),
    ).fetchone()
    return bool(row and row["exists"])


def column_exists(conn: Any, table_name: str, column_name: str) -> bool:
    """Return whether a column exists on a PostgreSQL table."""

    parsed = split_table_name(table_name)
    row = conn.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = %s
              AND table_name = %s
              AND column_name = %s
        ) AS exists
        """,
        (parsed.schema, parsed.name, column_name),
    ).fetchone()
    return bool(row and row["exists"])


def get_columns(conn: Any, table_name: str) -> list[dict[str, Any]]:
    """Return PostgreSQL column metadata ordered by ordinal position."""

    parsed = split_table_name(table_name)
    rows = conn.execute(
        """
        SELECT
            column_name,
            data_type,
            is_nullable,
            column_default,
            ordinal_position
        FROM information_schema.columns
        WHERE table_schema = %s
          AND table_name = %s
        ORDER BY ordinal_position
        """,
        (parsed.schema, parsed.name),
    ).fetchall()
    return [dict(row) for row in rows]


def column_names(conn: Any, table_name: str) -> list[str]:
    """Return only PostgreSQL column names."""

    return [row["column_name"] for row in get_columns(conn, table_name)]

