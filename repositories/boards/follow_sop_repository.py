"""Repository implementation for dynamic boards following the Follow SOP pattern."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

from werkzeug.datastructures import FileStorage

from db_connection import get_db_connection
from db.upsert import safe_upsert
from repositories.common.board_config import get_board_config
from utils.board_layout import order_value, sort_columns, sort_sections
from upload_utils import validate_uploaded_files
from id_generator import generate_followsop_number
from timezone_config import get_korean_time
from list_schema_utils import resolve_child_schema, deserialize_list_rows


class DynamicBoardRepository:
    """Encapsulates database operations used by dynamic, section-driven boards."""

    board_type = "follow_sop"
    default_sections: List[Tuple[str, str, int]] = [
        ("basic_info", "기본정보", 1),
        ("work_info", "작업정보", 2),
        ("additional", "추가기입정보", 3),
    ]
    identifier_column = "work_req_no"
    identifier_label = "점검번호"
    created_at_label = "등록일"

    def __init__(self, db_path: str, board_type: Optional[str] = None) -> None:
        self._db_path = db_path
        if board_type:
            self.board_type = board_type
        self._resolved_table: Optional[str] = None
        self._columns_cache: Dict[str, List[str]] = {}
        config = get_board_config(self.board_type)
        self.primary_table: str = config.get("primary_table", self.board_type)
        table_candidates = config.get("table_candidates") or ()
        self.table_candidates: Tuple[str, ...] = tuple(str(candidate) for candidate in table_candidates)
        self.section_table: str = config.get("section_table", f"{self.board_type}_sections")
        self.column_table: str = config.get("column_table", f"{self.board_type}_column_config")
        self.detail_table: str = config.get("detail_table", f"{self.board_type}_details")
        self.identifier_column = config.get("identifier_column", self.identifier_column)
        self.identifier_label = config.get("identifier_label", self.identifier_label)
        self.created_at_label = config.get("created_at_label", self.created_at_label)
        self.default_sections = list(config.get("default_sections", self.default_sections))
        self.display_name: str = config.get("display_name", self.board_type.replace("_", " ").title())
        generator = config.get("id_generator") or generate_followsop_number
        self.id_generator = generator if callable(generator) else generate_followsop_number
        self.log_prefix = f"[{self.board_type.upper()}]"

    @property
    def db_path(self) -> str:
        return self._db_path

    def _resolve_actor_label(self, data: Mapping[str, Any]) -> str:
        """Best-effort resolver for the current actor based on request payload."""
        def _extract(keys):
            for key in keys:
                value = data.get(key)
                if value not in (None, ''):
                    return str(value)
            return ''

        primary = _extract(('updated_by', 'created_by', 'actor_label'))
        if primary:
            return primary

        user_name = _extract(('user_name',))
        emp_id = _extract(('user_id', 'emp_id', 'userid'))
        login_id = _extract(('login_id', 'user_id'))

        if user_name and emp_id:
            return f"{user_name}/{emp_id}"
        if user_name:
            return user_name
        if emp_id:
            return emp_id
        if login_id:
            return login_id
        return 'SYSTEM'

    def _generate_identifier(self, created_at_dt):
        try:
            return self.id_generator(self.db_path, created_at_dt)
        except TypeError:
            return self.id_generator(self.db_path)

    # ------------------------------------------------------------------
    # Connection helpers

    @contextmanager
    def connection(self):
        conn = get_db_connection(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Internal metadata helpers

    def _table_exists(self, conn, table_name: str) -> bool:
        cursor = conn.cursor()
        table_key = (table_name or "").lower()
        try:
            if getattr(conn, "is_postgres", False):
                cursor.execute(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables
                        WHERE table_schema = %s AND table_name = %s
                    )
                    """,
                    ("public", table_key),
                )
                row = cursor.fetchone()
            else:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name = %s",
                    (table_key,),
                )
                row = cursor.fetchone()
        except Exception:
            return False

        if row is None:
            return False

        if isinstance(row, dict):
            try:
                return any(bool(value) for value in row.values())
            except Exception:
                return False

        if isinstance(row, (list, tuple)):
            return bool(row[0])

        return bool(row)

    def _resolve_table_name(self, conn) -> str:
        if self._resolved_table:
            return self._resolved_table

        candidates = [self.primary_table]
        candidates.extend(self.table_candidates)
        for candidate in candidates:
            if self._table_exists(conn, candidate):
                self._resolved_table = candidate
                return candidate

        # Fallback to the primary table name
        self._resolved_table = self.primary_table
        return self._resolved_table

    def _first_value(self, row, default=None):
        if row is None:
            return default
        if isinstance(row, dict):
            try:
                return next(iter(row.values()))
            except StopIteration:
                return default
        if isinstance(row, (list, tuple)):
            return row[0] if row else default
        if hasattr(row, '__getitem__') and not isinstance(row, (str, bytes)):
            try:
                return row[0]
            except Exception:
                pass
        if hasattr(row, 'values'):
            try:
                values = list(row.values())
                return values[0] if values else default
            except Exception:
                pass
        return row

    def _get_columns(self, conn, table_name: str) -> List[str]:
        table_key = (table_name or "").lower()
        if table_key in self._columns_cache:
            return self._columns_cache[table_key]

        cursor = conn.cursor()
        columns: List[str] = []

        try:
            if getattr(conn, "is_postgres", False):
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    ("public", table_key),
                )
                for row in cursor.fetchall():
                    if isinstance(row, dict):
                        columns.append(str(row.get("column_name")))
                    else:
                        columns.append(str(row[0]))
            else:
                cursor.execute(f"PRAGMA table_info({table_key})")
                for row in cursor.fetchall():
                    try:
                        columns.append(str(row["name"]))
                    except Exception:
                        columns.append(str(row[1]))
        except Exception:
            columns = []

        self._columns_cache[table_key] = columns
        return columns

    def _get_dropdown_options(self, column_key: str) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT option_code, option_value
                FROM dropdown_option_codes_v2
                WHERE board_type = %s AND column_key = %s AND is_active = 1
                ORDER BY display_order
                """,
                (self.board_type, column_key),
            )
            rows = cursor.fetchall()

        if not rows:
            return []

        if len(rows) == 1:
            value = rows[0]['option_value']
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.startswith('[') and stripped.endswith(']'):
                    try:
                        array = json.loads(stripped)
                        if isinstance(array, list):
                            return [
                                {
                                    'code': f"{column_key.upper()}_{index + 1:03d}",
                                    'value': str(item),
                                }
                                for index, item in enumerate(array)
                            ]
                    except Exception:
                        logging.debug(
                            "%s dropdown array parse failed for %s",
                            self.log_prefix,
                            column_key,
                        )

        return [
            {
                'code': row['option_code'],
                'value': row['option_value'],
            }
            for row in rows
        ]

    def _clean_custom_values(self, payload):
        """Normalize placeholder strings like 'None' to actual None."""
        if isinstance(payload, dict):
            cleaned: Dict[str, Any] = {}
            for key, value in payload.items():
                cleaned[key] = self._clean_custom_values(value)
            return cleaned

        if isinstance(payload, list):
            return [self._clean_custom_values(item) for item in payload]

        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped or stripped.lower() in ('none', 'null'):
                return None
            return stripped

        return payload

    def _coerce_display_values(self, payload):
        """Convert None/placeholder values to blanks for safer rendering."""
        if isinstance(payload, dict):
            return {
                key: self._coerce_display_values(value)
                for key, value in payload.items()
            }
        if isinstance(payload, list):
            return [self._coerce_display_values(item) for item in payload]
        if payload is None:
            return ''
        if isinstance(payload, str):
            stripped = payload.strip()
            if not stripped or stripped.lower() in ('none', 'null', 'undefined'):
                return ''
            return stripped
        return payload

    def _normalise_custom_data(self, value) -> Dict[str, Any]:
        if isinstance(value, dict):
            return self._clean_custom_values(value)
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return {}
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return self._clean_custom_values(parsed)
            except Exception:
                return {}
            return {}
        if hasattr(value, 'items'):
            try:
                return dict(value)
            except Exception:
                pass
        return {}

    # ------------------------------------------------------------------
    # List helpers

    def _load_list_columns(self, conn) -> Dict[str, Dict[str, Any]]:
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"""
                SELECT *
                FROM {self.column_table}
                WHERE COALESCE(is_active, 1) = 1
                  AND COALESCE(is_deleted, 0) = 0
                  AND LOWER(COALESCE(column_type, '')) = 'list'
                ORDER BY column_order
                """
            )
            rows = [dict(row) for row in cursor.fetchall()]
        except Exception:
            logging.debug("%s list column lookup failed", self.log_prefix, exc_info=True)
            return {}

        list_columns: Dict[str, Dict[str, Any]] = {}
        for row in rows:
            key = row.get('column_key')
            if not key:
                continue
            schema, generated = resolve_child_schema(row)
            if schema is not None:
                row['child_schema'] = schema
            if generated:
                row['_child_schema_generated'] = True
            list_columns[key] = row
        return list_columns

    def _normalize_list_custom_data(
        self,
        conn,
        custom_data: Optional[Mapping[str, Any]],
    ) -> Tuple[Dict[str, Any], List[str]]:
        if not isinstance(custom_data, Mapping):
            return {}, []

        normalized: Dict[str, Any] = dict(custom_data)
        errors: List[str] = []

        list_columns = self._load_list_columns(conn)
        if not list_columns:
            return normalized, errors

        for key, column in list_columns.items():
            if key not in custom_data:
                continue

            label = column.get('column_name') or key
            raw_value = custom_data.get(key)

            if raw_value in (None, '', []):
                normalized[key] = []
                continue

            if isinstance(raw_value, str):
                stripped = raw_value.strip()
                if not stripped:
                    normalized[key] = []
                    continue
                try:
                    parsed_value = json.loads(stripped)
                except json.JSONDecodeError:
                    errors.append(f"[{label}] JSON 형식이 올바르지 않습니다.")
                    normalized[key] = []
                    continue
                raw_list = parsed_value
            else:
                raw_list = raw_value

            if not isinstance(raw_list, list):
                errors.append(f"[{label}] 리스트 형식의 데이터를 기대합니다.")
                normalized[key] = []
                continue

            info = deserialize_list_rows(column, column.get('child_schema'), raw_list)

            for warning in info.get('warnings') or []:
                errors.append(f"[{label}] {warning}")

            for row_error in info.get('errors') or []:
                row_index = row_error.get('row')
                messages = row_error.get('messages') or []
                for message in messages:
                    if row_index is None:
                        errors.append(f"[{label}] {message}")
                    else:
                        errors.append(f"[{label}] 행 {row_index + 1}: {message}")

            normalized[key] = info.get('rows', raw_list)

        return normalized, errors

    def _build_list_payloads(
        self,
        dynamic_columns: Iterable[Mapping[str, Any]],
        custom_data: Optional[Mapping[str, Any]],
    ) -> Dict[str, Any]:
        if not isinstance(custom_data, Mapping):
            return {}
        payloads: Dict[str, Any] = {}
        for column in dynamic_columns or []:
            if not column or column.get('column_type') != 'list':
                continue
            key = column.get('column_key')
            if not key:
                continue

            schema, generated = resolve_child_schema(column)
            if schema is not None:
                column['child_schema'] = schema
            if generated:
                column['_child_schema_generated'] = True

            raw_value = custom_data.get(key)
            info = deserialize_list_rows(column, column.get('child_schema'), raw_value)
            payloads[key] = {
                'raw': self._ensure_raw_json(raw_value),
                'rows': info.get('rows', []),
                'raw_list': info.get('raw', []),
                'schema': column.get('child_schema'),
                'preset': info.get('preset'),
                'warnings': info.get('warnings', []),
                'errors': info.get('errors', []),
                'generated_schema': bool(column.get('_child_schema_generated')),
            }
        return payloads

    @staticmethod
    def _ensure_raw_json(value: Any) -> str:
        if value is None:
            return '[]'
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return '[]'

    @staticmethod
    def _is_child_schema_renderer_enabled() -> bool:
        flag = os.getenv('USE_CHILD_SCHEMA_RENDERER', '')
        if flag:
            return flag.lower() in {'1', 'true', 'y', 'yes'}
        # 기본값은 활성화
        return True

    # ------------------------------------------------------------------
    # Section / column metadata

    def ensure_default_sections(self) -> None:
        """Ensure 기본 섹션이 존재하도록 보강."""

        with self.connection() as conn:
            cursor = conn.cursor()
            for key, name, order in self.default_sections:
                cursor.execute(
                    f"SELECT COUNT(*) FROM {self.section_table} WHERE section_key = %s",
                    (key,),
                )
                if self._first_value(cursor.fetchone(), 0) == 0:
                    cursor.execute(
                        f"""
                        INSERT INTO {self.section_table}
                            (section_key, section_name, section_order, is_active, is_deleted)
                        VALUES
                            (%s, %s, %s, 1, 0)
                        ON CONFLICT (section_key) DO NOTHING
                        """,
                        (key, name, order),
                    )
            conn.commit()

    def fetch_sections(self) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT *
                FROM {self.section_table}
                WHERE COALESCE(is_active, 1) = 1
                  AND COALESCE(is_deleted, 0) = 0
                ORDER BY section_order
                """
            )
            sections = [dict(row) for row in cursor.fetchall()]
        return sort_sections(sections)

    def fetch_dynamic_columns(
        self, section_order_map: Mapping[str, float]
    ) -> List[Dict[str, Any]]:
        with self.connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT *
                FROM {self.column_table}
                WHERE COALESCE(is_active, 1) = 1
                  AND COALESCE(is_deleted, 0) = 0
                ORDER BY column_order
                """
            )
            rows = [dict(row) for row in cursor.fetchall()]
        return sort_columns(rows, dict(section_order_map))

    # ------------------------------------------------------------------
    # List queries

    def fetch_list(
        self,
        filters: Mapping[str, Any],
        pagination: Tuple[int, int],
    ) -> Tuple[int, List[Dict[str, Any]]]:
        page, per_page = pagination
        offset = (page - 1) * per_page
        total_count = 0
        items: List[Dict[str, Any]] = []

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))
            is_postgres = getattr(conn, "is_postgres", False)

            where_clauses = ["COALESCE(s.is_deleted, 0) = 0"]
            params: List[Any] = []

            company_name = (filters.get("company_name") or "").strip()
            business_number = (filters.get("business_number") or "").strip()

            if company_name:
                like_value = f"%{company_name}%"
                json_keys = ["company_name", "company_name_1cha"]
                direct_columns = [
                    col
                    for col in ("company_name", "primary_company")
                    if col in table_columns
                ]

                if is_postgres:
                    company_filters = [
                        f"(s.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"COALESCE(s.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    company_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(s.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"LOWER(COALESCE(s.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
                    )

                company_filters = [f for f in company_filters if f]
                if company_filters:
                    where_clauses.append("(" + " OR ".join(company_filters) + ")")
                    params.extend([like_value] * len(company_filters))

            if business_number:
                like_value = f"%{business_number}%"
                json_keys = ["business_number", "company_name_1cha_bizno"]
                direct_columns = [
                    col
                    for col in ("business_number", "primary_business_number")
                    if col in table_columns
                ]

                if is_postgres:
                    biz_filters = [
                        f"(s.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"COALESCE(s.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    biz_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(s.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"LOWER(COALESCE(s.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
                    )

                biz_filters = [f for f in biz_filters if f]
                if biz_filters:
                    where_clauses.append("(" + " OR ".join(biz_filters) + ")")
                    params.extend([like_value] * len(biz_filters))

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor = conn.cursor()
            count_query = f"SELECT COUNT(*) FROM {table} s WHERE {where_sql}"
            cursor.execute(count_query, params)
            count_row = cursor.fetchone()
            if count_row is None:
                total_count = 0
            elif isinstance(count_row, dict):
                total_count = int(next(iter(count_row.values()), 0) or 0)
            else:
                try:
                    total_count = int(count_row[0])
                except Exception:
                    try:
                        values = list(getattr(count_row, 'values')())
                        total_count = int(values[0] if values else 0)
                    except Exception:
                        total_count = 0

            query = (
                f"SELECT s.* FROM {table} s "
                f"WHERE {where_sql} "
                f"ORDER BY s.created_at DESC, s.{self.identifier_column} DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(query, [*params, per_page, offset])
            items = [dict(row) for row in cursor.fetchall()]

        return total_count, items

    # ------------------------------------------------------------------
    # Detail / register context

    def fetch_detail_context(self, identifier: str, is_popup: bool) -> Dict[str, Any]:
        base_context = self.fetch_register_context(is_popup=False)
        sections = base_context['sections']
        dynamic_columns = base_context['dynamic_columns']

        record: Dict[str, Any] = {}
        attachments: List[Dict[str, Any]] = []

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    f"""
                    SELECT *
                    FROM {table}
                    WHERE {self.identifier_column} = %s
                      AND COALESCE(is_deleted, 0) = 0
                    """,
                    (identifier,),
                )
            except Exception as exc:
                logging.error("%s detail query failed: %s", self.log_prefix, exc)
                return {}

            row = cursor.fetchone()
            if not row:
                return {}
            record = dict(row)
            record = self._clean_custom_values(record)

            try:
                cursor.execute(
                    f"""
                    SELECT detailed_content
                    FROM {self.detail_table}
                    WHERE {self.identifier_column} = %s
                    """,
                    (identifier,),
                )
                detail_row = cursor.fetchone()
                detail_value = self._extract_detail_row_value(detail_row)

                if detail_value is not None:
                    if isinstance(detail_value, (dict, list)):
                        try:
                            record['detailed_content'] = json.dumps(detail_value, ensure_ascii=False)
                        except Exception:
                            record['detailed_content'] = str(detail_value)
                    else:
                        record['detailed_content'] = str(detail_value)
            except Exception:
                logging.debug("%s detail content lookup skipped", self.log_prefix, exc_info=True)

            try:
                from board_services import AttachmentService

                attachment_service = AttachmentService(self.board_type, self._db_path, conn)
                attachments = attachment_service.list(identifier)
            except Exception:
                logging.debug("%s attachment lookup skipped", self.log_prefix, exc_info=True)

        custom_data = self._normalise_custom_data(record.get('custom_data'))
        if custom_data:
            record.update(custom_data)
        record['custom_data'] = custom_data

        list_payloads = self._build_list_payloads(dynamic_columns, custom_data)
        if list_payloads:
            record['list_payloads'] = list_payloads

        display_record = self._coerce_display_values(record)
        display_custom_data = self._coerce_display_values(custom_data or {})
        detail_context = dict(base_context)
        detail_context.update({
            'record': display_record,
            'sop': display_record,
            'instruction': display_record,
            'custom_data': display_custom_data,
            'section_data': {},
            'attachments': attachments,
            self.identifier_column: identifier,
            'identifier_column': self.identifier_column,
            'identifier_value': identifier,
            'all_column_keys': [
                column.get('column_key')
                for column in dynamic_columns
                if column.get('column_key')
            ],
            'is_popup': is_popup,
        })
        if list_payloads:
            detail_context['list_payloads'] = list_payloads
        detail_context.setdefault(
            'feature_toggles',
            {'child_schema_renderer': self._is_child_schema_renderer_enabled()},
        )
        return detail_context

    def fetch_register_context(self, is_popup: bool) -> Dict[str, Any]:
        self.ensure_default_sections()
        sections = self.fetch_sections()
        section_order_map = {
            section.get('section_key'): order_value(section.get('section_order'))
            for section in sections
        }
        dynamic_columns = self.fetch_dynamic_columns(section_order_map)
        renderer_enabled = self._is_child_schema_renderer_enabled()
        for column in dynamic_columns:
            if not isinstance(column, dict):
                continue
            if column.get('column_type') != 'list':
                continue
            schema, generated = resolve_child_schema(column, allow_generate=renderer_enabled)
            if schema is not None:
                column['child_schema'] = schema
            if generated:
                column['_child_schema_generated'] = True

        created_at_dt = get_korean_time()
        created_at = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
        identifier_value = self._generate_identifier(created_at_dt)

        basic_fields = [
            {
                'column_key': self.identifier_column,
                'column_name': self.identifier_label,
                'column_type': 'text',
                'is_required': 1,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': identifier_value,
            },
            {
                'column_key': 'created_at',
                'column_name': self.created_at_label,
                'column_type': 'datetime',
                'is_required': 1,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': created_at,
            },
        ]

        basic_info_dynamic = [
            col
            for col in dynamic_columns
            if col.get('tab') == 'basic_info'
            and col.get('column_key') not in [self.identifier_column, 'created_at']
        ]
        basic_fields.extend(basic_info_dynamic)

        section_columns = {'basic_info': basic_fields}
        for section in sections:
            if section['section_key'] != 'basic_info':
                section_columns[section['section_key']] = [
                    col for col in dynamic_columns if col.get('tab') == section['section_key']
                ]

        basic_options: Dict[str, Any] = {}
        for col in dynamic_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    options = self._get_dropdown_options(col_key)
                    if options:
                        basic_options[col_key] = options
                        col['dropdown_options_mapped'] = options

        today_date = get_korean_time().strftime('%Y-%m-%d')

        return {
            'dynamic_columns': dynamic_columns,
            'sections': sections,
            'section_columns': section_columns,
            'basic_options': basic_options,
            'today_date': today_date,
            'is_popup': is_popup,
            'identifier_column': self.identifier_column,
            'identifier_label': self.identifier_label,
            'identifier_value': identifier_value,
            'feature_toggles': {
                'child_schema_renderer': renderer_enabled,
            },
        }

    # ------------------------------------------------------------------
    # Detail content helpers

    def _fetch_current_detail(self, conn, identifier: str) -> Optional[str]:
        try:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT detailed_content FROM {self.detail_table} WHERE {self.identifier_column} = %s",
                (identifier,),
            )
            row = cursor.fetchone()
        except Exception:
            logging.debug('%s current detail lookup skipped', self.log_prefix, exc_info=True)
            return None

        return self._extract_detail_row_value(row)

    def _extract_detail_row_value(self, row) -> Optional[str]:
        if row is None:
            return None
        if isinstance(row, dict):
            return row.get('detailed_content')
        try:
            return row['detailed_content']
        except (TypeError, KeyError):
            try:
                return row[0]
            except Exception:
                return None

    def _extract_detailed_content(self, data: Mapping[str, Any], existing: Optional[str] = None) -> str:
        value = data.get('detailed_content')

        if value is None:
            for key in ('detail_content', 'detailedContent', 'content'):
                alt = data.get(key)
                if alt not in (None, ''):
                    value = alt
                    break

        if value is None:
            return existing or ''

        if isinstance(value, (list, tuple)):
            value = value[0] if value else ''

        try:
            text = str(value)
        except Exception:
            text = ''

        return text

    # ------------------------------------------------------------------
    # Save operations

    def save_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')
        detailed_content = self._extract_detailed_content(data)

        if not data.get('sections'):
            sections_json: Dict[str, Any] = {}
            for key in data.keys():
                if key in {'custom_data', 'attachment_data', 'detailed_content'}:
                    continue
                try:
                    sections_json[key] = json.loads(data.get(key) or '{}')
                except Exception:
                    sections_json[key] = {}
            custom_data = {}
            for payload in sections_json.values():
                if isinstance(payload, dict):
                    custom_data.update(payload)
        else:
            try:
                custom_data = json.loads(data.get('sections') or '{}')
            except Exception:
                custom_data = {}

        custom_data_raw = data.get('custom_data', '{}')
        try:
            if isinstance(custom_data_raw, dict):
                custom_data.update(custom_data_raw)
            else:
                custom_data.update(json.loads(custom_data_raw) or {})
        except Exception:
            pass

        try:
            logging.info(
                "%s incoming detailed_content length=%s",
                self.log_prefix,
                len(detailed_content or "")
            )
        except Exception:
            logging.debug("%s detailed_content logging skipped", self.log_prefix, exc_info=True)

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        created_at_dt = get_korean_time()
        identifier_value = (data.get(self.identifier_column) or '').strip()
        if not identifier_value:
            identifier_value = self._generate_identifier(created_at_dt)

        custom_data = self._clean_custom_values(custom_data)

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))

            custom_data, list_errors = self._normalize_list_custom_data(conn, custom_data)
            if list_errors:
                try:
                    conn.rollback()
                except Exception:
                    logging.debug("%s rollback after list validation failed", self.log_prefix, exc_info=True)
                return {
                    'success': False,
                    'message': list_errors[0],
                    'errors': list_errors,
                }, 400

            custom_data_json = json.dumps(custom_data, ensure_ascii=False)

            upsert_data: Dict[str, Any] = {
                self.identifier_column: identifier_value,
                'custom_data': custom_data_json,
            }

            actor_label = self._resolve_actor_label(data)

            if 'created_at' in table_columns:
                upsert_data['created_at'] = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
            if actor_label and 'created_by' in table_columns:
                upsert_data['created_by'] = actor_label
            if actor_label and 'updated_by' in table_columns:
                upsert_data['updated_by'] = actor_label
            if 'is_deleted' in table_columns:
                upsert_data['is_deleted'] = 0

            safe_upsert(conn, table, upsert_data)

            try:
                safe_upsert(
                    conn,
                    self.detail_table,
                    {
                        self.identifier_column: identifier_value,
                        'detailed_content': detailed_content,
                        'updated_at': None,
                    },
                    conflict_cols=[self.identifier_column],
                    update_cols=['detailed_content', 'updated_at'],
                )
            except Exception:
                logging.debug('%s details upsert failed', self.log_prefix, exc_info=True)

            attachment_data_raw = data.get('attachment_data', '[]')
            if isinstance(attachment_data_raw, list):
                attachment_meta = attachment_data_raw
            else:
                try:
                    attachment_meta = json.loads(attachment_data_raw or '[]')
                except Exception:
                    attachment_meta = []

            if valid_files:
                try:
                    from board_services import AttachmentService

                    attachment_service = AttachmentService(self.board_type, self._db_path, conn)
                    uploaded_by = actor_label or data.get('user_id', 'system')

                    for index, file_info in enumerate(valid_files):
                        file_obj: FileStorage = file_info['file']
                        meta: Dict[str, Any] = {}
                        if index < len(attachment_meta) and isinstance(attachment_meta[index], dict):
                            meta['description'] = attachment_meta[index].get('description', '')
                        meta.setdefault('uploaded_by', uploaded_by)
                        attachment_service.add(identifier_value, file_obj, meta)
                except Exception:
                    logging.error('%s attachment save failed', self.log_prefix, exc_info=True)

            conn.commit()

            try:
                detail_row = conn.execute(
                    f"SELECT detailed_content FROM {self.detail_table} WHERE {self.identifier_column} = %s",
                    (identifier_value,)
                ).fetchone()
                logging.info(
                    "%s detail length=%s",
                    self.log_prefix,
                    len(detail_row[0]) if detail_row and detail_row[0] else 0
                )
            except Exception:
                logging.debug("%s post-save detail check skipped", self.log_prefix, exc_info=True)

        return {
            'success': True,
            'message': f'{self.display_name}가 등록되었습니다.',
            self.identifier_column: identifier_value,
            'identifier_value': identifier_value,
        }, 200

    def update_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        identifier_value = (data.get(self.identifier_column) or '').strip()
        if not identifier_value:
            return {'success': False, 'message': f'{self.identifier_label}가 필요합니다.'}, 400

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        if not data.get('sections'):
            sections_json: Dict[str, Any] = {}
            for key in data.keys():
                if key in {'custom_data', 'attachment_data', 'detailed_content', 'deleted_attachments'}:
                    continue
                try:
                    sections_json[key] = json.loads(data.get(key) or '{}')
                except Exception:
                    sections_json[key] = {}
            custom_data = {}
            for payload in sections_json.values():
                if isinstance(payload, dict):
                    custom_data.update(payload)
        else:
            try:
                custom_data = json.loads(data.get('sections') or '{}')
            except Exception:
                custom_data = {}

        custom_data_raw = data.get('custom_data', '{}')
        try:
            if isinstance(custom_data_raw, dict):
                custom_data.update(custom_data_raw)
            else:
                custom_data.update(json.loads(custom_data_raw) or {})
        except Exception:
            pass

        deleted_raw = data.get('deleted_attachments', '[]')
        try:
            deleted_ids = [int(item) for item in json.loads(deleted_raw or '[]')]
        except Exception:
            deleted_ids = []

        attachment_data_raw = data.get('attachment_data', '[]')
        try:
            attachment_meta = (
                json.loads(attachment_data_raw or '[]')
                if not isinstance(attachment_data_raw, list)
                else attachment_data_raw
            )
        except Exception:
            attachment_meta = []
        if not isinstance(attachment_meta, list):
            attachment_meta = []

        custom_data = self._clean_custom_values(custom_data)

        with self.connection() as conn:
            existing_detail = self._fetch_current_detail(conn, identifier_value)
            detailed_content = self._extract_detailed_content(data, existing_detail)
            try:
                logging.info(
                    "%s update detail incoming length=%s",
                    self.log_prefix,
                    len(detailed_content or "")
                )
            except Exception:
                logging.debug("%s update detail logging skipped", self.log_prefix, exc_info=True)

            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))

            custom_data, list_errors = self._normalize_list_custom_data(conn, custom_data)
            if list_errors:
                try:
                    conn.rollback()
                except Exception:
                    logging.debug("%s rollback after list validation failed (update)", self.log_prefix, exc_info=True)
                return {
                    'success': False,
                    'message': list_errors[0],
                    'errors': list_errors,
                }, 400

            custom_data_json = json.dumps(custom_data, ensure_ascii=False)

            upsert_data: Dict[str, Any] = {
                self.identifier_column: identifier_value,
                'custom_data': custom_data_json,
            }

            actor_label = self._resolve_actor_label(data)
            update_cols: List[str] = ['custom_data']

            if 'updated_at' in table_columns:
                upsert_data['updated_at'] = get_korean_time().strftime('%Y-%m-%d %H:%M:%S')
                update_cols.append('updated_at')

            if actor_label:
                if 'updated_by' in table_columns:
                    upsert_data['updated_by'] = actor_label
                    update_cols.append('updated_by')
                elif 'created_by' in table_columns and 'updated_by' not in table_columns:
                    upsert_data['created_by'] = actor_label
                    update_cols.append('created_by')

            safe_upsert(
                conn,
                table,
                upsert_data,
                conflict_cols=[self.identifier_column],
                update_cols=update_cols,
            )

            safe_upsert(
                conn,
                self.detail_table,
                {
                    self.identifier_column: identifier_value,
                    'detailed_content': detailed_content,
                    'updated_at': None,
                },
                conflict_cols=[self.identifier_column],
                update_cols=['detailed_content', 'updated_at'],
            )

            from board_services import AttachmentService

            attachment_service = AttachmentService(self.board_type, self._db_path, conn)

            if deleted_ids:
                attachment_service.delete(deleted_ids)

            for meta in attachment_meta:
                attachment_id = None
                if isinstance(meta, dict) and meta.get('id') and not meta.get('isNew'):
                    try:
                        attachment_id = int(meta['id'])
                    except Exception:
                        attachment_id = None
                if attachment_id:
                    fields: Dict[str, Any] = {}
                    if 'description' in meta:
                        fields['description'] = meta.get('description', '')
                    if fields:
                        attachment_service.update_meta(attachment_id, fields)

            new_meta_iter = iter([
                meta for meta in attachment_meta
                if isinstance(meta, dict) and (not meta.get('id') or meta.get('isNew'))
            ])
            uploaded_by = actor_label or data.get('user_id', 'system')
            for file_info in valid_files:
                file_obj: FileStorage = file_info['file']
                meta: Dict[str, Any] = {}
                try:
                    candidate = next(new_meta_iter)
                except StopIteration:
                    candidate = None
                if isinstance(candidate, dict):
                    meta['description'] = candidate.get('description', '')
                meta.setdefault('uploaded_by', uploaded_by)
                attachment_service.add(identifier_value, file_obj, meta)

            conn.commit()

            try:
                detail_row = conn.execute(
                    f"SELECT detailed_content FROM {self.detail_table} WHERE {self.identifier_column} = %s",
                    (identifier_value,)
                ).fetchone()
                logging.info(
                    "%s update detail length=%s",
                    self.log_prefix,
                    len(detail_row[0]) if detail_row and detail_row[0] else 0
                )
            except Exception:
                logging.debug("%s update detail check skipped", self.log_prefix, exc_info=True)

        return {
            'success': True,
            'message': f'{self.display_name}가 수정되었습니다.',
            self.identifier_column: identifier_value,
            'identifier_value': identifier_value,
        }, 200


class FollowSopRepository(DynamicBoardRepository):
    """Backwards-compatible repository for the Follow SOP board."""

    board_type = "follow_sop"
