#!/usr/bin/env python3
"""
Apply scoring system to all detail and register pages
"""
import os
import re

# 추가할 채점 필드 HTML
scoring_field_html = '''                                {% elif col.column_type == 'scoring' %}
                                    <!-- 채점 필드 -->
                                    <div class="scoring-field" data-field="{{ col.column_key }}" data-config="{{ col.scoring_config | tojson | e }}">
                                        <div class="scoring-items">
                                            <!-- 동적으로 생성될 채점 항목들 -->
                                        </div>
                                        <input type="hidden" 
                                               class="{{ section.section_key }}-input" 
                                               data-field="{{ col.column_key }}"
                                               data-section="{{ section.section_key }}"
                                               value="{{ col_value | tojson | e }}">
                                    </div>
                                    
                                {% elif col.column_type == 'score_total' %}
                                    <!-- 총점 필드 (자동 계산) -->
                                    <div class="score-total-field">
                                        <div class="score-display">
                                            <span class="score-value">0</span>점
                                            <div class="score-breakdown">
                                                <span class="critical-count">중대: 0</span>
                                                <span class="major-count">주요: 0</span>
                                                <span class="minor-count">경미: 0</span>
                                                <span class="bonus-count">가점: 0</span>
                                            </div>
                                        </div>
                                        <input type="hidden" 
                                               class="{{ section.section_key }}-input" 
                                               data-field="{{ col.column_key }}"
                                               data-section="{{ section.section_key }}"
                                               value="{{ col_value }}">
                                    </div>
                                            '''

def update_template(file_path):
    """Update a template file with scoring system"""
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has scoring
    if 'column_type == \'scoring\'' in content:
        print(f"Already has scoring: {file_path}")
        return False
    
    # Find the textarea field and add scoring fields after it
    pattern = r'(\{% elif col\.column_type == \'textarea\' %\}.*?\n\s+.*?\n\s+.*?\n\s+.*?\n\s+.*?\n\s+.*?\n)'
    
    def replace_func(match):
        return match.group(1) + '\n' + scoring_field_html + '\n'
    
    updated_content = re.sub(pattern, replace_func, content, flags=re.DOTALL)
    
    if updated_content == content:
        print(f"No changes made to: {file_path}")
        return False
    
    # Backup original
    backup_path = file_path + '.backup_scoring'
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    # Write updated content
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(updated_content)
    
    print(f"Updated: {file_path}")
    return True

# List of templates to update
templates = [
    'templates/full-process-register.html',
    'templates/follow-sop-detail.html',
    'templates/follow-sop-register.html',
    'templates/safety-instruction-detail.html',
    'templates/safety-instruction-register.html'
]

for template in templates:
    update_template(template)

print("\nDone!")