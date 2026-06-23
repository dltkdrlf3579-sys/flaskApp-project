"""
데이터 존재 여부 확인
"""
import sqlite3
import json

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

print("=== follow_sop 테이블 확인 ===")
cursor.execute("SELECT work_req_no, custom_data FROM follow_sop WHERE work_req_no LIKE 'SOP-2025%'")
rows = cursor.fetchall()
print(f"총 {len(rows)}개 레코드")
for row in rows:
    work_req_no = row[0]
    custom_data = row[1]
    if custom_data:
        try:
            data = json.loads(custom_data) if isinstance(custom_data, str) else custom_data
            print(f"  {work_req_no}:")
            print(f"    - detailed_content: {data.get('detailed_content', 'None')[:50]}...")
            print(f"    - 필드 개수: {len(data)}")
        except:
            print(f"  {work_req_no}: 파싱 실패")
    else:
        print(f"  {work_req_no}: custom_data 없음")

print("\n=== follow_sop_details 테이블 확인 ===")
cursor.execute("SELECT work_req_no, detailed_content FROM follow_sop_details")
rows = cursor.fetchall()
print(f"총 {len(rows)}개 레코드")
for row in rows:
    print(f"  {row[0]}: {row[1][:50] if row[1] else 'None'}...")

print("\n=== follow_sop_cache 테이블 확인 ===")
cursor.execute("SELECT work_req_no FROM follow_sop_cache WHERE work_req_no LIKE 'SOP-2025%'")
rows = cursor.fetchall()
print(f"총 {len(rows)}개 레코드")
for row in rows:
    print(f"  {row[0]}")

conn.close()