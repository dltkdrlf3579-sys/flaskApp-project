#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
깨진 scoring 데이터 정리 스크립트
- 외부 컬럼명이 직접 들어간 필드 제거
- 정상적인 JSON 구조로 복구
"""

import psycopg2
import json
import sys

def cleanup_corrupted_data():
    # PostgreSQL 연결
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    conn.autocommit = True
    cursor = conn.cursor()

    print("=== Scoring 데이터 정리 시작 ===\n")

    # 1. 모든 full_process 레코드 확인
    cursor.execute("""
        SELECT fullprocess_number, custom_data
        FROM full_process
        WHERE custom_data IS NOT NULL
    """)

    total = 0
    cleaned = 0

    for row in cursor.fetchall():
        fp_num = row[0]
        custom_data = row[1]

        if not custom_data:
            continue

        total += 1
        needs_cleaning = False
        cleaned_data = {}

        # 각 필드 확인
        for key, value in custom_data.items():
            # 외부 컬럼명 패턴 체크 (tbm_, scre223_, test224_ 등)
            if ('_item_' in key or
                key.startswith('tbm_') or
                key.startswith('safety_') or
                key.startswith('quality_') or
                key.startswith('scre223_') or
                key.startswith('test224_') or
                key.startswith('test225_') or
                key == 'heavy_material_plan'):

                print(f"  [삭제] {fp_num}: {key} = {value}")
                needs_cleaning = True
                # 이런 필드는 제외
                continue

            # scoring 필드면 JSON 구조 확인
            elif key in ['tbm', 'safety_check', 'quality_audit', 'scre223', 'test224', 'test225']:
                # JSON 문자열이 아니면 초기화
                if not isinstance(value, str) or not value.startswith('{'):
                    print(f"  [복구] {fp_num}: {key} 초기화")

                    # 기본 구조로 초기화
                    if key == 'test225':
                        cleaned_data[key] = '{"item_1": null, "item_2": null, "item_3": null, "item_4": null}'
                    elif key == 'test224':
                        cleaned_data[key] = '{"item_1": null, "item_2": null}'
                    else:
                        cleaned_data[key] = '{"item_1": null, "item_2": null, "item_3": null}'
                    needs_cleaning = True
                else:
                    cleaned_data[key] = value
            else:
                # 정상 필드는 그대로 유지
                cleaned_data[key] = value

        # 정리가 필요한 경우 DB 업데이트
        if needs_cleaning:
            cursor.execute("""
                UPDATE full_process
                SET custom_data = %s
                WHERE fullprocess_number = %s
            """, (json.dumps(cleaned_data), fp_num))
            cleaned += 1
            print(f"  -> {fp_num} 정리 완료\n")

    print(f"\n=== 정리 완료 ===")
    print(f"총 {total}개 중 {cleaned}개 레코드 정리됨")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    response = input("정말로 깨진 데이터를 정리하시겠습니까? (yes/no): ")
    if response.lower() == 'yes':
        cleanup_corrupted_data()
    else:
        print("취소되었습니다.")