#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
app.py의 Boolean 쿼리를 PostgreSQL 호환으로 자동 변환
"""
import re

def fix_boolean_queries():
    """app.py의 Boolean 쿼리 수정"""
    
    # app.py 읽기
    with open('app.py', 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 수정 전 백업
    with open('app.py.backup', 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Boolean 패턴 변환
    replacements = [
        # is_active = 1 → is_active = TRUE
        (r'is_active\s*=\s*1(?!\d)', 'is_active = TRUE'),
        
        # is_active = 0 → is_active = FALSE  
        (r'is_active\s*=\s*0(?!\d)', 'is_active = FALSE'),
        
        # is_deleted = 1 → is_deleted = TRUE
        (r'is_deleted\s*=\s*1(?!\d)', 'is_deleted = TRUE'),
        
        # is_deleted = 0 → is_deleted = FALSE
        (r'is_deleted\s*=\s*0(?!\d)', 'is_deleted = FALSE'),
        
        # first_sync_done = 1 → first_sync_done = TRUE
        (r'first_sync_done\s*=\s*1(?!\d)', 'first_sync_done = TRUE'),
        
        # first_sync_done = 0 → first_sync_done = FALSE
        (r'first_sync_done\s*=\s*0(?!\d)', 'first_sync_done = FALSE'),
    ]
    
    modified_count = 0
    for pattern, replacement in replacements:
        matches = re.findall(pattern, content)
        if matches:
            content = re.sub(pattern, replacement, content)
            modified_count += len(matches)
            print(f"✅ '{pattern}' → '{replacement}': {len(matches)}개 변경")
    
    # 수정된 내용 저장
    with open('app.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"\n총 {modified_count}개 Boolean 쿼리 수정 완료!")
    print("백업 파일: app.py.backup")
    
    return modified_count

if __name__ == "__main__":
    print("=== app.py Boolean 쿼리 수정 ===\n")
    
    count = fix_boolean_queries()
    
    if count > 0:
        print("\n✅ 수정 완료! Flask 앱을 다시 실행하세요.")
    else:
        print("\n⚠️  수정할 항목이 없습니다.")