"""Full Process board controller for Phase 2 refactor."""

from __future__ import annotations

import json
import logging
import math
from typing import Any, Dict, Iterable, Mapping

from flask import jsonify, render_template

from column_utils import determine_linked_type, normalize_column_types
from common_mapping import smart_apply_mappings
from controllers import BoardController, BoardControllerConfig
from utils.board_layout import order_value


class FullProcessController(BoardController):
    """Controller that encapsulates Full Process board behaviour."""

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

        display_columns, scoring_cols, score_total_cols = self._build_display_columns(
            dynamic_columns
        )

        total_count, raw_items = self.repository.fetch_list(filters, (page, per_page))
        items = self._hydrate_items(
            raw_items,
            dynamic_columns,
            display_columns,
            scoring_cols,
            score_total_cols,
            total_count,
            page,
            per_page,
        )

        if items:
            items = smart_apply_mappings(
                items,
                "full_process",
                dynamic_columns,
                self.repository.db_path,
            )

        pagination = self._build_pagination(page, per_page, total_count)

        context = self._build_template_context(
            fullprocesses=items,
            dynamic_columns=dynamic_columns,
            sections=sections,
            display_columns=display_columns,
            section_columns=section_columns,
            pagination=pagination,
            search_params={k: v for k, v in filters.items() if v},
            total_count=total_count,
        )
        return render_template(self.config.list_template, **context)

    def detail_view(self, request, fullprocess_number: str) -> Any:
        context_data = self.repository.fetch_detail_context(
            fullprocess_number,
            request.args.get('popup') == '1',
        )
        if not context_data:
            return "Full Process를 찾을 수 없습니다.", 404
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
        return {
            "company_name": request.args.get("company_name", "").strip(),
            "business_number": request.args.get("business_number", "").strip(),
        }

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
            logging.warning("[FULL_PROCESS] normalize column types failed: %s", exc)

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
        self, dynamic_columns: Iterable[Dict[str, Any]]
    ) -> tuple[list[Dict[str, Any]], list[Dict[str, Any]], list[Dict[str, Any]]]:
        display_columns: list[Dict[str, Any]] = []
        scoring_cols: list[Dict[str, Any]] = []
        score_total_cols: list[Dict[str, Any]] = []

        excluded = {"detailed_content", "fullprocess_number", "created_at"}

        for column in dynamic_columns:
            column_key = column.get("column_key")
            if not column_key or column_key in excluded:
                continue

            column_type = column.get("column_type")
            if column_type == "scoring":
                display_columns.extend(self._expand_scoring_columns(column))
                scoring_cols.append(dict(column))
            else:
                display_columns.append(column)

        for column in dynamic_columns:
            if column.get("column_type") == "score_total":
                score_total_cols.append(dict(column))

        return display_columns, scoring_cols, score_total_cols

    def _expand_scoring_columns(self, column: Mapping[str, Any]) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        config = column.get("scoring_config")
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except Exception:
                config = {}
        config_items = (config or {}).get("items") or []
        for item in config_items:
            item_id = item.get("id")
            label = item.get("label") or item_id
            if not item_id:
                continue
            items.append(
                {
                    "column_key": f"{column.get('column_key')}__{item_id}",
                    "column_name": f"{column.get('column_name', column.get('column_key'))} - {label}",
                    "column_type": "number",
                    "input_type": "number_integer",
                    "is_active": 1,
                    "is_deleted": 0,
                    "tab": column.get("tab"),
                    "_virtual": 1,
                    "_source_scoring_key": column.get("column_key"),
                    "_source_item_id": item_id,
                }
            )
        return items

    def _hydrate_items(
        self,
        raw_items: Iterable[Mapping[str, Any]],
        dynamic_columns: Iterable[Mapping[str, Any]],
        display_columns: Iterable[Mapping[str, Any]],
        scoring_cols: Iterable[Mapping[str, Any]],
        score_total_cols: Iterable[Mapping[str, Any]],
        total_count: int,
        page: int,
        per_page: int,
    ) -> list[Dict[str, Any]]:
        items: list[Dict[str, Any]] = []
        offset = (page - 1) * per_page
        display_columns = list(display_columns)
        scoring_cols = list(scoring_cols)
        score_total_cols = list(score_total_cols)

        for idx, row in enumerate(raw_items):
            item = dict(row)
            custom_data = self._parse_custom_data(item.get("custom_data"))
            if isinstance(custom_data, dict):
                item.update(custom_data)

            self._flatten_scoring_fields(item, custom_data, display_columns)
            self._apply_score_totals(item, custom_data, scoring_cols, score_total_cols)

            item["no"] = total_count - offset - idx
            items.append(item)

        return items

    def _parse_custom_data(self, raw: Any) -> Mapping[str, Any]:
        if isinstance(raw, dict):
            return raw
        if isinstance(raw, str) and raw:
            try:
                return json.loads(raw)
            except Exception:
                logging.error("[FULL_PROCESS] custom_data parse error", exc_info=True)
        return {}

    def _flatten_scoring_fields(
        self,
        item: Dict[str, Any],
        custom_data: Mapping[str, Any],
        display_columns: Iterable[Mapping[str, Any]],
    ) -> None:
        for column in display_columns:
            if column.get("_virtual") != 1:
                continue
            src = column.get("_source_scoring_key")
            item_id = column.get("_source_item_id")
            if not src or not item_id:
                continue
            group_obj = custom_data.get(src)
            if isinstance(group_obj, str):
                try:
                    group_obj = json.loads(group_obj)
                except Exception:
                    group_obj = {}
            if isinstance(group_obj, dict):
                item[f"{src}__{item_id}"] = group_obj.get(item_id, 0)

    def _apply_score_totals(
        self,
        item: Dict[str, Any],
        custom_data: Mapping[str, Any],
        scoring_cols: Iterable[Mapping[str, Any]],
        score_total_cols: Iterable[Mapping[str, Any]],
    ) -> None:
        scoring_cols = list(scoring_cols)
        for total_col in score_total_cols:
            conf = total_col.get("scoring_config")
            if isinstance(conf, str):
                try:
                    conf = json.loads(conf)
                except Exception:
                    conf = {}
            conf = conf or {}
            base = conf.get("base_score", 100)
            include_keys = conf.get("include_keys") or []
            total = base

            if include_keys:
                for key in include_keys:
                    target = next((c for c in scoring_cols if c.get("column_key") == key), None)
                    if not target:
                        continue
                    sconf = target.get("scoring_config")
                    if isinstance(sconf, str):
                        try:
                            sconf = json.loads(sconf)
                        except Exception:
                            sconf = {}
                    sconf = sconf or {}
                    items_cfg = sconf.get("items") or []
                    group_obj = custom_data.get(key, {})
                    if isinstance(group_obj, str):
                        try:
                            group_obj = json.loads(group_obj)
                        except Exception:
                            group_obj = {}
                    for cfg in items_cfg:
                        iid = cfg.get("id")
                        delta = float(cfg.get("per_unit_delta") or 0)
                        count = 0
                        if isinstance(group_obj, dict) and iid in group_obj:
                            try:
                                count = int(group_obj.get(iid) or 0)
                            except Exception:
                                count = 0
                        total += count * delta
            else:
                total_key = conf.get("total_key") or "default"
                for s_column in scoring_cols:
                    sconf = s_column.get("scoring_config")
                    if isinstance(sconf, str):
                        try:
                            sconf = json.loads(sconf)
                        except Exception:
                            sconf = {}
                    sconf = sconf or {}
                    if (sconf.get("total_key") or "default") != total_key:
                        continue
                    items_cfg = sconf.get("items") or []
                    group_obj = custom_data.get(s_column.get("column_key"), {})
                    if isinstance(group_obj, str):
                        try:
                            group_obj = json.loads(group_obj)
                        except Exception:
                            group_obj = {}
                    for cfg in items_cfg:
                        iid = cfg.get("id")
                        delta = float(cfg.get("per_unit_delta") or 0)
                        count = 0
                        if isinstance(group_obj, dict) and iid in group_obj:
                            try:
                                count = int(group_obj.get(iid) or 0)
                            except Exception:
                                count = 0
                        total += count * delta

            item[total_col.get("column_key")] = total

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


def build_full_process_config() -> BoardControllerConfig:
    return BoardControllerConfig(
        board_type="full_process",
        list_template="full-process.html",
        detail_template="full-process-detail.html",
        register_template="full-process-register.html",
        attachments_enabled=True,
        scoring_enabled=True,
        per_page_default=20,
        extra_context={
            "menu_section": "full_process",
            "permission_code": "FULL_PROCESS",
        },
    )
