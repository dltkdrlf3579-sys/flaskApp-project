#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
운영환경에서 실행할 컬럼 추가 스크립트
"""
from db_connection import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

try:
    # follow_sop 테이블
    cursor.execute('ALTER TABLE follow_sop ADD COLUMN IF NOT EXISTS created_by TEXT')
    cursor.execute('ALTER TABLE follow_sop ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP')
    cursor.execute('ALTER TABLE follow_sop ADD COLUMN IF NOT EXISTS updated_by TEXT')
    print("follow_sop 테이블 컬럼 추가 완료")

    # full_process 테이블
    cursor.execute('ALTER TABLE full_process ADD COLUMN IF NOT EXISTS created_by TEXT')
    cursor.execute('ALTER TABLE full_process ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP')
    cursor.execute('ALTER TABLE full_process ADD COLUMN IF NOT EXISTS updated_by TEXT')
    print("full_process 테이블 컬럼 추가 완료")

    # cache 테이블들
    cursor.execute('ALTER TABLE followsop_cache ADD COLUMN IF NOT EXISTS created_by TEXT')
    cursor.execute('ALTER TABLE fullprocess_cache ADD COLUMN IF NOT EXISTS created_by TEXT')
    print("cache 테이블 컬럼 추가 완료")

    # safety_instructions 테이블
    cursor.execute('ALTER TABLE safety_instructions ADD COLUMN IF NOT EXISTS issuer_department TEXT')
    cursor.execute('ALTER TABLE safety_instructions ADD COLUMN IF NOT EXISTS created_by TEXT')
    cursor.execute('ALTER TABLE safety_instructions ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP')
    cursor.execute('ALTER TABLE safety_instructions ADD COLUMN IF NOT EXISTS updated_by TEXT')
    print("safety_instructions 테이블 컬럼 추가 완료")

    # safety_instructions_cache 테이블
    cursor.execute('ALTER TABLE safety_instructions_cache ADD COLUMN IF NOT EXISTS issuer_department TEXT')
    cursor.execute('ALTER TABLE safety_instructions_cache ADD COLUMN IF NOT EXISTS created_by TEXT')
    print("safety_instructions_cache 테이블 컬럼 추가 완료")

    conn.commit()
    print("\n모든 컬럼 추가 성공!")

except Exception as e:
    print(f"오류 발생: {e}")
    conn.rollback()
finally:
    conn.close()