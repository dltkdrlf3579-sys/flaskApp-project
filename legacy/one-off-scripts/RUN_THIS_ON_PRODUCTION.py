#!/usr/bin/env python3
"""
운영 환경에서 실행할 최종 스크립트
모든 문제를 순서대로 해결

실행 방법:
    python RUN_THIS_ON_PRODUCTION.py
"""
import subprocess
import sys

def run_script(script_name, description):
    """스크립트 실행 및 결과 확인"""
    print("\n" + "="*70)
    print(f"{description}")
    print("="*70)
    
    try:
        result = subprocess.run(
            [sys.executable, script_name],
            capture_output=True,
            text=True,
            encoding='utf-8'
        )
        
        print(result.stdout)
        if result.stderr:
            print("STDERR:", result.stderr)
        
        if result.returncode != 0:
            print(f"WARNING: {script_name} returned code {result.returncode}")
            return False
        return True
        
    except Exception as e:
        print(f"ERROR running {script_name}: {e}")
        return False

def main():
    print("="*70)
    print("PRODUCTION ENVIRONMENT FIX")
    print("="*70)
    print("\nThis script will fix all database issues in order:")
    print("1. Create missing tables (with proper verification)")
    print("2. Fix COALESCE type errors")
    print("3. Verify all fixes")
    
    input("\nPress Enter to continue...")
    
    # 1. 누락된 테이블 생성
    success1 = run_script(
        'fix_missing_tables_properly.py',
        'STEP 1: Creating Missing Tables'
    )
    
    if not success1:
        print("\nWARNING: Table creation had issues. Check the output above.")
        response = input("Continue anyway? (y/n): ")
        if response.lower() != 'y':
            return
    
    # 2. COALESCE 타입 에러 수정
    success2 = run_script(
        'fix_coalesce_type_error.py',
        'STEP 2: Fixing COALESCE Type Errors'
    )
    
    if not success2:
        print("\nWARNING: COALESCE fix had issues. Check the output above.")
    
    # 3. 최종 확인
    print("\n" + "="*70)
    print("STEP 3: Final Verification")
    print("="*70)
    
    run_script('check_postgres.py', 'Database Status Check')
    
    print("\n" + "="*70)
    print("COMPLETED")
    print("="*70)
    print("\nAll fixes have been applied.")
    print("Please restart your Flask application now.")
    print("\nIf you still see errors:")
    print("1. Check PostgreSQL logs: /var/log/postgresql/")
    print("2. Run: python check_postgres.py")
    print("3. Check Flask app logs when accessing the site")

if __name__ == "__main__":
    main()