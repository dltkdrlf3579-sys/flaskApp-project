#!/usr/bin/env python3
"""
Fix template escaping for scoring fields
"""
import os
import re

templates = [
    'templates/full-process-register.html',
    'templates/follow-sop-detail.html',
    'templates/follow-sop-register.html',
    'templates/safety-instruction-detail.html',
    'templates/safety-instruction-register.html'
]

for template in templates:
    if not os.path.exists(template):
        print(f"File not found: {template}")
        continue
    
    with open(template, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    
    # Fix data-config attribute
    if 'data-config="{{ col.scoring_config | tojson | e }}"' in content:
        content = content.replace(
            'data-config="{{ col.scoring_config | tojson | e }}"',
            'data-config="{{ col.scoring_config | default(\'{}\') | tojson }}"'
        )
        modified = True
    
    # Fix value attribute for scoring fields
    if 'value="{{ col_value | tojson | e }}"' in content:
        # Only replace within scoring field context
        lines = content.split('\n')
        new_lines = []
        in_scoring = False
        
        for line in lines:
            if 'column_type == \'scoring\'' in line:
                in_scoring = True
            elif 'column_type ==' in line and 'scoring' not in line:
                in_scoring = False
            
            if in_scoring and 'value="{{ col_value | tojson | e }}"' in line:
                line = line.replace(
                    'value="{{ col_value | tojson | e }}"',
                    'value="{{ col_value | default(\'{}\') | tojson }}"'
                )
                modified = True
            
            new_lines.append(line)
        
        content = '\n'.join(new_lines)
    
    if modified:
        with open(template, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {template}")
    else:
        print(f"No changes needed: {template}")

print("\nDone!")