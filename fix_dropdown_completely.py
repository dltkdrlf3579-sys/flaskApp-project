import sqlite3
import json

print("=== 드롭다운 데이터 완전 정리 시작 ===\n")

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 1. column3의 잘못된 데이터 완전 삭제
print("1. column3 기존 데이터 삭제")
cursor.execute("DELETE FROM dropdown_option_codes WHERE column_key = 'column3'")
print(f"   - 삭제된 행: {cursor.rowcount}개")

# 2. 올바른 개별 값으로 재삽입
print("\n2. 개별 값으로 재삽입")
codes = [
    ('column3', 'COLUMN3_001', '진행중', 1, 1),
    ('column3', 'COLUMN3_002', '완료', 2, 1),
    ('column3', 'COLUMN3_003', '보류', 3, 1),
]

for code_data in codes:
    cursor.execute("""
        INSERT INTO dropdown_option_codes 
        (column_key, option_code, option_value, display_order, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, code_data)
    print(f"   - {code_data[1]}: {code_data[2]}")

# 3. accident_column_config의 dropdown_options도 정정
print("\n3. accident_column_config 정정")
correct_options = json.dumps(["진행중", "완료", "보류"], ensure_ascii=False)
cursor.execute("""
    UPDATE accident_column_config 
    SET dropdown_options = ? 
    WHERE column_key = 'column3'
""", (correct_options,))
print(f"   - dropdown_options 설정: {correct_options}")

# 커밋
conn.commit()

# 4. 결과 확인
print("\n=== 결과 확인 ===")
print("\n[dropdown_option_codes 테이블]")
results = cursor.execute("""
    SELECT option_code, option_value, display_order, is_active 
    FROM dropdown_option_codes 
    WHERE column_key='column3'
    ORDER BY display_order
""").fetchall()

for r in results:
    print(f"  {r[0]}: '{r[1]}' (순서:{r[2]}, 활성:{r[3]})")

print("\n[accident_column_config 테이블]")
result = cursor.execute("""
    SELECT dropdown_options 
    FROM accident_column_config 
    WHERE column_key='column3'
""").fetchone()
if result:
    print(f"  dropdown_options: {result[0]}")
    parsed = json.loads(result[0])
    print(f"  파싱 결과: {parsed}")

# 5. Flask 함수 테스트
print("\n[Flask 함수 테스트]")
import sys
sys.path.insert(0, r'C:\Users\sanggil\flask-portal')
from app import get_dropdown_options_for_display

result = get_dropdown_options_for_display('column3')
if result:
    print(f"  get_dropdown_options_for_display 결과:")
    for item in result:
        print(f"    {item['code']}: {item['value']}")
else:
    print("  결과 없음")

conn.close()
print("\n=== 데이터 정리 완료! ===")