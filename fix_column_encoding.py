#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect('portal.db')
conn.execute("PRAGMA encoding = 'UTF-8'")
cursor = conn.cursor()

# Update the broken column names
updates = [
    ('incharge_person', '귀책담당자(임직원)'),
    ('incharge_person_id', '귀책담당자 ID'),
    ('incharge_person_dept', '귀책담당자 부서'),
    ('injured_person', '부상자명단')
]

for key, name in updates:
    cursor.execute('''
        UPDATE accident_column_config 
        SET column_name = ?
        WHERE column_key = ?
    ''', (name, key))
    print(f'Updated {key}: {name}')

conn.commit()

# Verify the update
cursor.execute("""
    SELECT column_key, column_name 
    FROM accident_column_config 
    WHERE column_key IN ('incharge_person', 'incharge_person_id', 'incharge_person_dept', 'injured_person')
""")
results = cursor.fetchall()
print('\nVerification - Updated columns:')
for row in results:
    print(f'  {row[0]}: {row[1]}')

conn.close()
print('\nColumn names have been fixed!')