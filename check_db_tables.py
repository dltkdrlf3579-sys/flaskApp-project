#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
데이터베이스 테이블 상태 확인
"""
import psycopg
import sys

def check_database_tables():
    dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
    
    try:
        conn = psycopg.connect(dsn)
        cur = conn.cursor()
        
        # 현재 테이블 조회
        cur.execute("""
            SELECT table_name, table_type 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            ORDER BY table_name
        """)
        
        tables = cur.fetchall()
        
        print("=== Current Database Tables ===")
        if tables:
            for table_name, table_type in tables:
                print(f"  - {table_name} ({table_type})")
        else:
            print("  No tables found in public schema")
        
        # 테이블별 행 수 확인 (존재하는 테이블만)
        print("\n=== Table Row Counts ===")
        for table_name, _ in tables:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                print(f"  - {table_name}: {count:,} rows")
            except Exception as e:
                print(f"  - {table_name}: Error - {e}")
        
        conn.close()
        return [table[0] for table in tables]
        
    except Exception as e:
        print(f"Database connection error: {e}")
        return []

if __name__ == "__main__":
    tables = check_database_tables()
    print(f"\nTotal tables found: {len(tables)}")