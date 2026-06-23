import sqlite3

# 데이터베이스 연결
conn = sqlite3.connect('change_request.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== Follow SOP Content 컬럼 정보 확인 ===")
print()

# 1. Content 컬럼과 column_order = 0인 컬럼들 확인
cursor.execute("""
    SELECT
        fcc.column_key,
        fcc.column_name,
        fcc.tab,
        fcc.column_order,
        fss.section_order,
        fcc.is_active,
        fcc.is_deleted
    FROM follow_sop_column_config fcc
    LEFT JOIN follow_sop_sections fss ON fcc.tab = fss.section_key
    WHERE fcc.column_key = 'content'
       OR fcc.column_order = 0
    ORDER BY fss.section_order, fcc.column_order
""")

results = cursor.fetchall()
print("1. content 컬럼과 column_order=0인 컬럼들:")
print("-" * 80)
for row in results:
    print(f"  column_key: {row['column_key']:20} | column_name: {row['column_name']:20}")
    print(f"  tab: {row['tab']:20} | column_order: {row['column_order']:5} | section_order: {row['section_order']}")
    print(f"  is_active: {row['is_active']} | is_deleted: {row['is_deleted']}")
    print("-" * 40)

print("\n2. custom_section_1 섹션의 모든 컬럼들 (column_order 순서):")
print("-" * 80)
cursor.execute("""
    SELECT
        column_key,
        column_name,
        column_order,
        is_active
    FROM follow_sop_column_config
    WHERE tab = 'custom_section_1'
      AND is_active = 1
      AND (is_deleted = 0 OR is_deleted IS NULL)
    ORDER BY column_order
""")

for row in cursor.fetchall():
    print(f"  {row['column_order']:3} | {row['column_key']:30} | {row['column_name']}")

print("\n3. column_order 중복 체크:")
print("-" * 80)
cursor.execute("""
    SELECT
        tab,
        column_order,
        COUNT(*) as count,
        GROUP_CONCAT(column_key) as column_keys
    FROM follow_sop_column_config
    WHERE is_active = 1
      AND (is_deleted = 0 OR is_deleted IS NULL)
    GROUP BY tab, column_order
    HAVING count > 1
    ORDER BY tab, column_order
""")

duplicates = cursor.fetchall()
if duplicates:
    for row in duplicates:
        print(f"  섹션: {row['tab']} | column_order: {row['column_order']} | 중복 개수: {row['count']}")
        print(f"  중복 컬럼들: {row['column_keys']}")
        print("-" * 40)
else:
    print("  중복된 column_order 없음")

print("\n4. 렌더링 순서 시뮬레이션 (섹션순서 → 컬럼순서):")
print("-" * 80)

# 섹션 순서대로 가져오기
cursor.execute("""
    SELECT section_key, section_name, section_order
    FROM follow_sop_sections
    WHERE is_active = 1
    ORDER BY section_order
""")
sections = cursor.fetchall()

for section in sections:
    print(f"\n[섹션 {section['section_order']}: {section['section_name']} ({section['section_key']})]")

    cursor.execute("""
        SELECT column_key, column_name, column_order
        FROM follow_sop_column_config
        WHERE tab = ?
          AND is_active = 1
          AND (is_deleted = 0 OR is_deleted IS NULL)
        ORDER BY column_order
        LIMIT 5
    """, (section['section_key'],))

    cols = cursor.fetchall()
    for col in cols:
        print(f"    {col['column_order']:3} | {col['column_key']:30} | {col['column_name']}")

print("\n5. column_order=0 문제 분석:")
print("-" * 80)
cursor.execute("""
    SELECT
        COUNT(*) as zero_count,
        GROUP_CONCAT(column_key) as zero_columns
    FROM follow_sop_column_config
    WHERE column_order = 0
      AND is_active = 1
      AND (is_deleted = 0 OR is_deleted IS NULL)
""")
zero_info = cursor.fetchone()
print(f"  column_order=0인 활성 컬럼 개수: {zero_info['zero_count']}")
if zero_info['zero_columns']:
    print(f"  해당 컬럼들: {zero_info['zero_columns']}")

conn.close()

print("\n분석 완료!")
print("=" * 80)
print("\n권장사항:")
print("1. column_order가 0인 컬럼들을 적절한 순서로 재배치")
print("2. 동일 섹션 내에서 column_order가 중복되지 않도록 조정")
print("3. Python 정렬 로직에서 column_order=0 처리 확인")