import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 테이블 목록 확인
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%attachment%'")
tables = cursor.fetchall()
print("Attachment tables:", tables)

# change_request_attachments 확인
try:
    cursor.execute("SELECT * FROM change_request_attachments WHERE item_id='CR-8'")
    attachments = cursor.fetchall()
    print(f"\nchange_request_attachments for CR-8: {len(attachments)} items")
    for att in attachments:
        print(f"  - {att}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
