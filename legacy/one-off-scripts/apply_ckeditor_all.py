#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
모든 상세/등록 페이지에 CKEditor 적용
"""

import os
import re
import sys

# UTF-8 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def update_template(filepath):
    """템플릿 파일에 CKEditor 적용"""
    
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 이미 CKEditor가 적용되어 있는지 확인
    if 'ckeditor-simple.js' in content:
        print(f"  [OK] Already has CKEditor: {filepath}")
        return False
    
    # content-editor.js를 ckeditor-simple.js로 교체
    if 'content-editor.js' in content:
        content = content.replace(
            '<script src="/static/js/content-editor.js"></script>',
            '<!-- CKEditor 스크립트 -->\n<script src="/static/js/ckeditor-simple.js"></script>'
        )
        print(f"  [OK] Replaced content-editor.js with ckeditor-simple.js")
    else:
        # {% endblock %} 앞에 CKEditor 스크립트 추가
        if '{% endblock %}' in content and 'ckeditor-simple.js' not in content:
            # 마지막 {% endblock %} 찾기
            last_endblock = content.rfind('{% endblock %}')
            if last_endblock != -1:
                # 그 앞에 스크립트 추가
                insert_pos = content.rfind('\n', 0, last_endblock)
                if insert_pos != -1:
                    content = (content[:insert_pos] + 
                              '\n\n<!-- CKEditor 스크립트 -->\n<script src="/static/js/ckeditor-simple.js"></script>\n' + 
                              content[insert_pos:])
                    print(f"  [OK] Added CKEditor script")
    
    # detailed-content textarea/div에 data-ckeditor="true" 추가
    patterns = [
        # textarea 패턴
        (r'(<textarea[^>]*id="detailed-content"[^>]*)(>)', r'\1 data-ckeditor="true"\2'),
        # div 패턴 
        (r'(<div[^>]*id="detailed-content"[^>]*)(>)', r'\1 data-ckeditor="true"\2'),
    ]
    
    for pattern, replacement in patterns:
        if re.search(pattern, content) and 'data-ckeditor="true"' not in content:
            content = re.sub(pattern, replacement, content)
            print(f"  [OK] Added data-ckeditor attribute")
    
    # 파일 저장
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)
    
    return True

def main():
    templates_dir = 'templates'
    
    # 처리할 파일 목록
    files = [
        'accident-detail.html',
        'accident-register.html', 
        'change-request-detail.html',
        'change-request-register.html',
        'full-process-detail.html',
        'full-process-register.html',
        'safety-instruction-detail.html',
        'safety-instruction-register.html',
        'partner-detail.html'
    ]
    
    print("Applying CKEditor to all templates...")
    print("=" * 50)
    
    for filename in files:
        filepath = os.path.join(templates_dir, filename)
        if os.path.exists(filepath):
            print(f"\nProcessing: {filename}")
            updated = update_template(filepath)
            if updated:
                print(f"  [OK] Updated successfully")
        else:
            print(f"\n[ERROR] File not found: {filename}")
    
    print("\n" + "=" * 50)
    print("[COMPLETE] CKEditor application complete!")

if __name__ == '__main__':
    main()