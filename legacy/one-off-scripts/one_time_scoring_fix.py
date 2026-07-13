#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
1회성 Full Process custom_data 변환 스크립트
평면적인 외부 컬럼을 config.ini 매핑에 따라 JSON 구조로 변환
"""

import json
import configparser
import psycopg2
import psycopg2.extras
from typing import Dict, Any, Set
import sys

def load_scoring_mappings(config_path: str = 'config.ini') -> Dict[str, Dict[str, str]]:
    """
    config.ini에서 scoring 섹션만 추출
    예: {"scre223": {"item_1": "scre223_item_1", ...}, ...}
    """
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    # 시스템 섹션 제외
    SYSTEM_SECTIONS = [
        'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
        'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
        'CONTENT_DATA_QUERIES', 'SSO'
    ]

    mappings = {}
    for section_name in config.sections():
        # 시스템 섹션 스킵
        if section_name.upper() in SYSTEM_SECTIONS:
            continue
        if section_name.upper().startswith('SCORING_MAPPING_'):
            continue

        # item_ 패턴 있는지 확인
        section_items = dict(config[section_name])
        item_mappings = {}

        for key, value in section_items.items():
            if key.startswith('item_'):
                item_mappings[key] = value

        if item_mappings:
            mappings[section_name] = item_mappings
            print(f"  Found section: {section_name} with {len(item_mappings)} items")

    return mappings

def transform_custom_data(old_data: Dict, mappings: Dict[str, Dict[str, str]]) -> tuple[Dict, bool]:
    """
    평면 데이터를 JSON 구조로 변환
    Input: {"c1": val, "scre223_item_1": 5, "scre223_item_2": 3, ...}
    Output: {"c1": val, "scre223": "{\"item_1\": 5, \"item_2\": 3, ...}", ...}
    """
    if not old_data:
        return old_data, False

    # 매핑에 사용되는 컬럼들 수집
    used_columns: Set[str] = set()
    for section_mappings in mappings.values():
        used_columns.update(section_mappings.values())

    new_data = {}
    has_changes = False

    # 1. 기존에 이미 JSON 구조인 섹션 확인
    for section_name in mappings.keys():
        if section_name in old_data:
            existing_value = old_data[section_name]
            # 이미 JSON 문자열이면 유지
            if isinstance(existing_value, str) and existing_value.startswith('{'):
                new_data[section_name] = existing_value
                continue

    # 2. 평면 컬럼을 JSON 구조로 변환
    for section_name, section_mappings in mappings.items():
        # 이미 처리된 섹션은 스킵
        if section_name in new_data:
            continue

        section_data = {}
        found_any = False

        for item_key, external_column in section_mappings.items():
            if external_column in old_data:
                value = old_data[external_column]
                section_data[item_key] = value if value not in [None, '', 'null'] else None
                found_any = True
            else:
                section_data[item_key] = None

        # 하나라도 매핑된 값이 있으면 섹션 생성
        if found_any or section_name in old_data:
            new_data[section_name] = json.dumps(section_data, ensure_ascii=False)
            has_changes = True
            print(f"    Transformed {section_name}: {len(section_data)} items")

    # 3. 매핑되지 않은 필드 유지 (scoring 컬럼 제외)
    for key, value in old_data.items():
        if key not in used_columns and key not in new_data:
            # 실제 테이블 컬럼과 충돌하는 것들 제외
            if key.lower() not in ['id', 'created_at', 'updated_at', 'is_deleted',
                                   'fullprocess_number', 'custom_data']:
                new_data[key] = value

    return new_data, has_changes

def main():
    print("=== One-Time Full Process Scoring Fix ===\n")

    # DB 연결
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    conn.autocommit = False

    try:
        # 1. 매핑 로드
        print("1. Loading config.ini mappings...")
        mappings = load_scoring_mappings('config.ini')
        print(f"   Loaded {len(mappings)} scoring sections\n")

        # 2. 변환이 필요한 레코드 찾기
        print("2. Scanning full_process records...")
        cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

        # 모든 레코드 스캔
        cursor.execute("""
            SELECT fullprocess_number, custom_data
            FROM full_process
            WHERE custom_data IS NOT NULL
        """)

        records = cursor.fetchall()
        print(f"   Found {len(records)} records with custom_data\n")

        # 3. 각 레코드 처리
        print("3. Processing records...")
        updated_count = 0

        for row in records:
            fp_num = row['fullprocess_number']
            custom_data = row['custom_data']

            # JSONB는 이미 dict로 옴
            if isinstance(custom_data, str):
                try:
                    custom_data = json.loads(custom_data)
                except:
                    print(f"   [ERROR] Invalid JSON in {fp_num}")
                    continue

            # 변환
            new_data, changed = transform_custom_data(custom_data, mappings)

            if changed:
                # DB 업데이트
                cursor.execute("""
                    UPDATE full_process
                    SET custom_data = %s
                    WHERE fullprocess_number = %s
                """, (json.dumps(new_data, ensure_ascii=False), fp_num))

                updated_count += 1
                print(f"   [UPDATE] {fp_num}")

                # 샘플 출력 (처음 3개만)
                if updated_count <= 3:
                    print(f"     Old keys: {list(custom_data.keys())[:5]}")
                    print(f"     New keys: {list(new_data.keys())[:5]}")

        print(f"\n4. Summary:")
        print(f"   Total records: {len(records)}")
        print(f"   Updated: {updated_count}")

        # 커밋 확인
        if updated_count > 0:
            response = input("\nCommit changes? (yes/no): ")
            if response.lower() == 'yes':
                conn.commit()
                print("   ✓ Changes committed!")
            else:
                conn.rollback()
                print("   ✗ Changes rolled back!")
        else:
            print("   No changes needed!")

    except Exception as e:
        print(f"\n[ERROR] {e}")
        conn.rollback()
        import traceback
        traceback.print_exc()

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    main()