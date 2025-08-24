import sqlite3
import json

# get_dropdown_options_for_display 함수 동작 테스트
def get_dropdown_options_for_display(column_key):
    """드롭다운 옵션을 코드-값 매핑 방식으로 가져오기"""
    try:
        conn = sqlite3.connect('portal.db')
        conn.row_factory = sqlite3.Row
        
        # 활성화된 코드 목록 조회
        codes = conn.execute("""
            SELECT option_code, option_value 
            FROM dropdown_option_codes
            WHERE column_key = ? AND is_active = 1
            ORDER BY display_order
        """, (column_key,)).fetchall()
        
        conn.close()
        
        if codes:
            # 코드-값 매핑 방식 반환
            result = [{'code': row['option_code'], 'value': row['option_value']} for row in codes]
            print(f"[OK] {column_key}: 코드-값 매핑 {len(result)}개 = {result}")
            return result
        else:
            print(f"[NO] {column_key}: 코드 없음")
            return None
    except Exception as e:
        print(f"[ERROR] 오류: {e}")
        return None

# column3에 대해 테스트
print("=== column3 테스트 ===")
result = get_dropdown_options_for_display('column3')

# accident_column_config 확인
conn = sqlite3.connect('portal.db')
cursor = conn.cursor()
config = cursor.execute("""
    SELECT column_key, column_name, column_type, dropdown_options 
    FROM accident_column_config 
    WHERE column_key = 'column3'
""").fetchone()

if config:
    print(f"\n=== accident_column_config ===")
    print(f"column_key: {config[0]}")
    print(f"column_name: {config[1]}")
    print(f"column_type: {config[2]}")
    print(f"dropdown_options: {config[3]}")
    
    if config[3]:
        try:
            parsed = json.loads(config[3])
            print(f"파싱된 옵션: {parsed}")
        except Exception as e:
            print(f"파싱 오류: {e}")

conn.close()