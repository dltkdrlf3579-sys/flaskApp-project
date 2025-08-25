import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def add_employee_id_column():
    """person_master 테이블에 employee_id 컬럼 추가"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # employee_id 컬럼이 있는지 확인
        cursor.execute("PRAGMA table_info(person_master)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'employee_id' not in columns:
            # employee_id 컬럼 추가
            cursor.execute("""
                ALTER TABLE person_master 
                ADD COLUMN employee_id VARCHAR(20)
            """)
            print("[SUCCESS] employee_id column added to person_master table")
            
            # 기존 데이터에 employee_id 업데이트
            cursor.execute("SELECT id, name FROM person_master")
            persons = cursor.fetchall()
            
            for person_id, name in persons:
                emp_id = f"E{person_id:03d}"
                cursor.execute("""
                    UPDATE person_master 
                    SET employee_id = ? 
                    WHERE id = ?
                """, (emp_id, person_id))
            
            print(f"[SUCCESS] Updated {len(persons)} records with employee_id")
            conn.commit()
        else:
            print("[INFO] employee_id column already exists")
            
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    add_employee_id_column()