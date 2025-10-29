"""Reusable controller for dynamic board-style pages."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Iterable, Mapping

from flask import jsonify, render_template

from column_utils import determine_linked_type, normalize_column_types
from common_mapping import smart_apply_mappings
from controllers import BoardController
from utils.board_layout import order_value


class DynamicBoardController(BoardController):
    """Generic controller implementation shared by dynamic board screens."""

    def list_view(self, request) -> Any:
        filters = self._extract_filters(request)
        page, per_page = self._default_pagination(request)

        self.repository.ensure_default_sections()
        sections = self.repository.fetch_sections()
        section_order_map = {
            section.get("section_key"): order_value(section.get("section_order"))
            for section in sections
        }

        dynamic_columns = self.repository.fetch_dynamic_columns(section_order_map)
        self._normalize_dynamic_columns(dynamic_columns)

        section_columns = {
            section["section_key"]: [
                column for column in dynamic_columns if column.get("tab") == section["section_key"]
            ]
            for section in sections
        }

        display_columns = self._build_display_columns(dynamic_columns)

        total_count, raw_items = self.repository.fetch_list(filters, (page, per_page))
        items = self._hydrate_items(
            raw_items,
            display_columns,
            total_count,
            page,
            per_page,
        )

        if items:
            items = smart_apply_mappings(
                items,
                self.config.board_type,
                dynamic_columns,
                self.repository.db_path,
            )

        pagination = self._build_pagination(page, per_page, total_count)

        template_args = {
            self.config.list_context_key: items,
            "records": items,
            "list_context_key": self.config.list_context_key,
            "dynamic_columns": dynamic_columns,
            "sections": sections,
            "display_columns": display_columns,
            "section_columns": section_columns,
            "pagination": pagination,
            "search_params": {k: v for k, v in filters.items() if v},
            "total_count": total_count,
        }
        context = self._build_template_context(**template_args)
        return render_template(self.config.list_template, **context)

    def detail_view(self, request, identifier: str) -> Any:
        context_data = self.repository.fetch_detail_context(
            identifier,
            request.args.get('popup') == '1',
        )
        if not context_data:
            return self.config.detail_missing_message, 404

        context = self._build_template_context(**context_data)
        return render_template(self.config.detail_template, **context)

    def register_view(self, request) -> Any:
        context_data = self.repository.fetch_register_context(
            request.args.get('popup') == '1'
        )
        context = self._build_template_context(**context_data)
        return render_template(self.config.register_template, **context)

    def save(self, request) -> Any:
        result = self.repository.save_from_request(request)
        return self._format_repository_result(result)

    def update(self, request) -> Any:
        handler = getattr(self.repository, 'update_from_request', None)
        if callable(handler):
            result = handler(request)
        else:
            result = self.repository.save_from_request(request)
        return self._format_repository_result(result)

    # ------------------------------------------------------------------
    # Internal helpers

    def _extract_filters(self, request) -> Dict[str, Any]:
        filters: Dict[str, Any] = {}
        for field in self.config.filter_fields:
            filters[field] = request.args.get(field, "").strip()
        return filters

    def _normalize_dynamic_columns(self, dynamic_columns: Iterable[Dict[str, Any]]) -> None:
        try:
            all_keys = {c.get("column_key") for c in dynamic_columns if c.get("column_key")}
            suffixes = [
                "_id",
                "_dept",
                "_department",
                "_department_code",
                "_bizno",
                "_company_bizno",
                "_code",
                "_company",
            ]

            def base_key_of(key: str) -> str:
                if not isinstance(key, str):
                    return ""
                for suffix in suffixes:
                    if key.endswith(suffix):
                        return key[: -len(suffix)]
                return key

            popup_map = {
                "person": "popup_person",
                "company": "popup_company",
                "department": "popup_department",
                "contractor": "popup_contractor",
                "division": "popup_division",
            }

            for column in dynamic_columns:
                column_key = (column.get("column_key") or "")
                base_key = base_key_of(column_key)

                if column_key.endswith(("_dept", "_department", "_department_code")):
                    column["column_type"] = "linked_dept"
                    continue

                if column_key.endswith(("_id", "_bizno", "_company", "_company_bizno")):
                    column["column_type"] = determine_linked_type(column)
                    continue

                if base_key and column_key == base_key:
                    if any(
                        (variant + "_company_bizno" in all_keys)
                        or (variant + "_bizno" in all_keys)
                        for variant in (base_key, base_key + "d")
                    ):
                        column["column_type"] = popup_map.get("company", column.get("column_type"))
                        column.setdefault("input_type", "table")
                        continue

                    if any(
                        (variant + suffix) in all_keys
                        for variant in (base_key, base_key + "d")
                        for suffix in ("_dept", "_department", "_department_code")
                    ):
                        column["column_type"] = popup_map.get("department", column.get("column_type"))
                        column.setdefault("input_type", "table")
                        continue

                    if any(
                        (variant + suffix) in all_keys
                        for variant in (base_key, base_key + "d")
                        for suffix in ("_division_code", "_division")
                    ):
                        column["column_type"] = popup_map.get("division", column.get("column_type"))
                        column.setdefault("input_type", "table")
                        continue

                    if any((variant + "_id") in all_keys for variant in (base_key, base_key + "d")):
                        column["column_type"] = popup_map.get("person", column.get("column_type"))
                        column.setdefault("input_type", "table")
        except Exception as exc:
            logging.warning("[%s] normalize column types failed: %s", self.config.board_type.upper(), exc)

        normalize_column_types(dynamic_columns)

    def _format_repository_result(self, result: Any):
        if isinstance(result, tuple):
            payload = result[0]
            status = result[1] if len(result) > 1 else 200
            headers = result[2] if len(result) > 2 else None

            if isinstance(payload, (dict, list)):
                response = jsonify(payload)
                if headers:
                    return response, status, headers
                return response, status
            return result

        if isinstance(result, (dict, list)):
            return jsonify(result)

        return result

    def _build_display_columns(
        self, dynamic_columns: Iterable[Mapping[str, Any]]
    ) -> list[Dict[str, Any]]:
        display_columns: list[Dict[str, Any]] = []

        excluded_keys = {
            "detailed_content",
            "work_req_no",
            "created_at",
            "fullprocess_number",
            "safeplace_no",
        }

        for column in dynamic_columns:
            column_key = column.get("column_key")
            if not column_key or column_key in excluded_keys:
                continue
            display_columns.append(column)

        return display_columns

    def _clean_placeholder_values(self, value):
        if isinstance(value, dict):
            return {
                key: self._clean_placeholder_values(val)
                for key, val in value.items()
            }
        if isinstance(value, list):
            return [self._clean_placeholder_values(item) for item in value]
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped or stripped.lower() in {'none', 'null', 'undefined'}:
                return None
            return stripped if stripped != value else value
        return value

    def _hydrate_items(
        self,
        raw_items: Iterable[Mapping[str, Any]],
        display_columns: Iterable[Mapping[str, Any]],
        total_count: int,
        page: int,
        per_page: int,
    ) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        offset = (page - 1) * per_page

        for idx, row in enumerate(raw_items):
            item = dict(row)
            custom_data = self._parse_custom_data(item.get("custom_data"))
            if isinstance(custom_data, dict):
                item.update(custom_data)
            for column in display_columns:
                column_key = column.get("column_key")
                if column_key and column_key in item:
                    item[column_key] = self._clean_placeholder_values(item[column_key])

            item["no"] = total_count - offset - idx
            items.append(item)

        return items

    def _parse_custom_data(self, raw: Any) -> Mapping[str, Any]:
        if isinstance(raw, dict):
            return self._clean_placeholder_values(raw)
        if isinstance(raw, str) and raw:
            try:
                parsed = json.loads(raw)
                return self._clean_placeholder_values(parsed)
            except Exception:
                logging.error("[%s] custom_data parse error", self.config.board_type.upper(), exc_info=True)
        return {}

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
                    "start": start,
                    "end": end,
                    "has_prev_window": start > 1,
                    "has_next_window": end < self.pages,
                    "prev_window_start": max(1, start - window_size),
                    "next_window_start": min(end + 1, self.pages),
                }

        return Pagination(page, per_page, total_count)
