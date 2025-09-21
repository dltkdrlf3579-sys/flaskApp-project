"""Repository implementation for the accident board."""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple

import sqlite3

from werkzeug.datastructures import FileStorage

from db_connection import get_db_connection
from db.upsert import safe_upsert
from section_service import SectionConfigService
from utils.sql_filters import sql_is_active_true, sql_is_deleted_false
from upload_utils import validate_uploaded_files
from timezone_config import get_korean_time
class AccidentRepository:
    """Encapsulates database operations used by the accident controller."""

    def __init__(self, db_path: str) -> None:
        self._db_path = db_path

    @property
    def db_path(self) -> str:
        return self._db_path

    @contextmanager
    def connection(self):
        conn = get_db_connection(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def fetch_list_context(
        self,
        filters: Mapping[str, Any],
        pagination: Tuple[int, int],
    ) -> Dict[str, Any]:
        """Replicates the existing accident() list view logic and returns template context."""

        from common_mapping import smart_apply_mappings

        page, per_page = pagination

        with self.connection() as conn:
            section_service = SectionConfigService('accident', self.db_path)
            sections = section_service.get_sections() or []

            dynamic_columns = self._fetch_dynamic_columns(conn)
            self._normalise_column_order(dynamic_columns, sections)
            all_keys = self._fetch_all_column_keys(conn, dynamic_columns)
            self._normalise_popup_types(dynamic_columns, all_keys)
            section_columns = self._build_section_columns(dynamic_columns, sections)

            total_count, accidents = self._fetch_accident_rows(
                conn, filters, page, per_page
            )

            accidents = self._post_process_accidents(
                conn,
                accidents,
                dynamic_columns,
                sections,
                section_columns,
                total_count,
                page,
                per_page,
                filters,
                smart_apply_mappings,
            )

            pagination_obj = self._build_pagination(page, per_page, total_count)

            return {
                'accidents': accidents,
                'dynamic_columns': dynamic_columns,
                'sections': sections,
                'section_columns': section_columns,
                'pagination': pagination_obj,
                'total_count': total_count,
                'search_params': dict(filters),
            }

    # ------------------------------------------------------------------
    # Detail

    def fetch_detail_context(self, accident_id: str, is_popup: bool) -> Dict[str, Any]:
        from common_mapping import smart_apply_mappings

        with self.connection() as conn:
            sections = self._load_sections_for_detail(conn)
            accident, custom_data = self._load_accident_record(conn, accident_id)
            if accident is None:
                return {}

            dynamic_columns = self._fetch_dynamic_columns(conn, include_deleted=True)
            self._normalise_popup_types(dynamic_columns, {c.get('column_key') for c in dynamic_columns if c.get('column_key')})
            section_columns = self._build_section_columns(dynamic_columns, sections)
            detailed_content = self._load_detailed_content(conn, accident.get('accident_number'))
            if detailed_content is not None:
                accident['detailed_content'] = detailed_content

            basic_options = self._load_basic_options_for_detail(conn, accident)
            attachments = self._load_attachments(conn, accident.get('accident_number'))

            mapped = smart_apply_mappings([accident], 'accident', dynamic_columns, self.db_path)
            accident = mapped[0] if mapped else accident

            accident_dict = DictAsAttr(accident)

            return {
                'accident': accident_dict,
                'custom_data': custom_data,
                'sections': sections,
                'section_columns': section_columns,
                'attachments': attachments,
                'basic_options': basic_options,
                'is_popup': is_popup,
            }

    # ------------------------------------------------------------------
    # Register

    def fetch_register_context(self, is_popup: bool) -> Dict[str, Any]:
        with self.connection() as conn:
            dynamic_columns = self._fetch_dynamic_columns(conn)
            self._prepare_register_columns(dynamic_columns)

            basic_options = self._load_basic_options(conn)
            section_service = SectionConfigService('accident', self.db_path)
            sections = section_service.get_sections()
            section_columns = self._build_register_section_columns(dynamic_columns, sections)

            today_date = get_korean_time().strftime('%Y-%m-%d')

            return {
                'dynamic_columns': dynamic_columns,
                'sections': sections,
                'section_columns': section_columns,
                'basic_options': basic_options,
                'today_date': today_date,
                'is_popup': is_popup,
            }

    def save_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        with self.connection() as conn:
            cursor = conn.cursor()

            accident_number, payload, custom_data = self._prepare_save_payload(request, cursor)

            logging.info("[ACCIDENT] create request for %s", accident_number)
            logging.info("[ACCIDENT] detailed_content length incoming=%s", len(data.get('detailed_content', '') or ''))

            try:
                logging.info("[ACCIDENT] payload preview: %s", {k: payload.get(k) for k in ('accident_number','accident_name','workplace','accident_grade','accident_date')})
                logging.info("[ACCIDENT] custom_data keys: %s", list((custom_data or {}).keys()))
            except Exception:
                logging.debug("[ACCIDENT] form logging skipped", exc_info=True)

            safe_upsert(
                conn,
                'accidents_cache',
                payload,
                conflict_cols=['accident_number'],
                update_cols=['accident_name', 'workplace', 'accident_grade', 'major_category', 'injury_form', 'injury_type', 'accident_date', 'created_at', 'report_date', 'day_of_week', 'building', 'floor', 'location_category', 'location_detail', 'custom_data']
            )

            safe_upsert(
                conn,
                'accident_details',
                {
                    'accident_number': accident_number,
                    'detailed_content': request.form.get('detailed_content', ''),
                    'updated_at': None,
                },
                conflict_cols=['accident_number'],
                update_cols=['detailed_content', 'updated_at'],
            )

            attachment_data = request.form.get('attachment_data', '[]')
            try:
                if isinstance(attachment_data, list):
                    attachment_meta = attachment_data
                else:
                    attachment_meta = json.loads(attachment_data or '[]')
            except Exception:
                attachment_meta = []

            if valid_files:
                from board_services import AttachmentService

                attachment_service = AttachmentService('accident', self.db_path, conn)
                uploaded_by = request.form.get('created_by') or request.form.get('user_id', 'system')

                for index, file_info in enumerate(valid_files):
                    file_obj: FileStorage = file_info['file']
                    meta: Dict[str, Any] = {}
                    if index < len(attachment_meta) and isinstance(attachment_meta[index], dict):
                        meta['description'] = attachment_meta[index].get('description', '')
                    meta.setdefault('uploaded_by', uploaded_by)
                    attachment_service.add(accident_number, file_obj, meta)

            conn.commit()

            try:
                check_row = conn.execute(
                    "SELECT accident_name, workplace, accident_grade, custom_data FROM accidents_cache WHERE accident_number = %s",
                    (accident_number,)
                ).fetchone()
                logging.info("[ACCIDENT] persisted row snapshot: %s", dict(check_row) if check_row else None)

                detail_row = conn.execute(
                    "SELECT detailed_content FROM accident_details WHERE accident_number = %s",
                    (accident_number,)
                ).fetchone()
                logging.info("[ACCIDENT] detail length=%s", len(detail_row[0]) if detail_row and detail_row[0] else 0)
            except Exception:
                logging.debug("[ACCIDENT] post-save verification skipped", exc_info=True)

        return {
            'success': True,
            'accident_number': accident_number,
            'message': '사고가 등록되었습니다.',
        }, 200

    def update_from_request(self, request) -> Any:
        data = request.form
        files: List[FileStorage] = request.files.getlist('files')

        accident_number = (data.get('accident_number') or '').strip()
        if not accident_number:
            return {'success': False, 'message': '사고번호가 필요합니다.'}, 400

        valid_files, validation_errors = validate_uploaded_files(files)
        if validation_errors:
            return {'success': False, 'message': validation_errors[0], 'errors': validation_errors}, 400

        base_fields_raw = data.get('base_fields', '{}')
        try:
            base_fields = json.loads(base_fields_raw) if isinstance(base_fields_raw, str) else base_fields_raw
        except Exception:
            base_fields = {}
        if not isinstance(base_fields, dict):
            base_fields = {}

        custom_data_raw = data.get('custom_data', '{}')
        try:
            custom_data = json.loads(custom_data_raw) if isinstance(custom_data_raw, str) else custom_data_raw
        except Exception:
            custom_data = {}
        if not isinstance(custom_data, dict):
            custom_data = {}

        def pick(key: str, default: str = '') -> str:
            value = data.get(key)
            if value not in (None, ''):
                return value
            value = base_fields.get(key)
            if value not in (None, ''):
                return value
            return default

        payload = {
            'accident_number': accident_number,
            'accident_name': pick('accident_name'),
            'workplace': pick('workplace'),
            'accident_grade': pick('accident_grade'),
            'major_category': pick('major_category'),
            'injury_form': pick('injury_form'),
            'injury_type': pick('injury_type'),
            'accident_date': pick('accident_date'),
            'report_date': pick('report_date', get_korean_time().strftime('%Y-%m-%d') if base_fields.get('report_date') else ''),
            'day_of_week': pick('day_of_week'),
            'building': pick('building'),
            'floor': pick('floor'),
            'location_category': pick('location_category'),
            'location_detail': pick('location_detail'),
            'custom_data': json.dumps(custom_data, ensure_ascii=False),
        }

        deleted_raw = data.get('deleted_attachments', '[]')
        try:
            deleted_ids = [int(item) for item in json.loads(deleted_raw or '[]')]
        except Exception:
            deleted_ids = []

        attachment_data_raw = data.get('attachment_data', '[]')
        try:
            attachment_meta = json.loads(attachment_data_raw or '[]') if not isinstance(attachment_data_raw, list) else attachment_data_raw
        except Exception:
            attachment_meta = []
        if not isinstance(attachment_meta, list):
            attachment_meta = []

        with self.connection() as conn:
            existing_row = conn.execute(
                "SELECT * FROM accidents_cache WHERE accident_number = %s",
                (accident_number,)
            ).fetchone()
            existing = dict(existing_row) if existing_row else {}

            for key in ['accident_name', 'workplace', 'accident_grade', 'major_category', 'injury_form', 'injury_type',
                         'accident_date', 'report_date', 'day_of_week', 'building', 'floor', 'location_category', 'location_detail']:
                if payload.get(key) in (None, '') and key in existing:
                    payload[key] = existing.get(key)

            safe_upsert(
                conn,
                'accidents_cache',
                payload,
                conflict_cols=['accident_number'],
                update_cols=[
                    'accident_name', 'workplace', 'accident_grade', 'major_category', 'injury_form',
                    'injury_type', 'accident_date', 'report_date', 'day_of_week', 'building', 'floor',
                    'location_category', 'location_detail', 'custom_data'
                ],
            )

            safe_upsert(
                conn,
                'accident_details',
                {
                    'accident_number': accident_number,
                    'detailed_content': data.get('detailed_content', ''),
                    'updated_at': None,
                },
                conflict_cols=['accident_number'],
                update_cols=['detailed_content', 'updated_at'],
            )

            from board_services import AttachmentService

            attachment_service = AttachmentService('accident', self.db_path, conn)

            if deleted_ids:
                attachment_service.delete(deleted_ids)

            for meta in attachment_meta:
                attachment_id = None
                if isinstance(meta, dict) and meta.get('id'):
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
                attachment_service.add(accident_number, file_obj, meta)

            conn.commit()

            try:
                detail_row = conn.execute(
                    "SELECT detailed_content FROM accident_details WHERE accident_number = %s",
                    (accident_number,)
                ).fetchone()
                logging.info(
                    "[ACCIDENT] update detail length=%s",
                    len(detail_row[0]) if detail_row and detail_row[0] else 0
                )
            except Exception:
                logging.debug("[ACCIDENT] update detail check skipped", exc_info=True)

        return {
            'success': True,
            'accident_number': accident_number,
            'message': '사고가 수정되었습니다.',
        }, 200

    # ------------------------------------------------------------------
    # Internal helpers (list)

    def _fetch_dynamic_columns(self, conn, include_deleted: bool = False) -> List[Dict[str, Any]]:
        where_active = sql_is_active_true('is_active', conn)
        where_deleted = sql_is_deleted_false('is_deleted', conn)
        where_clause = where_active
        if not include_deleted:
            where_clause = f"{where_active} AND {where_deleted}"

        rows = conn.execute(
            f"""
            SELECT * FROM accident_column_config
            WHERE {where_clause}
            ORDER BY column_order
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def _normalise_column_order(self, dynamic_columns: List[Dict[str, Any]], sections: Iterable[Mapping[str, Any]]):
        try:
            sec_order_map = {s['section_key']: int(s.get('section_order') or 0) for s in sections if s.get('section_key')}

            def _to_int(value):
                try:
                    return int(value)
                except Exception:
                    return 0

            def _sort_key(column):
                so = sec_order_map.get(column.get('tab'), 999)
                co = _to_int(column.get('column_order'))
                cid = _to_int(column.get('id'))
                return (so, co, cid)

            dynamic_columns.sort(key=_sort_key)
        except Exception:
            pass

    def _fetch_all_column_keys(self, conn, dynamic_columns: List[Dict[str, Any]]) -> set[str]:
        try:
            where_deleted = sql_is_deleted_false('is_deleted', conn)
            rows = conn.execute(
                f"SELECT column_key FROM accident_column_config WHERE {where_deleted}"
            ).fetchall()
            keys: set[str] = set()
            for row in rows:
                try:
                    keys.add(row['column_key'])
                except Exception:
                    try:
                        keys.add(row[0])
                    except Exception:
                        pass
            return {k for k in keys if k}
        except Exception:
            return {c.get('column_key') for c in dynamic_columns if c.get('column_key')}

    def _normalise_popup_types(self, dynamic_columns: List[Dict[str, Any]], key_set: set[str]):
        try:
            suffixes = ['_id', '_dept', '_bizno', '_business_number', '_code', '_company']

            def base_key_of(key: str) -> str:
                if not isinstance(key, str):
                    return ''
                for suffix in suffixes:
                    if key.endswith(suffix):
                        return key[:-len(suffix)]
                return key

            def infer_group(base_key: str) -> str:
                if not base_key:
                    return ''
                variants = [base_key, base_key + 'd']
                if any((v + '_bizno' in key_set) or (v + '_business_number' in key_set) for v in variants):
                    return 'company'
                if any((v + '_dept') in key_set for v in variants):
                    return 'person'
                if any((v + '_code') in key_set for v in variants):
                    return 'department'
                if any((v + '_company') in key_set for v in variants):
                    return 'contractor'
                return ''

            popup_map = {
                'person': 'popup_person',
                'company': 'popup_company',
                'department': 'popup_department',
                'contractor': 'popup_contractor',
            }

            for column in dynamic_columns:
                column_key = column.get('column_key')
                base_key = base_key_of(column_key)
                group = infer_group(base_key)
                if group and column_key == base_key:
                    current_type = column.get('column_type')
                    if not current_type or current_type in ('text', 'popup', 'table', 'table_select'):
                        column['column_type'] = popup_map.get(group, current_type)
                    column['input_type'] = column.get('input_type') or 'table'
        except Exception as exc:
            logging.error(f"accident_detail: normalize popup types failed: {exc}")

    def _build_section_columns(
        self,
        dynamic_columns: Iterable[Dict[str, Any]],
        sections: Iterable[Mapping[str, Any]],
    ) -> Dict[str, List[Dict[str, Any]]]:
        section_columns: Dict[str, List[Dict[str, Any]]] = {}
        for section in sections:
            section_columns[section['section_key']] = [
                column
                for column in dynamic_columns
                if column.get('tab') == section['section_key']
            ]
        return section_columns

    def _fetch_accident_rows(
        self,
        conn,
        filters: Mapping[str, Any],
        page: int,
        per_page: int,
    ) -> Tuple[int, List[Dict[str, Any]]]:
        where_deleted = sql_is_deleted_false('is_deleted', conn)
        query = f"SELECT * FROM accidents_cache WHERE {where_deleted}"
        params: List[Any] = []

        if filters.get('accident_date_start'):
            query += " AND accident_date >= %s"
            params.append(filters['accident_date_start'])

        if filters.get('accident_date_end'):
            query += " AND accident_date <= %s"
            params.append(filters['accident_date_end'])

        if filters.get('workplace'):
            query += " AND workplace LIKE %s"
            params.append(f"%{filters['workplace']}%")

        if filters.get('accident_grade'):
            query += " AND accident_grade LIKE %s"
            params.append(f"%{filters['accident_grade']}%")

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

        if self._table_has_column(conn, 'accidents_cache', 'created_at'):
            if getattr(conn, 'is_postgres', False):
                order_clause = " ORDER BY created_at DESC NULLS LAST, accident_number DESC"
            else:
                order_clause = " ORDER BY (created_at IS NULL), created_at DESC, accident_number DESC"
        else:
            if getattr(conn, 'is_postgres', False):
                order_clause = " ORDER BY report_date DESC NULLS LAST, accident_number DESC"
            else:
                order_clause = " ORDER BY (report_date IS NULL), report_date DESC, accident_number DESC"

        query += f"{order_clause} LIMIT %s OFFSET %s"
        offset = (page - 1) * per_page
        data = conn.execute(query, (*params, per_page, offset)).fetchall()
        accidents = [dict(row) for row in data]
        return total_count, accidents

    def _table_has_column(self, conn, table_name: str, column_name: str) -> bool:
        cursor = conn.cursor()
        try:
            if getattr(conn, 'is_postgres', False):
                cursor.execute(
                    """
                    SELECT 1
                    FROM information_schema.columns
                    WHERE table_name = %s AND column_name = %s
                    """,
                    (table_name, column_name),
                )
                return cursor.fetchone() is not None
            cursor.execute(f"PRAGMA table_info({table_name})")
            for row in cursor.fetchall():
                try:
                    name = row['name']
                except Exception:
                    name = row[1] if len(row) > 1 else None
                if (name or '').lower() == column_name.lower():
                    return True
            return False
        except Exception:
            return False
        finally:
            try:
                cursor.close()
            except Exception:
                pass

    def _post_process_accidents(
        self,
        conn,
        accidents: List[Dict[str, Any]],
        dynamic_columns: List[Dict[str, Any]],
        sections: List[Dict[str, Any]],
        section_columns: Dict[str, List[Dict[str, Any]]],
        total_count: int,
        page: int,
        per_page: int,
        filters: Mapping[str, Any],
        smart_apply_mappings,
    ) -> List[Dict[str, Any]]:
        offset = (page - 1) * per_page

        for idx, accident in enumerate(accidents):
            accident['no'] = total_count - offset - idx
            self._merge_custom_data(accident)
            self._enrich_accident_metadata(conn, accident)
            self._prepare_display_created_at(accident)

        try:
            accidents = smart_apply_mappings(accidents, 'accident', dynamic_columns, self.db_path)
        except Exception as exc:
            logging.error(f"accident mapping error(top): {exc}")

        return accidents

    def _merge_custom_data(self, accident: Dict[str, Any]) -> None:
        try:
            custom_raw = accident.get('custom_data')
            if not custom_raw:
                return
            if isinstance(custom_raw, dict):
                custom_data = custom_raw
            else:
                custom_data = json.loads(custom_raw) if custom_raw else {}

            if not isinstance(custom_data, dict):
                return

            base_protected_keys = {
                'accident_number','accident_name','workplace','accident_grade','major_category',
                'injury_form','injury_type','building','floor','location_category','location_detail',
                'accident_date','created_at','report_date','day_of_week',
                'responsible_company1','responsible_company1_no','responsible_company2','responsible_company2_no'
            }

            def _is_empty(value):
                if value is None:
                    return True
                if isinstance(value, str) and value.strip() == '':
                    return True
                return False

            acc_no = str(accident.get('accident_number') or '')
            is_direct = acc_no.startswith('ACC')

            safe_updates = {}
            for key, value in custom_data.items():
                if _is_empty(value):
                    continue
                if key in base_protected_keys:
                    if not is_direct:
                        continue
                    top_value = accident.get(key)
                    if _is_empty(top_value):
                        safe_updates[key] = value
                else:
                    safe_updates[key] = value

            if safe_updates:
                accident.update(safe_updates)

            accident['custom_data'] = custom_data
        except Exception as exc:
            logging.error(f"Error parsing custom_data: {exc}")

    def _enrich_accident_metadata(self, conn, accident: Dict[str, Any]) -> None:
        try:
            if accident.get('accident_number') and not accident.get('company_name'):
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT primary_company
                    FROM accidents_cache
                    WHERE accident_number = %s
                    """,
                    (accident['accident_number'],),
                )
                row = cursor.fetchone()
                if row and row[0]:
                    accident['company_name'] = row[0]
        except Exception:
            pass

    def _prepare_display_created_at(self, accident: Dict[str, Any]) -> None:
        accident_number = str(accident.get('accident_number') or '')
        if accident_number.startswith('K'):
            accident['display_created_at'] = accident.get('report_date', accident.get('created_at', '-'))
        else:
            accident['display_created_at'] = accident.get('created_at', '-')

    def _build_pagination(self, page: int, per_page: int, total_count: int):
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

        import math

        return Pagination(page, per_page, total_count)

    # ------------------------------------------------------------------
    # Detail helpers

    def _load_sections_for_detail(self, conn) -> List[Dict[str, Any]]:
        try:
            where_active = sql_is_active_true('is_active', conn)
            where_deleted = sql_is_deleted_false('is_deleted', conn)
            rows = conn.execute(
                f"""
                SELECT * FROM accident_sections
                WHERE {where_active}
                  AND {where_deleted}
                ORDER BY section_order
                """
            ).fetchall()
            sections = [dict(row) for row in rows]
        except Exception:
            where_active = sql_is_active_true('is_active', conn)
            rows = conn.execute(
                f"""
                SELECT * FROM section_config
                WHERE board_type = 'accident' AND {where_active}
                ORDER BY section_order
                """
            ).fetchall()
            sections = [dict(row) for row in rows]

        if not sections:
            sections = [
                {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
                {'section_key': 'accident_info', 'section_name': '사고정보', 'section_order': 2},
                {'section_key': 'location_info', 'section_name': '장소정보', 'section_order': 3},
                {'section_key': 'additional', 'section_name': '추가정보', 'section_order': 4},
            ]
        return sections

    def _load_accident_record(self, conn, accident_id: str) -> Tuple[Optional[Dict[str, Any]], Dict[str, Any]]:
        where_deleted = sql_is_deleted_false('is_deleted', conn)
        cursor = conn.cursor()

        accident_row = None
        accident_id_str = str(accident_id)
        if accident_id_str.isdigit():
            try:
                accident_row = cursor.execute(
                    f"SELECT * FROM accidents_cache WHERE id = %s AND {where_deleted}",
                    (accident_id,),
                ).fetchone()
            except Exception:
                accident_row = None

        if not accident_row:
            accident_row = cursor.execute(
                f"SELECT * FROM accidents_cache WHERE accident_number = %s AND {where_deleted}",
                (accident_id,),
            ).fetchone()

        if not accident_row:
            return None, {}

        accident = dict(accident_row)
        custom_data = {}
        custom_raw = accident.get('custom_data')
        if custom_raw:
            try:
                if isinstance(custom_raw, dict):
                    custom_data = custom_raw
                else:
                    custom_data = json.loads(custom_raw) if custom_raw else {}
                if isinstance(custom_data, dict):
                    if not accident.get('created_at') and custom_data.get('created_at'):
                        accident['created_at'] = custom_data.get('created_at')
            except Exception:
                custom_data = {}

        return accident, custom_data if isinstance(custom_data, dict) else {}

    def _load_basic_options_for_detail(self, conn, accident: Dict[str, Any]):
        accident_number = str(accident.get('accident_number') or '')
        if not accident_number.startswith('ACC'):
            return {}

        from board_services import CodeService

        code_service = CodeService('accident', self.db_path)
        basic_fields = ['workplace', 'accident_grade', 'major_category', 'injury_form', 'injury_type', 'floor', 'location_category', 'building']

        basic_options = {}
        for field in basic_fields:
            codes = code_service.list(field)
            if codes and 'option_code' in codes[0]:
                codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
            basic_options[field] = codes

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT building_code as option_code,
                       building_name as option_value
                FROM buildings_cache
                WHERE is_active = 1
                ORDER BY building_name
                """
            )
            rows = cursor.fetchall()
            if rows:
                basic_options['building'] = [dict(row) for row in rows]
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
            logging.debug('[ACCIDENT] building options load skipped', exc_info=True)

        return basic_options

    def _load_detailed_content(self, conn, accident_number: Optional[str]) -> Optional[str]:
        if not accident_number:
            return None

        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT detailed_content FROM accident_details WHERE accident_number = %s",
                (accident_number,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                return row.get('detailed_content')
            try:
                return row[0]
            except Exception:
                return None
        except Exception:
            logging.debug('[ACCIDENT] detailed_content fetch failed', exc_info=True)
            try:
                conn.rollback()
            except Exception:
                pass
            return None

    def _load_attachments(self, conn, accident_number: Optional[str]):
        if not accident_number:
            return []
        try:
            from board_services import AttachmentService

            service = AttachmentService('accident', self.db_path, conn)
            return service.list(accident_number)
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Register helpers

    def _prepare_register_columns(self, dynamic_columns: List[Dict[str, Any]]):
        for column in dynamic_columns:
            if column.get('column_span'):
                try:
                    column['column_span'] = int(column['column_span'])
                except Exception:
                    pass

        for column in dynamic_columns:
            if column.get('column_type') == 'dropdown':
                column['dropdown_options_mapped'] = self._get_dropdown_options(column.get('column_key'))

        dynamic_columns[:] = normalize_column_types(dynamic_columns)

    def _load_basic_options(self, conn):
        from board_services import CodeService

        code_service = CodeService('accident', self.db_path)
        basic_fields = ['workplace', 'accident_grade', 'major_category', 'injury_form', 'injury_type', 'floor', 'location_category', 'building']

        basic_options = {}
        for field in basic_fields:
            codes = code_service.list(field)
            if codes and 'option_code' in codes[0]:
                codes = [{'code': c['option_code'], 'value': c['option_value']} for c in codes]
            basic_options[field] = codes

        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT DISTINCT building_code as option_code,
                       building_name as option_value
                FROM buildings_cache
                WHERE is_active = 1
                ORDER BY building_name
                """
            )
            rows = cursor.fetchall()
            if rows:
                basic_options['building'] = [dict(row) for row in rows]
        except Exception:
            pass

        return basic_options

    def _build_register_section_columns(self, dynamic_columns, sections):
        section_columns: Dict[str, List[Dict[str, Any]]] = {}
        for section in sections:
            cols = [col for col in dynamic_columns if col.get('tab') == section['section_key']]

            def _order_key(column):
                try:
                    return (int(column.get('column_order') or 0), int(column.get('id') or 0))
                except Exception:
                    return (column.get('column_order') or 0, column.get('id') or 0)

            cols.sort(key=_order_key)

            if section['section_key'] == 'basic_info':
                cols = [col for col in cols if col.get('column_key') not in ['accident_number', 'created_at', 'report_date']]
                cols = [
                    {
                        'column_key': 'accident_number',
                        'column_name': '사고번호',
                        'column_type': 'text',
                        'tab': 'basic_info',
                        'column_order': -2,
                        'is_active': 1,
                        'is_readonly': 1,
                        'column_span': 1,
                        'default_value': 'ACC' + get_korean_time().strftime('%y%m%d%H%M'),
                    },
                    {
                        'column_key': 'created_at',
                        'column_name': '등록일',
                        'column_type': 'date',
                        'tab': 'basic_info',
                        'column_order': -1,
                        'is_active': 1,
                        'is_readonly': 1,
                        'column_span': 1,
                        'default_value': get_korean_time().strftime('%Y-%m-%d'),
                    },
                ] + cols

            section_columns[section['section_key']] = cols

        return section_columns

    def _get_dropdown_options(self, column_key: Optional[str]):
        if not column_key:
            return []

        with self.connection() as conn:
            cursor = conn.cursor()
            rows = cursor.execute(
                """
                SELECT option_code, option_value
                FROM dropdown_option_codes_v2
                WHERE board_type = %s AND column_key = %s AND is_active = 1
                ORDER BY display_order
                """,
                ('accident', column_key),
            ).fetchall()

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
                            "[ACCIDENT] dropdown array parse failed for %s",
                            column_key,
                        )

        return [
            {
                'code': row['option_code'],
                'value': row['option_value'],
            }
            for row in rows
        ]

    def _prepare_save_payload(self, request, cursor) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        accident_number = ''
        custom_data_raw = request.form.get('custom_data', '{}')
        custom_data = json.loads(custom_data_raw) if isinstance(custom_data_raw, str) and custom_data_raw else custom_data_raw
        if not isinstance(custom_data, dict):
            custom_data = {}

        base_fields_raw = request.form.get('base_fields', '{}')
        try:
            base_fields = json.loads(base_fields_raw) if base_fields_raw else {}
        except Exception:
            base_fields = {}
        if not isinstance(base_fields, dict):
            base_fields = {}

        def _get_field(key: str, default: str = '') -> str:
            value = request.form.get(key)
            if value in (None, ''):
                value = base_fields.get(key, default)
            return value if value is not None else default

        accident_number = _get_field('accident_number') or self._generate_accident_number(cursor)

        payload = {
            'accident_number': accident_number,
            'accident_name': _get_field('accident_name'),
            'workplace': _get_field('workplace'),
            'accident_grade': _get_field('accident_grade'),
            'major_category': _get_field('major_category'),
            'injury_form': _get_field('injury_form'),
            'injury_type': _get_field('injury_type'),
            'accident_date': _get_field('accident_date'),
            'created_at': get_korean_time().strftime('%Y-%m-%d'),
            'report_date': _get_field('report_date', get_korean_time().strftime('%Y-%m-%d')),
            'day_of_week': _get_field('day_of_week'),
            'building': _get_field('building'),
            'floor': _get_field('floor'),
            'location_category': _get_field('location_category'),
            'location_detail': _get_field('location_detail'),
            'custom_data': json.dumps(custom_data, ensure_ascii=False),
        }

        return accident_number, payload, custom_data

    def _generate_accident_number(self, cursor) -> str:
        base = get_korean_time().strftime('%y%m%d')
        cursor.execute(
            """
            SELECT accident_number
            FROM accidents_cache
            WHERE accident_number LIKE %s
            ORDER BY accident_number DESC
            LIMIT 1
            """,
            (f'ACC{base}%',),
        )
        row = cursor.fetchone()
        if row and row[0]:
            try:
                seq = int(str(row[0])[-2:]) + 1
            except Exception:
                seq = 1
        else:
            seq = 1
        return f'ACC{base}{seq:02d}'


class DictAsAttr(dict):
    """Utility wrapper to access dict keys as attributes (backwards compatibility)."""

    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError as exc:
            raise AttributeError(key) from exc


def normalize_column_types(columns: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    from column_utils import normalize_column_types as _normalize

    return _normalize(list(columns))
