import psycopg
from db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

try:
    # 기존 inspection_no 컬럼 삭제 (CASCADE로 외래키도 함께 삭제)
    cursor.execute("ALTER TABLE safe_workplace DROP COLUMN IF EXISTS inspection_no CASCADE")
    print("inspection_no 컬럼 및 관련 외래키 삭제 완료")

    # safeplace_no 컬럼 추가
    cursor.execute("ALTER TABLE safe_workplace ADD COLUMN IF NOT EXISTS safeplace_no VARCHAR(20) UNIQUE")
    print("safeplace_no 컬럼 추가 완료")

    conn.commit()
    print("DB 스키마 변경 완료!")

except Exception as e:
    conn.rollback()
    print(f"오류 발생: {e}")

finally:
    conn.close()