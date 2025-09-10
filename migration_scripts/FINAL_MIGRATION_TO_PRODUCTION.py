#!/usr/bin/env python3
"""
운영 환경 PostgreSQL 마이그레이션 최종 통합 스크립트
모든 필요한 단계를 올바른 순서로 실행

실행 방법:
    python FINAL_MIGRATION_TO_PRODUCTION.py
    
중요: 운영 환경에서만 실행하세요!
"""
import subprocess
import sys
import os
import psycopg
import configparser
from datetime import datetime

def get_postgres_dsn():
    """config.ini에서 PostgreSQL DSN 읽기"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def check_connection():
    """PostgreSQL 연결 확인"""
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        cursor.execute("SELECT current_database(), current_user, version()")
        db, user, version = cursor.fetchone()
        print(f"Connected to: {db}")
        print(f"User: {user}")
        print(f"PostgreSQL: {version[:30]}...")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        print(f"Connection failed: {e}")
        return False

def run_script(script_name, description, critical=True):
    """스크립트 실행"""
    print(f"\n{'='*70}")
    print(f"{description}")
    print(f"Script: {script_name}")
    print(f"{'='*70}")
    
    if not os.path.exists(script_name):
        print(f"WARNING: {script_name} not found")
        if critical:
            return False
        else:
            print("Skipping non-critical script...")
            return True
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            encoding='utf-8',
            errors='replace'  # 인코딩 에러 방지
        )
        
        # 출력 표시 (인코딩 문제 방지)
        output = result.stdout.replace('\u2705', '[OK]').replace('\u274c', '[ERROR]').replace('\u26a0\ufe0f', '[WARN]')
        print(output)
        
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"Script returned code: {result.returncode}")
            if critical:
                response = input("Critical script failed. Continue? (y/n): ")
                return response.lower() == 'y'
        
        return True
        
    except Exception as e:
        print(f"ERROR running {script_name}: {e}")
        if critical:
            response = input("Continue? (y/n): ")
            return response.lower() == 'y'
        return True

def main():
    print("="*70)
    print("POSTGRESQL MIGRATION TO PRODUCTION")
    print("="*70)
    print(f"Timestamp: {datetime.now()}")
    print("\nThis script will:")
    print("1. Install PostgreSQL compatibility functions")
    print("2. Create all required tables")
    print("3. Fix table structures and columns")
    print("4. Normalize table names")
    print("5. Fix query compatibility issues")
    print("6. Verify the migration")
    
    print("\n" + "="*70)
    print("IMPORTANT: Make sure you're running this on the PRODUCTION server!")
    print("="*70)
    
    response = input("\nAre you on the PRODUCTION server? (yes/no): ")
    if response.lower() != 'yes':
        print("Aborted. Only run this on production.")
        return
    
    # 연결 확인
    print("\n" + "="*70)
    print("CHECKING DATABASE CONNECTION")
    print("="*70)
    if not check_connection():
        print("Cannot connect to PostgreSQL. Check your config.ini")
        return
    
    # Phase 1: PostgreSQL 함수 설치
    if not run_script(
        'setup_pg_functions.py',
        'PHASE 1: Installing PostgreSQL Compatibility Functions',
        critical=True
    ):
        print("Failed to install functions. Aborting.")
        return
    
    # Phase 2: 메인 테이블 생성
    if not run_script(
        'create_all_postgresql_tables.py',
        'PHASE 2: Creating Main Tables',
        critical=True
    ):
        print("Failed to create main tables. Aborting.")
        return
    
    # Phase 3: 캐시 및 config 테이블 생성
    if not run_script(
        'fix_missing_tables_properly.py',
        'PHASE 3: Creating Cache and Config Tables',
        critical=True
    ):
        print("Failed to create cache/config tables. Aborting.")
        return
    
    # Phase 4: sync_date 컬럼 추가
    if not run_script(
        'add_sync_date_columns.py',
        'PHASE 4: Adding sync_date Columns',
        critical=False  # 이미 있을 수 있음
    ):
        pass
    
    # Phase 5: 테이블 정규화 (follow_sop, full_process)
    normalize_script = 'migrations/normalize_follow_full_tables_fixed.py'
    if os.path.exists(normalize_script):
        if not run_script(
            normalize_script,
            'PHASE 5: Normalizing Table Names',
            critical=True
        ):
            print("Failed to normalize tables. Continuing...")
    else:
        print("PHASE 5: Normalize script not found, skipping...")
    
    # Phase 6: COALESCE 타입 에러 수정
    if not run_script(
        'fix_coalesce_type_error.py',
        'PHASE 6: Fixing COALESCE Type Errors',
        critical=True
    ):
        print("Failed to fix COALESCE errors. Check manually.")
    
    # Phase 7: 최종 검증
    print("\n" + "="*70)
    print("PHASE 7: FINAL VERIFICATION")
    print("="*70)
    
    run_script(
        'check_postgres.py',
        'Checking Database Status',
        critical=False
    )
    
    # 요약
    print("\n" + "="*70)
    print("MIGRATION SUMMARY")
    print("="*70)
    
    try:
        dsn = get_postgres_dsn()
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        # 테이블 수 확인
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables 
            WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        """)
        table_count = cursor.fetchone()[0]
        print(f"Total tables: {table_count}")
        
        # 주요 테이블 확인
        important_tables = [
            'safety_instructions', 'accidents', 'follow_sop', 'full_process',
            'followsop_cache', 'fullprocess_cache', 'safety_instructions_cache',
            'safety_instruction_column_config', 'follow_sop_column_config'
        ]
        
        missing = []
        for table in important_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            if not cursor.fetchone()[0]:
                missing.append(table)
        
        if missing:
            print(f"\nWARNING: Missing tables: {', '.join(missing)}")
        else:
            print("\nSUCCESS: All important tables exist!")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error checking status: {e}")
    
    print("\n" + "="*70)
    print("MIGRATION COMPLETED")
    print("="*70)
    print("\nNext steps:")
    print("1. Restart the Flask application")
    print("2. Test the website functionality")
    print("3. Check application logs for any errors")
    print("\nIf errors occur, check:")
    print("- Flask application logs")
    print("- PostgreSQL logs: /var/log/postgresql/")
    print("- Run: python check_postgres.py")

if __name__ == "__main__":
    main()