"""리팩토링 테스트"""
import sqlite3
from database_config import DatabaseConfig

DB_PATH = "portal.db"
db_config = DatabaseConfig()

print("\n=== 리팩토링 테스트 시작 ===")
print(f"1. External DB Enabled: {db_config.external_db_enabled}")

# DB에서 사고 조회
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row

# 동적 컬럼 조회
dynamic_columns_rows = conn.execute("""
    SELECT * FROM accident_column_config 
    WHERE is_active = 1 
    ORDER BY column_order
""").fetchall()
dynamic_columns = [dict(row) for row in dynamic_columns_rows]
print(f"2. Dynamic columns: {len(dynamic_columns)}개")

# 로컬 사고 조회
all_accidents = []
try:
    local_accidents_rows = conn.execute("""
        SELECT * FROM accidents_cache 
        ORDER BY accident_date DESC, accident_number DESC
    """).fetchall()
    
    print(f"3. 로컬 DB 사고: {len(local_accidents_rows)}개")
    
    for row in local_accidents_rows:
        accident = dict(row)
        if 'id' not in accident or not accident['id']:
            accident['id'] = len(all_accidents) + 1000
        accident['accident_name'] = accident.get('accident_name') or f"사고_{accident['accident_number']}"
        accident['custom_data'] = accident.get('custom_data', '{}')
        all_accidents.append(accident)
    
    print(f"4. 로컬 사고 처리 완료: {len(all_accidents)}개")
    
    # ACC 사고 확인
    acc_accidents = [a for a in all_accidents if a['accident_number'].startswith('ACC')]
    print(f"5. ACC 사고: {len(acc_accidents)}개")
    if acc_accidents:
        print(f"   예시: {[a['accident_number'] for a in acc_accidents[:3]]}")
        
except Exception as e:
    print(f"오류 발생: {e}")
    import traceback
    traceback.print_exc()

# 더미 데이터 추가 테스트
if not db_config.external_db_enabled:
    dummy_count = 50
    print(f"6. 더미 데이터 {dummy_count}개 추가 예정")
    final_total = len(all_accidents) + dummy_count
    print(f"7. 최종 예상 총 개수: {final_total}개")

conn.close()
print("\n=== 테스트 완료 ===")