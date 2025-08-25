import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def update_dept_field():
    """column4를 담당부서로 설정하고 linked_dept 타입으로 변경"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # column4를 담당부서로 변경
        cursor.execute("""
            UPDATE accident_column_config 
            SET column_name = '담당부서',
                column_type = 'linked_dept'
            WHERE column_key = 'column4'
        """)
        
        # column5 담당자 확인
        cursor.execute("""
            UPDATE accident_column_config 
            SET column_name = '담당자'
            WHERE column_key = 'column5'
        """)
        
        # 순서 재정렬 - column5(담당자) 다음에 column4(담당부서)가 오도록
        # 먼저 모든 컬럼의 순서를 가져옴
        cursor.execute("""
            SELECT id, column_key, column_name, column_order
            FROM accident_column_config
            WHERE is_active = 1
            ORDER BY column_order
        """)
        columns = cursor.fetchall()
        
        # 새로운 순서 할당
        new_order = 1
        ordered_columns = []
        
        # column5(담당자)까지 처리
        for col in columns:
            if col[1] == 'column5':
                ordered_columns.append((new_order, col[0]))
                new_order += 1
                # column5 다음에 column4 추가
                for c in columns:
                    if c[1] == 'column4':
                        ordered_columns.append((new_order, c[0]))
                        new_order += 1
                        break
            elif col[1] != 'column4':  # column4는 이미 처리했으므로 스킵
                ordered_columns.append((new_order, col[0]))
                new_order += 1
        
        # 순서 업데이트
        for order, col_id in ordered_columns:
            cursor.execute("""
                UPDATE accident_column_config
                SET column_order = ?
                WHERE id = ?
            """, (order, col_id))
        
        conn.commit()
        
        # 결과 확인
        print("[SUCCESS] 담당부서 필드 설정 완료")
        print("\n[변경 후 동적 컬럼]")
        cursor.execute("""
            SELECT column_name, column_key, column_type, column_order
            FROM accident_column_config
            WHERE is_active = 1
            ORDER BY column_order
        """)
        for row in cursor.fetchall():
            print(f"  순서 {row[3]}: {row[0]} ({row[1]}) - 타입: {row[2]}")
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    update_dept_field()