#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
partner_change_requests 업데이트 디버깅
"""

import pandas as pd
import psycopg2
from sqlalchemy import create_engine, text
import json

def check_table_structure():
    """테이블 구조 확인"""
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("1. partner_change_requests 테이블 구조")
    print("=" * 60)

    cursor.execute("""
        SELECT column_name, data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'partner_change_requests'
        ORDER BY ordinal_position
    """)

    columns = cursor.fetchall()
    print(f"\n총 {len(columns)}개 컬럼:")
    for col in columns:
        print(f"  - {col[0]}: {col[1]} (nullable: {col[2]}, default: {col[3]})")

    cursor.close()
    conn.close()

    return [col[0] for col in columns]

def check_data_sample():
    """현재 데이터 샘플 확인"""
    engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')

    print("\n" + "=" * 60)
    print("2. 현재 데이터 샘플 (3개)")
    print("=" * 60)

    query = """
    SELECT id, request_number, company_name, status, created_at, updated_at
    FROM partner_change_requests
    ORDER BY updated_at DESC
    LIMIT 3
    """

    df = pd.read_sql(query, engine)
    print("\n최근 업데이트된 데이터:")
    for idx, row in df.iterrows():
        print(f"  ID {row['id']}: {row['request_number']}")
        print(f"    회사: {row['company_name']}")
        print(f"    상태: {row['status']}")
        print(f"    생성: {row['created_at']}")
        print(f"    수정: {row['updated_at']}")
        print()

    engine.dispose()

def test_update_with_commit():
    """직접 UPDATE 테스트 (커밋 확인)"""
    engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')

    print("=" * 60)
    print("3. 직접 UPDATE 테스트")
    print("=" * 60)

    # 1개 행만 테스트
    query = "SELECT * FROM partner_change_requests LIMIT 1"
    df = pd.read_sql(query, engine)

    if df.empty:
        print("데이터가 없습니다.")
        return

    row = df.iloc[0]
    test_id = row['id']
    old_value = row.get('other_info', '')

    print(f"\n테스트 대상:")
    print(f"  ID: {test_id}")
    print(f"  기존 other_info: '{old_value}'")

    # UPDATE 실행
    new_value = f"테스트 업데이트 - {pd.Timestamp.now()}"

    with engine.begin() as conn:  # begin()을 사용하면 자동 커밋
        result = conn.execute(
            text("""
                UPDATE partner_change_requests
                SET other_info = :new_value,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = :id
            """),
            {"new_value": new_value, "id": test_id}
        )
        print(f"\n업데이트 실행: {result.rowcount}개 행 영향받음")

    # 확인
    verify_query = f"SELECT id, other_info, updated_at FROM partner_change_requests WHERE id = {test_id}"
    verify_df = pd.read_sql(verify_query, engine)

    if not verify_df.empty:
        print(f"\n업데이트 확인:")
        print(f"  새 other_info: '{verify_df.iloc[0]['other_info']}'")
        print(f"  updated_at: {verify_df.iloc[0]['updated_at']}")

        if verify_df.iloc[0]['other_info'] == new_value:
            print("  ✅ 업데이트 성공!")
        else:
            print("  ❌ 업데이트 실패!")

    engine.dispose()

def test_dataframe_update():
    """DataFrame 방식 UPDATE 테스트"""
    engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')

    print("\n" + "=" * 60)
    print("4. DataFrame 방식 UPDATE 테스트")
    print("=" * 60)

    # 데이터 읽기
    df = pd.read_sql("SELECT * FROM partner_change_requests LIMIT 5", engine)

    if df.empty:
        print("데이터가 없습니다.")
        return

    print(f"\n{len(df)}개 행 로드됨")

    # 수정
    df['other_info'] = f"DataFrame 업데이트 - {pd.Timestamp.now()}"

    # 방법 1: to_sql with replace (위험 - 전체 테이블 덮어씀)
    # df.to_sql('partner_change_requests', engine, if_exists='replace', index=False)

    # 방법 2: 개별 UPDATE (안전)
    update_count = 0
    with engine.begin() as conn:
        for idx, row in df.iterrows():
            result = conn.execute(
                text("""
                    UPDATE partner_change_requests
                    SET other_info = :other_info,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE id = :id
                """),
                {"other_info": row['other_info'], "id": row['id']}
            )
            update_count += result.rowcount

    print(f"\n업데이트 결과: {update_count}개 행")

    # 확인
    ids = df['id'].tolist()
    verify_query = f"SELECT id, other_info FROM partner_change_requests WHERE id IN ({','.join(map(str, ids))})"
    verify_df = pd.read_sql(verify_query, engine)

    print("\n업데이트 확인:")
    for idx, row in verify_df.iterrows():
        print(f"  ID {row['id']}: {row['other_info'][:50]}...")

    engine.dispose()

def check_missing_columns():
    """DataFrame과 테이블 컬럼 불일치 확인"""
    engine = create_engine('postgresql://postgres:admin123@localhost:5432/portal_dev')

    print("\n" + "=" * 60)
    print("5. 컬럼 불일치 확인")
    print("=" * 60)

    # 테이블 컬럼
    table_cols = check_table_structure()

    # DataFrame 컬럼 (예시)
    df = pd.read_sql("SELECT * FROM partner_change_requests LIMIT 1", engine)
    df_cols = list(df.columns)

    print(f"\n테이블 컬럼 ({len(table_cols)}개):")
    print(f"  {', '.join(table_cols)}")

    print(f"\nDataFrame 컬럼 ({len(df_cols)}개):")
    print(f"  {', '.join(df_cols)}")

    # 차이 확인
    missing_in_df = set(table_cols) - set(df_cols)
    extra_in_df = set(df_cols) - set(table_cols)

    if missing_in_df:
        print(f"\n⚠️ DataFrame에 없는 컬럼:")
        print(f"  {', '.join(missing_in_df)}")

    if extra_in_df:
        print(f"\n⚠️ 테이블에 없는 DataFrame 컬럼:")
        print(f"  {', '.join(extra_in_df)}")

    engine.dispose()

def main():
    """전체 디버깅 실행"""
    try:
        # 1. 테이블 구조
        check_table_structure()

        # 2. 현재 데이터
        check_data_sample()

        # 3. 직접 UPDATE 테스트
        test_update_with_commit()

        # 4. DataFrame UPDATE
        test_dataframe_update()

        # 5. 컬럼 불일치
        check_missing_columns()

    except Exception as e:
        print(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()