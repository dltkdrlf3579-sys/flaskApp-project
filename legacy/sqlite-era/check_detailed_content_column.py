#!/usr/bin/env python3
"""
follow_sop 테이블에 detailed_content 컬럼이 있는지 확인
"""

from db_connection import get_db_connection

conn = get_db_connection('flask-portal.db')
cursor = conn.cursor()

# PostgreSQL인지 확인
try:
    # 컬럼 정보 조회
    cursor.execute("""
        SELECT column_name
        FROM information_schema.columns
        WHERE table_name = 'follow_sop'
        ORDER BY ordinal_position
    """)

    columns = cursor.fetchall()
    if columns:
        print("=== follow_sop 테이블 컬럼 목록 ===")
        for col in columns:
            print(f"  - {col[0]}")

        # detailed_content 컬럼 확인
        column_names = [col[0] for col in columns]
        if 'detailed_content' in column_names:
            print("\n✅ detailed_content 컬럼이 있습니다!")
        else:
            print("\n❌ detailed_content 컬럼이 없습니다!")
    else:
        print("컬럼 정보를 가져올 수 없습니다.")

except Exception as e:
    print(f"오류: {e}")
    # SQLite 방식 시도
    try:
        cursor.execute("PRAGMA table_info(follow_sop)")
        columns = cursor.fetchall()
        print("\n=== follow_sop 테이블 컬럼 목록 (SQLite) ===")
        for col in columns:
            print(f"  - {col[1]}")  # col[1]이 컬럼명
    except:
        pass

conn.close()