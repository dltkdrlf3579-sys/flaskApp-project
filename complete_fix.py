import sqlite3
import json

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

print("=== 완전 정리 시작 ===\n")

# 1. dropdown_option_codes 테이블 정리
print("1. dropdown_option_codes 테이블 정리")
cursor.execute("DELETE FROM dropdown_option_codes WHERE column_key = 'column3'")
print(f"   - 기존 데이터 {cursor.rowcount}개 삭제")

# 새로운 코드 생성 (올바른 개별 값으로)
codes = [
    ('column3', 'COLUMN3_001', 'a', 1, 1),
    ('column3', 'COLUMN3_002', 'b', 2, 1),
    ('column3', 'COLUMN3_003', 'c', 3, 1),
    ('column3', 'COLUMN3_004', 'd', 4, 1),
]

for code_data in codes:
    cursor.execute("""
        INSERT INTO dropdown_option_codes 
        (column_key, option_code, option_value, display_order, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, code_data)
print(f"   - 새 코드 {len(codes)}개 추가")

# 2. accident_column_config 테이블 정리
print("\n2. accident_column_config 테이블 정리")
correct_options = json.dumps(["a", "b", "c", "d"], ensure_ascii=False)
cursor.execute("""
    UPDATE accident_column_config 
    SET dropdown_options = ? 
    WHERE column_key = 'column3'
""", (correct_options,))
print(f"   - dropdown_options 수정: {correct_options}")

conn.commit()

# 3. 결과 확인
print("\n=== 정리 결과 확인 ===")

print("\n[dropdown_option_codes]")
results = cursor.execute("""
    SELECT option_code, option_value 
    FROM dropdown_option_codes 
    WHERE column_key='column3' 
    ORDER BY display_order
""").fetchall()
for r in results:
    print(f"  {r[0]}: {r[1]}")

print("\n[accident_column_config]")
result = cursor.execute("""
    SELECT dropdown_options 
    FROM accident_column_config 
    WHERE column_key='column3'
""").fetchone()
if result:
    print(f"  dropdown_options: {result[0]}")
    try:
        parsed = json.loads(result[0])
        print(f"  파싱 결과: {parsed}")
        print(f"  타입: {type(parsed)}, 길이: {len(parsed)}")
    except Exception as e:
        print(f"  파싱 오류: {e}")

conn.close()
print("\n=== 완료! ===")