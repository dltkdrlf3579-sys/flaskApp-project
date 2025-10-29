"""Repository for board-specific column configuration management."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, List

from db_connection import get_db_connection
from repositories.common.board_config import get_board_config


_PROTECTED_COMMON = {"attachments", "detailed_content", "notes", "note", "created_at"}
_PER_BOARD_PROTECTED = {
    'accident': {"accident_number"},
    'safety_instruction': {"issue_number"},
    'change_request': {"request_number"},
    'follow_sop': {"work_req_no"},
    'full_process': {"fullprocess_number"},
    'subcontract_approval': {"approval_number"},
    'subcontract_report': {"report_number"},
}


class ColumnConfigRepository:
    """Encapsulates CRUD operations for board column configuration tables."""

    def __init__(self, db_path: str, board_type: str) -> None:
        self.db_path = db_path
        self.board_type = board_type
        self.config = get_board_config(board_type)
        self.table = self.config['column_table']

    # ------------------------------------------------------------------
    # Helpers

    def _protected_columns(self) -> set[str]:
        protected = set(_PROTECTED_COMMON)
        protected |= _PER_BOARD_PROTECTED.get(self.board_type, set())
        return {col.lower() for col in protected}

    def _fetch_existing_columns(self, cursor) -> set[str]:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
            """,
            (self.table,),
        )
        return {row[0] for row in cursor.fetchall()}

    # ------------------------------------------------------------------
    # Public API

    def list(self, *, active_only: bool = True) -> List[Dict[str, Any]]:
        conn = get_db_connection(self.db_path)
        try:
            protected = self._protected_columns()
            protected_quoted: List[str] = []
            for col in sorted(protected):
                safe = (col or '').replace("'", "''")
                protected_quoted.append("'" + safe + "'")
            protected_sql = ','.join(protected_quoted) if protected_quoted else "''"

            where_clauses = [
                "COALESCE(is_deleted, 0) = 0",
                "COALESCE(is_system, 0) = 0",
                f"LOWER(column_key) NOT IN ({protected_sql})",
            ]
            if active_only:
                where_clauses.append("COALESCE(is_active, 1) = 1")

            query = (
                f"SELECT * FROM {self.table} "
                f"WHERE {' AND '.join(where_clauses)} "
                "ORDER BY column_order"
            )

            rows = conn.execute(query).fetchall()
            return [dict(row) for row in rows]
        finally:
            conn.close()

    def add(self, data: Dict[str, Any]) -> int:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        try:
            column_key = data.get('column_key')
            if not column_key:
                cursor.execute(
                    f"""
                    SELECT COALESCE(MAX(CAST(SUBSTRING(column_key FROM 7) AS INTEGER)), 0)
                    FROM {self.table}
                    WHERE column_key LIKE 'column%'
                    """
                )
                max_seq = cursor.fetchone()[0] or 0
                column_key = f"column{max_seq + 1}"

            cursor.execute(
                f"SELECT COALESCE(MAX(column_order), 0) FROM {self.table}"
            )
            next_order = (cursor.fetchone()[0] or 0) + 1

            existing_columns = self._fetch_existing_columns(cursor)

            columns: List[str] = ['column_key', 'column_name', 'column_type', 'column_order', 'is_active']
            values: List[Any] = [
                column_key,
                data['column_name'],
                data['column_type'],
                next_order,
                1,
            ]

            if 'dropdown_options' in existing_columns:
                columns.append('dropdown_options')
                if data.get('column_type') == 'dropdown':
                    values.append(json.dumps(data.get('dropdown_options', [])))
                else:
                    values.append(None)

            if 'table_name' in existing_columns and 'table_name' in data:
                columns.append('table_name')
                values.append(data['table_name'])

            if 'table_type' in existing_columns and 'table_type' in data:
                columns.append('table_type')
                values.append(data['table_type'])

            placeholders = ', '.join(['%s'] * len(values))
            column_clause = ', '.join(columns)

            cursor.execute_with_returning_id(
                f"""
                INSERT INTO {self.table} ({column_clause}, created_at, updated_at)
                VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                values,
            )
            new_id = cursor.lastrowid
            conn.commit()
            return new_id
        finally:
            conn.close()

    def update(self, column_id: int, data: Dict[str, Any]) -> bool:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT column_key, COALESCE(is_system, 0) FROM {self.table} WHERE id = %s",
                (column_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Column not found")
            col_key = row[0]
            is_system = row[1]
            if is_system == 1 or str(col_key).lower() in self._protected_columns():
                raise ValueError("Protected column cannot be modified")

            update_fields: List[str] = []
            params: List[Any] = []

            if 'column_name' in data:
                update_fields.append('column_name = %s')
                params.append(data['column_name'])

            if 'column_type' in data:
                update_fields.append('column_type = %s')
                params.append(data['column_type'])

            if 'dropdown_options' in data:
                update_fields.append('dropdown_options = %s')
                params.append(json.dumps(data['dropdown_options']))

            if 'is_active' in data:
                update_fields.append('is_active = %s')
                params.append(1 if data['is_active'] else 0)

            if 'column_order' in data:
                update_fields.append('column_order = %s')
                params.append(data['column_order'])

            if update_fields:
                update_fields.append('updated_at = CURRENT_TIMESTAMP')
                params.append(column_id)
                cursor.execute(
                    f"""
                    UPDATE {self.table}
                    SET {', '.join(update_fields)}
                    WHERE id = %s
                    """,
                    params,
                )
                conn.commit()
            return True
        finally:
            conn.close()

    def delete(self, column_id: int, *, hard_delete: bool = False) -> bool:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT column_key, COALESCE(is_system, 0) FROM {self.table} WHERE id = %s",
                (column_id,),
            )
            row = cursor.fetchone()
            if not row:
                raise ValueError("Column not found")
            col_key, is_system = row[0], row[1]
            if is_system == 1 or str(col_key).lower() in self._protected_columns():
                raise ValueError("Protected column cannot be deleted")

            if hard_delete:
                cursor.execute(
                    f"DELETE FROM {self.table} WHERE id = %s",
                    (column_id,),
                )
            else:
                cursor.execute(
                    f"""
                    UPDATE {self.table}
                    SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (column_id,),
                )
            conn.commit()
            return True
        finally:
            conn.close()

    def reorder(self, items: Iterable[Dict[str, Any]]) -> bool:
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        try:
            for item in items:
                cursor.execute(
                    f"""
                    UPDATE {self.table}
                    SET column_order = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (item['column_order'], item['id']),
                )
            conn.commit()
            return True
        finally:
            conn.close()
