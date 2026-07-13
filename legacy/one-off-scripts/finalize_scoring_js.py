#!/usr/bin/env python3
"""
Add scoring JS at the end of templates
"""
import os

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
    
    # Check if already has the JS at the end
    if 'scoring-system.js' in content and '{% endblock %}' in content:
        # Check if it's right before endblock
        if 'scoring-system.js' in content.split('{% endblock %}')[0].split('\n')[-5:]:
            print(f"Already properly configured: {template}")
            continue
    
    # Find the last {% endblock %} and add JS before it
    if '{% endblock %}' in content:
        # Remove existing scoring-system.js references if any
        content = content.replace('<script src="{{ url_for(\'static\', filename=\'js/scoring-system.js\') }}"></script>', '')
        
        # Add before last endblock
        content = content.replace('{% endblock %}', 
            '<script src="{{ url_for(\'static\', filename=\'js/scoring-system.js\') }}"></script>\n\n{% endblock %}')
        
        with open(template, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Updated: {template}")
    else:
        print(f"No endblock found: {template}")

print("\nDone!")