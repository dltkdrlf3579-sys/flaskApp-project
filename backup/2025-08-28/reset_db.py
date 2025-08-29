#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 테이블 재생성 스크립트
partner_class 컬럼 누락 문제 해결
"""

import sqlite3
import os

# 데이터베이스 경로
DB_PATH = "portal.db"

def reset_partners_cache():
    """partners_cache 테이블 재생성"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # 기존 테이블 삭제
        print("기존 partners_cache 테이블 삭제 중...")
        cursor.execute("DROP TABLE IF EXISTS partners_cache")
        
        # 새 테이블 생성 (올바른 스키마)
        print("새 partners_cache 테이블 생성 중...")
        cursor.execute('''
            CREATE TABLE partners_cache (
                business_number TEXT PRIMARY KEY,
                company_name TEXT NOT NULL,
                partner_class TEXT,
                business_type_major TEXT,
                business_type_minor TEXT,
                hazard_work_flag TEXT,
                representative TEXT,
                address TEXT,
                average_age INTEGER,
                annual_revenue BIGINT,
                transaction_count TEXT,
                permanent_workers INTEGER,
                synced_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        conn.commit()
        print("[SUCCESS] partners_cache 테이블 재생성 완료!")
        
        # 테이블 구조 확인
        cursor.execute("PRAGMA table_info(partners_cache)")
        columns = cursor.fetchall()
        print("\n새 테이블 컬럼 구조:")
        for col in columns:
            print(f"  - {col[1]}: {col[2]}")
            
    except Exception as e:
        print(f"[ERROR] 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 50)
    print("partners_cache 테이블 재생성 스크립트")
    print("=" * 50)
    
    if not os.path.exists(DB_PATH):
        print(f"[WARNING] 데이터베이스 파일 '{DB_PATH}'가 존재하지 않습니다.")
        print("새 데이터베이스를 생성합니다...")
    
    reset_partners_cache()
    print("\n완료! 이제 app.py를 다시 실행하세요.")
