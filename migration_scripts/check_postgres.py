#!/usr/bin/env python3
"""
PostgreSQL 데이터베이스 상태 확인 스크립트
모든 테이블과 데이터 현황을 체크

Usage:
    python check_postgres.py
"""
import psycopg
import configparser
from datetime import datetime

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def check_postgres():
    """PostgreSQL 데이터를 확인하는 함수"""
    
    try:
        # PostgreSQL 연결
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
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
        
        main_summary = []
        for table in main_tables:
            try:
                # 테이블 존재 확인
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table,))
                exists = cursor.fetchone()[0]
                
                if exists:
                    # 데이터 개수
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    
                    # 최신 데이터 시간
                    try:
                        cursor.execute(f'SELECT MAX(created_at) FROM {table}')
                        latest = cursor.fetchone()[0]
                        latest_str = latest.strftime('%Y-%m-%d %H:%M:%S') if latest else 'N/A'
                    except:
                        latest_str = 'N/A'
                    
                    main_summary.append([table, 'OK', count, latest_str])
                else:
                    main_summary.append([table, 'MISSING', '-', '-'])
            except Exception as e:
                main_summary.append([table, 'ERROR', f'Error: {str(e)[:20]}', '-'])
        
        # 메인 테이블 출력
        print(f"{'Table':<30} {'Status':<8} {'Count':<10} {'Latest Data':<20}")
        print("-" * 70)
        for row in main_summary:
            print(f"{row[0]:<30} {row[1]:<8} {str(row[2]):<10} {row[3]:<20}")
        
        # 2. 캐시 테이블 확인
        print("\n=== 캐시 테이블 상태 ===")
        cache_tables = [
            'safety_instructions_cache',
            'accidents_cache',
            'followsop_cache',  # 언더스코어 없음!
            'fullprocess_cache',  # 언더스코어 없음!
            'follow_sop_cache',  # 둘 다 체크
            'full_process_cache',  # 둘 다 체크
            'partners_cache',
            'change_requests_cache',
            'partner_standards_cache'
        ]
        
        cache_summary = []
        for table in cache_tables:
            try:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table,))
                exists = cursor.fetchone()[0]
                
                if exists:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    
                    try:
                        cursor.execute(f'SELECT MAX(created_at) FROM {table}')
                        latest = cursor.fetchone()[0]
                        latest_str = latest.strftime('%Y-%m-%d %H:%M:%S') if latest else 'N/A'
                    except:
                        latest_str = 'N/A'
                    
                    cache_summary.append([table, 'OK', count, latest_str])
                else:
                    cache_summary.append([table, 'MISSING', '-', '-'])
            except Exception as e:
                cache_summary.append([table, 'ERROR', f'Error', '-'])
        
        print(f"{'Table':<35} {'Status':<8} {'Count':<10} {'Latest Data':<20}")
        print("-" * 70)
        for row in cache_summary:
            print(f"{row[0]:<35} {row[1]:<8} {str(row[2]):<10} {row[3]:<20}")
        
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
        
        config_summary = []
        for table in config_tables:
            try:
                cursor.execute("""
                    SELECT EXISTS (
                        SELECT FROM information_schema.tables 
                        WHERE table_name = %s
                    )
                """, (table,))
                exists = cursor.fetchone()[0]
                
                if exists:
                    cursor.execute(f'SELECT COUNT(*) FROM {table}')
                    count = cursor.fetchone()[0]
                    
                    # scoring_config 컬럼 확인
                    cursor.execute("""
                        SELECT EXISTS (
                            SELECT FROM information_schema.columns 
                            WHERE table_name = %s AND column_name = 'scoring_config'
                        )
                    """, (table,))
                    has_scoring = cursor.fetchone()[0]
                    scoring_status = '✅' if has_scoring else '❌'
                    
                    config_summary.append([table, '✅', count, scoring_status])
                else:
                    config_summary.append([table, '❌', '-', '-'])
            except Exception as e:
                config_summary.append([table, '⚠️', 'Error', '-'])
        
        print(f"{'Table':<40} {'Status':<8} {'Count':<10} {'Scoring':<10}")
        print("-" * 70)
        for row in config_summary:
            print(f"{row[0]:<40} {row[1]:<8} {str(row[2]):<10} {row[3]:<10}")
        
        # 4. 전체 테이블 개수
        print(f"\n{'='*70}")
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
            status = '✅' if exists else '❌'
            print(f"{func}: {status}")
        
        # 6. 최근 등록된 데이터 샘플 (있으면)
        print(f"\n{'='*70}")
        print("최근 등록된 데이터 (각 테이블별 최신 1건)")
        print(f"{'='*70}\n")
        
        sample_tables = ['safety_instructions_cache', 'accidents_cache', 'partner_change_requests']
        for table in sample_tables:
            try:
                cursor.execute(f"""
                    SELECT * FROM {table}
                    ORDER BY created_at DESC
                    LIMIT 1
                """)
                
                row = cursor.fetchone()
                if row:
                    columns = [desc[0] for desc in cursor.description]
                    print(f"[{table}]")
                    # 주요 컬럼만 표시 (처음 5개)
                    for col, val in list(zip(columns, row))[:5]:
                        # 긴 텍스트는 축약
                        if isinstance(val, str) and len(str(val)) > 50:
                            val = str(val)[:50] + '...'
                        print(f"  {col:20} : {val}")
                    print()
            except:
                pass
        
        cursor.close()
        conn.close()
        
        print(f"{'='*70}")
        print("✅ PostgreSQL 상태 확인 완료!")
        print(f"{'='*70}\n")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print("\nPostgreSQL 연결 실패. 다음을 확인하세요:")
        print("1. PostgreSQL 서버가 실행 중인지")
        print("2. config.ini의 postgres_dsn이 올바른지")
        print("3. 데이터베이스와 사용자가 존재하는지")

if __name__ == "__main__":
    check_postgres()