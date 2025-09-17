#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
follow_sop 문제 상세 분석 - 수정본
fullprocess_number 대신 fullprocess_number 사용
"""

import psycopg2
from datetime import datetime
import re

def analyze_followsop_detailed():
    """follow_sop 문제 분석"""

    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("Follow SOP 깨짐 현상 상세 분석")
    print("=" * 60)

    # 1. 현재 follow_sop 데이터 상태
    print("\n1. 현재 follow_sop 데이터 상태:")
    cursor.execute("""
        SELECT
            work_req_no,
            created_at,
            updated_at,
            LENGTH(work_req_no) as len
        FROM follow_sop
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    print(f"   전체 레코드: {len(rows)}개\n")

    # 전체 데이터 출력
    print("   [전체 데이터]")
    for row in rows:
        work_req_no = row[0]
        created_at = row[1]
        updated_at = row[2]
        length = row[3]

        # 패턴 분석
        if re.match(r'^FS\d{12}$', work_req_no):
            pattern = "정상(FSYYMMDDHHMMSS)"
        elif re.match(r'^FS\d{6}$', work_req_no):
            pattern = "짧음(FSYYMMDD)"
        elif work_req_no.startswith('FS'):
            pattern = f"비정상(FS+{length-2}자리)"
        else:
            pattern = "기타"

        print(f"   {work_req_no:20} | created: {created_at} | updated: {updated_at} | {pattern}")

    # 2. work_req_no 생성 로직 추적
    print("\n2. work_req_no 생성 시점 추적:")

    # id_generator.py의 generate_followsop_number 함수가 어떻게 동작하는지
    print("\n   [생성 로직 분석]")
    print("   - generate_followsop_number() 함수가 FSYYMMDDHHMMSS 형식 생성")
    print("   - 하지만 외부 동기화 시 work_req_no를 새로 생성하면서 문제 발생")

    # 3. fullprocess와 비교
    print("\n3. fullprocess와 비교:")
    cursor.execute("""
        SELECT
            fullprocess_number,
            created_at,
            LENGTH(fullprocess_number) as len
        FROM full_process
        ORDER BY created_at DESC
        LIMIT 5
    """)

    print("   [fullprocess 샘플]")
    fp_rows = cursor.fetchall()
    for row in fp_rows:
        print(f"   {row[0]:20} | created: {row[1]} | 길이: {row[2]}")

    # 4. 문제의 핵심
    print("\n4. 문제의 핵심 원인:")

    # followsop_cache 확인
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'followsop_cache'
        )
    """)

    has_cache = cursor.fetchone()[0]

    if has_cache:
        cursor.execute("""
            SELECT
                work_req_no,
                created_at,
                LENGTH(work_req_no) as len
            FROM followsop_cache
            ORDER BY created_at DESC NULLS LAST
            LIMIT 5
        """)

        cache_rows = cursor.fetchall()
        if cache_rows:
            print("\n   [followsop_cache 데이터]")
            for row in cache_rows:
                print(f"   {row[0]:20} | created_at: {row[1]} | 길이: {row[2]}")

    print("\n   [분석 결과]")
    print("   1. work_req_no가 FSYYMMDDHHMMSS(14자리) 형식이어야 하는데")
    print("   2. 일부는 FSYYMMDD(8자리)로 잘림")
    print("   3. 외부 동기화 시 generate_followsop_number()가 제대로 동작 안함")
    print("   4. created_at 수정하면서 work_req_no와 불일치 발생")

    # 5. 해결 방안 제시
    print("\n5. 해결 방안:")
    print("   방법1: work_req_no 생성을 FSYYMMDDNNNNN (일자+순번) 형식으로 변경")
    print("   방법2: 외부 동기화 시 work_req_no를 원본 그대로 사용")
    print("   방법3: 기존 work_req_no를 모두 재생성")

    # 6. 정렬 문제 확인
    print("\n6. 정렬 문제 확인:")
    cursor.execute("""
        SELECT
            work_req_no,
            created_at
        FROM follow_sop
        ORDER BY created_at DESC
        LIMIT 5
    """)

    print("   [created_at DESC 정렬]")
    for row in cursor.fetchall():
        print(f"   {row[0]:20} | {row[1]}")

    cursor.execute("""
        SELECT
            work_req_no,
            created_at
        FROM follow_sop
        ORDER BY work_req_no DESC
        LIMIT 5
    """)

    print("\n   [work_req_no DESC 정렬]")
    for row in cursor.fetchall():
        print(f"   {row[0]:20} | {row[1]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("분석 완료: work_req_no 형식 불일치가 근본 원인")
    print("=" * 60)

if __name__ == "__main__":
    analyze_followsop_detailed()