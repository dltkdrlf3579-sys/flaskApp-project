#!/usr/bin/env python3
"""
캐시 테이블에 누락된 sync_date 컬럼 추가
운영 환경에서 sync_date 컬럼이 없을 때 실행

Usage:
    python add_sync_date_columns.py
"""
import psycopg
import configparser

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def add_sync_date_columns():
    """모든 캐시 테이블에 sync_date 컬럼 추가"""
    
    dsn = get_postgres_dsn()
    conn = psycopg.connect(dsn)
    cursor = conn.cursor()
    
    print("캐시 테이블에 sync_date 컬럼 추가 중...")
    
    # 모든 캐시 테이블 목록
    cache_tables = [
        'followsop_cache',
        'follow_sop_cache',
        'fullprocess_cache', 
        'full_process_cache',
        'safety_instructions_cache',
        'accidents_cache',
        'partners_cache',
        'partner_standards_cache',
        'change_requests_cache'
    ]
    
    for table in cache_tables:
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if not cursor.fetchone()[0]:
                print(f"[SKIP] {table}: 테이블 없음")
                continue
            
            # sync_date 컬럼 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = 'sync_date'
                )
            """, (table,))
            
            if cursor.fetchone()[0]:
                print(f"[OK] {table}: sync_date 이미 존재")
            else:
                # sync_date 컬럼 추가
                cursor.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """)
                print(f"[ADDED] {table}: sync_date 컬럼 추가됨")
                
                # 기존 데이터의 sync_date를 created_at으로 업데이트
                cursor.execute(f"""
                    UPDATE {table} 
                    SET sync_date = created_at 
                    WHERE sync_date IS NULL AND created_at IS NOT NULL
                """)
                
        except Exception as e:
            print(f"[ERROR] {table}: {e}")
    
    # synced_at이 있는 경우 sync_date로 복사 (호환성)
    print("\nsynced_at -> sync_date 마이그레이션...")
    for table in cache_tables:
        try:
            cursor.execute("""
                SELECT column_name FROM information_schema.columns 
                WHERE table_name = %s AND column_name IN ('synced_at', 'sync_date')
            """, (table,))
            
            columns = [row[0] for row in cursor.fetchall()]
            
            if 'synced_at' in columns and 'sync_date' in columns:
                # synced_at 데이터를 sync_date로 복사
                cursor.execute(f"""
                    UPDATE {table} 
                    SET sync_date = synced_at 
                    WHERE sync_date IS NULL AND synced_at IS NOT NULL
                """)
                print(f"[MIGRATED] {table}: synced_at -> sync_date")
                
        except Exception as e:
            print(f"[ERROR] {table} migration: {e}")
    
    conn.commit()
    cursor.close()
    conn.close()
    
    print("\n✅ sync_date 컬럼 추가 완료!")

if __name__ == "__main__":
    add_sync_date_columns()