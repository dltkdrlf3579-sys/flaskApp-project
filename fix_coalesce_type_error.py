#!/usr/bin/env python3
"""
COALESCE 타입 에러 수정
fullprocess와 followsop의 sync_date 관련 쿼리 수정
"""
import os

def fix_database_config():
    """database_config.py의 COALESCE 타입 에러 수정"""
    
    print("="*70)
    print("COALESCE Type Error Fix")
    print("="*70)
    
    file_path = 'database_config.py'
    
    if not os.path.exists(file_path):
        print(f"ERROR: {file_path} not found")
        return False
    
    # 백업 생성
    import shutil
    backup_path = f"{file_path}.backup_coalesce"
    shutil.copy2(file_path, backup_path)
    print(f"Backup created: {backup_path}")
    
    # 파일 읽기
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    # COALESCE 패턴 수정 - followsop과 fullprocess
    replacements = [
        # followsop_cache 관련
        (
            "COALESCE(NULLIF(json_extract(c.custom_data, '$.created_at'), ''), c.sync_date)",
            "COALESCE(NULLIF(json_extract(c.custom_data, '$.created_at'), '')::timestamp, c.sync_date)"
        ),
        # 더 일반적인 패턴
        (
            "COALESCE(json_extract(c.custom_data, '$.created_at'), c.sync_date)",
            "COALESCE(NULLIF(json_extract(c.custom_data, '$.created_at'), '')::timestamp, c.sync_date)"
        ),
        # fullprocess_cache 관련 (동일한 패턴)
        (
            "COALESCE(NULLIF(json_extract(f.custom_data, '$.created_at'), ''), f.sync_date)",
            "COALESCE(NULLIF(json_extract(f.custom_data, '$.created_at'), '')::timestamp, f.sync_date)"
        ),
        (
            "COALESCE(json_extract(f.custom_data, '$.created_at'), f.sync_date)",
            "COALESCE(NULLIF(json_extract(f.custom_data, '$.created_at'), '')::timestamp, f.sync_date)"
        ),
        # 다른 테이블들도 동일한 패턴 적용
        (
            "COALESCE(NULLIF(json_extract(custom_data, '$.created_at'), ''), sync_date)",
            "COALESCE(NULLIF(json_extract(custom_data, '$.created_at'), '')::timestamp, sync_date)"
        ),
    ]
    
    changes_made = 0
    for old_pattern, new_pattern in replacements:
        if old_pattern in content:
            content = content.replace(old_pattern, new_pattern)
            changes_made += 1
            print(f"  Fixed: {old_pattern[:50]}...")
    
    if changes_made > 0:
        # 수정된 내용 저장
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"\nTotal fixes applied: {changes_made}")
        print(f"File updated: {file_path}")
        return True
    else:
        print("\nNo COALESCE patterns found that need fixing.")
        print("Checking for already fixed patterns...")
        
        # 이미 수정되었는지 확인
        if "::timestamp" in content:
            print("  Found ::timestamp casting - already fixed!")
        else:
            print("  WARNING: No COALESCE patterns found at all!")
            print("  This might indicate a different file structure.")
        
        return False

if __name__ == "__main__":
    success = fix_database_config()
    
    if success:
        print("\n" + "="*70)
        print("SUCCESS: COALESCE type errors fixed!")
        print("="*70)
        print("\nNext steps for production server:")
        print("1. Run: python fix_missing_tables_properly.py")
        print("2. Run: python fix_coalesce_type_error.py")
        print("3. Restart Flask application")
    else:
        print("\n" + "="*70)
        print("Check if the file is already fixed or has different structure")
        print("="*70)