"""Repository implementation for the Full Process board."""

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
from id_generator import generate_fullprocess_number
from timezone_config import get_korean_time


class FullProcessRepository:
    """Encapsulates database operations used by the Full Process controller."""

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

        for candidate in ("full_process", "full_process_cache", "fullprocess_cache"):
            if self._table_exists(conn, candidate):
                self._resolved_table = candidate
                return candidate

        # Fallback to the modern table name
        self._resolved_table = "full_process"
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
                    value = None
                    if isinstance(row, dict):
                        value = row.get("column_name")
                    else:
                        try:
                            value = row[0]
                        except Exception:
                            value = None
                    if value:
                        columns.append(str(value))
            else:
                cursor.execute(f"PRAGMA table_info({table_key})")
                for row in cursor.fetchall():
                    value = None
                    try:
                        value = row["name"]  # sqlite3.Row / SqliteRowCompat supports key access
                    except Exception:
                        try:
                            value = row[1]
                        except Exception:
                            value = None
                    if value:
                        columns.append(str(value))
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
                ('full_process', column_key),
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
                            "[FULL_PROCESS] dropdown array parse failed for %s",
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
        if not isinstance(payload, dict):
            return payload
        cleaned = {}
        for key, value in payload.items():
            if isinstance(value, str):
                stripped = value.strip()
                if stripped.lower() in ('none', 'null'):
                    cleaned[key] = None
                elif stripped == '':
                    cleaned[key] = None
                else:
                    cleaned[key] = stripped
            elif isinstance(value, dict):
                cleaned[key] = self._clean_custom_values(value)
            else:
                cleaned[key] = value
        return cleaned

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
    # Scoring helpers

    def _extract_total_score_value(self, value: Any) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
        """Return a printable total_score and optional meta map."""

        meta: Optional[Dict[str, Any]] = None

        if value is None:
            return None, None

        if isinstance(value, (int, float)):
            return str(value), None

        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return '', None
            try:
                parsed = json.loads(stripped)
            except Exception:
                return stripped, None

            if isinstance(parsed, (int, float)):
                return str(parsed), None

            if isinstance(parsed, dict):
                meta = parsed
                total = parsed.get('total')
                if total is None:
                    return '', meta
                return str(total), meta

            return stripped, None

        if isinstance(value, dict):
            meta = value
            total = value.get('total')
            if total is None:
                return '', meta
            return str(total), meta

        try:
            return str(value), None
        except Exception:
            return None, None

    def _inject_score_totals(
        self,
        process: Dict[str, Any],
        custom_data: Dict[str, Any],
        dynamic_columns: Iterable[Dict[str, Any]],
    ) -> None:
        """Ensure score_total columns surface their stored totals for templates."""

        if not isinstance(process, dict) or not isinstance(custom_data, dict):
            return

        totals_meta: Dict[str, Any] = {}

        for column in dynamic_columns:
            if column.get('column_type') != 'score_total':
                continue
            key = column.get('column_key')
            if not key:
                continue

            raw_value = custom_data.get(key)
            if raw_value is None and key in process:
                raw_value = process.get(key)

            display_value, meta = self._extract_total_score_value(raw_value)

            if display_value is not None:
                process[key] = display_value
                custom_data[key] = display_value
            if meta:
                totals_meta[key] = meta

        if totals_meta:
            process.setdefault('_score_total_meta', {}).update(totals_meta)

    # ------------------------------------------------------------------
    # Section / column metadata

    def ensure_default_sections(self) -> None:
        """Guarantee that 기본정보/프로세스 정보 섹션이 존재."""

        defaults = [
            ("basic_info", "기본정보", 1),
            ("process_info", "프로세스 정보", 2),
        ]

        with self.connection() as conn:
            cursor = conn.cursor()
            for key, name, order in defaults:
                cursor.execute(
                    "SELECT COUNT(*) FROM full_process_sections WHERE section_key = %s",
                    (key,),
                )
                if (cursor.fetchone() or [0])[0] == 0:
                    cursor.execute(
                        """
                        INSERT INTO full_process_sections
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
                FROM full_process_sections
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
                FROM full_process_column_config
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

            where_clauses = ["COALESCE(p.is_deleted, 0) = 0"]
            params: List[Any] = []

            company_name = (filters.get("company_name") or "").strip()
            business_number = (filters.get("business_number") or "").strip()

            if company_name:
                like_value = f"%{company_name}%"
                json_keys = ["company_name", "company_1cha"]
                direct_columns = [
                    col
                    for col in ("company_name", "primary_company")
                    if col in table_columns
                ]

                if is_postgres:
                    company_filters = [
                        f"(p.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"COALESCE(p.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    company_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(p.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    company_filters.extend(
                        [f"LOWER(COALESCE(p.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
                    )

                company_filters = [f for f in company_filters if f]
                if company_filters:
                    where_clauses.append("(" + " OR ".join(company_filters) + ")")
                    params.extend([like_value] * len(company_filters))

            if business_number:
                like_value = f"%{business_number}%"
                json_keys = ["business_number", "company_1cha_bizno"]
                direct_columns = [
                    col
                    for col in ("business_number", "primary_business_number")
                    if col in table_columns
                ]

                if is_postgres:
                    biz_filters = [
                        f"(p.custom_data->>'{key}') ILIKE %s"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"COALESCE(p.{col}, '') ILIKE %s" for col in direct_columns]
                    )
                else:
                    biz_filters = [
                        f"LOWER(COALESCE(JSON_EXTRACT(p.custom_data, '$.{key}'), '')) LIKE LOWER(%s)"
                        for key in json_keys
                    ]
                    biz_filters.extend(
                        [f"LOWER(COALESCE(p.{col}, '')) LIKE LOWER(%s)" for col in direct_columns]
                    )

                biz_filters = [f for f in biz_filters if f]
                if biz_filters:
                    where_clauses.append("(" + " OR ".join(biz_filters) + ")")
                    params.extend([like_value] * len(biz_filters))

            where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

            cursor = conn.cursor()
            count_query = f"SELECT COUNT(*) FROM {table} p WHERE {where_sql}"
            cursor.execute(count_query, params)
            total_count = int(self._first_value(cursor.fetchone(), 0) or 0)

            query = (
                f"SELECT p.* FROM {table} p "
                f"WHERE {where_sql} "
                "ORDER BY p.created_at DESC "
                "LIMIT %s OFFSET %s"
            )
            cursor.execute(query, [*params, per_page, offset])
            items = [dict(row) for row in cursor.fetchall()]

        return total_count, items

    # ------------------------------------------------------------------
    # Placeholder detail/save operations (to be implemented in later steps)

    def fetch_detail_context(self, fullprocess_number: str, is_popup: bool) -> Dict[str, Any]:
        base_context = self.fetch_register_context(is_popup=False)
        sections = base_context['sections']
        dynamic_columns = base_context['dynamic_columns']

        process: Dict[str, Any] = {}
        attachments: List[Dict[str, Any]] = []

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            cursor = conn.cursor()

            try:
                cursor.execute(
                    f"""
                    SELECT *
                    FROM {table}
                    WHERE fullprocess_number = %s
                      AND COALESCE(is_deleted, 0) = 0
                    """,
                    (fullprocess_number,),
                )
            except Exception as exc:
                logging.error("[FULL_PROCESS] detail query failed: %s", exc)
                return {}

            row = cursor.fetchone()
            if not row:
                return {}
            process = dict(row)

            try:
                cursor.execute(
                    """
                    SELECT detailed_content
                    FROM full_process_details
                    WHERE fullprocess_number = %s
                    """,
                    (fullprocess_number,),
                )
                detail_row = cursor.fetchone()
                detail_value = self._extract_detail_row_value(detail_row)

                if detail_value is not None:
                    if isinstance(detail_value, (dict, list)):
                        try:
                            process['detailed_content'] = json.dumps(detail_value, ensure_ascii=False)
                        except Exception:
                            process['detailed_content'] = str(detail_value)
                    else:
                        process['detailed_content'] = str(detail_value)
            except Exception:
                logging.debug("[FULL_PROCESS] detail content lookup skipped", exc_info=True)

            try:
                from board_services import AttachmentService

                attachment_service = AttachmentService('full_process', self._db_path, conn)
                attachments = attachment_service.list(fullprocess_number)
            except Exception:
                logging.debug("[FULL_PROCESS] attachment lookup skipped", exc_info=True)

        custom_data = self._normalise_custom_data(process.get('custom_data'))
        if custom_data:
            process.update(custom_data)

        self._inject_score_totals(process, custom_data, dynamic_columns)
        process['custom_data'] = custom_data

        detail_context = dict(base_context)
        detail_context.update({
            'process': process,
            'instruction': process,
            'custom_data': custom_data,
            'section_data': {},
            'attachments': attachments,
            'fullprocess_number': fullprocess_number,
            'all_column_keys': [
                column.get('column_key')
                for column in dynamic_columns
                if column.get('column_key')
            ],
            'external_scoring_data': None,
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

        from timezone_config import get_korean_time

        created_at_dt = get_korean_time()
        created_at = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
        fullprocess_number = generate_fullprocess_number(self.db_path, created_at_dt)

        basic_fields = [
            {
                'column_key': 'fullprocess_number',
                'column_name': '평가번호',
                'column_type': 'text',
                'is_required': 1,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': fullprocess_number,
            },
            {
                'column_key': 'created_at',
                'column_name': '등록일',
                'column_type': 'datetime',
                'is_required': 1,
                'is_readonly': 1,
                'tab': 'basic_info',
                'default_value': created_at,
            },
        ]

        basic_info_dynamic = [
            col for col in dynamic_columns
            if col.get('tab') == 'basic_info'
            and col.get('column_key') not in ['fullprocess_number', 'created_at']
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
        }

    # ------------------------------------------------------------------
    # Detail content helpers

    def _fetch_current_detail(self, conn, fullprocess_number: str) -> Optional[str]:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT detailed_content FROM full_process_details WHERE fullprocess_number = %s",
                (fullprocess_number,),
            )
            row = cursor.fetchone()
        except Exception:
            logging.debug('[FULL_PROCESS] current detail lookup skipped', exc_info=True)
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

    def save_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')
        detailed_content = self._extract_detailed_content(data)

        if not data.get('sections'):
            # Legacy form posts use per-section JSON payloads
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
                "[FULL_PROCESS] incoming detailed_content length=%s",
                len(detailed_content or "")
            )
        except Exception:
            logging.debug("[FULL_PROCESS] detailed_content logging skipped", exc_info=True)

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        created_at_dt = get_korean_time()
        fullprocess_number = data.get('fullprocess_number') or generate_fullprocess_number(self.db_path, created_at_dt)

        custom_data_json = json.dumps(custom_data, ensure_ascii=False)

        with self.connection() as conn:
            table = self._resolve_table_name(conn)
            table_columns = set(self._get_columns(conn, table))

            upsert_data: Dict[str, Any] = {
                'fullprocess_number': fullprocess_number,
                'custom_data': custom_data_json,
            }

            if 'created_at' in table_columns:
                upsert_data['created_at'] = created_at_dt.strftime('%Y-%m-%d %H:%M:%S')
            if 'created_by' in table_columns:
                upsert_data['created_by'] = data.get('created_by') or data.get('user_id', 'system')
            if 'is_deleted' in table_columns:
                upsert_data['is_deleted'] = 0

            safe_upsert(conn, table, upsert_data)

            try:
                safe_upsert(
                    conn,
                    'full_process_details',
                    {
                        'fullprocess_number': fullprocess_number,
                        'detailed_content': detailed_content,
                        'updated_at': None,
                    },
                    conflict_cols=['fullprocess_number'],
                    update_cols=['detailed_content', 'updated_at'],
                )
            except Exception:
                logging.debug('[FULL_PROCESS] details upsert failed', exc_info=True)

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

                    attachment_service = AttachmentService('full_process', self._db_path, conn)
                    uploaded_by = data.get('created_by') or data.get('user_id', 'system')

                    for index, file_info in enumerate(valid_files):
                        file_obj: FileStorage = file_info['file']
                        meta: Dict[str, Any] = {}
                        if index < len(attachment_meta) and isinstance(attachment_meta[index], dict):
                            meta['description'] = attachment_meta[index].get('description', '')
                        meta.setdefault('uploaded_by', uploaded_by)
                        attachment_service.add(fullprocess_number, file_obj, meta)
                except Exception:
                    logging.error('[FULL_PROCESS] attachment save failed', exc_info=True)

            conn.commit()

            try:
                detail_row = conn.execute(
                    "SELECT detailed_content FROM full_process_details WHERE fullprocess_number = %s",
                    (fullprocess_number,)
                ).fetchone()
                logging.info(
                    "[FULL_PROCESS] detail length=%s",
                    len(detail_row[0]) if detail_row and detail_row[0] else 0
                )
            except Exception:
                logging.debug("[FULL_PROCESS] post-save detail check skipped", exc_info=True)

        return {
            'success': True,
            'message': 'Full Process가 등록되었습니다.',
            'fullprocess_number': fullprocess_number,
        }, 200

    def update_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        fullprocess_number = (data.get('fullprocess_number') or '').strip()
        if not fullprocess_number:
            return {'success': False, 'message': '평가번호가 필요합니다.'}, 400

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

        with self.connection() as conn:
            existing_detail = self._fetch_current_detail(conn, fullprocess_number)
            detailed_content = self._extract_detailed_content(data, existing_detail)
            try:
                logging.info(
                    "[FULL_PROCESS] update detail incoming length=%s",
                    len(detailed_content or "")
                )
            except Exception:
                logging.debug("[FULL_PROCESS] update detail logging skipped", exc_info=True)

            table = self._resolve_table_name(conn)

            safe_upsert(
                conn,
                table,
                {
                    'fullprocess_number': fullprocess_number,
                    'custom_data': custom_data_json,
                },
                conflict_cols=['fullprocess_number'],
                update_cols=['custom_data'],
            )

            safe_upsert(
                conn,
                'full_process_details',
                {
                    'fullprocess_number': fullprocess_number,
                    'detailed_content': detailed_content,
                    'updated_at': None,
                },
                conflict_cols=['fullprocess_number'],
                update_cols=['detailed_content', 'updated_at'],
            )

            from board_services import AttachmentService

            attachment_service = AttachmentService('full_process', self._db_path, conn)

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
            uploaded_by = data.get('updated_by') or data.get('user_id', 'system')
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
                attachment_service.add(fullprocess_number, file_obj, meta)

            conn.commit()

            try:
                detail_row = conn.execute(
                    "SELECT detailed_content FROM full_process_details WHERE fullprocess_number = %s",
                    (fullprocess_number,)
                ).fetchone()
                logging.info(
                    "[FULL_PROCESS] update detail length=%s",
                    len(detail_row[0]) if detail_row and detail_row[0] else 0
                )
            except Exception:
                logging.debug("[FULL_PROCESS] update detail check skipped", exc_info=True)

        return {
            'success': True,
            'message': 'Full Process가 수정되었습니다.',
            'fullprocess_number': fullprocess_number,
        }, 200
