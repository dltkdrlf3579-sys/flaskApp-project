import json
from db_connection import get_db_connection

def main():
    sample = {
        "company_name": "샘플 협력사",
        "business_number": "123-45-67890",
        "work_type": "점검",
        "inspector_name": "홍길동",
        "request_date": "2025-09-22",
        "worker_count": "5",
        "work_duration": "4시간",
        "work_location": "서울 공장",
        "attachments": [
            {"file_name": "sample.pdf", "description": "테스트 첨부"}
        ]
    }

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT work_req_no FROM follow_sop ORDER BY work_req_no LIMIT 5")
    rows = [r[0] if not isinstance(r, dict) else r['work_req_no'] for r in cur.fetchall()]

    payload = json.dumps(sample, ensure_ascii=False)
    for work_req_no in rows:
        cur.execute(
            "UPDATE follow_sop SET custom_data = %s WHERE work_req_no = %s",
            (payload, work_req_no),
        )

    conn.commit()
    conn.close()
    print(f"Updated {len(rows)} rows with sample data")

if __name__ == "__main__":
    main()
