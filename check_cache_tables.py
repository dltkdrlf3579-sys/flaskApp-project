#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
캐시 테이블 데이터 확인 스크립트
운영 서버에서 실행하여 동기화 상태 확인
"""

import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

print("=" * 70)
print("캐시 테이블 데이터 확인")
print("=" * 70)

# 1. 캐시 테이블 데이터 개수
print("\n1. 캐시 테이블 데이터 개수:")
tables = [
    ('partners_cache', 'business_number', 'company_name'),
    ('accidents_cache', 'accident_number', 'accident_name'),
    ('safety_instructions_cache', 'issue_number', 'issuer')
]

for table, id_col, name_col in tables:
    # 전체 개수
    cursor.execute(f"SELECT COUNT(*) FROM {table}")
    total = cursor.fetchone()[0]
    
    # is_deleted 상태별 개수
    cursor.execute(f"SELECT is_deleted, COUNT(*) FROM {table} GROUP BY is_deleted")
    deleted_stats = cursor.fetchall()
    
    print(f"\n{table}:")
    print(f"  총 {total}개 레코드")
    for stat in deleted_stats:
        status = "삭제됨" if stat[0] == 1 else "활성"
        print(f"    - is_deleted={stat[0]} ({status}): {stat[1]}개")
    
    # 샘플 데이터 3개
    cursor.execute(f"""
        SELECT {id_col}, {name_col}, is_deleted 
        FROM {table} 
        WHERE is_deleted = 0 OR is_deleted IS NULL
        LIMIT 3
    """)
    samples = cursor.fetchall()
    if samples:
        print("  샘플 데이터 (활성 상태만):")
        for sample in samples:
            print(f"    - {sample[0]}: {sample[1]} (is_deleted={sample[2]})")
    else:
        print("  [경고] 활성 데이터가 없습니다!")

# 2. 로컬 테이블 데이터 개수 (비교용)
print("\n" + "=" * 70)
print("2. 로컬 테이블 데이터 개수 (비교):")
local_tables = [
    'follow_sop',
    'full_process', 
    'safety_instructions'
]

for table in local_tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"  {table}: {count}개")
    except:
        print(f"  {table}: 테이블 없음")

# 3. 동기화 이력 확인
print("\n" + "=" * 70)
print("3. 동기화 이력:")
cursor.execute("""
    SELECT last_full_sync FROM sync_state WHERE id=1
""")
sync_state = cursor.fetchone()
if sync_state:
    print(f"  마지막 동기화: {sync_state[0]}")
else:
    print("  동기화 이력 없음")

conn.close()

print("\n" + "=" * 70)
print("확인 완료")
print("=" * 70)
print("\n[중요] 캐시 테이블에 데이터가 있고 is_deleted=0인데도")
print("게시판에서 안 보인다면 app.py의 조회 로직을 확인해야 합니다.")