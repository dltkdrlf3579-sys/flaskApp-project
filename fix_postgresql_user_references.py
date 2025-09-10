#!/usr/bin/env python3
"""
PostgreSQL 스크립트들에서 portal_user 참조를 postgres로 수정하는 스크립트
"""
import os
import re

def fix_file(file_path):
    """파일에서 portal_user 참조를 수정"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        original_content = content
        
        # postgresql 섹션 참조를 DATABASE 섹션으로 변경
        content = re.sub(r"config\.get\('postgresql'", "config.get('DATABASE'", content)
        
        # portal_user를 postgres로 변경
        content = re.sub(r'portal_user', 'postgres', content)
        
        # DSN에서 사용자 이름 통일
        content = re.sub(r'postgresql://portal_user:', 'postgresql://postgres:', content)
        
        # config.ini에서 postgres_dsn 직접 읽도록 수정
        pattern = r"host = config\.get\('DATABASE', 'host'.*?\n.*?portal_dsn = f'postgresql.*?"
        replacement = "postgres_dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')"
        content = re.sub(pattern, replacement, content, flags=re.DOTALL)
        
        if content != original_content:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'[FIXED] {file_path}')
        else:
            print(f'[SKIP] {file_path} - no changes needed')
            
    except Exception as e:
        print(f'[ERROR] {file_path}: {e}')

def main():
    """메인 실행"""
    files_to_fix = [
        'phase6_jsonb_migration.py',
        'phase6_validation_tools.py', 
        'phase8_cutover_rollback.py',
        'test_pg_functions_smoke.py'
    ]
    
    print('PostgreSQL 사용자 참조 수정 중...')
    
    for file_path in files_to_fix:
        if os.path.exists(file_path):
            fix_file(file_path)
        else:
            print(f'[SKIP] {file_path} - file not found')
    
    print('[완료] 모든 파일 수정 완료!')

if __name__ == '__main__':
    main()