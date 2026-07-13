#!/usr/bin/env python3
"""
개발 환경의 정확한 테이블 구조를 SQL로 덤프
운영 환경에서 그대로 실행할 수 있는 CREATE TABLE 문 생성
"""
import psycopg
import configparser

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn')

def dump_table_structure(cursor, table_name):
    """테이블 구조를 CREATE TABLE SQL로 변환"""
    
    # 컬럼 정보 가져오기
    cursor.execute("""
        SELECT 
            column_name,
            data_type,
            character_maximum_length,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_name = %s
        ORDER BY ordinal_position
    """, (table_name,))
    
    columns = cursor.fetchall()
    if not columns:
        return None
    
    # CREATE TABLE 문 생성
    sql = f"CREATE TABLE IF NOT EXISTS {table_name} (\n"
    column_defs = []
    
    for col in columns:
        name, dtype, max_len, nullable, default = col
        
        # 데이터 타입 처리
        if dtype == 'character varying' and max_len:
            type_str = f"VARCHAR({max_len})"
        elif dtype == 'integer' and 'nextval' in str(default):
            type_str = "SERIAL" if name == 'id' else "INTEGER"
        elif dtype == 'timestamp without time zone':
            type_str = "TIMESTAMP"
        else:
            type_str = dtype.upper()
        
        # 컬럼 정의
        col_def = f"    {name} {type_str}"
        
        # PRIMARY KEY
        if name == 'id' and 'SERIAL' in type_str:
            col_def = f"    {name} SERIAL PRIMARY KEY"
        # NOT NULL
        elif nullable == 'NO' and name != 'id':
            col_def += " NOT NULL"
        
        # DEFAULT
        if default and 'nextval' not in str(default):
            if 'CURRENT_TIMESTAMP' in default:
                col_def += " DEFAULT CURRENT_TIMESTAMP"
            elif dtype == 'jsonb':
                col_def += " DEFAULT '{}'"
            elif dtype == 'integer' and default == '0':
                col_def += " DEFAULT 0"
        
        column_defs.append(col_def)
    
    sql += ",\n".join(column_defs)
    sql += "\n);"
    
    # UNIQUE 제약 추가
    cursor.execute("""
        SELECT kcu.column_name
        FROM information_schema.table_constraints tc
        JOIN information_schema.key_column_usage kcu 
            ON tc.constraint_name = kcu.constraint_name
        WHERE tc.table_name = %s 
        AND tc.constraint_type = 'UNIQUE'
    """, (table_name,))
    
    unique_cols = [row[0] for row in cursor.fetchall()]
    for col in unique_cols:
        sql += f"\n-- UNIQUE: {col}"
    
    return sql

def main():
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("-- 개발 환경 테이블 구조 덤프")
    print("-- 운영 환경에서 이 SQL을 그대로 실행하세요\n")
    
    # 중요 테이블 목록
    tables = [
        # 메인 테이블
        'safety_instructions',
        'accidents', 
        'follow_sop',
        'full_process',
        'partners',
        'change_requests',
        'partner_change_requests',
        
        # 캐시 테이블
        'safety_instructions_cache',
        'accidents_cache',
        'followsop_cache',
        'fullprocess_cache',
        'partners_cache',
        'change_requests_cache',
        'partner_standards_cache',
        
        # 컬럼 설정 테이블
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_change_column_config'
    ]
    
    for table in tables:
        sql = dump_table_structure(cursor, table)
        if sql:
            print(f"\n-- {table}")
            print(sql)
        else:
            print(f"\n-- {table}: NOT FOUND")
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    main()