import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def setup_linked_dept():
    """담당자와 담당부서 필드를 연결 설정"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 현재 동적 컬럼 확인
        cursor.execute("""
            SELECT * FROM accident_column_config 
            WHERE is_active = 1
            ORDER BY column_order
        """)
        columns = cursor.fetchall()
        
        print("[현재 활성화된 동적 컬럼]")
        for col in columns:
            print(f"  {col[2]}: {col[1]} (타입: {col[3]})")
        
        # 담당자 컬럼이 있는지 확인
        person_col = None
        dept_col = None
        
        for col in columns:
            # column_key가 column5이고 타입이 popup_person인 경우
            if col[2] == 'column5' and col[3] == 'popup_person':
                person_col = col
            # 담당부서 관련 컬럼 찾기
            elif '담당부서' in col[1] or '부서' in col[1] or col[2] == 'column4':
                dept_col = col
        
        if person_col:
            print(f"\n[담당자 컬럼 발견]: {person_col[1]}")
            
            # 담당부서 컬럼이 없으면 생성
            if not dept_col:
                # 담당자 컬럼 다음 위치에 담당부서 컬럼 추가
                next_order = person_col[5] + 1
                
                # 기존 컬럼들의 순서를 조정
                cursor.execute("""
                    UPDATE accident_column_config 
                    SET column_order = column_order + 1
                    WHERE column_order >= ?
                """, (next_order,))
                
                # 담당부서 컬럼 추가
                cursor.execute("""
                    INSERT INTO accident_column_config 
                    (column_name, column_key, column_type, dropdown_options, column_order, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, ('담당부서', 'linked_dept', 'linked_dept', None, next_order, 1))
                
                print(f"[SUCCESS] 담당부서 컬럼 추가 완료 (순서: {next_order})")
            else:
                # 담당부서 컬럼이 있으면 타입과 위치 업데이트
                print(f"[담당부서 컬럼 발견]: {dept_col[1]}")
                
                # 타입을 linked_dept로 변경
                cursor.execute("""
                    UPDATE accident_column_config 
                    SET column_type = 'linked_dept'
                    WHERE id = ?
                """, (dept_col[0],))
                
                # 담당자 컬럼 바로 다음으로 위치 조정
                if dept_col[5] != person_col[5] + 1:
                    new_order = person_col[5] + 1
                    
                    # 다른 컬럼들 순서 조정
                    cursor.execute("""
                        UPDATE accident_column_config 
                        SET column_order = column_order + 1
                        WHERE column_order >= ? AND id != ?
                    """, (new_order, dept_col[0]))
                    
                    # 담당부서 컬럼 위치 업데이트
                    cursor.execute("""
                        UPDATE accident_column_config 
                        SET column_order = ?
                        WHERE id = ?
                    """, (new_order, dept_col[0]))
                    
                    print(f"[SUCCESS] 담당부서 컬럼 위치 조정 완료 (순서: {new_order})")
                else:
                    print("[INFO] 담당부서 컬럼이 이미 올바른 위치에 있습니다")
        else:
            print("\n[INFO] 담당자 컬럼이 없습니다. 먼저 담당자 컬럼을 추가해주세요.")
        
        conn.commit()
        
        # 변경 후 컬럼 확인
        print("\n[변경 후 동적 컬럼]")
        cursor.execute("""
            SELECT * FROM accident_column_config 
            WHERE is_active = 1
            ORDER BY column_order
        """)
        columns = cursor.fetchall()
        for col in columns:
            print(f"  순서 {col[5]}: {col[1]} (타입: {col[3]})")
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    setup_linked_dept()