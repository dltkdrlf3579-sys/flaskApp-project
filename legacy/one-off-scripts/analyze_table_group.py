#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
table_group 패턴 분석
"""
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database_config import get_db_connection

def analyze():
    conn = get_db_connection()
    cursor = conn.cursor()

    print("=" * 80)
    print("📊 table_group 사용 패턴 분석")
    print("=" * 80)

    # company 관련 필드들
    cursor.execute("""
        SELECT column_key, table_group, table_type, input_type
        FROM follow_sop_column_config
        WHERE column_key LIKE %s OR column_key LIKE %s
        LIMIT 10
    """, ('%company%', '%worker%'))

    rows = cursor.fetchall()
    print("\n### company/worker 관련 필드 ###")
    for row in rows:
        print(f"  {row[0]}")
        print(f"    - table_group: {row[1]}")
        print(f"    - table_type: {row[2]}")
        print(f"    - input_type: {row[3]}")

    # 관련 필드들 (bizno로 끝나는)
    cursor.execute("""
        SELECT column_key, table_group, table_type
        FROM follow_sop_column_config
        WHERE column_key LIKE %s
    """, ('%_bizno',))

    rows = cursor.fetchall()
    print("\n### _bizno로 끝나는 필드 ###")
    for row in rows:
        print(f"  {row[0]}: group={row[1]}, type={row[2]}")

    # table_group 값 패턴
    cursor.execute("""
        SELECT DISTINCT table_group
        FROM follow_sop_column_config
        WHERE table_group IS NOT NULL
        LIMIT 20
    """)

    groups = cursor.fetchall()
    print("\n### 실제 table_group 값들 ###")
    for g in groups:
        print(f"  - {g[0]}")

    print("\n### 분석 결과 ###")
    print("""
    table_group이 column_key와 동일한 값으로 설정되어 있으면:

    1. add_company_info → table_group: add_company_info
    2. add_company_info_bizno → table_group: add_company_info (베이스와 동일!)

    이렇게 되면 _bizno 필드도 베이스 필드와 같은 그룹을 갖게 되어
    충돌 문제가 해결됩니다!

    예시:
    - worker_bizno → table_group: worker → employee 타입
    - company_bizno → table_group: company → company 타입
    """)

    cursor.close()
    conn.close()

if __name__ == "__main__":
    analyze()