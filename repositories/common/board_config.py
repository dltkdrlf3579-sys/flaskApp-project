"""공통 보드 메타데이터 정의."""

from __future__ import annotations

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
    },
    'full_process': {
        'board_type': 'full_process',
        'display_name': 'Full Process',
        'number_prefix': 'FP',
        'cache_table': 'full_process',
        'column_table': 'full_process_column_config',
        'upload_path': 'uploads/full_process/',
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
