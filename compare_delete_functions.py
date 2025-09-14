#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
각 admin 페이지의 deleteSection 함수 비교
"""
import os
import re
import sys
import io

# UTF-8 encoding 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

templates = [
    'templates/admin-follow-sop-columns.html',
    'templates/admin-full-process-columns.html',
    'templates/admin-accident-columns.html',
    'templates/admin-safety-instruction-columns.html'
]

for template in templates:
    if not os.path.exists(template):
        print(f"❌ {template} 파일 없음")
        continue

    print(f"\n{'='*60}")
    print(f"📄 {template}")
    print('='*60)

    with open(template, 'r', encoding='utf-8') as f:
        content = f.read()

    # deleteSection 함수 찾기
    pattern = r'function deleteSection.*?\n(.*?\n){50}'
    matches = re.findall(pattern, content, re.DOTALL)

    if matches:
        # API 호출 부분 찾기
        api_pattern = r'fetch\([\'"`](.*?)[\'"`].*?method.*?[\'"`]DELETE'
        api_matches = re.findall(api_pattern, content, re.DOTALL)

        if api_matches:
            print(f"✅ DELETE API 엔드포인트: {api_matches[0]}")
        else:
            print("❌ DELETE API 호출 없음")

        # 실제 삭제 로직 확인
        if 'sectionsToDelete' in content:
            print("⚠️ sectionsToDelete 배열 사용 (일괄 삭제 가능)")

        if 'sections = sections.filter' in content:
            print("📝 로컬 배열에서 필터링")

        if 'renderSections()' in content:
            print("🔄 renderSections() 호출")

        if 'loadColumns()' in content:
            print("📊 loadColumns() 호출")

    else:
        print("❌ deleteSection 함수 없음")