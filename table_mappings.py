"""Centralized table column mapping presets used by admin column editors."""
from __future__ import annotations

from copy import deepcopy
from typing import Dict, Any

_TABLE_COLUMN_MAPPINGS: Dict[str, Dict[str, Any]] = {
    "follow_sop": {
        "person": {
            "name": "담당자",
            "columns": [
                {
                    "name": "담당자",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_person",
                    "field_type": "popup",
                    "lookup_type": "person",
                    "stores": ["name", "id", "department", "company", "bizno"],
                },
                {
                    "name": "담당자 ID",
                    "label": "{base} ID",
                    "key": "{base}_id",
                    "key_suffix": "_id",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.id",
                    "read_only": True,
                },
                {
                    "name": "담당자 부서",
                    "label": "{base} 부서",
                    "key": "{base}_dept",
                    "key_suffix": "_dept",
                    "type": "linked_dept",
                    "field_type": "text",
                    "bind": "{base}.department",
                    "read_only": True,
                },
            ],
        },
        "company": {
            "name": "업체",
            "columns": [
                {
                    "name": "업체명",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_company",
                    "field_type": "popup",
                    "lookup_type": "company",
                    "stores": ["name", "bizno"],
                },
                {
                    "name": "사업자번호",
                    "label": "{base} 사업자번호",
                    "key": "{base}_bizno",
                    "key_suffix": "_bizno",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.bizno",
                    "read_only": True,
                },
            ],
        },
        "department": {
            "name": "부서",
            "columns": [
                {
                    "name": "부서명",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_department",
                    "field_type": "popup",
                    "lookup_type": "department",
                    "stores": ["name", "code"],
                },
                {
                    "name": "부서코드",
                    "label": "{base} 코드",
                    "key": "{base}_code",
                    "key_suffix": "_code",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.code",
                    "read_only": True,
                },
            ],
        },
        "building": {
            "name": "건물",
            "columns": [
                {
                    "name": "건물명",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_building",
                    "field_type": "popup",
                    "lookup_type": "building",
                    "stores": ["name", "code"],
                },
                {
                    "name": "건물코드",
                    "label": "{base} 코드",
                    "key": "{base}_code",
                    "key_suffix": "_code",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.code",
                    "read_only": True,
                },
            ],
        },
        "contractor": {
            "name": "협력사 근로자",
            "columns": [
                {
                    "name": "성함",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_contractor",
                    "field_type": "popup",
                    "lookup_type": "contractor",
                    "stores": ["name", "id", "company", "bizno"],
                },
                {
                    "name": "ID",
                    "label": "{base} ID",
                    "key": "{base}_id",
                    "key_suffix": "_id",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.id",
                    "read_only": True,
                },
                {
                    "name": "소속업체",
                    "label": "{base} 소속업체",
                    "key": "{base}_company",
                    "key_suffix": "_company",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.company",
                    "read_only": True,
                },
                {
                    "name": "사업자번호",
                    "label": "{base} 사업자번호",
                    "key": "{base}_bizno",
                    "key_suffix": "_bizno",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.bizno",
                    "read_only": True,
                },
            ],
        },
        "division": {
            "name": "사업부",
            "columns": [
                {
                    "name": "사업부명",
                    "label": "{base}",
                    "key": "{base}",
                    "key_suffix": "",
                    "type": "popup_division",
                    "field_type": "popup",
                    "lookup_type": "division",
                    "stores": ["name", "code", "parent"],
                },
                {
                    "name": "사업부코드",
                    "label": "{base} 코드",
                    "key": "{base}_code",
                    "key_suffix": "_code",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.code",
                    "read_only": True,
                },
                {
                    "name": "상위사업부",
                    "label": "{base} 상위사업부",
                    "key": "{base}_parent",
                    "key_suffix": "_parent",
                    "type": "linked_text",
                    "field_type": "text",
                    "bind": "{base}.parent",
                    "read_only": True,
                },
            ],
        },
    }
}

# Accident 보드는 Follow SOP와 동일한 프리셋을 재사용한다.
_TABLE_COLUMN_MAPPINGS["accident"] = deepcopy(_TABLE_COLUMN_MAPPINGS["follow_sop"])
_TABLE_COLUMN_MAPPINGS["safety_instruction"] = deepcopy(_TABLE_COLUMN_MAPPINGS["follow_sop"])


def get_table_mappings(board_type: str) -> Dict[str, Any]:
    """Return table mapping presets for the given board type."""
    return _TABLE_COLUMN_MAPPINGS.get(board_type, {})
