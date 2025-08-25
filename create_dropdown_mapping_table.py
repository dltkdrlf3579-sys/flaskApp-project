import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def create_dropdown_mapping_table():
    """dropdown_code_mapping 테이블 생성"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 테이블 생성
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dropdown_code_mapping (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key VARCHAR(50) NOT NULL,
                code VARCHAR(20) NOT NULL,
                option_value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(column_key, code)
            )
        """)
        
        # 인덱스 생성
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dropdown_mapping_column 
            ON dropdown_code_mapping(column_key)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_dropdown_mapping_active 
            ON dropdown_code_mapping(is_active)
        """)
        
        conn.commit()
        print("[SUCCESS] dropdown_code_mapping table created successfully")
        
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(dropdown_code_mapping)")
        columns = cursor.fetchall()
        print("\n[Table Structure]")
        for col in columns:
            print(f"  {col[1]}: {col[2]}")
        
    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        conn.rollback()
        
    finally:
        conn.close()

if __name__ == "__main__":
    create_dropdown_mapping_table()