import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

print("=== column3의 dropdown_option_codes 정리 ===")

# column3의 모든 코드 삭제
cursor.execute("DELETE FROM dropdown_option_codes WHERE column_key = 'column3'")
print(f"기존 데이터 {cursor.rowcount}개 삭제")

# 새로운 코드 생성
codes = [
    ('column3', 'COLUMN3_001', 'a', 1, 1),
    ('column3', 'COLUMN3_002', 'b', 2, 1),
    ('column3', 'COLUMN3_003', 'c', 3, 1),
]

for code_data in codes:
    cursor.execute("""
        INSERT INTO dropdown_option_codes 
        (column_key, option_code, option_value, display_order, is_active)
        VALUES (?, ?, ?, ?, ?)
    """, code_data)
    print(f"추가: {code_data[1]} = {code_data[2]}")

conn.commit()

# 확인
print("\n=== 정리 후 상태 ===")
results = cursor.execute("""
    SELECT option_code, option_value 
    FROM dropdown_option_codes 
    WHERE column_key='column3' 
    ORDER BY display_order
""").fetchall()

for r in results:
    print(f"{r[0]}: {r[1]}")

conn.close()