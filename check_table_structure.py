#!/usr/bin/env python3
"""
테이블 구조 확인 스크립트
"""
import psycopg
import configparser
import re

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        print(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
        return None
    
    user, password, host, port, database = match.groups()
    
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=database,
            user=user,
            password=password
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        print(f"PostgreSQL 연결 실패: {e}")
        return None

def check_table_columns(conn, table_name):
    """테이블 컬럼 확인"""
    cursor = conn.cursor()
    
    print(f"\n{'='*60}")
    print(f"[{table_name}] 테이블 구조")
    print('='*60)
    
    try:
        cursor.execute("""
            SELECT column_name, data_type, character_maximum_length, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name,))
        
        columns = cursor.fetchall()
        
        if not columns:
            print(f"테이블이 존재하지 않거나 컬럼이 없습니다.")
            return
        
        print(f"총 {len(columns)}개 컬럼:")
        print("-" * 60)
        
        for col_name, data_type, max_length, nullable, default in columns:
            length = f"({max_length})" if max_length else ""
            null_str = "NULL" if nullable == 'YES' else "NOT NULL"
            default_str = f" DEFAULT {default}" if default else ""
            print(f"  {col_name:30} {data_type}{length:10} {null_str}{default_str}")
            
    except Exception as e:
        print(f"오류: {e}")

def main():
    conn = get_pg_connection()
    if not conn:
        return
    
    # 모든 cache 테이블 확인
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache'
    ]
    
    for table in tables:
        check_table_columns(conn, table)
    
    conn.close()

if __name__ == "__main__":
    main()