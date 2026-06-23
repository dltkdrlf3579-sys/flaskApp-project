#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
process_duration과 process_output 필드를 additional 섹션으로 이동
"""

import sqlite3
import json

def fix_section():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()

    try:
        # process_duration과 process_output을 additional 섹션으로 이동
        cursor.execute("""
            UPDATE full_process_column_config
            SET tab = 'additional'
            WHERE column_key IN ('process_duration', 'process_output')
        """)

        affected = cursor.rowcount
        print(f"수정된 행: {affected}")

        # 확인
        cursor.execute("""
            SELECT column_key, column_name, tab
            FROM full_process_column_config
            WHERE column_key IN ('process_duration', 'process_output')
        """)

        print("\n변경 후 상태:")
        for row in cursor.fetchall():
            print(f"  {row[0]}: {row[1]} -> tab={row[2]}")

        conn.commit()
        print("\n✅ 섹션 정보가 수정되었습니다.")

    except Exception as e:
        conn.rollback()
        print(f"❌ 오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_section()