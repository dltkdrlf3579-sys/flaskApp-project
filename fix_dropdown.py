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
print(f"column3의 dropdown_options를 수정했습니다: {correct_options}")

# 확인
result = cursor.execute("SELECT dropdown_options FROM accident_column_config WHERE column_key='column3'").fetchone()
print(f"수정 후: {result[0]}")

conn.close()