#!/usr/bin/env python3
"""
Add scoring system JS and CSS to all relevant templates
"""
import os
import re

def add_assets_to_template(file_path):
    """Add scoring JS and CSS to template"""
    
    if not os.path.exists(file_path):
        print(f"File not found: {file_path}")
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if already has scoring assets
    if 'scoring-system.js' in content or 'scoring-system.css' in content:
        print(f"Already has scoring assets: {file_path}")
        return False
    
    modified = False
    
    # Add CSS link before </style> or </head>
    if '</style>' in content and 'scoring-system.css' not in content:
        # Add link tag after the last </style>
        style_pos = content.rfind('</style>')
        if style_pos != -1:
            insert_pos = style_pos + len('</style>')
            css_link = '\n<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/scoring-system.css\') }}">\n'
            content = content[:insert_pos] + css_link + content[insert_pos:]
            modified = True
    elif '</head>' in content and 'scoring-system.css' not in content:
        # Add before </head>
        content = content.replace('</head>', 
            '<link rel="stylesheet" href="{{ url_for(\'static\', filename=\'css/scoring-system.css\') }}">\n</head>')
        modified = True
    
    # Add JS script before </body> or at end of file
    if 'scoring-system.js' not in content:
        if '</body>' in content:
            # Add before </body>
            content = content.replace('</body>', 
                '<script src="{{ url_for(\'static\', filename=\'js/scoring-system.js\') }}"></script>\n</body>')
            modified = True
        elif '</html>' in content:
            # Add before </html>
            content = content.replace('</html>', 
                '<script src="{{ url_for(\'static\', filename=\'js/scoring-system.js\') }}"></script>\n</html>')
            modified = True
    
    if modified:
        # Backup original
        backup_path = file_path + '.backup_assets'
        with open(backup_path, 'w', encoding='utf-8') as f:
            with open(file_path, 'r', encoding='utf-8') as orig:
                f.write(orig.read())
        
        # Write updated content
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"Updated: {file_path}")
        return True
    else:
        print(f"No changes needed: {file_path}")
        return False

# List of templates to update
templates = [
    'templates/full-process-detail.html',
    'templates/full-process-register.html',
    'templates/follow-sop-detail.html',
    'templates/follow-sop-register.html',
    'templates/safety-instruction-detail.html',
    'templates/safety-instruction-register.html'
]

for template in templates:
    add_assets_to_template(template)

print("\nDone!")