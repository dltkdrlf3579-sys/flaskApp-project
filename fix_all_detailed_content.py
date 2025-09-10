#!/usr/bin/env python3
"""
모든 게시판의 detailed_content 문제 수정
detailed_content를 별도 컬럼이 아닌 custom_data JSONB 내부로 이동
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

def check_and_migrate_detailed_content(conn):
    """detailed_content 컬럼 확인 및 마이그레이션"""
    cursor = conn.cursor()
    
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache'
    ]
    
    for table in tables:
        print(f"\n{'='*60}")
        print(f"[{table}] 처리 중...")
        print('='*60)
        
        try:
            # detailed_content 컬럼이 있는지 확인
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'detailed_content'
            """, (table,))
            
            has_detailed_content = cursor.fetchone() is not None
            
            if has_detailed_content:
                print(f"  [발견] detailed_content 컬럼이 존재합니다.")
                
                # 데이터 마이그레이션 - detailed_content를 custom_data로 이동
                cursor.execute(f"""
                    UPDATE {table}
                    SET custom_data = 
                        CASE 
                            WHEN custom_data IS NULL THEN 
                                jsonb_build_object('detailed_content', detailed_content)
                            ELSE 
                                custom_data || jsonb_build_object('detailed_content', detailed_content)
                        END
                    WHERE detailed_content IS NOT NULL AND detailed_content != ''
                """)
                
                migrated = cursor.rowcount
                print(f"  [마이그레이션] {migrated}개 레코드의 detailed_content를 custom_data로 이동")
                
                # detailed_content 컬럼 삭제
                cursor.execute(f"""
                    ALTER TABLE {table} DROP COLUMN IF EXISTS detailed_content
                """)
                print(f"  [삭제] detailed_content 컬럼 제거 완료")
                
            else:
                print(f"  [확인] detailed_content 컬럼이 없습니다. (정상)")
                
        except Exception as e:
            print(f"  [오류] {e}")

def verify_structure(conn):
    """최종 구조 확인"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("최종 테이블 구조 확인")
    print("="*60)
    
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache'
    ]
    
    for table in tables:
        cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = %s AND column_name IN ('custom_data', 'detailed_content')
            ORDER BY column_name
        """, (table,))
        
        columns = [row[0] for row in cursor.fetchall()]
        
        if 'detailed_content' in columns:
            print(f"[문제] {table}: detailed_content 컬럼이 여전히 존재!")
        elif 'custom_data' in columns:
            print(f"[OK] {table}: custom_data만 존재 (정상)")
        else:
            print(f"[경고] {table}: custom_data 컬럼이 없음")

def main():
    conn = get_pg_connection()
    if not conn:
        return
    
    print("="*60)
    print("detailed_content 마이그레이션 시작")
    print("="*60)
    
    try:
        # 1. detailed_content 확인 및 마이그레이션
        check_and_migrate_detailed_content(conn)
        
        # 2. 최종 확인
        verify_structure(conn)
        
        print("\n[완료] 모든 처리가 완료되었습니다!")
        
    except Exception as e:
        print(f"\n[ERROR] 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()