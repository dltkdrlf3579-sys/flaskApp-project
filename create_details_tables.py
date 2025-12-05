#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
details 테이블 생성 스크립트
모든 보드의 상세내용을 저장할 _details 테이블을 생성합니다.
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

def create_details_tables():
    """모든 보드의 _details 테이블 생성"""

    conn = sqlite3.connect('iqa.db')
    cursor = conn.cursor()

    # 각 보드별 details 테이블 생성
    tables = [
        ('accident_details', 'accident_number'),
        ('safety_instruction_details', 'issue_number'),
        ('followsop_details', 'work_req_no'),
        ('fullprocess_details', 'fullprocess_number'),
        ('partner_details', 'business_number'),
        ('change_request_details', 'request_number')
    ]

    for table_name, pk_column in tables:
        try:
            # 테이블이 이미 있는지 확인
            cursor.execute(f"""
                SELECT name FROM sqlite_master
                WHERE type='table' AND name='{table_name}'
            """)

            if cursor.fetchone():
                logging.info(f"테이블 {table_name}이 이미 존재합니다.")
                continue

            # 테이블 생성
            cursor.execute(f"""
                CREATE TABLE {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    {pk_column} TEXT NOT NULL UNIQUE,
                    detailed_content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 인덱스 생성
            cursor.execute(f"""
                CREATE INDEX idx_{table_name}_{pk_column}
                ON {table_name}({pk_column})
            """)

            logging.info(f"✅ 테이블 생성 완료: {table_name}")

        except Exception as e:
            logging.error(f"❌ 테이블 생성 실패 ({table_name}): {e}")

    conn.commit()

    # 생성된 테이블 확인
    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name LIKE '%_details'
        ORDER BY name
    """)

    created_tables = cursor.fetchall()
    print("\n생성된 _details 테이블 목록:")
    for table in created_tables:
        print(f"  - {table[0]}")

    conn.close()
    logging.info("\n모든 details 테이블 생성 완료!")

if __name__ == "__main__":
    create_details_tables()