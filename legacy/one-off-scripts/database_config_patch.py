#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
database_config.py의 sync_fullprocess_from_external_db 함수 패치
외부 쿼리 결과를 config.ini 매핑에 따라 JSON 구조화
"""

import json
import logging
import configparser
import os
from typing import Dict, Any

def transform_fullprocess_data(row_dict: Dict, config_path: str = 'config.ini') -> Dict:
    """
    외부 쿼리의 평면 데이터를 config.ini 매핑에 따라 구조화

    Input: {"c1": val, "item1": 5, "item2": 3, ...}
    Output: {"c1": val, "scre223": "{\"item_1\": 5, ...}", ...}
    """
    # config.ini 읽기
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 시스템 섹션 제외
    SYSTEM_SECTIONS = [
        'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
        'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
        'CONTENT_DATA_QUERIES', 'SSO'
    ]

    # scoring 섹션과 매핑 찾기
    scoring_mappings = {}
    for section_name in config.sections():
        if section_name.upper() in SYSTEM_SECTIONS:
            continue
        if section_name.upper().startswith('SCORING_MAPPING_'):
            continue

        section_items = dict(config[section_name])
        item_mappings = {}
        for key, value in section_items.items():
            if key.startswith('item_'):
                item_mappings[key] = value

        if item_mappings:
            scoring_mappings[section_name] = item_mappings
            logging.debug(f"[SYNC] Found scoring section: {section_name}")

    # 변환 시작
    transformed = {}
    used_columns = set()

    # 1. scoring 매핑에 사용되는 컬럼 수집
    for section_name, mappings in scoring_mappings.items():
        for json_key, external_column in mappings.items():
            used_columns.add(external_column)

    # 2. scoring 섹션별로 JSON 구조 생성
    for section_name, mappings in scoring_mappings.items():
        section_data = {}

        for json_key, external_column in mappings.items():
            if external_column in row_dict:
                value = row_dict[external_column]
                # null, None, 빈 문자열 처리
                section_data[json_key] = value if value not in [None, '', 'null'] else None
            else:
                section_data[json_key] = None

        # JSON 문자열로 저장
        transformed[section_name] = json.dumps(section_data, ensure_ascii=False)
        logging.debug(f"[SYNC] Created {section_name}: {len(section_data)} items")

    # 3. scoring에 사용되지 않은 일반 필드 처리
    for key, value in row_dict.items():
        if key not in used_columns:
            # full_process 테이블의 실제 컬럼과 충돌하는 것들 제외
            if key.lower() not in ['id', 'created_at', 'updated_at', 'is_deleted',
                                   'fullprocess_number', 'custom_data']:
                transformed[key] = value

    return transformed


# 패치된 sync 함수 (실제로는 database_config.py를 수정해야 함)
def sync_fullprocess_from_external_db_patched(self):
    """
    기존 sync 함수의 패치 버전
    1200-1208줄 부분만 수정
    """
    # ... 기존 코드 ...

    # 원래 코드:
    # row_dict = row.to_dict()
    # custom_data = json.dumps(row_dict, ensure_ascii=False, default=str)

    # 패치된 코드:
    row_dict = row.to_dict() if hasattr(row, 'to_dict') else dict(row)

    # 날짜 타입 변환 (기존 코드 유지)
    for k, v in row_dict.items():
        if isinstance(v, (pd.Timestamp, datetime, date)):
            row_dict[k] = str(v)
        elif pd.isna(v):
            row_dict[k] = None

    # ★★★ 핵심 변경: 평면 데이터를 구조화 ★★★
    transformed_data = transform_fullprocess_data(row_dict)
    custom_data = json.dumps(transformed_data, ensure_ascii=False, default=str)

    # ... 나머지 코드 ...


if __name__ == "__main__":
    # 테스트
    test_data = {
        "c1": "value1",
        "c2": "value2",
        "scre223_item_1": 5,
        "scre223_item_2": 3,
        "scre223_item_3": 2,
        "test224_item_1": 10,
        "test224_item_2": 7,
        "other_field": "other_value"
    }

    result = transform_fullprocess_data(test_data)
    print("Transformed data:")
    for key, val in result.items():
        if key in ['scre223', 'test224', 'test225']:
            print(f"  {key}: {val}")
        else:
            print(f"  {key}: {val}")