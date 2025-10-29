"""Utility helpers for dynamic list column child schema management.

This module centralizes default schema templates for legacy presets
and provides functions to parse, generate, and serialize child schema
metadata. The helpers are backend-only for now and allow gradual
migration away from hard-coded list presets.
"""
from __future__ import annotations

import json
from copy import deepcopy
from typing import Any, Dict, List, Optional, Tuple

# Default schema templates derived from existing hard-coded list presets.
# Automatic presets disabled; keep empty to require explicit configuration.
_DEFAULT_PRESET_SCHEMAS: Dict[str, Dict[str, Any]] = {}

_LEGACY_ROW_MAPPINGS: Dict[str, Dict[str, str]] = {
    "partner_worker": {
        "name": "worker.label",
        "id": "worker_id",
        "company": "company_name",
        "bizno": "business_no",
    },
    "company": {
        "name": "company.label",
        "bizno": "business_no",
    },
}


def parse_child_schema(raw: Any) -> Optional[Dict[str, Any]]:
    """Parse raw schema value into a dict if possible."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else None
        except json.JSONDecodeError:
            return None
    return None


def _apply_column_overrides(schema: Dict[str, Any], column_meta: Dict[str, Any]) -> Dict[str, Any]:
    """Adjust default schema using metadata overrides from the column."""
    overrides = deepcopy(schema)
    meta = overrides.setdefault("rowModeMeta", {})

    # Allow simple overrides via optional metadata fields.
    count_label = column_meta.get("list_count_label") or column_meta.get("count_label")
    if count_label:
        meta["countLabel"] = count_label
        meta.setdefault("unit", count_label)

    duplicate_key = column_meta.get("duplicate_key")
    if duplicate_key:
        meta["duplicateKey"] = duplicate_key

    row_mode = column_meta.get("row_mode") or column_meta.get("rowMode")
    if row_mode in {"single", "multi"}:
        overrides["rowMode"] = row_mode

    return overrides


def generate_schema_from_preset(column_meta: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Generate a child schema based on legacy preset metadata."""
    preset = (column_meta.get("list_item_type") or column_meta.get("input_type") or "").strip()
    if not preset:
        return None

    template = _DEFAULT_PRESET_SCHEMAS.get(preset)
    if not template:
        return None

    return _apply_column_overrides(deepcopy(template), column_meta)


def resolve_child_schema(
    column_meta: Dict[str, Any], *, allow_generate: bool = False
) -> Tuple[Optional[Dict[str, Any]], bool]:
    """Return (schema, generated_flag) for a column configuration."""
    schema = parse_child_schema(column_meta.get("child_schema"))
    if schema is not None:
        return schema, False

    if not allow_generate:
        return None, False

    generated = generate_schema_from_preset(column_meta)
    return generated, generated is not None


def dump_child_schema(schema: Any) -> Optional[str]:
    """Serialize a schema dict to JSON for storage."""
    if schema is None:
        return None
    if isinstance(schema, str):
        # Assume already serialized JSON string.
        return schema
    if isinstance(schema, dict):
        return json.dumps(schema, ensure_ascii=False)
    return None


def _apply_mapping_to_row(preset: str, row: Dict[str, Any]) -> Dict[str, Any]:
    """Create additional keys on top of the legacy row based on preset mapping."""
    mapping = _LEGACY_ROW_MAPPINGS.get(preset, {})
    additions: Dict[str, Any] = {}

    for legacy_key, target_key in mapping.items():
        if legacy_key not in row:
            continue
        value = row.get(legacy_key)
        if value is None:
            continue

        # Support nested target keys using dot notation (e.g., worker.label).
        parts = target_key.split('.')
        cursor = additions
        for idx, part in enumerate(parts):
            if idx == len(parts) - 1:
                cursor[part] = value
            else:
                cursor = cursor.setdefault(part, {})

    return additions


def validate_rows_against_schema(schema: Optional[Dict[str, Any]], rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate rows using schema definition and return structured errors."""
    if not schema or not isinstance(schema, dict):
        return []

    child_fields = schema.get('childFields') or []
    if not child_fields:
        return []

    field_map = {
        field.get('key'): field
        for field in child_fields
        if isinstance(field, dict) and field.get('key')
    }

    errors: List[Dict[str, Any]] = []

    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append({'row': idx, 'messages': ['항목 데이터가 객체 형태가 아닙니다.']})
            continue

        row_errors: List[str] = []
        for key, field in field_map.items():
            label = field.get('label') or key
            value = row.get(key)

            if field.get('required'):
                if value in (None, '', []):
                    row_errors.append(f"필수 값 누락: {label}")

            validation = field.get('validation') or {}
            if value not in (None, ''):
                if 'maxLength' in validation and isinstance(value, str):
                    if len(value) > validation['maxLength']:
                        row_errors.append(f"{label} 길이 초과 ({len(value)}/{validation['maxLength']})")
                if 'min' in validation:
                    try:
                        numeric = float(value)
                        if numeric < validation['min']:
                            row_errors.append(f"{label} 값은 {validation['min']} 이상이어야 합니다.")
                    except (TypeError, ValueError):
                        row_errors.append(f"{label} 값이 숫자가 아닙니다.")
                if 'max' in validation:
                    try:
                        numeric = float(value)
                        if numeric > validation['max']:
                            row_errors.append(f"{label} 값은 {validation['max']} 이하이어야 합니다.")
                    except (TypeError, ValueError):
                        row_errors.append(f"{label} 값이 숫자가 아닙니다.")

        if row_errors:
            errors.append({'row': idx, 'messages': row_errors})

    return errors


def deserialize_list_rows(
    column_meta: Dict[str, Any], schema: Optional[Dict[str, Any]], raw_value: Any
) -> Dict[str, Any]:
    """Best-effort normalization of list column payloads.

    Returns a structure with parsed rows, raw list and any conversion warnings.
    This is a non-destructive helper: original keys remain while additional
    schema-aware keys are merged in when possible.
    """

    if raw_value is None:
        raw_list: List[Any] = []
    elif isinstance(raw_value, list):
        raw_list = raw_value
    elif isinstance(raw_value, str):
        try:
            parsed = json.loads(raw_value)
            raw_list = parsed if isinstance(parsed, list) else []
        except json.JSONDecodeError:
            raw_list = []
    else:
        raw_list = []

    preset = (column_meta.get("list_item_type") or column_meta.get("input_type") or "").strip()
    warnings: List[str] = []
    normalized_rows: List[Dict[str, Any]] = []

    for idx, item in enumerate(raw_list):
        if not isinstance(item, dict):
            warnings.append(f"row {idx} is not an object; skipped")
            continue
        merged = dict(item)
        additions = _apply_mapping_to_row(preset, item)
        if additions:
            # Merge nested dictionaries carefully.
            for key, value in additions.items():
                if isinstance(value, dict) and isinstance(merged.get(key), dict):
                    merged[key].update(value)
                else:
                    merged.setdefault(key, value)
        normalized_rows.append(merged)

    validation_errors = validate_rows_against_schema(schema, normalized_rows)

    return {
        "rows": normalized_rows,
        "raw": raw_list,
        "warnings": warnings,
        "schema": schema,
        "preset": preset,
        "errors": validation_errors,
    }


__all__ = [
    "parse_child_schema",
    "generate_schema_from_preset",
    "resolve_child_schema",
    "dump_child_schema",
    "validate_rows_against_schema",
    "deserialize_list_rows",
]
