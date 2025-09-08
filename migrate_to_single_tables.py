#!/usr/bin/env python3
"""
데이터베이스 단순화 마이그레이션
cache 테이블과 일반 테이블을 하나로 통합
"""
import sqlite3
import json
from datetime import datetime

def migrate_database():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    print("데이터베이스 단순화 마이그레이션 시작...")
    
    try:
        # 1. 사고 테이블 통합
        print("사고 데이터 통합 중...")
        
        # accidents 테이블에 data_source 컬럼 추가
        cursor.execute("""
            ALTER TABLE accidents_cache 
            ADD COLUMN data_source TEXT DEFAULT 'external'
        """)
        
        cursor.execute("""
            ALTER TABLE accidents_cache 
            ADD COLUMN sync_date DATETIME DEFAULT CURRENT_TIMESTAMP
        """)
        
        # accidents_cache를 accidents로 이름 변경
        cursor.execute("DROP TABLE IF EXISTS accidents")
        cursor.execute("ALTER TABLE accidents_cache RENAME TO accidents")
        
        print("사고 테이블 통합 완료")
        
        # 2. 환경안전지시서 통합
        print("환경안전지시서 데이터 통합 중...")
        
        # safety_instructions_cache에 data_source 추가
        cursor.execute("""
            ALTER TABLE safety_instructions_cache 
            ADD COLUMN data_source TEXT DEFAULT 'external'
        """)
        
        cursor.execute("""
            ALTER TABLE safety_instructions_cache 
            ADD COLUMN sync_date DATETIME DEFAULT CURRENT_TIMESTAMP
        """)
        
        # 기존 safety_instructions 수동 데이터가 있다면 cache로 이동
        cursor.execute("SELECT COUNT(*) FROM safety_instructions")
        manual_count = cursor.fetchone()[0]
        
        if manual_count > 0:
            print(f"수동 입력 데이터 {manual_count}개 이동 중...")
            cursor.execute("""
                INSERT INTO safety_instructions_cache 
                SELECT *, 'manual' as data_source, CURRENT_TIMESTAMP as sync_date 
                FROM safety_instructions
            """)
        
        # 기존 테이블 삭제 후 이름 변경
        cursor.execute("DROP TABLE IF EXISTS safety_instructions")
        cursor.execute("ALTER TABLE safety_instructions_cache RENAME TO safety_instructions")
        
        print("환경안전지시서 테이블 통합 완료")
        
        # 3. 협력사 테이블 통합
        print("협력사 데이터 통합 중...")
        
        cursor.execute("""
            ALTER TABLE partners_cache 
            ADD COLUMN data_source TEXT DEFAULT 'external'
        """)
        
        cursor.execute("""
            ALTER TABLE partners_cache 
            ADD COLUMN sync_date DATETIME DEFAULT CURRENT_TIMESTAMP
        """)
        
        # 기존 partners 수동 데이터 이동
        cursor.execute("SELECT COUNT(*) FROM partners")
        manual_partners = cursor.fetchone()[0]
        
        if manual_partners > 0:
            print(f"수동 협력사 데이터 {manual_partners}개 이동 중...")
            cursor.execute("""
                INSERT INTO partners_cache 
                SELECT *, 'manual' as data_source, CURRENT_TIMESTAMP as sync_date 
                FROM partners
            """)
        
        cursor.execute("DROP TABLE IF EXISTS partners")
        cursor.execute("ALTER TABLE partners_cache RENAME TO partners")
        
        print("협력사 테이블 통합 완료")
        
        # 4. 모든 데이터를 활성화 (is_deleted = 0)
        print("모든 데이터 활성화 중...")
        cursor.execute("UPDATE accidents SET is_deleted = 0 WHERE is_deleted IS NULL")
        cursor.execute("UPDATE safety_instructions SET is_deleted = 0 WHERE is_deleted IS NULL")
        cursor.execute("UPDATE partners SET is_deleted = 0 WHERE is_deleted IS NULL")
        
        conn.commit()
        print("마이그레이션 완료!")
        
        # 결과 확인
        print("\n마이그레이션 결과:")
        cursor.execute("SELECT COUNT(*), data_source FROM accidents GROUP BY data_source")
        for count, source in cursor.fetchall():
            print(f"  - 사고: {count}개 ({source})")
            
        cursor.execute("SELECT COUNT(*), data_source FROM safety_instructions GROUP BY data_source")
        for count, source in cursor.fetchall():
            print(f"  - 지시서: {count}개 ({source})")
            
        cursor.execute("SELECT COUNT(*), data_source FROM partners GROUP BY data_source")
        for count, source in cursor.fetchall():
            print(f"  - 협력사: {count}개 ({source})")
        
    except Exception as e:
        print(f"마이그레이션 실패: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_database()