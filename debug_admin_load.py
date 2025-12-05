#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Admin 페이지 로드 시 데이터 확인
"""

import sqlite3
import json

def debug_admin_load():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("Admin 페이지 로드 시뮬레이션")
        print("=" * 60)

        # /admin-fullprocess-columns 페이지가 로드할 때 실행되는 쿼리
        cursor.execute("""
            SELECT
                id, column_key, column_name, column_type,
                is_active, is_required, dropdown_options,
                column_order, column_span, tab,
                is_deleted
            FROM full_process_column_config
            WHERE is_deleted = 0
            ORDER BY tab, column_order
        """)

        columns = cursor.fetchall()

        print(f"\n총 {len(columns)}개 컬럼 로드됨")

        # 섹션별로 그룹화
        sections = {}
        for col in columns:
            tab = col[9]  # tab 필드
            if tab not in sections:
                sections[tab] = []
            sections[tab].append({
                'id': col[0],
                'column_key': col[1],
                'column_name': col[2],
                'tab': col[9],
                'column_order': col[7],
                'is_active': col[4]
            })

        print("\n[섹션별 컬럼 분포]")
        for section, cols in sections.items():
            print(f"\n{section} ({len(cols)}개):")
            for col in cols[:3]:  # 처음 3개만 표시
                print(f"  - {col['column_key']}: {col['column_name']} (order: {col['column_order']}, active: {col['is_active']})")
            if len(cols) > 3:
                print(f"  ... 외 {len(cols)-3}개")

        # process_duration과 process_output 특별 확인
        print("\n[process_duration, process_output 위치 확인]")
        cursor.execute("""
            SELECT column_key, column_name, tab, column_order, is_active
            FROM full_process_column_config
            WHERE column_key IN ('process_duration', 'process_output')
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]}: tab={row[2]}, order={row[3]}, active={row[4]}")

        # 섹션 정보 로드
        print("\n[섹션 설정 정보]")
        cursor.execute("""
            SELECT section_key, section_name, section_order, is_active
            FROM full_process_sections
            WHERE is_active = 1
            ORDER BY section_order
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} (order: {row[2]})")

    except Exception as e:
        print(f"오류 발생: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    debug_admin_load()