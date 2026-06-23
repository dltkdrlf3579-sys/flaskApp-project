"""
메인 테이블과 캐시 테이블의 컬럼을 동기화하는 스크립트
캐시 테이블의 컬럼을 메인 테이블에 추가하거나, 그 반대로 처리
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db_connection import get_db_connection
import logging

logging.basicConfig(level=logging.INFO)

def get_columns(conn, table_name):
    """테이블의 컬럼 목록 가져오기"""
    cursor = conn.cursor()
    
    if hasattr(conn, 'is_postgres') and conn.is_postgres:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (table_name.lower(),))
    else:
        cursor.execute(f"PRAGMA table_info({table_name})")
    
    columns = {}
    for row in cursor.fetchall():
        if hasattr(conn, 'is_postgres') and conn.is_postgres:
            col_name = row[0]
            col_type = row[1]
            nullable = row[2] == 'YES'
        else:
            col_name = row[1]
            col_type = row[2]
            nullable = row[3] == 0
        
        columns[col_name] = {
            'type': col_type,
            'nullable': nullable
        }
    
    return columns

def sync_table_columns(table_main, table_cache):
    """메인 테이블과 캐시 테이블의 컬럼 동기화"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 1. 각 테이블의 컬럼 가져오기
        main_columns = get_columns(conn, table_main)
        cache_columns = get_columns(conn, table_cache)
        
        print(f"\n=== {table_main} vs {table_cache} ===")
        print(f"메인 테이블 컬럼: {list(main_columns.keys())}")
        print(f"캐시 테이블 컬럼: {list(cache_columns.keys())}")
        
        # 2. 캐시에만 있는 컬럼을 메인에 추가
        cache_only = set(cache_columns.keys()) - set(main_columns.keys())
        if cache_only:
            print(f"\n캐시에만 있는 컬럼 (메인에 추가할 컬럼): {cache_only}")
            for col in cache_only:
                col_info = cache_columns[col]
                
                # PostgreSQL 타입 매핑
                if hasattr(conn, 'is_postgres') and conn.is_postgres:
                    if 'character' in col_info['type'] or 'text' in col_info['type']:
                        col_type = 'TEXT'
                    elif 'integer' in col_info['type']:
                        col_type = 'INTEGER'
                    elif 'timestamp' in col_info['type']:
                        col_type = 'TIMESTAMP'
                    elif 'json' in col_info['type']:
                        col_type = 'JSONB'
                    else:
                        col_type = 'TEXT'
                else:
                    col_type = col_info['type']
                
                try:
                    sql = f"ALTER TABLE {table_main} ADD COLUMN {col} {col_type}"
                    print(f"실행: {sql}")
                    cursor.execute(sql)
                    conn.commit()
                    print(f"✅ {col} 컬럼을 {table_main}에 추가했습니다")
                except Exception as e:
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"⚠️ {col} 컬럼이 이미 존재합니다")
                    else:
                        print(f"❌ {col} 추가 실패: {e}")
                    conn.rollback()
        
        # 3. 메인에만 있는 컬럼을 캐시에 추가
        main_only = set(main_columns.keys()) - set(cache_columns.keys())
        if main_only:
            print(f"\n메인에만 있는 컬럼 (캐시에 추가할 컬럼): {main_only}")
            for col in main_only:
                col_info = main_columns[col]
                
                # PostgreSQL 타입 매핑
                if hasattr(conn, 'is_postgres') and conn.is_postgres:
                    if 'character' in col_info['type'] or 'text' in col_info['type']:
                        col_type = 'TEXT'
                    elif 'integer' in col_info['type']:
                        col_type = 'INTEGER'
                    elif 'timestamp' in col_info['type']:
                        col_type = 'TIMESTAMP'
                    elif 'json' in col_info['type']:
                        col_type = 'JSONB'
                    else:
                        col_type = 'TEXT'
                else:
                    col_type = col_info['type']
                
                try:
                    sql = f"ALTER TABLE {table_cache} ADD COLUMN {col} {col_type}"
                    print(f"실행: {sql}")
                    cursor.execute(sql)
                    conn.commit()
                    print(f"✅ {col} 컬럼을 {table_cache}에 추가했습니다")
                except Exception as e:
                    if 'already exists' in str(e).lower() or 'duplicate' in str(e).lower():
                        print(f"⚠️ {col} 컬럼이 이미 존재합니다")
                    else:
                        print(f"❌ {col} 추가 실패: {e}")
                    conn.rollback()
        
        if not cache_only and not main_only:
            print("✅ 테이블 구조가 이미 동일합니다!")
        
        return True
        
    except Exception as e:
        print(f"❌ 오류 발생: {e}")
        return False
    finally:
        conn.close()

def copy_data_from_cache_to_main(table_main, table_cache):
    """캐시 테이블의 데이터를 메인 테이블로 복사 (중복 제외)"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 공통 컬럼 찾기
        main_columns = get_columns(conn, table_main)
        cache_columns = get_columns(conn, table_cache)
        common_columns = list(set(main_columns.keys()) & set(cache_columns.keys()))
        
        if not common_columns:
            print(f"❌ 공통 컬럼이 없습니다")
            return False
        
        # Primary key 찾기 (첫 번째 컬럼으로 가정)
        pk_column = None
        if 'work_req_no' in common_columns:
            pk_column = 'work_req_no'
        elif 'fullprocess_number' in common_columns:
            pk_column = 'fullprocess_number'
        elif 'issue_number' in common_columns:
            pk_column = 'issue_number'
        elif 'id' in common_columns:
            pk_column = 'id'
        
        if pk_column:
            # 중복 제외하고 복사
            columns_str = ', '.join(common_columns)
            
            sql = f"""
                INSERT INTO {table_main} ({columns_str})
                SELECT {columns_str}
                FROM {table_cache}
                WHERE {pk_column} NOT IN (
                    SELECT {pk_column} FROM {table_main}
                    WHERE {pk_column} IS NOT NULL
                )
            """
            
            print(f"\n데이터 복사 중: {table_cache} → {table_main}")
            cursor.execute(sql)
            copied = cursor.rowcount
            conn.commit()
            print(f"✅ {copied}개 레코드를 복사했습니다")
        else:
            print(f"⚠️ Primary key를 찾을 수 없어 수동 복사가 필요합니다")
        
        return True
        
    except Exception as e:
        print(f"❌ 데이터 복사 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("테이블 구조 동기화 스크립트")
    print("=" * 60)
    
    # 동기화할 테이블 쌍
    table_pairs = [
        ('follow_sop', 'follow_sop_cache'),
        ('full_process', 'full_process_cache'),
        ('safety_instructions', 'safety_instructions_cache')
    ]
    
    for main, cache in table_pairs:
        # 1. 컬럼 구조 동기화
        sync_table_columns(main, cache)
        
        # 2. 데이터 복사 옵션
        print(f"\n{cache}의 데이터를 {main}으로 복사하시겠습니까? (y/n): ", end='')
        answer = input().strip().lower()
        if answer == 'y':
            copy_data_from_cache_to_main(main, cache)
    
    print("\n" + "=" * 60)
    print("완료!")
    print("=" * 60)