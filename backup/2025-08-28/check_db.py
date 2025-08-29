import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# change_requests 확인
cursor.execute("SELECT request_number, detailed_content, updated_at FROM change_requests WHERE request_number='CR-8'")
result = cursor.fetchone()
if result:
    print(f"Request: {result[0]}")
    print(f"Content: {result[1][:100] if result[1] else 'None'}...")
    print(f"Updated: {result[2]}")
else:
    print("CR-8 not found")

# 첨부파일 확인
cursor.execute("SELECT COUNT(*) FROM change_request_attachments WHERE item_id='CR-8'")
count = cursor.fetchone()[0]
print(f"\nAttachments: {count}")

conn.close()
