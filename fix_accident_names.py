#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3

# DB 연결
conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 모든 ACC 사고의 accident_name을 수정
cursor.execute("""
    SELECT id, accident_number 
    FROM accidents_cache 
    WHERE accident_number LIKE 'ACC%'
""")

rows = cursor.fetchall()
for row in rows:
    id_val = row[0]
    acc_num = row[1]
    new_name = f"사고_{acc_num}"
    
    cursor.execute("UPDATE accidents_cache SET accident_name = ? WHERE id = ?", 
                   (new_name, id_val))
    print(f"Updated ID {id_val}: {acc_num} -> {new_name}")

conn.commit()

# 확인
cursor.execute("""
    SELECT accident_number, accident_name 
    FROM accidents_cache 
    WHERE accident_number LIKE 'ACC%'
    ORDER BY id DESC 
    LIMIT 5
""")

print("\nVerification:")
for row in cursor.fetchall():
    print(f"  {row[0]}: {row[1]}")

conn.close()
print("\nDone!")