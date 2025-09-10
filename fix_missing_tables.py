#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL 누락된 테이블 생성 및 Boolean 타입 수정
"""
from db_connection import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)

def create_missing_tables():
    """누락된 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. partner_standards_column_config 테이블 생성
        logging.info("Creating partner_standards_column_config table...")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS partner_standards_column_config (
                id SERIAL PRIMARY KEY,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # 2. 다른 누락 가능한 테이블들도 확인
        missing_tables = [
            ('partner_change_requests', '''
                CREATE TABLE IF NOT EXISTS partner_change_requests (
                    id SERIAL PRIMARY KEY,
                    request_number TEXT UNIQUE,
                    business_number TEXT,
                    company_name TEXT,
                    change_type TEXT,
                    change_details TEXT,
                    status TEXT DEFAULT 'requested',
                    requested_by TEXT,
                    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    approved_by TEXT,
                    approved_at TIMESTAMP,
                    is_deleted BOOLEAN DEFAULT FALSE
                )
            '''),
            ('dropdown_codes', '''
                CREATE TABLE IF NOT EXISTS dropdown_codes (
                    id SERIAL PRIMARY KEY,
                    column_key TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT NOT NULL,
                    sort_order INTEGER DEFAULT 0,
                    is_active BOOLEAN DEFAULT TRUE,
                    board_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(column_key, code, board_type)
                )
            '''),
            ('responsible_master', '''
                CREATE TABLE IF NOT EXISTS responsible_master (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT,
                    phone TEXT,
                    department TEXT,
                    position TEXT,
                    is_active BOOLEAN DEFAULT TRUE,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            '''),
            ('pages', '''
                CREATE TABLE IF NOT EXISTS pages (
                    id SERIAL PRIMARY KEY,
                    url TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    content TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        ]
        
        for table_name, create_sql in missing_tables:
            logging.info(f"Creating {table_name} table...")
            cursor.execute(create_sql)
        
        conn.commit()
        logging.info("✅ All missing tables created successfully!")
        
        # 테이블 목록 확인
        cursor.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        tables = cursor.fetchall()
        
        logging.info("\nCurrent tables in PostgreSQL:")
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        logging.error(f"Error creating tables: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def fix_boolean_queries():
    """Boolean 쿼리 수정 필요 항목 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Boolean 컬럼들 확인
        cursor.execute("""
            SELECT table_name, column_name 
            FROM information_schema.columns 
            WHERE data_type = 'boolean' 
            AND table_schema = 'public'
            ORDER BY table_name, column_name
        """)
        
        boolean_columns = cursor.fetchall()
        
        print("\n📊 Boolean 컬럼들 (1 → TRUE로 변경 필요):")
        for table, column in boolean_columns:
            print(f"  {table}.{column}")
            
        print("\n⚠️  app.py에서 수정 필요한 패턴:")
        print("  - WHERE is_active = 1  →  WHERE is_active = TRUE")
        print("  - WHERE is_deleted = 0  →  WHERE is_deleted = FALSE")
        print("  - DEFAULT 1  →  DEFAULT TRUE")
        print("  - DEFAULT 0  →  DEFAULT FALSE")
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("=== PostgreSQL 테이블 수정 스크립트 ===\n")
    
    # 1. 누락된 테이블 생성
    create_missing_tables()
    
    # 2. Boolean 쿼리 수정 필요 항목 확인
    fix_boolean_queries()
    
    print("\n✅ 완료! 이제 Flask 앱을 다시 실행하세요.")