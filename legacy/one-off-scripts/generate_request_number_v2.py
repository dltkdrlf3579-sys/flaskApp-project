#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
request_number 생성 - CRYYMMNNN 형식
예: CR2412001, CR2412002, ..., CR2412999 (월별 최대 999개)
"""

import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime

def generate_request_numbers_for_df(df, connection_string='postgresql://postgres:admin123@localhost:5432/portal_dev'):
    """
    DataFrame에 request_number 자동 생성 (CRYYMMNNN 형식)

    Parameters:
    - df: request_number를 생성할 DataFrame (created_at 컬럼 필요)
    - connection_string: PostgreSQL 연결 문자열

    Returns:
    - df: request_number가 추가된 DataFrame
    """

    engine = create_engine(connection_string)

    # created_at이 없으면 현재 시간 사용
    if 'created_at' not in df.columns:
        df['created_at'] = datetime.now()

    # created_at을 datetime으로 변환
    df['created_at'] = pd.to_datetime(df['created_at'])

    # 연월(YYMM) 추출
    df['year_month'] = df['created_at'].dt.strftime('%y%m')

    # 기존 데이터에서 각 월별 마지막 순번 가져오기
    existing_numbers = {}

    for ym in df['year_month'].unique():
        pattern = f"CR{ym}%"

        query = f"""
        SELECT request_number
        FROM partner_change_requests
        WHERE request_number LIKE '{pattern}'
        ORDER BY request_number DESC
        LIMIT 1
        """

        try:
            result = pd.read_sql(query, engine)
            if not result.empty:
                last_num = result.iloc[0]['request_number']
                # CRYYMMNNN에서 NNN 부분 추출
                last_seq = int(last_num[6:9])  # CR2412001 -> 001
                existing_numbers[ym] = last_seq
            else:
                existing_numbers[ym] = 0
        except:
            existing_numbers[ym] = 0

    # request_number 생성
    request_numbers = []
    month_counters = existing_numbers.copy()

    # created_at 기준으로 정렬
    df_sorted = df.sort_values('created_at').reset_index(drop=True)

    for idx, row in df_sorted.iterrows():
        ym = row['year_month']

        # 해당 월의 다음 순번
        month_counters[ym] = month_counters.get(ym, 0) + 1

        # CRYYMMNNN 형식으로 생성
        request_num = f"CR{ym}{month_counters[ym]:03d}"
        request_numbers.append(request_num)

        # 999 초과 체크
        if month_counters[ym] > 999:
            print(f"⚠️ 경고: {ym} 월의 request_number가 999를 초과했습니다!")

    df_sorted['request_number'] = request_numbers

    # year_month 임시 컬럼 제거
    df_sorted = df_sorted.drop('year_month', axis=1)

    engine.dispose()

    return df_sorted

def update_existing_data(connection_string='postgresql://postgres:admin123@localhost:5432/portal_dev'):
    """
    기존 데이터의 request_number를 CRYYMMNNN 형식으로 업데이트
    """

    engine = create_engine(connection_string)

    print("=" * 60)
    print("기존 데이터 request_number 업데이트")
    print("=" * 60)

    # 기존 데이터 읽기
    query = """
    SELECT id, request_number, created_at
    FROM partner_change_requests
    ORDER BY created_at, id
    """

    df = pd.read_sql(query, engine)
    print(f"\n✅ {len(df)}개 데이터 로드됨")

    # 기존 request_number 백업
    df['old_request_number'] = df['request_number']

    # created_at을 datetime으로 변환
    df['created_at'] = pd.to_datetime(df['created_at'])

    # 연월별로 그룹화하여 순번 생성
    df['year_month'] = df['created_at'].dt.strftime('%y%m')

    # 새 request_number 생성
    new_numbers = []
    for ym, group in df.groupby('year_month'):
        # 해당 월 내에서 created_at 순으로 정렬
        group_sorted = group.sort_values(['created_at', 'id']).reset_index(drop=True)

        for idx in range(len(group_sorted)):
            new_num = f"CR{ym}{idx+1:03d}"
            new_numbers.append((group_sorted.iloc[idx]['id'], new_num))

    # DataFrame 생성
    update_df = pd.DataFrame(new_numbers, columns=['id', 'new_request_number'])

    # 원본 df와 병합
    df = df.merge(update_df, on='id', how='left')

    print(f"\n변경 예시 (처음 10개):")
    for idx in range(min(10, len(df))):
        row = df.iloc[idx]
        print(f"  {row['old_request_number']} → {row['new_request_number']}")

    # 실제 업데이트 (각 행별로)
    update_count = 0
    with engine.begin() as conn:
        for _, row in df.iterrows():
            if row['new_request_number'] and row['new_request_number'] != row['old_request_number']:
                conn.execute(
                    """
                    UPDATE partner_change_requests
                    SET request_number = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE id = %s
                    """,
                    (row['new_request_number'], row['id'])
                )
                update_count += 1

    print(f"\n✅ {update_count}개 레코드 업데이트 완료")

    # 최종 확인
    verify_query = """
    SELECT request_number, COUNT(*) as count
    FROM partner_change_requests
    WHERE request_number LIKE 'CR%'
    GROUP BY request_number
    HAVING COUNT(*) > 1
    """

    duplicates = pd.read_sql(verify_query, engine)
    if not duplicates.empty:
        print(f"\n⚠️ 경고: 중복된 request_number 발견:")
        print(duplicates)
    else:
        print(f"\n✅ 중복 없음 - 모든 request_number가 유니크합니다")

    engine.dispose()

def demo_usage():
    """
    사용 예시
    """
    print("\n" + "=" * 60)
    print("사용 예시")
    print("=" * 60)

    print("""
# 1. 새 데이터에 request_number 생성
df = pd.DataFrame({
    'company_name': ['회사A', '회사B', '회사C'],
    'created_at': ['2024-12-01', '2024-12-01', '2024-12-02']
})
df_with_numbers = generate_request_numbers_for_df(df)

# 2. 기존 데이터 업데이트
update_existing_data()

# 3. DataFrame에서 직접 생성 (간단한 버전)
from datetime import datetime
yymm = datetime.now().strftime('%y%m')
df['request_number'] = [f"CR{yymm}{i+1:03d}" for i in range(len(df))]
    """)

def main():
    """
    메인 실행
    """
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == 'update':
        # 기존 데이터 업데이트
        update_existing_data()
    else:
        # 사용법 표시
        demo_usage()

        print("\n" + "=" * 60)
        print("실행 옵션")
        print("=" * 60)
        print("python generate_request_number_v2.py         # 사용법 보기")
        print("python generate_request_number_v2.py update  # 기존 데이터 업데이트")

if __name__ == "__main__":
    main()