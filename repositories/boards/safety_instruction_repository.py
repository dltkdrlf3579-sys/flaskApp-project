"""Repository implementation for the Safety Instruction board."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import sqlite3

from werkzeug.datastructures import FileStorage

from db_connection import get_db_connection
from db.upsert import safe_upsert
from upload_utils import validate_uploaded_files
from utils.sql_filters import sql_is_active_true, sql_is_deleted_false
from column_utils import normalize_column_types
from section_service import SectionConfigService
from timezone_config import get_korean_time


class SafetyInstructionRepository:
    """Encapsulates database operations for safety instruction board."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._columns_cache: Dict[str, List[str]] = {}

    @property
    def db_path(self) -> str:
        return self._db_path

    # ------------------------------------------------------------------
    # Connection helper

    @contextmanager
    def connection(self):
        conn = get_db_connection(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    # ------------------------------------------------------------------
    # Metadata helpers

    def _get_table_columns(self, conn, table_name: str) -> List[str]:
        key = (table_name or '').lower()
        if key in self._columns_cache:
            return self._columns_cache[key]

        columns: List[str] = []
        cursor = conn.cursor()
        try:
            if getattr(conn, 'is_postgres', False):
                cursor.execute(
                    """
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    ('public', key),
                )
                rows = cursor.fetchall()
                for row in rows:
                    if isinstance(row, dict):
                        columns.append(str(row.get('column_name')))
                    else:
                        try:
                            columns.append(str(row[0]))
                        except Exception:
                            pass
            else:
                cursor.execute(f"PRAGMA table_info({key})")
                rows = cursor.fetchall()
                for row in rows:
                    try:
                        columns.append(str(row['name']))
                    except Exception:
                        try:
                            columns.append(str(row[1]))
                        except Exception:
                            pass
        except Exception:
            columns = []
        finally:
            try:
                cursor.close()
            except Exception:
                pass

        filtered = [col for col in columns if col]
        self._columns_cache[key] = filtered
        return filtered

    def _deserialize_custom_data(self, value: Any) -> Dict[str, Any]:
        """Normalize stored custom_data into a plain dict."""
        if isinstance(value, dict):
            return value
        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return {}
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, dict):
                    return parsed
            except Exception:
                logging.debug("[SAFETY_INSTRUCTION] custom_data deserialize failed", exc_info=True)
        elif hasattr(value, 'items'):
            try:
                return dict(value)
            except Exception:
                logging.debug("[SAFETY_INSTRUCTION] custom_data mapping coercion failed", exc_info=True)
        return {}

    # ------------------------------------------------------------------
    # List context

    def fetch_list_context(
        self,
        filters: Mapping[str, Any],
        pagination: Tuple[int, int],
    ) -> Dict[str, Any]:
        from common_mapping import smart_apply_mappings

        page, per_page = pagination

        with self.connection() as conn:
            sections = self._load_sections(conn)
            dynamic_columns = normalize_column_types(self._load_dynamic_columns(conn))
            section_columns = self._build_section_columns(dynamic_columns, sections)

            total_count, items = self._fetch_rows(conn, filters, page, per_page)
            items = self._process_rows(items, dynamic_columns, total_count, page, per_page)

            try:
                items = smart_apply_mappings(items, 'safety_instruction', dynamic_columns, self.db_path)
            except Exception as exc:
                logging.error(f"[SAFETY INSTRUCTION] mapping error: {exc}")

            pagination_obj = self._build_pagination(page, per_page, total_count)

            return {
                'safety_instructions': items,
                'dynamic_columns': dynamic_columns,
                'sections': sections,
                'section_columns': section_columns,
                'pagination': pagination_obj,
                'search_params': dict(filters),
                'filters': dict(filters),
                'total_count': total_count,
            }

    # ------------------------------------------------------------------
    # Detail context

    def fetch_detail_context(self, issue_number: str, is_popup: bool) -> Dict[str, Any]:
        with self.connection() as conn:
            sections = self._load_sections(conn)
            dynamic_columns = normalize_column_types(self._load_dynamic_columns(conn))
            section_columns = self._build_section_columns(dynamic_columns, sections)
            basic_options = self._load_basic_options(conn)

            instruction = self._load_instruction(conn, issue_number)
            if not instruction:
                return {}

            attachments = self._load_attachments(conn, issue_number)

            return {
                'instruction': instruction,
                'custom_data': instruction.get('custom_data', {}),
                'sections': sections,
                'section_columns': section_columns,
                'attachments': attachments,
                'basic_options': basic_options,
                'is_popup': is_popup,
            }

    # ------------------------------------------------------------------
    # Register context

    def fetch_register_context(self, is_popup: bool) -> Dict[str, Any]:
        with self.connection() as conn:
            dynamic_columns = normalize_column_types(self._load_dynamic_columns(conn))
            sections = self._load_sections(conn)
            section_columns = self._build_section_columns(dynamic_columns, sections)
            basic_options = self._load_basic_options(conn)

            today_date = get_korean_time().strftime('%Y-%m-%d')

            return {
                'dynamic_columns': dynamic_columns,
                'sections': sections,
                'section_columns': section_columns,
                'basic_info_columns': section_columns.get('basic_info', []),
                'violation_info_columns': section_columns.get('violation_info', []),
                'additional_columns': section_columns.get('additional', []),
                'basic_options': basic_options,
                'today_date': today_date,
                'is_popup': is_popup,
            }

    # ------------------------------------------------------------------
    # Save / Update

    def save_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        with self.connection() as conn:
            payload = self._prepare_save_payload(request)
            issue_number = payload['issue_number']

            table_columns = set(self._get_table_columns(conn, 'safety_instructions'))
            filtered_payload = {
                key: value for key, value in payload.items() if key in table_columns
            }

            update_candidates = [
                'issuer',
                'issuer_department',
                'classification',
                'employment_type',
                'primary_company',
                'primary_business_number',
                'subcontractor',
                'subcontractor_business_number',
                'disciplined_person',
                'gbm',
                'business_division',
                'team',
                'department',
                'violation_date',
                'discipline_date',
                'discipline_department',
                'discipline_type',
                'accident_type',
                'accident_grade',
                'safety_violation_grade',
                'violation_type',
                'custom_data',
                'updated_at',
            ]
            update_cols = [col for col in update_candidates if col in table_columns]
            if 'custom_data' in table_columns and 'custom_data' not in update_cols:
                update_cols.append('custom_data')
            if 'updated_at' in table_columns and 'updated_at' not in update_cols:
                update_cols.append('updated_at')

            fallback_updates = [
                col for col in ('custom_data', 'updated_at') if col in table_columns
            ]

            safe_upsert(
                conn,
                'safety_instructions',
                filtered_payload,
                conflict_cols=['issue_number'],
                update_cols=update_cols or fallback_updates or list(filtered_payload.keys()),
            )

            detail_columns = set(self._get_table_columns(conn, 'safety_instruction_details'))
            detail_payload = {
                'issue_number': issue_number,
                'detailed_content': request.form.get('detailed_content', ''),
                'updated_at': None,
            }
            detail_payload = {
                key: value for key, value in detail_payload.items() if key in detail_columns
            }
            detail_update_cols = [
                col for col in ('detailed_content', 'updated_at') if col in detail_columns
            ]

            if detail_payload:
                fallback_detail_updates = [
                    col for col in ('detailed_content', 'updated_at') if col in detail_columns
                ]

                safe_upsert(
                    conn,
                    'safety_instruction_details',
                    detail_payload,
                    conflict_cols=['issue_number'],
                    update_cols=detail_update_cols or fallback_detail_updates or list(detail_payload.keys()),
                )

            attachment_data = request.form.get('attachment_data', '[]')
            try:
                attachment_meta = json.loads(attachment_data or '[]') if not isinstance(attachment_data, list) else attachment_data
            except Exception:
                attachment_meta = []
            logging.info("[SAFETY_INSTRUCTION] attachment meta: %s", attachment_meta)

            if valid_files:
                from board_services import AttachmentService

                attachment_service = AttachmentService('safety_instruction', self.db_path, conn)
                uploaded_by = request.form.get('created_by') or request.form.get('user_id', 'system')

                for index, file_info in enumerate(valid_files):
                    file_obj: FileStorage = file_info['file']
                    meta: Dict[str, Any] = {}
                    if index < len(attachment_meta) and isinstance(attachment_meta[index], dict):
                        meta['description'] = attachment_meta[index].get('description', '')
                    meta.setdefault('uploaded_by', uploaded_by)
                    logging.info(
                        "[SAFETY_INSTRUCTION] saving attachment #%s description=%s",
                        index,
                        meta.get('description')
                    )
                    attachment_service.add(issue_number, file_obj, meta)

            conn.commit()

        return {
            'success': True,
            'issue_number': issue_number,
            'message': '환경안전 지시서가 등록되었습니다.',
        }, 200

    def update_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')
        issue_number = data.get('issue_number')
        custom_data_raw = data.get('custom_data', '{}')
        detailed_content = data.get('detailed_content', '')

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        try:
            if isinstance(custom_data_raw, dict):
                custom_data = custom_data_raw
            else:
                custom_data = json.loads(custom_data_raw) if custom_data_raw else {}
        except Exception:
            return {'success': False, 'message': '잘못된 데이터 형식입니다.'}, 400

        if not issue_number:
            return {'success': False, 'message': '발부번호가 필요합니다.'}, 400

        attachment_meta_raw = data.get('attachment_data', '[]')
        try:
            attachment_meta = (
                json.loads(attachment_meta_raw or '[]')
                if not isinstance(attachment_meta_raw, list)
                else attachment_meta_raw
            )
        except Exception:
            attachment_meta = []
        logging.info(
            "[SAFETY_INSTRUCTION] update attachment meta: %s",
            attachment_meta
        )

        deleted_attachments_raw = data.get('deleted_attachments', '[]')
        try:
            deleted_attachment_ids = [
                int(item) for item in json.loads(deleted_attachments_raw or '[]')
            ]
        except Exception:
            deleted_attachment_ids = []

        with self.connection() as conn:
            is_postgres = getattr(conn, 'is_postgres', False)
            timestamp_expr = 'NOW()' if is_postgres else "datetime('now')"

            table_columns = set(self._get_table_columns(conn, 'safety_instructions'))
            set_parts: List[str] = []
            params: List[Any] = []

            if 'custom_data' in table_columns:
                set_parts.append('custom_data = %s')
                params.append(json.dumps(custom_data, ensure_ascii=False))

            updated_by = request.form.get('updated_by') or request.form.get('user_id', 'system')
            if 'updated_by' in table_columns:
                set_parts.append('updated_by = %s')
                params.append(updated_by)

            if 'updated_at' in table_columns:
                set_parts.append(f'updated_at = {timestamp_expr}')

            detail_columns = set(self._get_table_columns(conn, 'safety_instruction_details'))
            detail_set_parts: List[str] = []
            detail_params: List[Any] = []

            if 'detailed_content' in detail_columns:
                detail_set_parts.append('detailed_content = %s')
                detail_params.append(detailed_content)

            if 'updated_at' in detail_columns:
                detail_set_parts.append(f'updated_at = {timestamp_expr}')
            from board_services import AttachmentService

            cursor = None
            try:
                if set_parts:
                    cursor = conn.cursor()
                    params.append(issue_number)
                    sql = f"UPDATE safety_instructions SET {', '.join(set_parts)} WHERE issue_number = %s"
                    cursor.execute(sql, params)

                if detail_set_parts:
                    if cursor is None:
                        cursor = conn.cursor()
                    detail_params.append(issue_number)
                    detail_sql = (
                        f"UPDATE safety_instruction_details SET {', '.join(detail_set_parts)} "
                        "WHERE issue_number = %s"
                    )
                    cursor.execute(detail_sql, detail_params)

                attachment_service = AttachmentService('safety_instruction', self.db_path, conn)

                if deleted_attachment_ids:
                    attachment_service.delete(deleted_attachment_ids)

                for meta in attachment_meta:
                    try:
                        attachment_id = int(meta.get('id')) if meta and meta.get('id') else None
                    except Exception:
                        attachment_id = None
                    if attachment_id:
                        fields: Dict[str, Any] = {}
                        if 'description' in meta:
                            fields['description'] = meta.get('description', '')
                        if fields:
                            logging.info(
                                "[SAFETY_INSTRUCTION] update meta attachment_id=%s fields=%s",
                                attachment_id,
                                fields
                            )
                            attachment_service.update_meta(attachment_id, fields)

                if valid_files:
                    new_meta = [m for m in attachment_meta if isinstance(m, dict) and m.get('isNew')]
                    uploaded_by = data.get('updated_by') or data.get('user_id', 'system')
                    for idx, file_info in enumerate(valid_files):
                        file_obj: FileStorage = file_info['file']
                        meta: Dict[str, Any] = {}
                        if idx < len(new_meta):
                            meta['description'] = new_meta[idx].get('description', '')
                        meta.setdefault('uploaded_by', uploaded_by)
                        logging.info(
                            "[SAFETY_INSTRUCTION] add new attachment idx=%s desc=%s",
                            idx,
                            meta.get('description')
                        )
                        attachment_service.add(issue_number, file_obj, meta)

                conn.commit()
            finally:
                if cursor is not None:
                    try:
                        cursor.close()
                    except Exception:
                        pass

        return {'success': True, 'message': '환경안전 지시서가 수정되었습니다.'}

    # ------------------------------------------------------------------
    # Internal helpers (list)

    def _load_sections(self, conn) -> List[Dict[str, Any]]:
        try:
            where_active = sql_is_active_true('is_active', conn)
            where_deleted = sql_is_deleted_false('is_deleted', conn)
            rows = conn.execute(
                f"""
                SELECT *
                FROM safety_instruction_sections
                WHERE {where_active}
                  AND {where_deleted}
                ORDER BY section_order
                """
            ).fetchall()
            sections = [dict(row) for row in rows]
        except Exception:
            section_service = SectionConfigService('safety_instruction', self.db_path)
            sections = section_service.get_sections()

        if not sections:
            sections = [
                {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
                {'section_key': 'violation_info', 'section_name': '위반정보', 'section_order': 2},
                {'section_key': 'additional', 'section_name': '추가기입정보', 'section_order': 3},
            ]

        return sections

    def _load_dynamic_columns(self, conn) -> List[Dict[str, Any]]:
        where_active = sql_is_active_true('is_active', conn)
        where_deleted = sql_is_deleted_false('is_deleted', conn)
        rows = conn.execute(
            f"""
            SELECT *
            FROM safety_instruction_column_config
            WHERE {where_active}
              AND {where_deleted}
            ORDER BY column_order
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _build_section_columns(
        self,
        dynamic_columns: Iterable[Dict[str, Any]],
        sections: Iterable[Mapping[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        return {
            section['section_key']: [
                column
                for column in dynamic_columns
                if column.get('tab') == section['section_key']
                and column.get('column_key') not in ['detailed_content']
            ]
            for section in sections
        }

    def _fetch_rows(
        self,
        conn,
        filters: Mapping[str, Any],
        page: int,
        per_page: int,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        table_name = 'safety_instructions'
        table_columns = set(self._get_table_columns(conn, table_name))
        is_postgres = getattr(conn, 'is_postgres', False)

        where_deleted = sql_is_deleted_false('is_deleted', conn)
        query = f"SELECT * FROM {table_name} WHERE {where_deleted}"
        params: List[Any] = []

        if filters.get('company_name'):
            query += " AND (primary_company LIKE %s OR subcontractor LIKE %s)"
            params.extend([
                f"%{filters['company_name']}%",
                f"%{filters['company_name']}%",
            ])

        if filters.get('business_number'):
            query += " AND (primary_business_number LIKE %s OR subcontractor_business_number LIKE %s)"
            params.extend([
                f"%{filters['business_number']}%",
                f"%{filters['business_number']}%",
            ])

        if filters.get('violation_date_from'):
            if getattr(conn, 'is_postgres', False):
                query += " AND (custom_data->>'violation_date') >= %s"
            else:
                query += " AND json_extract(custom_data, '$.violation_date') >= %s"
            params.append(filters['violation_date_from'])

        if filters.get('violation_date_to'):
            if getattr(conn, 'is_postgres', False):
                query += " AND (custom_data->>'violation_date') <= %s"
            else:
                query += " AND json_extract(custom_data, '$.violation_date') <= %s"
            params.append(filters['violation_date_to'])

        count_query = f"SELECT COUNT(*) FROM ({query}) AS total"
        count_row = conn.execute(count_query, params).fetchone()
        if count_row is None:
            total_count = 0
        else:
            try:
                total_count = int(count_row[0])
            except Exception:
                try:
                    total_count = int(next(iter(count_row.values())))
                except Exception:
                    total_count = 0

        offset = (page - 1) * per_page

        has_created_at = 'created_at' in table_columns
        has_violation_date = 'violation_date' in table_columns

        if has_created_at:
            if is_postgres:
                order_clause = " ORDER BY created_at DESC NULLS LAST, issue_number DESC"
            else:
                order_clause = " ORDER BY (created_at IS NULL), created_at DESC, issue_number DESC"
        elif has_violation_date:
            if is_postgres:
                order_clause = " ORDER BY violation_date DESC NULLS LAST, issue_number DESC"
            else:
                order_clause = " ORDER BY (violation_date IS NULL), violation_date DESC, issue_number DESC"
        else:
            if is_postgres:
                order_clause = (
                    " ORDER BY (custom_data->>'violation_date') DESC NULLS LAST, issue_number DESC"
                )
            else:
                order_clause = (
                    " ORDER BY (json_extract(custom_data, '$.violation_date') IS NULL), "
                    "json_extract(custom_data, '$.violation_date') DESC, issue_number DESC"
                )
        query += f"{order_clause} LIMIT %s OFFSET %s"
        items = conn.execute(query, (*params, per_page, offset)).fetchall()
        return total_count, [dict(row) for row in items]

    def _process_rows(
        self,
        items: List[Dict[str, Any]],
        dynamic_columns: List[Dict[str, Any]],
        total_count: int,
        page: int,
        per_page: int,
    ) -> List[Dict[str, Any]]:
        offset = (page - 1) * per_page

        for idx, item in enumerate(items):
            item['no'] = total_count - offset - idx
            custom_data = self._deserialize_custom_data(item.get('custom_data'))
            item['custom_data'] = custom_data

            if custom_data:
                for key, value in custom_data.items():
                    if key not in item or item[key] in (None, '', 'null'):
                        item[key] = value

        return items

    def _build_pagination(self, page: int, per_page: int, total_count: int):
        import math

        class Pagination:
            def __init__(self, page: int, per_page: int, total_count: int) -> None:
                self.page = page
                self.per_page = per_page
                self.total_count = total_count
                self.pages = math.ceil(total_count / per_page) if total_count > 0 else 1
                self.has_prev = page > 1
                self.prev_num = page - 1 if self.has_prev else None
                self.has_next = page < self.pages
                self.next_num = page + 1 if self.has_next else None

            def iter_pages(self, window_size: int = 10):
                start = ((self.page - 1) // window_size) * window_size + 1
                end = min(start + window_size - 1, self.pages)
                for num in range(start, end + 1):
                    yield num

            def get_window_info(self, window_size: int = 10):
                start = ((self.page - 1) // window_size) * window_size + 1
                end = min(start + window_size - 1, self.pages)
                return {
                    'start': start,
                    'end': end,
                    'has_prev_window': start > 1,
                    'has_next_window': end < self.pages,
                    'prev_window_start': max(1, start - window_size),
                    'next_window_start': min(end + 1, self.pages),
                }

        return Pagination(page, per_page, total_count)

    def _load_instruction(self, conn, issue_number: str) -> Optional[Dict[str, Any]]:
        where_deleted = sql_is_deleted_false('is_deleted', conn)
        row = conn.execute(
            f"""
            SELECT *
            FROM safety_instructions
            WHERE issue_number = %s
              AND {where_deleted}
            """,
            (issue_number,),
        ).fetchone()
        if not row:
            return None

        instruction = dict(row)
        custom_raw = instruction.get('custom_data')
        if custom_raw:
            try:
                if isinstance(custom_raw, dict):
                    instruction['custom_data'] = custom_raw
                else:
                    instruction['custom_data'] = json.loads(custom_raw) if custom_raw else {}
            except Exception:
                instruction['custom_data'] = {}
        else:
            instruction['custom_data'] = {}

        detailed_row = conn.execute(
            """
            SELECT detailed_content
            FROM safety_instruction_details
            WHERE issue_number = %s
            """,
            (issue_number,),
        ).fetchone()
        if detailed_row and detailed_row[0]:
            instruction['detailed_content'] = detailed_row[0]
        else:
            instruction['detailed_content'] = ''

        return instruction

    def _load_attachments(self, conn, issue_number: str):
        from board_services import AttachmentService

        try:
            service = AttachmentService('safety_instruction', self.db_path, conn)
            return service.list(issue_number)
        except Exception:
            return []

    def _load_basic_options(self, conn):
        from board_services import CodeService

        code_service = CodeService('safety_instruction', self.db_path)
        basic_fields = ['discipline_type', 'accident_type', 'accident_grade', 'safety_violation_grade']

        options = {}
        for field in basic_fields:
            codes = code_service.list(field)
            if codes and 'option_code' in codes[0]:
                codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
            options[field] = codes
        return options

    def _prepare_save_payload(self, request):
        form = request.form
        custom_data_raw = form.get('custom_data', '{}')
        try:
            custom_data = json.loads(custom_data_raw) if isinstance(custom_data_raw, str) else custom_data_raw
        except Exception:
            custom_data = {}

        issue_number = custom_data.get('issue_number') or form.get('issue_number') or self._generate_issue_number()

        def pick(*keys, default=''):
            for key in keys:
                if not key:
                    continue
                value = custom_data.get(key)
                if value not in (None, ''):
                    return value
                value = form.get(key)
                if value not in (None, ''):
                    return value
            return default

        payload = {
            'issue_number': issue_number,
            'issuer': pick('issuer'),
            'issuer_department': pick('issuer_department', 'department'),
            'classification': pick('classification'),
            'employment_type': pick('employment_type'),
            'primary_company': pick('primary_company', 'company_name'),
            'primary_business_number': pick('primary_business_number', 'business_number'),
            'subcontractor': pick('subcontractor', 'subcontractor_name'),
            'subcontractor_business_number': pick('subcontractor_business_number', 'subcontractor_bizno', 'subcontractor_business_number'),
            'disciplined_person': pick('disciplined_person'),
            'gbm': pick('gbm'),
            'business_division': pick('business_division'),
            'team': pick('team'),
            'department': pick('department'),
            'violation_date': pick('violation_date'),
            'discipline_date': pick('discipline_date'),
            'discipline_department': pick('discipline_department'),
            'discipline_type': pick('discipline_type'),
            'accident_type': pick('accident_type'),
            'accident_grade': pick('accident_grade'),
            'safety_violation_grade': pick('safety_violation_grade'),
            'violation_type': pick('violation_type'),
            'custom_data': json.dumps(custom_data, ensure_ascii=False),
            'created_at': get_korean_time().strftime('%Y-%m-%d %H:%M:%S'),
            'updated_at': None,
        }

        return payload

    def _generate_issue_number(self) -> str:
        today = get_korean_time()
        prefix = today.strftime('%Y-%m-')

        try:
            with self.connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT issue_number
                    FROM safety_instructions
                    WHERE issue_number LIKE %s
                    ORDER BY issue_number DESC
                    LIMIT 1
                    """,
                    (f"{prefix}%",),
                )
                row = cursor.fetchone()
        except Exception:
            row = None

        next_seq = 1
        if row:
            try:
                last_number = row[0] if not isinstance(row, dict) else row.get('issue_number')
            except Exception:
                last_number = None
            if isinstance(last_number, str):
                try:
                    suffix = last_number.rsplit('-', 1)[-1]
                    next_seq = int(suffix) + 1
                except Exception:
                    next_seq = 1

        return f"{prefix}{next_seq:02d}"
