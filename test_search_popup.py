import sqlite3
import os

# DB 경로 설정
DB_PATH = os.path.join(os.path.dirname(__file__), 'portal.db')

def test_tables():
    """테이블 구조 확인"""
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 50)
    print("테이블 구조 확인")
    print("=" * 50)
    
    # emp_table 확인
    try:
        cursor.execute("PRAGMA table_info(emp_table)")
        columns = cursor.fetchall()
        if columns:
            print("\n[emp_table 컬럼 정보]")
            for col in columns:
                print(f"  - {col[1]}: {col[2]}")
                
            # 샘플 데이터 확인
            cursor.execute("SELECT * FROM emp_table WHERE enabled = 1 LIMIT 3")
            rows = cursor.fetchall()
            print(f"\n  샘플 데이터 ({len(rows)}건):")
            for row in rows:
                print(f"    {row}")
        else:
            print("\n[emp_table이 없습니다]")
    except Exception as e:
        print(f"\n[emp_table 오류: {e}]")
    
    # person_master 확인
    try:
        cursor.execute("PRAGMA table_info(person_master)")
        columns = cursor.fetchall()
        if columns:
            print("\n[person_master 컬럼 정보]")
            for col in columns:
                print(f"  - {col[1]}: {col[2]}")
                
            # 샘플 데이터 확인
            cursor.execute("SELECT * FROM person_master WHERE is_active = 1 LIMIT 3")
            rows = cursor.fetchall()
            print(f"\n  샘플 데이터 ({len(rows)}건):")
            for row in rows:
                print(f"    {row}")
        else:
            print("\n[person_master가 없습니다]")
    except Exception as e:
        print(f"\n[person_master 오류: {e}]")
    
    conn.close()

if __name__ == "__main__":
    test_tables()