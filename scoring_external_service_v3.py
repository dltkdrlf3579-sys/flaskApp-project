#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Full Process Scoring 외부 쿼리 매핑 서비스 v3
- 완전 동적, 하드코딩 없음
- config.ini 기반으로만 동작
- 어떤 섹션명이든 처리 가능
"""

import json
import logging
import configparser
import os
from typing import Dict, Any


def _as_bool(value: str) -> bool:
    """Interpret common truthy strings as boolean True."""
    return value.strip().lower() in {"1", "true", "yes", "on"}


def is_scoring_enabled(config_path: str = None) -> bool:
    """Check configuration and environment flags to decide if scoring runs."""
    env_value = os.environ.get("ENABLE_EXTERNAL_SCORING")
    if env_value is not None:
        try:
            return _as_bool(env_value)
        except AttributeError:
            return False

    if not config_path:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    if config.has_option('APPLICATION', 'scoring_enabled'):
        return config.getboolean('APPLICATION', 'scoring_enabled', fallback=True)

    return True


SCORING_ENABLED = is_scoring_enabled()
_SCORING_DISABLED_LOGGED = False

def get_scoring_sections_from_config(config_path: str = None) -> Dict[str, Dict[str, str]]:
    """
    config.ini에서 scoring 섹션들을 동적으로 찾기
    하드코딩 없음 - item_ 패턴이 있는 모든 섹션 자동 인식
    """
    if not config_path:
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')

    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 시스템 섹션들 (이것들은 scoring이 아님)
    SYSTEM_SECTIONS = [
        'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
        'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
        'CONTENT_DATA_QUERIES', 'SSO'
    ]

    scoring_mappings = {}

    # 모든 섹션 순회
    for section_name in config.sections():
        # 시스템 섹션 제외
        if section_name.upper() in SYSTEM_SECTIONS:
            continue

        # SCORING_MAPPING_ 프리픽스 섹션 제외
        if section_name.upper().startswith('SCORING_MAPPING_'):
            continue

        # 섹션의 모든 키 확인
        section_items = dict(config[section_name])

        # item_ 패턴이 있는지 확인
        item_mappings = {}
        for key, value in section_items.items():
            if key.startswith('item_'):
                item_mappings[key] = value

        # item_ 패턴이 하나라도 있으면 scoring 섹션
        if item_mappings:
            scoring_mappings[section_name] = item_mappings
            logging.info(f"[SCORING] Found section: {section_name} with {len(item_mappings)} items")

    return scoring_mappings


def get_external_data_flat(cursor, fullprocess_number: str) -> Dict[str, Any]:
    """
    외부 테이블에서 평면적으로 모든 데이터 가져오기
    SELECT * 로 동적으로 처리
    """
    try:
        cursor.execute("""
            SELECT * FROM external_scoring_table
            WHERE fullprocess_number = %s
        """, (fullprocess_number,))

        row = cursor.fetchone()
        if not row:
            logging.warning(f"[SCORING] No external data for {fullprocess_number}")
            return {}

        # 컬럼명 동적으로 가져오기
        column_names = [desc[0] for desc in cursor.description]

        # 평면적인 딕셔너리로 변환
        flat_data = {}
        for i, col_name in enumerate(column_names):
            # 메타데이터 컬럼 제외
            if col_name not in ['id', 'fullprocess_number', 'created_at', 'updated_at']:
                flat_data[col_name] = row[i]

        logging.info(f"[SCORING] Got {len(flat_data)} fields from external table")
        return flat_data

    except Exception as e:
        logging.error(f"[SCORING] Error getting external data: {e}")
        return {}


def transform_flat_to_structured(flat_data: Dict, scoring_mappings: Dict) -> Dict[str, Any]:
    """
    평면 데이터를 config.ini 매핑에 따라 구조화된 JSON으로 변환

    Input (flat_data):
        {"c1": "val", "item1": 5, "item2": 3, "item3": 2, "item4": 10, ...}

    Output (structured):
        {
            "c1": "val",
            "scre223": "{\"item_1\": 5, \"item_2\": 3, \"item_3\": 2}",
            "test224": "{\"item_1\": 10, \"item_2\": 7}",
            ...
        }
    """
    structured_data = {}
    used_columns = set()

    # 1. 먼저 scoring 매핑에 사용되는 컬럼들 수집
    for section_name, mappings in scoring_mappings.items():
        for json_key, external_column in mappings.items():
            used_columns.add(external_column)

    # 2. Scoring 섹션별로 JSON 구조 생성
    for section_name, mappings in scoring_mappings.items():
        section_data = {}

        for json_key, external_column in mappings.items():
            if external_column in flat_data:
                value = flat_data[external_column]
                section_data[json_key] = value if value is not None else None
                logging.debug(f"[SCORING] {section_name}.{json_key} = {value} (from {external_column})")
            else:
                section_data[json_key] = None

        # JSON 문자열로 저장
        structured_data[section_name] = json.dumps(section_data)
        logging.info(f"[SCORING] Created section {section_name}: {len(section_data)} items")

    # 3. Scoring에 사용되지 않은 일반 필드들 처리
    for key, value in flat_data.items():
        if key not in used_columns:
            structured_data[key] = value
            logging.debug(f"[SCORING] Regular field: {key} = {value}")

    return structured_data


def apply_external_scoring_to_custom_data(cursor, fullprocess_number: str, existing_custom_data: Dict) -> Dict:
    """
    외부 데이터를 가져와서 custom_data 업데이트
    완전 동적, config.ini 기반
    """
    global _SCORING_DISABLED_LOGGED

    if not SCORING_ENABLED:
        if not _SCORING_DISABLED_LOGGED:
            logging.info("[SCORING] External scoring disabled; skipping update.")
            _SCORING_DISABLED_LOGGED = True
        return existing_custom_data

    try:
        # 1. config.ini에서 scoring 섹션들 동적으로 가져오기
        scoring_mappings = get_scoring_sections_from_config()

        if not scoring_mappings:
            logging.info("[SCORING] No scoring sections found in config.ini; skipping external scoring.")
            return existing_custom_data

        logging.info(f"[SCORING] Processing sections: {list(scoring_mappings.keys())}")

        # 2. 외부 데이터 평면적으로 가져오기
        flat_external_data = get_external_data_flat(cursor, fullprocess_number)

        if not flat_external_data:
            return existing_custom_data

        # 3. 평면 데이터를 구조화된 형태로 변환
        structured_data = transform_flat_to_structured(flat_external_data, scoring_mappings)

        # 4. 기존 custom_data와 병합
        updated_custom_data = existing_custom_data.copy() if existing_custom_data else {}

        for key, value in structured_data.items():
            # scoring 섹션인 경우 (JSON 문자열)
            if key in scoring_mappings:
                # 기존 값이 있으면 병합, 없으면 새로 생성
                if key in updated_custom_data:
                    try:
                        # 기존 값 파싱
                        existing = json.loads(updated_custom_data[key]) if isinstance(updated_custom_data[key], str) else {}
                        # 새 값 파싱
                        new_values = json.loads(value)
                        # 병합 (새 값 우선)
                        existing.update(new_values)
                        updated_custom_data[key] = json.dumps(existing)
                    except:
                        # 파싱 실패시 새 값으로 대체
                        updated_custom_data[key] = value
                else:
                    updated_custom_data[key] = value
            else:
                # 일반 필드
                updated_custom_data[key] = value

        return updated_custom_data

    except Exception as e:
        logging.error(f"[SCORING] Error in apply_external_scoring: {e}")
        import traceback
        traceback.print_exc()
        return existing_custom_data


# 테스트 함수
def test_dynamic_mapping():
    """동적 매핑 테스트"""
    print("=== Dynamic Scoring Mapping Test ===\n")

    # 1. config.ini 섹션 확인
    sections = get_scoring_sections_from_config()
    print(f"Found {len(sections)} scoring sections:\n")

    for section_name, mappings in sections.items():
        print(f"[{section_name}]")
        for key, val in mappings.items():
            print(f"  {key} = {val}")
        print()

    # 2. 실제 데이터로 테스트
    import psycopg2
    conn = psycopg2.connect("postgresql://postgres:admin123@localhost:5432/portal_dev")
    cursor = conn.cursor()

    test_fp = 'FP2412160001'

    # 외부 데이터
    flat = get_external_data_flat(cursor, test_fp)
    print(f"External data: {len(flat)} fields\n")

    # 변환
    structured = transform_flat_to_structured(flat, sections)
    print("Structured data:")
    for key, val in structured.items():
        if key in sections:
            print(f"  {key}: [JSON structure with {len(json.loads(val))} items]")
        else:
            print(f"  {key}: {val}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_dynamic_mapping()
