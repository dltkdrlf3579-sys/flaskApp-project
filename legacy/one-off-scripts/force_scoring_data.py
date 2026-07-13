#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
강제로 scoring 데이터를 custom_data에 주입하는 스크립트
config.ini 섹션에 맞춰 테스트 데이터 생성
"""

import json
import configparser
import psycopg2
import psycopg2.extras
from typing import Dict, Any
import random

def load_scoring_sections(config_path: str = 'config.ini') -> Dict[str, Dict[str, str]]:
    """config.ini에서 scoring 섹션 로드"""
    config = configparser.ConfigParser()
    config.read(config_path, encoding='utf-8')

    SYSTEM_SECTIONS = [
        'DEFAULT', 'DATABASE', 'SECURITY', 'LOGGING', 'DASHBOARD',
        'SQL_QUERIES', 'COLUMNS', 'MASTER_DATA_QUERIES',
        'CONTENT_DATA_QUERIES', 'SSO'
    ]

    scoring_sections = {}
    for section_name in config.sections():
        if section_name.upper() in SYSTEM_SECTIONS:
            continue
        if section_name.upper().startswith('SCORING_MAPPING_'):
            continue

        # item_ 패턴이 있는 섹션만
        section_items = dict(config[section_name])
        item_mappings = {}

        for key, value in section_items.items():
            if key.startswith('item_'):
                item_mappings[key] = value

        if item_mappings:
            scoring_sections[section_name] = item_mappings
            print(f"  Found section: {section_name} with {len(item_mappings)} items")

    return scoring_sections

def create_test_scoring_data(sections: Dict[str, Dict[str, str]]) -> Dict[str, Any]:
    """테스트용 scoring 데이터 생성"""
    test_data = {}

    # 기본 필드들
    test_data['process_name'] = 'Test Process'
    test_data['department'] = 'Test Dept'
    test_data['created_by'] = 'Test User'

    # 각 섹션별로 JSON 문자열 생성
    for section_name, item_mappings in sections.items():
        section_data = {}
        for item_key, _ in item_mappings.items():
            # 랜덤 점수 생성 (1-5 또는 null)
            value = random.choice([1, 2, 3, 4, 5, None, None])  # null 확률 높임
            section_data[item_key] = value

        # JSON 문자열로 저장
        test_data[section_name] = json.dumps(section_data, ensure_ascii=False)
        print(f"    Created {section_name}: {section_data}")

    return test_data

def force_update_records(conn, sections: Dict[str, Dict[str, str]], record_count: int = 3):
    """특정 레코드들에 강제로 scoring 데이터 주입"""
    cursor = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)

    try:
        # 1. 업데이트할 레코드 선택
        cursor.execute("""
            SELECT fullprocess_number, custom_data
            FROM full_process
            ORDER BY created_at DESC
            LIMIT %s
        """, (record_count,))

        records = cursor.fetchall()

        if not records:
            print("No records found to update!")
            return

        print(f"\n2. Updating {len(records)} records...")

        for row in records:
            fp_num = row['fullprocess_number']
            existing_data = row['custom_data'] or {}

            # 기존 데이터 유지하면서 scoring 추가
            if isinstance(existing_data, str):
                try:
                    existing_data = json.loads(existing_data)
                except:
                    existing_data = {}

            # scoring 데이터 생성
            new_data = existing_data.copy()

            # 각 섹션별로 데이터 생성
            for section_name, item_mappings in sections.items():
                section_data = {}
                for item_key, _ in item_mappings.items():
                    # 랜덤 점수 (보다 현실적인 분포)
                    rand = random.random()
                    if rand < 0.3:  # 30% null
                        value = None
                    elif rand < 0.5:  # 20% 낮은 점수
                        value = random.randint(1, 2)
                    elif rand < 0.8:  # 30% 중간 점수
                        value = random.randint(3, 4)
                    else:  # 20% 높은 점수
                        value = 5

                    section_data[item_key] = value

                # JSON 문자열로 저장
                new_data[section_name] = json.dumps(section_data, ensure_ascii=False)

            # DB 업데이트
            cursor.execute("""
                UPDATE full_process
                SET custom_data = %s
                WHERE fullprocess_number = %s
            """, (json.dumps(new_data, ensure_ascii=False), fp_num))

            print(f"   Updated {fp_num}:")
            for section in sections.keys():
                if section in new_data:
                    print(f"     - {section}: {new_data[section][:50]}...")

        conn.commit()
        print(f"\n✅ Successfully updated {len(records)} records!")

        # 3. 결과 확인
        print("\n3. Verification:")
        cursor.execute("""
            SELECT fullprocess_number, custom_data::text
            FROM full_process
            WHERE fullprocess_number = ANY(%s)
        """, (list(r['fullprocess_number'] for r in records),))

        for row in cursor.fetchall():
            data = json.loads(row['custom_data']) if row['custom_data'] else {}
            print(f"   {row['fullprocess_number']}:")
            for section in sections.keys():
                if section in data:
                    print(f"     ✓ {section} exists")

    except Exception as e:
        conn.rollback()
        print(f"Error: {e}")
        raise
    finally:
        cursor.close()

def main():
    print("=== Force Scoring Data Injection ===\n")

    # 1. config.ini에서 섹션 로드
    print("1. Loading scoring sections from config.ini...")
    sections = load_scoring_sections('config.ini')
    print(f"   Found {len(sections)} scoring sections\n")

    if not sections:
        print("No scoring sections found in config.ini!")
        return

    # DB 연결
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )

    try:
        # 몇 개 레코드 업데이트할지 선택
        count = input("How many records to update? (default=3): ").strip()
        record_count = int(count) if count else 3

        # 강제 업데이트
        force_update_records(conn, sections, record_count)

    finally:
        conn.close()

if __name__ == "__main__":
    main()