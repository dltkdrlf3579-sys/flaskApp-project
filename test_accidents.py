import sqlite3

DB_PATH = "portal.db"

# 로컬 DB에서 사고 조회
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

accidents = conn.execute("""
    SELECT accident_number, accident_name, accident_date 
    FROM accidents_cache 
    ORDER BY accident_date DESC, accident_number DESC
""").fetchall()

print(f"\n총 {len(accidents)}개 사고가 DB에 있습니다:\n")

for acc in accidents:
    print(f"  - {acc['accident_number']}: {acc['accident_name']} ({acc['accident_date']})")

# ACC로 시작하는 사고만 확인
acc_accidents = [a for a in accidents if a['accident_number'].startswith('ACC')]
print(f"\n수동 등록된 사고 (ACC): {len(acc_accidents)}개")

conn.close()