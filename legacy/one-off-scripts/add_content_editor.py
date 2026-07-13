#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
모든 register 페이지에 content-editor.js 추가
"""
import os

register_files = [
    'templates/accident-register.html',
    'templates/change-request-register.html', 
    'templates/safety-instruction-register.html',
    'templates/full-process-register.html',
    'templates/follow-sop-register.html'
]

script_tag = '''
<!-- Content Editor 스크립트 추가 -->
<script src="/static/js/content-editor.js"></script>

{% endblock %}'''

for file_path in register_files:
    if os.path.exists(file_path):
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 이미 추가되어 있는지 확인
        if 'content-editor.js' in content:
            print(f"Already has: {os.path.basename(file_path)}")
            continue
        
        # 마지막 {% endblock %}를 찾아서 대체
        if content.strip().endswith('{% endblock %}'):
            content = content.rsplit('{% endblock %}', 1)[0] + script_tag
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            print(f"Added to: {os.path.basename(file_path)}")
        else:
            print(f"Could not find endblock in: {os.path.basename(file_path)}")

print("\nDone!")