#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
pandas DataFrame의 custom_data를 config.ini 기반으로 변환
평면 데이터 → JSON 구조화
"""

import json
import configparser
import pandas as pd
from typing import Dict, Any

def transform_custom_data_from_df(df, config_path='config.ini'):
    """
    DataFrame의 custom_data 컬럼을 변환

    Input df.custom_data: {"scre223_item_1": 5, "test224_item_1": 3, ...}
    Output: {"scre223": "{\"item_1\": 5, ...}", "test224": "{\"item_1\": 3, ...}", ...}
    """

    # 1. config.ini 읽기
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 시스템 섹션 제외
    SYSTEM_SECTIONS = [
        'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
        'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
        'CONTENT_DATA_QUERIES', 'SSO'
    ]

    # 2. scoring 섹션과 매핑 찾기
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
            print(f"Found section: {section_name} with {len(item_mappings)} items")

    # 3. 각 row의 custom_data 변환
    def transform_row(row_data):
        if not row_data:
            return row_data

        # JSON 문자열이면 파싱
        if isinstance(row_data, str):
            try:
                row_data = json.loads(row_data)
            except:
                return row_data

        # 변환 시작
        transformed = {}
        used_columns = set()

        # scoring 매핑에 사용되는 컬럼들 수집
        for section_name, mappings in scoring_mappings.items():
            for json_key, external_column in mappings.items():
                used_columns.add(external_column)

        # 각 섹션별로 JSON 구조 생성
        for section_name, mappings in scoring_mappings.items():
            section_data = {}
            has_data = False

            for json_key, external_column in mappings.items():
                if external_column in row_data:
                    value = row_data[external_column]
                    section_data[json_key] = value if value not in [None, '', 'null'] else None
                    has_data = True
                else:
                    section_data[json_key] = None

            # 데이터가 있으면 JSON 문자열로 저장
            if has_data:
                transformed[section_name] = json.dumps(section_data, ensure_ascii=False)

        # scoring에 사용되지 않은 필드들 유지
        for key, value in row_data.items():
            if key not in used_columns and key not in transformed:
                # 실제 테이블 컬럼과 충돌하는 것들 제외
                if key.lower() not in ['id', 'created_at', 'updated_at', 'is_deleted',
                                       'fullprocess_number', 'custom_data']:
                    transformed[key] = value

        return transformed

    # 4. DataFrame 변환
    df['custom_data'] = df['custom_data'].apply(transform_row)

    return df


# 사용 예시
if __name__ == "__main__":
    # 예시 데이터
    sample_data = {
        'fullprocess_number': ['FP001', 'FP002'],
        'custom_data': [
            {
                "scre223_item_1": 5,
                "scre223_item_2": 3,
                "scre223_item_3": 2,
                "test224_item_1": 4,
                "test224_item_2": 1,
                "other_field": "value1"
            },
            {
                "test225_item_1": 3,
                "test225_item_2": 4,
                "test225_item_3": 5,
                "test225_item_4": 2,
                "tbm_helmet_check": 1,
                "tbm_safety_brief": 3,
                "other_field": "value2"
            }
        ]
    }

    df = pd.DataFrame(sample_data)

    print("=== Before Transformation ===")
    for idx, row in df.iterrows():
        print(f"{row['fullprocess_number']}: {list(row['custom_data'].keys())}")

    # 변환
    df = transform_custom_data_from_df(df)

    print("\n=== After Transformation ===")
    for idx, row in df.iterrows():
        print(f"{row['fullprocess_number']}: {list(row['custom_data'].keys())}")
        for key, val in row['custom_data'].items():
            if key in ['scre223', 'test224', 'test225', 'tbm', 'safety_check', 'quality_audit']:
                print(f"  {key}: {val}")