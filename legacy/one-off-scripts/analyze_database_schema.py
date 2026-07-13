#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 스키마 전체 분석 스크립트
"""
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime

# PostgreSQL 연결
conn = psycopg2.connect(
    host="localhost",
    database="portal_dev",
    user="postgres",
    password="admin123",
    port=5432
)
cursor = conn.cursor(cursor_factory=RealDictCursor)

print("=" * 80)
print("데이터베이스 스키마 전체 분석")
print("분석 시작: " + datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
print("=" * 80)

# 1. 모든 테이블 목록 확인
print("\n1. 데이터베이스 내 모든 테이블 목록")
print("-" * 60)
cursor.execute("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'public'
    ORDER BY table_name
""")

all_tables = cursor.fetchall()
print(f"총 테이블 수: {len(all_tables)}개\n")

# 테이블을 카테고리별로 분류
permission_tables = []
user_tables = []
board_tables = []
config_tables = []
other_tables = []

for table in all_tables:
    table_name = table['table_name']
    print(f"  - {table_name}")

    # 카테고리 분류
    if 'permission' in table_name or 'role' in table_name or 'auth' in table_name:
        permission_tables.append(table_name)
    elif 'user' in table_name:
        user_tables.append(table_name)
    elif any(board in table_name for board in ['follow_sop', 'full_process', 'accident', 'safety']):
        board_tables.append(table_name)
    elif 'config' in table_name or 'column' in table_name or 'section' in table_name:
        config_tables.append(table_name)
    else:
        other_tables.append(table_name)

# 2. 권한 관련 테이블 상세 분석
print("\n2. 권한/역할 관련 테이블 상세 분석")
print("-" * 60)
print(f"권한 관련 테이블: {permission_tables}")

for table_name in permission_tables:
    print(f"\n[{table_name}]")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))

    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col['column_name']:25} | {col['data_type']:20} | nullable: {col['is_nullable']}")

    # 샘플 데이터 확인
    cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
    count = cursor.fetchone()
    print(f"  레코드 수: {count['cnt']}")

# 3. 사용자 관련 테이블 상세 분석
print("\n3. 사용자 관련 테이블 상세 분석")
print("-" * 60)
print(f"사용자 관련 테이블: {user_tables}")

for table_name in user_tables:
    print(f"\n[{table_name}]")
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
        LIMIT 10
    """, (table_name,))

    columns = cursor.fetchall()
    for col in columns:
        print(f"  - {col['column_name']:25} | {col['data_type']:20}")

# 4. user_menu_roles 테이블 존재 확인
print("\n4. user_menu_roles 테이블 존재 확인")
print("-" * 60)
cursor.execute("""
    SELECT EXISTS (
        SELECT 1
        FROM information_schema.tables
        WHERE table_name = 'user_menu_roles'
    )
""")
exists = cursor.fetchone()
if exists['exists']:
    print("✓ user_menu_roles 테이블 존재")
    # 컬럼 구조 확인
    cursor.execute("""
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'user_menu_roles'
        ORDER BY ordinal_position
    """)
    columns = cursor.fetchall()
    print("컬럼 구조:")
    for col in columns:
        print(f"  - {col['column_name']:25} | {col['data_type']:20}")
else:
    print("✗ user_menu_roles 테이블 없음!")
    print("\n대체 가능한 테이블 찾기...")

    # 비슷한 이름의 테이블 찾기
    for table in all_tables:
        table_name = table['table_name']
        if 'menu' in table_name or 'role' in table_name:
            print(f"  후보: {table_name}")

# 5. 코드에서 참조하는 테이블 목록
print("\n5. 코드에서 참조하는 테이블 검증")
print("-" * 60)

code_referenced_tables = [
    'system_users',
    'user_menu_roles',
    'follow_sop_column_config',
    'follow_sop_sections',
    'full_process_column_config',
    'full_process_sections',
    'accident_column_config',
    'accident_sections',
    'safety_instruction_column_config',
    'safety_instruction_sections',
    'change_request_column_config',
    'change_request_sections'
]

for table_name in code_referenced_tables:
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        )
    """, (table_name,))
    exists = cursor.fetchone()
    if exists['exists']:
        print(f"✓ {table_name:35} - 존재")
    else:
        print(f"✗ {table_name:35} - 없음! (생성 필요)")

# 6. 분석 결과 저장
analysis_result = {
    'analysis_time': datetime.now().isoformat(),
    'total_tables': len(all_tables),
    'permission_tables': permission_tables,
    'user_tables': user_tables,
    'board_tables': board_tables,
    'config_tables': config_tables,
    'missing_tables': [],
    'recommendations': []
}

# 누락된 테이블 확인
for table_name in code_referenced_tables:
    cursor.execute("""
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_name = %s
        )
    """, (table_name,))
    exists = cursor.fetchone()
    if not exists['exists']:
        analysis_result['missing_tables'].append(table_name)

# 권고사항 생성
if 'user_menu_roles' in analysis_result['missing_tables']:
    analysis_result['recommendations'].append(
        "user_menu_roles 테이블 생성 필요 - 사용자별 메뉴 권한 관리용"
    )

print("\n6. 분석 결과 요약")
print("-" * 60)
print(f"총 테이블 수: {analysis_result['total_tables']}")
print(f"누락된 테이블: {len(analysis_result['missing_tables'])}개")
for table in analysis_result['missing_tables']:
    print(f"  - {table}")

print("\n권고사항:")
for rec in analysis_result['recommendations']:
    print(f"  - {rec}")

# JSON 파일로 저장
with open('database_schema_analysis.json', 'w', encoding='utf-8') as f:
    json.dump(analysis_result, f, indent=2, ensure_ascii=False)

print("\n분석 결과가 database_schema_analysis.json 파일에 저장되었습니다.")

conn.close()
print("\n분석 완료!")