#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Admin 저장 문제 진단 - full-process와 follow-sop 비교
"""

import sqlite3
import json

def check_column_tabs():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()

    try:
        print("=" * 60)
        print("Full Process 컬럼의 섹션 정보 확인")
        print("=" * 60)

        # process_duration과 process_output의 현재 섹션 확인
        cursor.execute("""
            SELECT column_key, column_name, tab, column_order, is_active
            FROM full_process_column_config
            WHERE column_key IN ('process_duration', 'process_output')
            ORDER BY column_order
        """)

        print("\n[process_duration, process_output 필드 상태]")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")
            print(f"    - tab: {row[2]}")
            print(f"    - order: {row[3]}")
            print(f"    - active: {row[4]}")
            print()

        # 모든 섹션별 컬럼 수 확인
        print("\n[Full Process 섹션별 컬럼 수]")
        cursor.execute("""
            SELECT tab, COUNT(*) as cnt
            FROM full_process_column_config
            WHERE is_active = 1 AND is_deleted = 0
            GROUP BY tab
            ORDER BY tab
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}개")

        # Follow SOP 비교
        print("\n" + "=" * 60)
        print("Follow SOP 섹션별 컬럼 수 (비교용)")
        print("=" * 60)

        cursor.execute("""
            SELECT tab, COUNT(*) as cnt
            FROM follow_sop_column_config
            WHERE is_active = 1 AND is_deleted = 0
            GROUP BY tab
            ORDER BY tab
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}개")

        # 섹션 설정 테이블 확인
        print("\n" + "=" * 60)
        print("섹션 설정 테이블 확인")
        print("=" * 60)

        # Full Process 섹션
        cursor.execute("""
            SELECT section_key, section_name, section_order
            FROM full_process_section_config
            WHERE is_active = 1
            ORDER BY section_order
        """)

        print("\n[Full Process 섹션 설정]")
        for row in cursor.fetchall():
            print(f"  {row[1]} ({row[0]}) - order: {row[2]}")

        # Follow SOP 섹션
        cursor.execute("""
            SELECT section_key, section_name, section_order
            FROM follow_sop_section_config
            WHERE is_active = 1
            ORDER BY section_order
        """)

        print("\n[Follow SOP 섹션 설정]")
        for row in cursor.fetchall():
            print(f"  {row[1]} ({row[0]}) - order: {row[2]}")

        # 마지막 수정 시간 확인
        print("\n" + "=" * 60)
        print("마지막 수정 시간 확인")
        print("=" * 60)

        cursor.execute("""
            SELECT 'full_process' as board, MAX(updated_at) as last_update
            FROM full_process_column_config
            WHERE column_key IN ('process_duration', 'process_output')
            UNION ALL
            SELECT 'follow_sop' as board, MAX(updated_at) as last_update
            FROM follow_sop_column_config
            WHERE updated_at IS NOT NULL
        """)

        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]}")

    except Exception as e:
        print(f"오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_column_tabs()