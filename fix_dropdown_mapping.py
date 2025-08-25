import sqlite3
import json
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def fix_dropdown_mapping():
    """잘못 저장된 드롭다운 매핑 수정"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 현재 dropdown_code_mapping 확인
        cursor.execute("""
            SELECT id, column_key, code, option_value 
            FROM dropdown_code_mapping
        """)
        
        mappings = cursor.fetchall()
        
        for mapping_id, column_key, code, option_value in mappings:
            # JSON 배열 문자열인지 확인
            if option_value and option_value.startswith('[') and option_value.endswith(']'):
                try:
                    # JSON 파싱
                    options = json.loads(option_value)
                    
                    if isinstance(options, list):
                        print(f"[{column_key}] JSON 배열 발견: {options}")
                        
                        # 기존 매핑 삭제
                        cursor.execute("""
                            DELETE FROM dropdown_code_mapping 
                            WHERE column_key = ?
                        """, (column_key,))
                        
                        # 올바른 매핑 추가 (각 옵션을 개별 레코드로)
                        for i, option in enumerate(options):
                            new_code = f"{column_key.upper()}_{i+1:03d}"
                            cursor.execute("""
                                INSERT INTO dropdown_code_mapping 
                                (column_key, code, option_value, display_order, is_active)
                                VALUES (?, ?, ?, ?, 1)
                            """, (column_key, new_code, str(option), i + 1))
                        
                        print(f"[{column_key}] {len(options)}개 옵션으로 수정 완료")
                            
                except json.JSONDecodeError as e:
                    print(f"[{column_key}] JSON 파싱 실패: {e}")
                except Exception as e:
                    print(f"[{column_key}] 처리 중 오류: {e}")
        
        conn.commit()
        
        # 수정 후 결과 확인
        print("\n[수정 후 드롭다운 매핑]")
        cursor.execute("""
            SELECT column_key, code, option_value, display_order
            FROM dropdown_code_mapping
            ORDER BY column_key, display_order
        """)
        
        for row in cursor.fetchall():
            print(f"  {row[0]} - {row[1]}: {row[2]} (순서: {row[3]})")
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    fix_dropdown_mapping()