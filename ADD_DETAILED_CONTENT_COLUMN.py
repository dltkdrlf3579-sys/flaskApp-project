#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
partner_details 테이블에 detailed_content 컬럼 추가
"""

import psycopg
from db_connection import get_db_connection

def add_detailed_content_column():
    conn = get_db_connection()
    cur = conn.cursor()
    
    try:
        # detailed_content 컬럼이 이미 있는지 확인
        cur.execute("""
            SELECT COUNT(*) 
            FROM information_schema.columns 
            WHERE table_name = 'partner_details' 
            AND column_name = 'detailed_content'
        """)
        
        if cur.fetchone()[0] > 0:
            print("[OK] detailed_content column already exists.")
        else:
            # detailed_content 컬럼 추가
            print("[INFO] Adding detailed_content column to partner_details table...")
            cur.execute("""
                ALTER TABLE partner_details 
                ADD COLUMN detailed_content TEXT
            """)
            
            # 기존 detail_content 데이터를 detailed_content로 복사
            print("[INFO] Copying data from detail_content to detailed_content...")
            cur.execute("""
                UPDATE partner_details 
                SET detailed_content = detail_content
                WHERE detail_content IS NOT NULL
            """)
            
            conn.commit()
            print("[OK] detailed_content column added successfully!")
            
            # 결과 확인
            cur.execute("""
                SELECT COUNT(*) 
                FROM partner_details 
                WHERE detailed_content IS NOT NULL
            """)
            count = cur.fetchone()[0]
            print(f"[INFO] {count} records copied to detailed_content.")
            
    except Exception as e:
        print(f"[ERROR] {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    add_detailed_content_column()