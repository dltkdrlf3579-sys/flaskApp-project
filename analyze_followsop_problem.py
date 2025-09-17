#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
follow_sop 문제 상세 분석
- work_req_no 깨짐 현상
- created_at 정렬 문제
- fullprocess와의 차이점
"""

import psycopg2
from datetime import datetime
import re

def analyze_followsop_problem():
    """follow_sop 문제 분석"""

    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("Follow SOP 문제 상세 분석")
    print("=" * 60)

    # 1. work_req_no 패턴 분석
    print("\n1. work_req_no 패턴 분석:")
    cursor.execute("""
        SELECT
            work_req_no,
            created_at,
            LENGTH(work_req_no) as len,
            CASE
                WHEN work_req_no ~ '^FS\d{12}$' THEN 'FSYYMMDDHHMMSS (정상)'
                WHEN work_req_no ~ '^FS\d{6}$' THEN 'FSYYMMDD (짧음)'
                WHEN work_req_no ~ '^FS\d+$' THEN 'FS+숫자 (비정상)'
                WHEN work_req_no LIKE 'SOP-%' THEN 'SOP 패턴'
                WHEN work_req_no LIKE 'TEST%' THEN '테스트'
                ELSE '기타'
            END as pattern_type
        FROM follow_sop
        ORDER BY created_at DESC
    """)

    rows = cursor.fetchall()
    print(f"   전체 레코드: {len(rows)}개")

    pattern_counts = {}
    for row in rows:
        pattern = row[3]
        pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

        # 비정상 패턴 상세 출력
        if '비정상' in pattern or '짧음' in pattern:
            print(f"   [문제] {row[0]} (길이:{row[2]}) - {row[3]} - created_at: {row[1]}")

    print("\n   패턴 통계:")
    for pattern, count in pattern_counts.items():
        print(f"   - {pattern}: {count}개")

    # 2. created_at vs work_req_no 일치성 검사
    print("\n2. created_at vs work_req_no 일치성 검사:")
    cursor.execute("""
        SELECT
            work_req_no,
            created_at,
            CASE
                WHEN work_req_no ~ '^FS(\d{2})(\d{2})(\d{2})' THEN
                    SUBSTRING(work_req_no, 3, 6)
                ELSE NULL
            END as extracted_date
        FROM follow_sop
        WHERE work_req_no LIKE 'FS%'
        ORDER BY created_at DESC
    """)

    mismatches = 0
    for row in cursor.fetchall():
        work_req_no = row[0]
        created_at = row[1]
        extracted = row[2]

        if extracted and created_at:
            # YYMMDD 추출
            created_yymmdd = created_at.strftime('%y%m%d')
            if extracted[:6] != created_yymmdd:
                mismatches += 1
                print(f"   [불일치] {work_req_no}: created={created_yymmdd}, extracted={extracted[:6]}")

    print(f"   불일치 개수: {mismatches}개")

    # 3. fullprocess와 비교
    print("\n3. fullprocess와 비교:")

    # fullprocess 구조
    cursor.execute("""
        SELECT
            process_id,
            created_at,
            LENGTH(process_id) as len
        FROM full_process
        ORDER BY created_at DESC
        LIMIT 5
    """)

    print("   fullprocess 샘플:")
    for row in cursor.fetchall():
        print(f"   - {row[0]} (길이:{row[2]}) - created_at: {row[1]}")

    # follow_sop 구조
    cursor.execute("""
        SELECT
            work_req_no,
            created_at,
            LENGTH(work_req_no) as len
        FROM follow_sop
        ORDER BY created_at DESC
        LIMIT 5
    """)

    print("\n   follow_sop 샘플:")
    for row in cursor.fetchall():
        print(f"   - {row[0]} (길이:{row[2]}) - created_at: {row[1]}")

    # 4. 중복 검사
    print("\n4. 중복 검사:")
    cursor.execute("""
        SELECT
            work_req_no,
            COUNT(*) as cnt
        FROM follow_sop
        GROUP BY work_req_no
        HAVING COUNT(*) > 1
    """)

    duplicates = cursor.fetchall()
    if duplicates:
        print("   [경고] 중복된 work_req_no:")
        for dup in duplicates:
            print(f"   - {dup[0]}: {dup[1]}개")
    else:
        print("   [OK] 중복 없음")

    # 5. 캐시 테이블 확인
    print("\n5. followsop_cache 테이블 확인:")
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_name = 'followsop_cache'
        )
    """)

    if cursor.fetchone()[0]:
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                COUNT(DISTINCT work_req_no) as unique_no
            FROM followsop_cache
        """)

        cache_stats = cursor.fetchone()
        print(f"   캐시 레코드: {cache_stats[0]}개")
        print(f"   고유 번호: {cache_stats[1]}개")

        # 캐시의 work_req_no 패턴
        cursor.execute("""
            SELECT
                work_req_no,
                created_at
            FROM followsop_cache
            LIMIT 5
        """)

        print("   캐시 샘플:")
        for row in cursor.fetchall():
            print(f"   - {row[0]}: {row[1]}")
    else:
        print("   [INFO] followsop_cache 테이블 없음")

    # 6. 근본 원인 분석
    print("\n6. 근본 원인 분석:")
    print("   [원인1] work_req_no 생성 로직이 FSYYMMDDHHMMSS 형식을 따르지 않음")
    print("   [원인2] 외부 DB 동기화 시 work_req_no를 새로 생성하면서 기존 번호 덮어쓰기")
    print("   [원인3] created_at 수정 시 work_req_no와 불일치 발생")

    # 7. fullprocess 생성 로직 확인
    print("\n7. fullprocess의 process_id 패턴:")
    cursor.execute("""
        SELECT
            process_id,
            CASE
                WHEN process_id ~ '^CR\d{6}-\d{3}$' THEN 'CRYYMMNN-NNN (정상)'
                ELSE '기타'
            END as pattern
        FROM full_process
        LIMIT 5
    """)

    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]}")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("분석 완료")
    print("=" * 60)

if __name__ == "__main__":
    analyze_followsop_problem()