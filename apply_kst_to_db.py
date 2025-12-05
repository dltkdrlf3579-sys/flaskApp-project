#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스의 모든 테이블에 한국 시간대 적용
"""

import sqlite3
import pytz
from datetime import datetime

DB_PATH = 'portal.db'
KST = pytz.timezone('Asia/Seoul')

def apply_kst_to_database():
    """데이터베이스에 한국 시간대 적용"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # SQLite에서 한국 시간을 반환하는 사용자 정의 함수 생성
    def get_kst_now():
        return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
    
    # 함수 등록
    conn.create_function('KST_NOW', 0, get_kst_now)
    
    # partner_change_requests 테이블 업데이트
    try:
        # 기존 created_at, updated_at 컬럼을 한국 시간으로 변환
        cursor.execute("""
            UPDATE partner_change_requests 
            SET created_at = datetime(created_at, '+9 hours'),
                updated_at = datetime(updated_at, '+9 hours')
            WHERE created_at NOT LIKE '%+%'
        """)
        print(f"partner_change_requests 테이블 시간대 업데이트 완료: {cursor.rowcount}건")
    except Exception as e:
        print(f"partner_change_requests 업데이트 중 오류: {e}")
    
    # safety_instructions 테이블 업데이트
    try:
        cursor.execute("""
            UPDATE safety_instructions 
            SET created_at = datetime(created_at, '+9 hours'),
                updated_at = datetime(updated_at, '+9 hours')
            WHERE created_at NOT LIKE '%+%'
        """)
        print(f"safety_instructions 테이블 시간대 업데이트 완료: {cursor.rowcount}건")
    except Exception as e:
        print(f"safety_instructions 업데이트 중 오류: {e}")
    
    # accidents_cache 테이블 업데이트
    try:
        cursor.execute("""
            UPDATE accidents_cache 
            SET created_at = datetime(created_at, '+9 hours'),
                updated_at = datetime(updated_at, '+9 hours')
            WHERE created_at NOT LIKE '%+%' AND created_at IS NOT NULL
        """)
        print(f"accidents_cache 테이블 시간대 업데이트 완료: {cursor.rowcount}건")
    except Exception as e:
        print(f"accidents_cache 업데이트 중 오류: {e}")
    
    conn.commit()
    conn.close()
    print("\n모든 테이블의 시간대를 한국 시간(KST)으로 업데이트했습니다.")

if __name__ == '__main__':
    apply_kst_to_database()