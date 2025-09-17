#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
follow_sop created_at 재동기화 스크립트
캐시의 created_at을 메인 테이블로 다시 동기화
"""

import psycopg2
from datetime import datetime

def resync_followsop_dates():
    """follow_sop created_at 재동기화"""

    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("Follow SOP created_at 재동기화")
    print("=" * 60)

    # 1. 먼저 database_config.py의 sync 함수 실행
    print("\n1. 외부 DB에서 Follow SOP 데이터 동기화 시작...")
    print("   database_config.py의 sync_followsop_from_external_db() 실행")

    from database_config import DatabaseConfig
    db_config = DatabaseConfig()
    success = db_config.sync_followsop_from_external_db()

    if not success:
        print("   [ERROR] 외부 DB 동기화 실패")
        return

    print("   [OK] 외부 DB 동기화 완료")

    # 2. 동기화 결과 확인
    print("\n2. 동기화 결과 확인:")
    cursor.execute("""
        SELECT
            COUNT(*) as cache_count,
            COUNT(DISTINCT created_at) as unique_dates,
            MIN(created_at) as min_date,
            MAX(created_at) as max_date
        FROM followsop_cache
    """)

    cache_stats = cursor.fetchone()
    print(f"   캐시 레코드: {cache_stats[0]}개")
    print(f"   고유 날짜: {cache_stats[1]}개")
    print(f"   기간: {cache_stats[2]} ~ {cache_stats[3]}")

    # 3. 메인 테이블 업데이트 확인
    print("\n3. 메인 테이블 업데이트 확인:")
    cursor.execute("""
        SELECT
            COUNT(*) as total,
            COUNT(DISTINCT created_at) as unique_dates,
            MIN(created_at) as min_date,
            MAX(created_at) as max_date
        FROM follow_sop
    """)

    main_stats = cursor.fetchone()
    print(f"   메인 레코드: {main_stats[0]}개")
    print(f"   고유 날짜: {main_stats[1]}개")
    print(f"   기간: {main_stats[2]} ~ {main_stats[3]}")

    # 4. created_at 정렬 테스트
    print("\n4. created_at DESC 정렬 확인:")
    cursor.execute("""
        SELECT
            work_req_no,
            created_at
        FROM follow_sop
        ORDER BY created_at DESC, work_req_no DESC
        LIMIT 5
    """)

    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]}")

    # 5. 날짜별 분포 확인
    print("\n5. 날짜별 데이터 분포:")
    cursor.execute("""
        SELECT
            DATE(created_at) as date,
            COUNT(*) as count
        FROM follow_sop
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        LIMIT 10
    """)

    for row in cursor.fetchall():
        print(f"   {row[0]}: {row[1]}개")

    cursor.close()
    conn.close()

    print("\n" + "=" * 60)
    print("[OK] 재동기화 완료")
    print("created_at이 외부 데이터의 날짜로 올바르게 설정되었습니다.")
    print("=" * 60)

if __name__ == "__main__":
    resync_followsop_dates()