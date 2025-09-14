#!/usr/bin/env python3
"""
TEST001 데이터 리셋
"""

from db_connection import get_db_connection
import json

conn = get_db_connection('flask-portal.db')
cursor = conn.cursor()

# TEST001 데이터 완전 리셋
clean_data = {
    "company_name": "",
    "business_number": "",
    "request_date": "",
    "department": "",
    "created_by": "",
    "work_type": "",
    "work_location": "",
    "work_content": "",
    "work_status": "",
    "worker_count": "",
    "work_duration": "",
    "test": "",
    "test2": "",
    "testt": "",
    "test_field1": "",
    "test_field2": ""
}

cursor.execute("""
    UPDATE follow_sop
    SET custom_data = ?
    WHERE work_req_no = 'TEST001'
""", (json.dumps(clean_data),))

conn.commit()
print("TEST001 데이터를 리셋했습니다.")

# 확인
cursor.execute("""
    SELECT custom_data
    FROM follow_sop
    WHERE work_req_no = 'TEST001'
""")

row = cursor.fetchone()
if row:
    data = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    print(f"리셋 후 필드 개수: {len(data)}")
    print("모든 필드가 빈 문자열로 초기화됨")

conn.close()