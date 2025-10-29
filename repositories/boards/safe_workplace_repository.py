"""Repository implementation for the Safe Workplace board."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import json
import logging

from werkzeug.datastructures import FileStorage

from db_connection import get_db_connection
from db.upsert import safe_upsert
from utils.board_layout import order_value, sort_columns, sort_sections
from upload_utils import validate_uploaded_files
from id_generator import generate_safeplace_number
from timezone_config import get_korean_time


class SafeWorkplaceRepository:
    """Encapsulates database operations used by the Safe Workplace controller."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._resolved_table: Optional[str] = None
        self._columns_cache: Dict[str, List[str]] = {}

    @property
    def db_path(self) -> str:
        return self._db_path

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

    def _resolve_actor_label(self, data: Mapping[str, Any]) -> str:
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

        for candidate in ("safe_workplace", "safe_workplace_cache"):
            if self._table_exists(conn, candidate):
                self._resolved_table = candidate
                return candidate

        self._resolved_table = "safe_workplace"
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
                ('safe_workplace', column_key),
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
                            "[SAFE_WORKPLACE] dropdown array parse failed for %s",
                            column_key,
                        )

        return [
            {
                'code': row['option_code'],
                'value': row['option_value'],
            }
            for row in rows
        ]

    def _normalise_custom_data(self, value) -> Dict[str, Any]:
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            cleaned = value.strip()
            if not cleaned:
                return {}
            try:
                parsed = json.loads(cleaned)
                if isinstance(parsed, dict):
                    return parsed
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
    # Section / column metadata

    def ensure_default_sections(self) -> None:
        defaults = [
            ("basic_info", "기본정보", 1),
            ("workplace_info", "작업장정보", 2),
            ("safety_info", "안전정보", 3),
        ]

        with self.connection() as conn:
            cursor = conn.cursor()
            for key, name, order in defaults:
                cursor.execute(
                    "SELECT COUNT(*) FROM safe_workplace_sections WHERE section_key = %s",
                    (key,),
                )
                if self._first_value(cursor.fetchone(), 0) == 0:
                    cursor.execute(
                        """
                        INSERT INTO safe_workplace_sections
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
                """
                SELECT *
                FROM safe_workplace_sections
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
                """
                SELECT *
                FROM safe_workplace_column_config
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

            where_clauses = ["COALESCE(sw.is_deleted, 0) = 0"]
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
                        f"(sw.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"COALESCE(sw.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    company_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(sw.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"LOWER(COALESCE(sw.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
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
                        f"(sw.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"COALESCE(sw.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    biz_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(sw.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"LOWER(COALESCE(sw.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
                    )

                biz_filters = [f for f in biz_filters if f]
                if biz_filters:
                    where_clauses.append("(" + " OR ".join(biz_filters) + ")")
                    params.extend([like_value] * len(biz_filters))

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor = conn.cursor()
            count_query = f"SELECT COUNT(*) FROM {table} sw WHERE {where_sql}"
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

            order_pk = "safeplace_no" if "safeplace_no" in table_columns else "id"
            query = (
                f"SELECT sw.* FROM {table} sw "
                f"WHERE {where_sql} "
                f"ORDER BY sw.created_at DESC, sw.{order_pk} DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(query, [*params, per_page, offset])
            items = [dict(row) for row in cursor.fetchall()]

        return total_count, items

    # ------------------------------------------------------------------
    # Detail / register context

    def fetch_detail_context(self, safeplace_no: str, is_popup: bool) -> Dict[str, Any]:
        base_context = self.fetch_register_context(is_popup=False)
        sections = base_context['sections']
        dynamic_columns = base_context['dynamic_columns']

        workplace: Dict[str, Any] = {}
        attachments: List[Dict[str, Any]] = []

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    f"""
                    SELECT *
                    FROM {table}
                    WHERE safeplace_no = %s
                      AND COALESCE(is_deleted, 0) = 0
                    """,
                    (safeplace_no,),
                )
            except Exception as exc:
                logging.error("[SAFE_WORKPLACE] detail query failed: %s", exc)
                return {}

            row = cursor.fetchone()
            if not row:
                return {}
            workplace = dict(row)

            try:
                cursor.execute(
                    """
                    SELECT detailed_content
                    FROM safe_workplace_details
                    WHERE safeplace_no = %s
                    """,
                    (safeplace_no,),
                )
                detail_row = cursor.fetchone()
                detail_value = None
                if detail_row is not None:
                    if isinstance(detail_row, dict):
                        detail_value = detail_row.get('detailed_content')
                    elif isinstance(detail_row, (list, tuple)):
                        detail_value = detail_row[0] if detail_row else None
                    elif hasattr(detail_row, 'keys'):
                        try:
                            detail_value = detail_row['detailed_content']
                        except Exception:
                            values = list(detail_row.values()) if hasattr(detail_row, 'values') else []
                            detail_value = values[0] if values else None
                    else:
                        detail_value = detail_row
                if detail_value is not None:
                    if isinstance(detail_value, (dict, list)):
                        try:
                            workplace['detailed_content'] = json.dumps(detail_value, ensure_ascii=False)
                        except Exception:
                            workplace['detailed_content'] = str(detail_value)
                    else:
                        workplace['detailed_content'] = str(detail_value)
            except Exception:
                logging.debug("[SAFE_WORKPLACE] detail content lookup skipped", exc_info=True)

            try:
                from board_services import AttachmentService

                attachment_service = AttachmentService('safe_workplace', self._db_path, conn)
                attachments = attachment_service.list(safeplace_no)
            except Exception:
                logging.debug("[SAFE_WORKPLACE] attachment lookup skipped", exc_info=True)

        custom_data = self._normalise_custom_data(workplace.get('custom_data'))
        if custom_data:
            workplace.update(custom_data)
        workplace['custom_data'] = custom_data

        detail_context = dict(base_context)
        detail_context.update({
            'workplace': workplace,
            'custom_data': custom_data,
            'attachments': attachments,
            'safeplace_no': safeplace_no,
            'all_column_keys': [
                column.get('column_key')
                for column in dynamic_columns
                if column.get('column_key')
            ],
            'is_popup': is_popup,
        })
        return detail_context

    def fetch_register_context(self, is_popup: bool) -> Dict[str, Any]:
        self.ensure_default_sections()
        sections = self.fetch_sections()
        section_order_map = {
            section.get('section_key'): order_value(section.get('section_order'))
            for section in sections
        }
        dynamic_columns = self.fetch_dynamic_columns(section_order_map)

        created_at_dt = get_korean_time()
        created_at = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
        safeplace_no = generate_safeplace_number(self.db_path, created_at_dt)

        filtered_columns = [
            col
            for col in dynamic_columns
            if col.get('column_key') not in ['safeplace_no', 'created_at', 'updated_by', 'updated_at']
        ]

        basic_fields = [
            {
                'column_key': 'safeplace_no',
                'column_name': '점검번호',
                'column_type': 'text',
                'is_required': 1,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': safeplace_no,
            },
            {
                'column_key': 'created_at',
                'column_name': '등록일',
                'column_type': 'datetime',
                'is_required': 0,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': created_at,
            },
            {
                'column_key': 'updated_by',
                'column_name': '등록자',
                'column_type': 'text',
                'is_required': 0,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': '',
            },
            {
                'column_key': 'updated_at',
                'column_name': '수정일',
                'column_type': 'datetime',
                'is_required': 0,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': created_at,
            },
        ]

        basic_info_dynamic = [
            col
            for col in filtered_columns
            if col.get('tab') == 'basic_info'
        ]
        basic_fields.extend(basic_info_dynamic)

        section_columns = {'basic_info': basic_fields}
        for section in sections:
            if section['section_key'] != 'basic_info':
                section_columns[section['section_key']] = [
                    col for col in filtered_columns if col.get('tab') == section['section_key']
                ]

        basic_options: Dict[str, Any] = {}
        for col in filtered_columns:
            if col.get('column_type') == 'dropdown':
                col_key = col.get('column_key')
                if col_key:
                    options = self._get_dropdown_options(col_key)
                    if options:
                        basic_options[col_key] = options
                        col['dropdown_options_mapped'] = options

        today_date = get_korean_time().strftime('%Y-%m-%d')

        return {
            'dynamic_columns': filtered_columns,
            'sections': sections,
            'section_columns': section_columns,
            'basic_options': basic_options,
            'safeplace_no': safeplace_no,
            'created_at': created_at,
            'today_date': today_date,
            'is_popup': is_popup,
        }

    # ------------------------------------------------------------------
    # Save operations

    def save_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')
        actor_label = self._resolve_actor_label(data)
        detailed_content = data.get('detailed_content', '')
        actor_label = self._resolve_actor_label(data)

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

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        created_at_dt = get_korean_time()
        safeplace_no = data.get('safeplace_no') or generate_safeplace_number(self.db_path, created_at_dt)

        custom_data_json = json.dumps(custom_data, ensure_ascii=False)

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))

            upsert_data: Dict[str, Any] = {
                'safeplace_no': safeplace_no,
                'custom_data': custom_data_json,
            }

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
                    'safe_workplace_details',
                    {
                        'safeplace_no': safeplace_no,
                        'detailed_content': detailed_content,
                        'updated_at': None,
                    },
                    conflict_cols=['safeplace_no'],
                    update_cols=['detailed_content', 'updated_at'],
                )
            except Exception:
                logging.debug('[SAFE_WORKPLACE] details upsert failed', exc_info=True)

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

                    attachment_service = AttachmentService('safe_workplace', self._db_path, conn)
                    uploaded_by = actor_label or data.get('user_id', 'system')

                    for index, file_info in enumerate(valid_files):
                        file_obj: FileStorage = file_info['file']
                        meta: Dict[str, Any] = {}
                        if index < len(attachment_meta) and isinstance(attachment_meta[index], dict):
                            meta['description'] = attachment_meta[index].get('description', '')
                        meta.setdefault('uploaded_by', uploaded_by)
                        attachment_service.add(safeplace_no, file_obj, meta)
                except Exception:
                    logging.error('[SAFE_WORKPLACE] attachment save failed', exc_info=True)

            conn.commit()

        return {
            'success': True,
            'message': '안전한 일터가 등록되었습니다.',
            'safeplace_no': safeplace_no,
        }, 200

    def update_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        safeplace_no = (data.get('safeplace_no') or '').strip()
        if not safeplace_no:
            return {'success': False, 'message': '안전한 일터 번호가 필요합니다.'}, 400

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

        custom_data_json = json.dumps(custom_data, ensure_ascii=False)
        detailed_content = data.get('detailed_content', '')

        deleted_raw = data.get('deleted_attachments', '[]')
        try:
            deleted_ids = [
                int(str(item).strip())
                for item in json.loads(deleted_raw or '[]')
                if isinstance(item, (int, str)) and str(item).strip().isdigit()
            ]
        except Exception:
            deleted_ids = []

        attachment_data_raw = data.get('attachment_data', '[]')
        if isinstance(attachment_data_raw, list):
            attachment_meta = attachment_data_raw
        else:
            try:
                attachment_meta = json.loads(attachment_data_raw or '[]')
            except Exception:
                attachment_meta = []
        if not isinstance(attachment_meta, list):
            attachment_meta = []

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))

            upsert_data: Dict[str, Any] = {
                'safeplace_no': safeplace_no,
                'custom_data': custom_data_json,
            }

            update_cols = ['custom_data']

            timestamp = get_korean_time().strftime('%Y-%m-%d %H:%M:%S')
            if 'updated_at' in table_columns:
                upsert_data['updated_at'] = timestamp
                update_cols.append('updated_at')

            updated_by = actor_label or data.get('user_id', 'system')
            if 'updated_by' in table_columns:
                upsert_data['updated_by'] = updated_by
                update_cols.append('updated_by')
            elif data.get('updated_by') and 'created_by' in table_columns:
                upsert_data['created_by'] = updated_by
                update_cols.append('created_by')

            safe_upsert(
                conn,
                table,
                upsert_data,
                conflict_cols=['safeplace_no'],
                update_cols=update_cols,
            )

            safe_upsert(
                conn,
                'safe_workplace_details',
                {
                    'safeplace_no': safeplace_no,
                    'detailed_content': detailed_content,
                    'updated_at': None,
                },
                conflict_cols=['safeplace_no'],
                update_cols=['detailed_content', 'updated_at'],
            )

            from board_services import AttachmentService

            attachment_service = AttachmentService('safe_workplace', self._db_path, conn)

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
            uploaded_by = updated_by or 'system'

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
                attachment_service.add(safeplace_no, file_obj, meta)

            conn.commit()

        return {
            'success': True,
            'message': '안전한 일터가 수정되었습니다.',
            'safeplace_no': safeplace_no,
        }, 200
