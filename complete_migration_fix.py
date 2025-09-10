#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""완전한 마이그레이션 수정 - SQLite 구조 그대로 복사"""
import sqlite3
from db_connection import get_db_connection

def recreate_table_from_sqlite(table_name):
    """SQLite 테이블 구조를 그대로 PostgreSQL로 복사"""
    
    # SQLite 연결
    sqlite_conn = sqlite3.connect('portal.db')
    sqlite_cursor = sqlite_conn.cursor()
    
    # PostgreSQL 연결
    pg_conn = get_db_connection()
    pg_cursor = pg_conn.cursor()
    
    print(f"\n=== Recreating {table_name} ===")
    
    # 1. SQLite 구조 가져오기
    sqlite_cursor.execute(f"PRAGMA table_info({table_name})")
    columns = sqlite_cursor.fetchall()
    
    # 2. PostgreSQL 테이블 백업 및 삭제
    pg_cursor.execute(f"DROP TABLE IF EXISTS {table_name}_old")
    try:
        pg_cursor.execute(f"ALTER TABLE {table_name} RENAME TO {table_name}_old")
    except:
        pass  # 테이블이 없을 수도 있음
    
    # 3. 새 테이블 생성 (SQLite 구조 기반)
    create_sql = f"CREATE TABLE {table_name} ("
    col_defs = []
    
    for col in columns:
        col_name = col[1]
        col_type = col[2]
        is_pk = col[5]
        
        # SQLite 타입을 PostgreSQL 타입으로 변환
        if is_pk:
            pg_type = "SERIAL PRIMARY KEY"
        elif "INT" in col_type.upper():
            pg_type = "INTEGER"
        elif "TEXT" in col_type.upper() or "VARCHAR" in col_type.upper():
            pg_type = "TEXT"
        elif "DATE" in col_type.upper():
            if "TIME" in col_type.upper():
                pg_type = "TIMESTAMP"
            else:
                pg_type = "DATE"
        elif "BOOL" in col_type.upper():
            pg_type = "INTEGER"  # Boolean을 INTEGER로
        elif "JSON" in col_type.upper():
            pg_type = "JSONB"
        else:
            pg_type = "TEXT"
        
        # 기본값 처리
        default = col[4]
        if default:
            if "CURRENT" in str(default).upper():
                default = "DEFAULT CURRENT_TIMESTAMP"
            elif default == "0":
                default = "DEFAULT 0"
            elif default == "1":
                default = "DEFAULT 1"
            else:
                default = f"DEFAULT '{default}'"
        else:
            default = ""
        
        col_def = f"{col_name} {pg_type} {default}"
        col_defs.append(col_def.strip())
    
    create_sql += ", ".join(col_defs) + ")"
    
    print(f"Creating table with {len(col_defs)} columns...")
    pg_cursor.execute(create_sql)
    pg_conn.commit()
    
    # 4. 데이터 복사
    sqlite_conn.row_factory = sqlite3.Row
    sqlite_cursor = sqlite_conn.cursor()
    sqlite_cursor.execute(f"SELECT * FROM {table_name}")
    rows = sqlite_cursor.fetchall()
    
    if rows:
        print(f"Copying {len(rows)} rows...")
        for row in rows:
            data = dict(row)
            
            # JSONB 필드 처리
            for key in data:
                if data[key] and key.endswith('_data') or 'json' in key.lower():
                    import json
                    try:
                        if isinstance(data[key], str):
                            data[key] = json.loads(data[key])
                    except:
                        pass
            
            # INSERT
            columns = list(data.keys())
            values = [data[col] for col in columns]
            placeholders = ['%s'] * len(columns)
            
            insert_sql = f"""
                INSERT INTO {table_name} ({','.join(columns)})
                VALUES ({','.join(placeholders)})
                ON CONFLICT DO NOTHING
            """
            
            try:
                pg_cursor.execute(insert_sql, values)
            except Exception as e:
                print(f"  Error: {e}")
        
        pg_conn.commit()
    
    # 5. 결과 확인
    pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
    count = pg_cursor.fetchone()[0]
    print(f"✅ Success! {count} rows in {table_name}")
    
    sqlite_conn.close()
    pg_conn.close()

# 주요 테이블들 재생성
tables_to_fix = [
    'accidents_cache',
    'safety_instructions_cache', 
    'follow_sop',
    'full_process'
]

for table in tables_to_fix:
    try:
        recreate_table_from_sqlite(table)
    except Exception as e:
        print(f"Error with {table}: {e}")

print("\n✅ Migration fix complete!")