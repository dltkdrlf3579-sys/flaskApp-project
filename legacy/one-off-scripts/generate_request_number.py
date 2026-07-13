#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
request_number 생성 공식 및 기존 데이터 확인
"""

import psycopg2
import pandas as pd
from datetime import datetime
from sqlalchemy import create_engine

def check_existing_patterns():
    """기존 request_number 패턴 확인"""
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("1. 기존 request_number 패턴 확인")
    print("=" * 60)

    # 기존 데이터 조회
    cursor.execute("""
        SELECT request_number
        FROM partner_change_requests
        WHERE request_number IS NOT NULL
        ORDER BY request_number
        LIMIT 20
    """)

    existing = cursor.fetchall()
    print(f"\n기존 request_number 예시 (최대 20개):")
    for row in existing:
        print(f"  - {row[0]}")

    # 패턴 분석
    cursor.execute("""
        SELECT
            SUBSTRING(request_number, 1, 2) as prefix,
            COUNT(*) as count
        FROM partner_change_requests
        WHERE request_number IS NOT NULL
        GROUP BY SUBSTRING(request_number, 1, 2)
        ORDER BY count DESC
    """)

    patterns = cursor.fetchall()
    print(f"\n접두사 패턴 분석:")
    for pattern in patterns:
        print(f"  - '{pattern[0]}': {pattern[1]}개")

    cursor.close()
    conn.close()

def generate_request_number_formula():
    """request_number 생성 공식들"""

    print("\n" + "=" * 60)
    print("2. request_number 생성 공식")
    print("=" * 60)

    # 공식 1: CR-YYYYMM-NN (연도월-순번)
    now = datetime.now()
    year_month = now.strftime('%Y%m')
    sequence_num = 1  # 실제로는 DB에서 마지막 번호 조회 후 +1

    formula1 = f"CR-{year_month}-{sequence_num:02d}"
    print(f"\n공식1 (CR-YYYYMM-NN):")
    print(f"  예시: {formula1}")
    print(f"  코드: f\"CR-{{datetime.now().strftime('%Y%m')}}-{{sequence_num:02d}}\"")

    # 공식 2: CR-YYYYMMDD-NNN (연도월일-순번)
    year_month_day = now.strftime('%Y%m%d')
    formula2 = f"CR-{year_month_day}-{sequence_num:03d}"
    print(f"\n공식2 (CR-YYYYMMDD-NNN):")
    print(f"  예시: {formula2}")
    print(f"  코드: f\"CR-{{datetime.now().strftime('%Y%m%d')}}-{{sequence_num:03d}}\"")

    # 공식 3: CR-YYMM-NNNN (2자리연도월-순번)
    year_month_short = now.strftime('%y%m')
    formula3 = f"CR-{year_month_short}-{sequence_num:04d}"
    print(f"\n공식3 (CR-YYMM-NNNN):")
    print(f"  예시: {formula3}")
    print(f"  코드: f\"CR-{{datetime.now().strftime('%y%m')}}-{{sequence_num:04d}}\"")

    # 공식 4: CR + Unix timestamp
    import time
    timestamp = int(time.time())
    formula4 = f"CR{timestamp}"
    print(f"\n공식4 (CR + timestamp):")
    print(f"  예시: {formula4}")
    print(f"  코드: f\"CR{{int(time.time())}}\"")

    return {
        'formula1': formula1,
        'formula2': formula2,
        'formula3': formula3,
        'formula4': formula4
    }

def get_next_sequence_number(prefix_pattern):
    """특정 패턴의 다음 순번 가져오기"""
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("3. 다음 순번 계산")
    print("=" * 60)

    # 현재 월 기준 마지막 번호 찾기
    year_month = datetime.now().strftime('%Y%m')
    pattern = f"CR-{year_month}-%"

    cursor.execute("""
        SELECT request_number
        FROM partner_change_requests
        WHERE request_number LIKE %s
        ORDER BY request_number DESC
        LIMIT 1
    """, (pattern,))

    last_number = cursor.fetchone()

    if last_number:
        # 마지막 번호에서 순번 추출
        last_req_num = last_number[0]
        print(f"\n현재 월({year_month}) 마지막 번호: {last_req_num}")

        # 순번 부분 추출 (마지막 '-' 뒤의 숫자)
        try:
            last_seq = int(last_req_num.split('-')[-1])
            next_seq = last_seq + 1
            print(f"다음 순번: {next_seq}")
        except:
            next_seq = 1
            print(f"순번 추출 실패, 1부터 시작")
    else:
        next_seq = 1
        print(f"\n현재 월({year_month}) 데이터 없음, 1부터 시작")

    next_request_number = f"CR-{year_month}-{next_seq:02d}"
    print(f"다음 request_number: {next_request_number}")

    cursor.close()
    conn.close()

    return next_request_number

def create_bulk_request_numbers(count=10):
    """여러 개의 request_number 일괄 생성"""
    print("\n" + "=" * 60)
    print("4. 일괄 생성 예시")
    print("=" * 60)

    year_month = datetime.now().strftime('%Y%m')

    # DataFrame으로 일괄 생성 예시
    request_numbers = []
    for i in range(1, count + 1):
        request_numbers.append(f"CR-{year_month}-{i:02d}")

    df = pd.DataFrame({
        'request_number': request_numbers,
        'created_at': datetime.now()
    })

    print(f"\n생성된 request_number 목록:")
    for num in request_numbers[:5]:  # 처음 5개만 표시
        print(f"  - {num}")
    print(f"  ... (총 {count}개)")

    return df

def main():
    """전체 실행"""
    try:
        # 1. 기존 패턴 확인
        check_existing_patterns()

        # 2. 생성 공식
        formulas = generate_request_number_formula()

        # 3. 다음 순번
        next_num = get_next_sequence_number("CR-202412-%")

        # 4. 일괄 생성 예시
        df = create_bulk_request_numbers(10)

        print("\n" + "=" * 60)
        print("5. 권장 공식")
        print("=" * 60)
        print("""
# Python에서 사용:
from datetime import datetime

def generate_request_number(sequence_num):
    year_month = datetime.now().strftime('%Y%m')
    return f"CR-{year_month}-{sequence_num:02d}"

# pandas DataFrame에서 사용:
df['request_number'] = df.index.map(lambda i: f"CR-{datetime.now().strftime('%Y%m')}-{i+1:02d}")

# SQL에서 사용:
# PostgreSQL: 'CR-' || TO_CHAR(NOW(), 'YYYYMM') || '-' || LPAD(sequence_num::text, 2, '0')
        """)

    except Exception as e:
        print(f"\n❌ 오류: {e}")

if __name__ == "__main__":
    main()