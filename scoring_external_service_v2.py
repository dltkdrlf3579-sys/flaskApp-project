#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Full Process Scoring 외부 쿼리 매핑 서비스 v2
- 단순하고 명확한 구조
- config.ini 기반 동적 매핑
- 하드코딩 없음
"""

import json
import logging
import configparser
import os
from typing import Dict, Any

def get_external_scoring_data(cursor, fullprocess_number: str) -> Dict[str, Any]:
    """외부 테이블에서 모든 데이터를 동적으로 가져오기"""
    try:
        # 테이블의 모든 컬럼 가져오기 (동적)
        cursor.execute("""
            SELECT * FROM external_scoring_table
            WHERE fullprocess_number = %s
        """, (fullprocess_number,))

        row = cursor.fetchone()
        if not row:
            logging.warning(f"[SCORING] No external data found for {fullprocess_number}")
            return {}

        # 컬럼명 가져오기
        column_names = [desc[0] for desc in cursor.description]

        # 딕셔너리로 변환
        external_data = {}
        for i, col_name in enumerate(column_names):
            # fullprocess_number, id, created_at 등은 제외
            if col_name not in ['id', 'fullprocess_number', 'created_at', 'updated_at']:
                external_data[col_name] = row[i]

        logging.info(f"[SCORING] External data loaded: {len(external_data)} fields")
        return external_data

    except Exception as e:
        logging.error(f"[SCORING] Error getting external data: {e}")
        return {}


def apply_external_scoring_to_custom_data(cursor, fullprocess_number: str, existing_custom_data: Dict) -> Dict:
    """config.ini 매핑에 따라 custom_data 업데이트"""
    try:
        # config.ini 경로
        config_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'config.ini')
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')

        # 외부 데이터 가져오기
        external_data = get_external_scoring_data(cursor, fullprocess_number)
        if not external_data:
            return existing_custom_data

        # custom_data 복사
        updated_custom_data = existing_custom_data.copy() if existing_custom_data else {}

        # 시스템 섹션 제외 목록
        system_sections = [
            'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
            'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
            'CONTENT_DATA_QUERIES', 'SSO'
        ]

        # config.ini의 각 섹션 확인
        for section_name in config.sections():
            # 시스템 섹션 스킵
            if section_name.upper() in system_sections:
                continue

            # SCORING_MAPPING_ 프리픽스 섹션도 스킵
            if section_name.upper().startswith('SCORING_MAPPING_'):
                continue

            # item_ 패턴이 있는지 확인
            section_items = dict(config[section_name])
            has_item_pattern = any(key.startswith('item_') for key in section_items.keys())

            if not has_item_pattern:
                continue

            logging.info(f"[SCORING] Processing section: {section_name}")

            # custom_data에 이 섹션 키가 있는지 확인
            if section_name not in updated_custom_data:
                # 없으면 빈 JSON 구조 생성
                item_structure = {}
                for key in section_items.keys():
                    if key.startswith('item_'):
                        item_structure[key] = None
                updated_custom_data[section_name] = json.dumps(item_structure)
                logging.info(f"[SCORING] Created new field: {section_name}")

            # 기존 값 파싱
            field_value = updated_custom_data[section_name]
            if isinstance(field_value, str) and field_value.startswith('{'):
                try:
                    current_items = json.loads(field_value)
                except:
                    current_items = {}
            else:
                current_items = {}

            # 매핑 적용
            updated_items = {}
            for item_key, external_column in section_items.items():
                if item_key.startswith('item_'):
                    # 외부 데이터에서 값 가져오기
                    if external_column in external_data:
                        value = external_data[external_column]
                        updated_items[item_key] = value if value is not None else None
                        logging.info(f"[SCORING] {section_name}.{item_key} = {value} (from {external_column})")
                    else:
                        # 외부 데이터에 없으면 기존 값 유지 또는 null
                        updated_items[item_key] = current_items.get(item_key)

            # JSON 문자열로 저장
            if updated_items:
                updated_custom_data[section_name] = json.dumps(updated_items)

        return updated_custom_data

    except Exception as e:
        logging.error(f"[SCORING] Error applying external scoring: {e}")
        return existing_custom_data


# 테스트 함수
def test_mapping():
    """매핑 테스트"""
    import psycopg2

    conn = psycopg2.connect("postgresql://postgres:admin123@localhost:5432/portal_dev")
    cursor = conn.cursor()

    # 1. config.ini 확인
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    print("=== Config Scoring Sections ===")
    system_sections = ['DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
                       'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
                       'CONTENT_DATA_QUERIES', 'SSO']

    for section in config.sections():
        if section.upper() not in system_sections and not section.upper().startswith('SCORING_MAPPING_'):
            items = dict(config[section])
            if any(key.startswith('item_') for key in items.keys()):
                print(f"\n[{section}]")
                for key, val in items.items():
                    if key.startswith('item_'):
                        print(f"  {key} = {val}")

    # 2. 외부 데이터 확인
    test_fp = 'FP2412160001'
    external_data = get_external_scoring_data(cursor, test_fp)
    print(f"\n=== External Data for {test_fp} ===")
    for key, val in external_data.items():
        print(f"  {key}: {val}")

    cursor.close()
    conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_mapping()