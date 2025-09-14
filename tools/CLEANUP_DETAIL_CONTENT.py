#!/usr/bin/env python3
"""
detail_content 관련 코드를 모두 detailed_content로 변경

DB 통일 후 실행하세요!
"""

import os
import re

def cleanup_code():
    """detail_content 참조를 모두 detailed_content로 변경"""
    
    files_to_update = [
        ('database_config.py', [
            # 호환성 처리 코드 제거하고 직접 사용
            (r"# 칼럼명 호환성 처리.*?content_column = .*?\n", "", re.DOTALL),
            (r"content_column = '[^']+'\s*", ""),
            (r"pd\.\{content_column\}", "pd.detailed_content"),
            (r"detail_content", "detailed_content"),
        ]),
        ('app.py', [
            (r"detail_content", "detailed_content"),
        ]),
        ('db/upsert.py', [
            (r"detail_content", "detailed_content"),
        ]),
    ]
    
    print("=" * 60)
    print("detail_content → detailed_content 코드 정리")
    print("=" * 60)
    
    for filename, patterns in files_to_update:
        filepath = os.path.join(os.path.dirname(os.path.dirname(__file__)), filename)
        
        if not os.path.exists(filepath):
            print(f"⚠️  {filename} 파일이 없습니다.")
            continue
        
        # 백업
        with open(filepath, 'r', encoding='utf-8') as f:
            original = f.read()
        
        with open(filepath + '.backup', 'w', encoding='utf-8') as f:
            f.write(original)
        
        # 변경
        modified = original
        changes = 0
        
        for pattern, replacement, *flags in patterns:
            if flags:
                new_content = re.sub(pattern, replacement, modified, flags=flags[0])
            else:
                new_content = modified.replace(pattern, replacement)
            
            if new_content != modified:
                changes += modified.count(pattern)
                modified = new_content
        
        # 저장
        if changes > 0:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(modified)
            print(f"✅ {filename}: {changes}개 변경")
        else:
            print(f"⭕ {filename}: 변경사항 없음")
    
    print("\n특별 처리가 필요한 부분:")
    print("1. database_config.py 1256-1262 라인의 호환성 코드를 수동으로 제거")
    print("   간단히: content_column 변수 제거하고 직접 'detailed_content' 사용")
    print("\n완료!")

if __name__ == '__main__':
    cleanup_code()