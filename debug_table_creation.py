#!/usr/bin/env python3
"""
테이블 생성 문제 디버깅
"""
import psycopg
import configparser

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
    print(f"DSN: {dsn}")
    return dsn

def debug_creation():
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("\n=== 데이터베이스 정보 ===")
    cursor.execute("SELECT current_database(), current_schema(), current_user")
    db, schema, user = cursor.fetchone()
    print(f"Database: {db}")
    print(f"Schema: {schema}")
    print(f"User: {user}")
    
    print("\n=== followsop_cache 테이블 생성 시도 ===")
    
    # 1. 먼저 삭제 시도
    try:
        cursor.execute("DROP TABLE IF EXISTS followsop_cache")
        conn.commit()
        print("기존 테이블 삭제됨 (있었다면)")
    except Exception as e:
        print(f"삭제 실패: {e}")
        conn.rollback()
    
    # 2. 생성 시도
    try:
        cursor.execute('''
            CREATE TABLE followsop_cache (
                id SERIAL PRIMARY KEY,
                work_req_no TEXT UNIQUE,
                custom_data JSONB DEFAULT '{}',
                sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        print("✅ followsop_cache 생성 성공!")
    except Exception as e:
        print(f"❌ 생성 실패: {e}")
        conn.rollback()
        return
    
    # 3. 확인 - 여러 방법으로
    print("\n=== 테이블 존재 확인 (3가지 방법) ===")
    
    # 방법 1: information_schema
    cursor.execute("""
        SELECT table_name, table_schema 
        FROM information_schema.tables 
        WHERE table_name = 'followsop_cache'
    """)
    result = cursor.fetchall()
    print(f"1. information_schema: {result}")
    
    # 방법 2: pg_tables
    cursor.execute("""
        SELECT tablename, schemaname 
        FROM pg_tables 
        WHERE tablename = 'followsop_cache'
    """)
    result = cursor.fetchall()
    print(f"2. pg_tables: {result}")
    
    # 방법 3: 직접 SELECT
    try:
        cursor.execute("SELECT COUNT(*) FROM followsop_cache")
        count = cursor.fetchone()[0]
        print(f"3. Direct SELECT: 테이블 존재함, 행 수: {count}")
    except Exception as e:
        print(f"3. Direct SELECT 실패: {e}")
    
    # 4. 모든 테이블 목록
    print("\n=== 현재 스키마의 모든 테이블 ===")
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = %s 
        AND table_name LIKE %s
        ORDER BY table_name
    """, (schema, '%cache%'))
    tables = cursor.fetchall()
    for t in tables:
        print(f"  - {t[0]}")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    debug_creation()