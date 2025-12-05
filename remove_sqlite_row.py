#!/usr/bin/env python3
"""
Remove all sqlite3.Row occurrences from app.py
"""

import re

# Read app.py
with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences before
count_before = len(re.findall(r'conn\.row_factory = sqlite3\.Row', content))
print(f"Found {count_before} occurrences of 'conn.row_factory = sqlite3.Row'")

# Remove all occurrences (including the entire line)
content = re.sub(r'^\s*conn\.row_factory = sqlite3\.Row.*$\n?', '', content, flags=re.MULTILINE)

# Count occurrences after
count_after = len(re.findall(r'conn\.row_factory = sqlite3\.Row', content))
print(f"After removal: {count_after} occurrences remaining")

# Write back
with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Successfully removed {count_before - count_after} lines")