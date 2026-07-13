#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
모든 Full Process scoring 데이터 초기화
- 깨진 데이터 전부 삭제
- scoring 필드만 깨끗한 JSON 구조로 초기화
"""

import psycopg2
import json

def reset_all_scoring():
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    conn.autocommit = True
    cursor = conn.cursor()

    print("=== 모든 Scoring 데이터 리셋 ===\n")

    # 1. 모든 full_process 레코드의 custom_data 초기화
    cursor.execute("""
        SELECT fullprocess_number, custom_data
        FROM full_process
        WHERE custom_data IS NOT NULL
    """)

    records = cursor.fetchall()
    print(f"총 {len(records)}개 레코드 발견\n")

    reset_count = 0

    for fp_num, current_data in records:
        # 새로운 깨끗한 custom_data 생성
        clean_data = {}

        if current_data:
            # 기존 non-scoring 필드는 유지
            for key, value in current_data.items():
                # JSON 문자열이면서 item_ 패턴이 있으면 scoring 필드
                if isinstance(value, str) and value.startswith('{'):
                    try:
                        parsed = json.loads(value)
                        if any(k.startswith('item_') for k in parsed.keys()):
                            # scoring 필드 - null로 초기화
                            reset_items = {}
                            for item_key in parsed.keys():
                                if item_key.startswith('item_'):
                                    reset_items[item_key] = None
                            clean_data[key] = json.dumps(reset_items)
                            print(f"  [RESET] {fp_num}: {key}")
                        else:
                            clean_data[key] = value  # scoring 아님 - 유지
                    except:
                        clean_data[key] = value  # JSON 아님 - 유지
                # 깨진 외부 컬럼명은 제거
                elif ('_item_' in key or
                      key.startswith('tbm_') or
                      key.startswith('safety_') or
                      key.startswith('quality_') or
                      key.startswith('scre223_') or
                      key.startswith('test224_') or
                      key.startswith('test225_')):
                    print(f"  [DELETE] {fp_num}: {key} (corrupted field)")
                    # 이 필드는 제외
                    continue
                else:
                    # 정상 필드는 유지
                    clean_data[key] = value

        # DB 업데이트
        cursor.execute("""
            UPDATE full_process
            SET custom_data = %s
            WHERE fullprocess_number = %s
        """, (json.dumps(clean_data) if clean_data else None, fp_num))

        reset_count += 1

    print(f"\n=== 완료 ===")
    print(f"{reset_count}개 레코드 리셋됨")

    # 2. 외부 테이블 데이터 확인
    cursor.execute("SELECT COUNT(*) FROM external_scoring_table")
    ext_count = cursor.fetchone()[0]
    print(f"\n외부 테이블에 {ext_count}개의 매핑 데이터 있음")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    response = input("정말로 모든 scoring 데이터를 리셋하시겠습니까? (yes/no): ")
    if response.lower() == 'yes':
        reset_all_scoring()
        print("\n이제 상세 페이지를 방문하면 자동으로 외부 데이터가 매핑됩니다.")
    else:
        print("취소되었습니다.")