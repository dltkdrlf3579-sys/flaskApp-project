#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL 누락된 모든 테이블 생성
SQLite 스키마를 PostgreSQL로 완벽 복제
"""
from db_connection import get_db_connection
import sqlite3
import logging

logging.basicConfig(level=logging.INFO)

def create_all_missing_tables():
    """모든 누락된 테이블 생성"""
    
    pg_conn = get_db_connection()
    pg_cursor = pg_conn.cursor()
    
    # 중요한 누락 테이블들 생성
    tables_sql = [
        # section_config (섹션 설정 - 매우 중요!)
        """CREATE TABLE IF NOT EXISTS section_config (
            id SERIAL PRIMARY KEY,
            board_type TEXT NOT NULL,
            section_key TEXT NOT NULL,
            section_name TEXT NOT NULL,
            section_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            is_deleted BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(board_type, section_key)
        )""",
        
        # follow_sop_sections
        """CREATE TABLE IF NOT EXISTS follow_sop_sections (
            section_key TEXT PRIMARY KEY,
            section_name TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )""",
        
        # full_process_sections  
        """CREATE TABLE IF NOT EXISTS full_process_sections (
            section_key TEXT PRIMARY KEY,
            section_name TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE
        )""",
        
        # follow_sop_column_config
        """CREATE TABLE IF NOT EXISTS follow_sop_column_config (
            id SERIAL PRIMARY KEY,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT DEFAULT 'text',
            column_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            dropdown_options TEXT,
            tab TEXT,
            column_span INTEGER DEFAULT 1,
            linked_columns TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # full_process_column_config
        """CREATE TABLE IF NOT EXISTS full_process_column_config (
            id SERIAL PRIMARY KEY,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT DEFAULT 'text',
            column_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            dropdown_options TEXT,
            tab TEXT,
            column_span INTEGER DEFAULT 1,
            linked_columns TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # safety_instruction_column_config
        """CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
            id SERIAL PRIMARY KEY,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT DEFAULT 'text',
            column_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            dropdown_options TEXT,
            tab TEXT,
            column_span INTEGER DEFAULT 1,
            linked_columns TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # change_request_column_config
        """CREATE TABLE IF NOT EXISTS change_request_column_config (
            id SERIAL PRIMARY KEY,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT DEFAULT 'text',
            column_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            dropdown_options TEXT,
            tab TEXT,
            column_span INTEGER DEFAULT 1,
            linked_columns TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""",
        
        # dropdown_option_codes_v2 (중요!)
        """CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
            id SERIAL PRIMARY KEY,
            column_key TEXT NOT NULL,
            code TEXT NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT TRUE,
            board_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(column_key, code, board_type)
        )""",
        
        # master_sync_state
        """CREATE TABLE IF NOT EXISTS master_sync_state (
            id SERIAL PRIMARY KEY CHECK (id=1),
            first_sync_done BOOLEAN DEFAULT FALSE,
            sync_date TIMESTAMP
        )""",
        
        # sync_state
        """CREATE TABLE IF NOT EXISTS sync_state (
            name TEXT PRIMARY KEY,
            first_sync_done BOOLEAN DEFAULT FALSE,
            first_sync_at TIMESTAMP
        )"""
    ]
    
    # 테이블 생성 실행
    for i, sql in enumerate(tables_sql, 1):
        try:
            pg_cursor.execute(sql)
            logging.info(f"Table {i}/{len(tables_sql)} created")
        except Exception as e:
            logging.error(f"Failed to create table {i}: {e}")
    
    pg_conn.commit()
    
    # 생성된 테이블 확인
    pg_cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public'
    """)
    count = pg_cursor.fetchone()[0]
    
    logging.info(f"\n✅ PostgreSQL 총 {count}개 테이블")
    
    pg_conn.close()
    return count

def copy_section_config_data():
    """section_config 데이터 복사"""
    sqlite_conn = sqlite3.connect('portal.db')
    sqlite_conn.row_factory = sqlite3.Row
    pg_conn = get_db_connection()
    pg_cursor = pg_conn.cursor()
    
    # section_config 데이터 복사
    cursor = sqlite_conn.cursor()
    cursor.execute("SELECT * FROM section_config")
    sections = cursor.fetchall()
    
    for section in sections:
        try:
            data = dict(section)
            # Boolean 값 변환
            if 'is_active' in data:
                data['is_active'] = bool(data['is_active'])
            if 'is_deleted' in data:
                data['is_deleted'] = bool(data['is_deleted'])
            
            from db.upsert import safe_upsert
            safe_upsert(pg_conn, 'section_config', data, ['board_type', 'section_key'])
        except Exception as e:
            print(f"Section config error: {e}")
    
    pg_conn.commit()
    
    # 컬럼 설정들도 복사
    column_tables = [
        'accident_column_config',
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'partner_standards_column_config'
    ]
    
    for table in column_tables:
        try:
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            for row in rows:
                data = dict(row)
                if 'is_active' in data:
                    data['is_active'] = bool(data['is_active'])
                
                safe_upsert(pg_conn, table, data, ['column_key'])
            
            print(f"{table}: {len(rows)} rows copied")
        except Exception as e:
            print(f"{table} error: {e}")
    
    pg_conn.commit()
    sqlite_conn.close()
    pg_conn.close()

if __name__ == "__main__":
    print("=== 모든 누락 테이블 생성 ===\n")
    
    # 1. 테이블 생성
    count = create_all_missing_tables()
    
    # 2. 데이터 복사
    print("\n=== 설정 데이터 복사 ===")
    copy_section_config_data()
    
    print("\n✅ 완료! Flask 앱을 다시 실행하세요.")