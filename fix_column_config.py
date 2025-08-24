import sqlite3
import json

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# column3의 dropdown_options를 올바른 형식으로 수정
correct_options = json.dumps(["a", "b", "c"], ensure_ascii=False)

cursor.execute("""
    UPDATE accident_column_config 
    SET dropdown_options = ? 
    WHERE column_key = 'column3'
""", (correct_options,))

conn.commit()

# 확인
result = cursor.execute("""
    SELECT column_key, dropdown_options 
    FROM accident_column_config 
    WHERE column_key='column3'
""").fetchone()

print(f"column_key: {result[0]}")
print(f"dropdown_options: {result[1]}")

# JSON 파싱 테스트
try:
    parsed = json.loads(result[1])
    print(f"파싱된 옵션: {parsed}")
    print(f"옵션 개수: {len(parsed)}")
except Exception as e:
    print(f"파싱 오류: {e}")

conn.close()