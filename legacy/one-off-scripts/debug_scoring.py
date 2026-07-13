#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Scoring 매핑 디버깅 스크립트
운영환경에서 실제로 어떤 일이 일어나는지 확인
"""

import psycopg2
import json
import sys
sys.path.insert(0, '.')

def debug_full_process(fp_number):
    conn = psycopg2.connect("postgresql://postgres:admin123@localhost:5432/portal_dev")
    cursor = conn.cursor()

    print(f"=== DEBUGGING {fp_number} ===\n")

    # 1. full_process 테이블의 실제 컬럼들
    print("1. FULL_PROCESS TABLE COLUMNS:")
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'full_process'
        ORDER BY ordinal_position
    """)
    all_columns = [row[0] for row in cursor.fetchall()]
    for col in all_columns:
        if 'scre' in col or 'test' in col or 'item' in col:
            print(f"   [PROBLEM] {col}")
        else:
            print(f"   {col}")

    # 2. SELECT * 결과
    print(f"\n2. SELECT * FROM full_process WHERE fullprocess_number = '{fp_number}':")
    cursor.execute("SELECT * FROM full_process WHERE fullprocess_number = %s", (fp_number,))
    row = cursor.fetchone()
    if row:
        full_dict = {all_columns[i]: row[i] for i in range(len(all_columns))}
        for key, val in full_dict.items():
            if key == 'custom_data':
                print(f"   {key}: [JSONB field]")
                if val:
                    for k, v in val.items():
                        print(f"      {k}: {repr(v)[:100]}")
            else:
                print(f"   {key}: {repr(val)[:100]}")

    # 3. custom_data 내용 분석
    print(f"\n3. CUSTOM_DATA ANALYSIS:")
    if row and row[1]:  # custom_data is usually 2nd column
        custom_data = row[1]
        if isinstance(custom_data, dict):
            for key, val in custom_data.items():
                if isinstance(val, str) and val.startswith('{'):
                    try:
                        parsed = json.loads(val)
                        print(f"   {key}: JSON with items: {list(parsed.keys())}")
                    except:
                        print(f"   {key}: Invalid JSON - {repr(val)[:50]}")
                else:
                    print(f"   {key}: {type(val).__name__} - {repr(val)[:50]}")

    # 4. external_scoring_table 데이터
    print(f"\n4. EXTERNAL_SCORING_TABLE DATA:")
    cursor.execute("SELECT * FROM external_scoring_table WHERE fullprocess_number = %s", (fp_number,))
    ext_row = cursor.fetchone()
    if ext_row:
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'external_scoring_table'
            ORDER BY ordinal_position
        """)
        ext_columns = [row[0] for row in cursor.fetchall()]
        ext_dict = {ext_columns[i]: ext_row[i] for i in range(len(ext_columns))}
        for key, val in ext_dict.items():
            if val and val != 0:
                print(f"   {key}: {val}")
    else:
        print("   No external data found")

    # 5. 매핑 시뮬레이션
    print(f"\n5. MAPPING SIMULATION:")
    from scoring_external_service_v2 import apply_external_scoring_to_custom_data

    if row and row[1]:
        original = row[1]
        updated = apply_external_scoring_to_custom_data(cursor, fp_number, original)

        for key in ['scre223', 'test224', 'test225']:
            if key in original and key in updated:
                if original[key] != updated[key]:
                    print(f"   {key}: CHANGED")
                    print(f"      FROM: {original[key][:50]}")
                    print(f"      TO: {updated[key][:50]}")
                else:
                    print(f"   {key}: NO CHANGE")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    fp_number = input("Enter fullprocess_number to debug: ").strip()
    if not fp_number:
        fp_number = 'FP2412160001'
    debug_full_process(fp_number)