"""공통 보드 메타데이터 정의."""

from __future__ import annotations

from id_generator import (
    generate_followsop_number,
    generate_fullprocess_number,
    generate_subcontract_approval_number,
    generate_subcontract_report_number,
)

DYNAMIC_BOARD_DEFAULT_SECTIONS = (
    ("basic_info", "기본정보", 1),
    ("work_info", "작업정보", 2),
    ("additional", "추가기입정보", 3),
)

BOARD_CONFIGS = {
    'accident': {
        'board_type': 'accident',
        'display_name': '협력사 사고',
        'number_prefix': 'ACC',
        'cache_table': 'accidents_cache',
        'column_table': 'accident_column_config',
        'upload_path': 'uploads/accident/',
    },
    'safety_instruction': {
        'board_type': 'safety_instruction',
        'display_name': '환경안전 지시서',
        'number_prefix': 'SI',
        'cache_table': 'safety_instructions',
        'column_table': 'safety_instruction_column_config',
        'upload_path': 'uploads/safety_instruction/',
    },
    'change_request': {
        'board_type': 'change_request',
        'display_name': '기준정보 변경요청',
        'number_prefix': 'CR',
        'cache_table': 'change_requests',
        'column_table': 'change_request_column_config',
        'upload_path': 'uploads/change_request/',
    },
    'follow_sop': {
        'board_type': 'follow_sop',
        'display_name': 'Follow SOP',
        'number_prefix': 'FS',
        'cache_table': 'follow_sop',
        'column_table': 'follow_sop_column_config',
        'upload_path': 'uploads/follow_sop/',
        'primary_table': 'follow_sop',
        'table_candidates': ('follow_sop_cache', 'followsop_cache'),
        'section_table': 'follow_sop_sections',
        'detail_table': 'follow_sop_details',
        'identifier_column': 'work_req_no',
        'identifier_label': '점검번호',
        'created_at_label': '등록일',
        'default_sections': DYNAMIC_BOARD_DEFAULT_SECTIONS,
        'id_generator': generate_followsop_number,
    },
    'subcontract_approval': {
        'board_type': 'subcontract_approval',
        'display_name': '산안법 도급승인',
        'number_prefix': 'SA',
        'cache_table': 'subcontract_approval',
        'column_table': 'subcontract_approval_column_config',
        'upload_path': 'uploads/subcontract_approval/',
        'primary_table': 'subcontract_approval',
        'section_table': 'subcontract_approval_sections',
        'detail_table': 'subcontract_approval_details',
        'identifier_column': 'approval_number',
        'identifier_label': '승인번호',
        'created_at_label': '등록일',
        'default_sections': (("basic_info", "기본정보", 1),),
        'id_generator': generate_subcontract_approval_number,
    },
    'subcontract_report': {
        'board_type': 'subcontract_report',
        'display_name': '화관법 도급신고',
        'number_prefix': 'SR',
        'cache_table': 'subcontract_report',
        'column_table': 'subcontract_report_column_config',
        'upload_path': 'uploads/subcontract_report/',
        'primary_table': 'subcontract_report',
        'section_table': 'subcontract_report_sections',
        'detail_table': 'subcontract_report_details',
        'identifier_column': 'report_number',
        'identifier_label': '신고번호',
        'created_at_label': '등록일',
        'default_sections': (("basic_info", "기본정보", 1),),
        'id_generator': generate_subcontract_report_number,
    },
    'full_process': {
        'board_type': 'full_process',
        'display_name': 'Full Process',
        'number_prefix': 'FP',
        'cache_table': 'full_process',
        'column_table': 'full_process_column_config',
        'upload_path': 'uploads/full_process/',
        'primary_table': 'full_process',
        'table_candidates': ('full_process_cache', 'fullprocess_cache'),
        'section_table': 'full_process_sections',
        'detail_table': 'full_process_details',
        'identifier_column': 'fullprocess_number',
        'identifier_label': '평가번호',
        'created_at_label': '등록일',
        'default_sections': DYNAMIC_BOARD_DEFAULT_SECTIONS,
        'id_generator': generate_fullprocess_number,
    },
    'safe_workplace': {
        'board_type': 'safe_workplace',
        'display_name': 'Safe Workplace',
        'number_prefix': 'SP',
        'cache_table': 'safe_workplace',
        'column_table': 'safe_workplace_column_config',
        'upload_path': 'uploads/safe_workplace/',
    },
}


class BoardConfigError(ValueError):
    """Raised when a board type is not recognised."""


def get_board_config(board_type: str) -> dict:
    config = BOARD_CONFIGS.get(board_type)
    if not config:
        raise BoardConfigError(f"Unknown board type: {board_type}")
    return config
