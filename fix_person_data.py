#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 기존 샘플 데이터 삭제
cursor.execute('DELETE FROM person_master WHERE employee_id IN (?, ?, ?, ?, ?)', 
               ('10001', '10002', '10003', '10004', '10005'))

# 새 샘플 데이터 추가
persons = [
    ('10001', '김철수', '안전보건팀'),
    ('10002', '이영희', '생산1팀'),
    ('10003', '박민수', '품질관리팀'),
    ('10004', '정수진', '인사팀'),
    ('10005', '최동욱', '총무팀')
]

for emp_id, name, dept in persons:
    cursor.execute('''
        INSERT INTO person_master (employee_id, name, department, is_active)
        VALUES (?, ?, ?, 1)
    ''', (emp_id, name, dept))

conn.commit()
print('Added sample persons successfully')

# 확인
cursor.execute('SELECT employee_id, name, department FROM person_master WHERE employee_id LIKE ?', ('1000%',))
rows = cursor.fetchall()
for row in rows:
    print(f"ID: {row[0]}, Name: {row[1]}, Dept: {row[2]}")

conn.close()