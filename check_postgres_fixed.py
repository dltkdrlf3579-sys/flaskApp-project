#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 상태 확인 스크립트 (수정된 버전)
각 테이블 체크마다 새로운 연결 사용하여 트랜잭션 문제 방지
"""
import psycopg
import configparser
from datetime import datetime

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def check_table(table_name):
    """개별 테이블 체크 (새 연결 사용)"""
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        exists = cursor.fetchone()[0]
        
        if not exists:
            cursor.close()
            conn.close()
            return 'MISSING', '-', '-'
        
        # 데이터 개수
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        
        # 최신 데이터 시간 (created_at 컬럼이 있는 경우)
        latest_str = 'N/A'
        try:
            cursor.execute(f'SELECT MAX(created_at) FROM {table_name}')
            latest = cursor.fetchone()[0]
            if latest:
                latest_str = latest.strftime('%Y-%m-%d %H:%M:%S')
        except:
            latest_str = 'N/A'
        
        cursor.close()
        conn.close()
        
        return 'OK', count, latest_str
        
    except Exception as e:
        return 'ERROR', f'Error', str(e)[:30]

def check_column_config(table_name):
    """컬럼 설정 테이블 체크 (scoring_config 포함)"""
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = %s
            )
        """, (table_name,))
        exists = cursor.fetchone()[0]
        
        if not exists:
            cursor.close()
            conn.close()
            return 'MISSING', '-', '-'
        
        # 데이터 개수
        cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
        count = cursor.fetchone()[0]
        
        # scoring_config 컬럼 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT FROM information_schema.columns 
                WHERE table_name = %s AND column_name = 'scoring_config'
            )
        """, (table_name,))
        has_scoring = cursor.fetchone()[0]
        scoring_status = 'YES' if has_scoring else 'NO'
        
        cursor.close()
        conn.close()
        
        return 'OK', count, scoring_status
        
    except Exception as e:
        return 'ERROR', 'Error', str(e)[:30]

def check_postgres():
    """PostgreSQL 데이터를 확인하는 함수"""
    
    print(f"\n{'='*70}")
    print(f"PostgreSQL 데이터 확인 - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*70}\n")
    
    # 1. 메인 테이블 확인
    print("=== 메인 테이블 상태 ===")
    main_tables = [
        'safety_instructions',
        'accidents',
        'follow_sop',
        'full_process',
        'change_requests',
        'partner_change_requests',
        'partners'
    ]
    
    print(f"{'Table':<30} {'Status':<8} {'Count':<10} {'Latest Data':<20}")
    print("-" * 70)
    
    for table in main_tables:
        status, count, latest = check_table(table)
        print(f"{table:<30} {status:<8} {str(count):<10} {latest:<20}")
    
    # 2. 캐시 테이블 확인
    print("\n=== 캐시 테이블 상태 ===")
    cache_tables = [
        'safety_instructions_cache',
        'accidents_cache',
        'followsop_cache',  # 실제 사용하는 테이블 (언더스코어 없음)
        'fullprocess_cache',  # 실제 사용하는 테이블 (언더스코어 없음)
        'partners_cache',
        'change_requests_cache',
        'partner_standards_cache'
    ]
    
    print(f"{'Table':<35} {'Status':<8} {'Count':<10} {'Latest Data':<20}")
    print("-" * 70)
    
    for table in cache_tables:
        status, count, latest = check_table(table)
        print(f"{table:<35} {status:<8} {str(count):<10} {latest:<20}")
    
    # 3. 컬럼 설정 테이블 확인
    print("\n=== 컬럼 설정 테이블 상태 ===")
    config_tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'partner_change_column_config'
    ]
    
    print(f"{'Table':<40} {'Status':<8} {'Count':<10} {'Scoring':<10}")
    print("-" * 70)
    
    for table in config_tables:
        status, count, scoring = check_column_config(table)
        print(f"{table:<40} {status:<8} {str(count):<10} {scoring:<10}")
    
    # 4. 전체 테이블 개수
    print(f"\n{'='*70}")
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
        """)
        total_tables = cursor.fetchone()[0]
        print(f"총 테이블 수: {total_tables}개")
        
        # 5. 주요 함수 확인
        print(f"\n=== PostgreSQL 함수 상태 ===")
        functions = ['json_extract', 'datetime']
        for func in functions:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM pg_proc 
                    WHERE proname = %s
                )
            """, (func,))
            exists = cursor.fetchone()[0]
            status = 'YES' if exists else 'NO'
            print(f"{func}: {status}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking summary: {e}")
    
    print(f"\n{'='*70}")
    print("[SUCCESS] PostgreSQL 상태 확인 완료!")
    print(f"{'='*70}\n")

if __name__ == "__main__":
    check_postgres()