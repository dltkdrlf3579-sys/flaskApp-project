#!/usr/bin/env python3
"""
TEST001의 모든 필드를 상세히 출력
"""

from db_connection import get_db_connection
import json

conn = get_db_connection('flask-portal.db')
cursor = conn.cursor()

cursor.execute("""
    SELECT custom_data, detailed_content
    FROM follow_sop
    WHERE work_req_no = 'TEST001'
""")

row = cursor.fetchone()
if row:
    custom_data = json.loads(row[0]) if isinstance(row[0], str) else row[0]

    print("=== TEST001 custom_data 전체 내용 ===")
    print(json.dumps(custom_data, indent=2, ensure_ascii=False))

    print(f"\n=== detailed_content ===")
    print(row[1] if row[1] else '비어있음')

conn.close()