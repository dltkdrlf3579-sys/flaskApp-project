# -*- coding: utf-8 -*-
import sqlite3

# 데이터베이스 연결
conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 기존 데이터 삭제
cursor.execute("DELETE FROM contractors_cache")

# 협력사 근로자 더미 데이터 (다시 추가)
contractors = [
    ('W001', '김철수', '한국건설(주)', '123-45-67890'),
    ('W002', '이영희', '대한전기(주)', '234-56-78901'),
    ('W003', '박민수', '서울설비(주)', '345-67-89012'),
    ('W004', '정수진', '한국건설(주)', '123-45-67890'),
    ('W005', '최동훈', '안전관리(주)', '456-78-90123'),
    ('W006', '김미나', '대한전기(주)', '234-56-78901'),
    ('W007', '이준호', '서울설비(주)', '345-67-89012'),
    ('W008', '박서연', '청소용역(주)', '567-89-01234'),
    ('W009', '정우성', '경비용역(주)', '678-90-12345'),
    ('W010', '강하늘', '한국건설(주)', '123-45-67890'),
    ('W011', '송지효', '시설관리(주)', '789-01-23456'),
    ('W012', '유재석', '대한전기(주)', '234-56-78901'),
    ('W013', '김종국', '서울설비(주)', '345-67-89012'),
    ('W014', '하하', '안전관리(주)', '456-78-90123'),
    ('W015', '전소민', '청소용역(주)', '567-89-01234'),
    ('W016', '양세찬', '경비용역(주)', '678-90-12345'),
    ('W017', '이광수', '한국건설(주)', '123-45-67890'),
    ('W018', '송강', '시설관리(주)', '789-01-23456'),
    ('W019', '김태희', '대한전기(주)', '234-56-78901'),
    ('W020', '비', '서울설비(주)', '345-67-89012')
]

# 데이터 삽입
cursor.executemany('''
    INSERT INTO contractors_cache (worker_id, worker_name, company_name, business_number)
    VALUES (?, ?, ?, ?)
''', contractors)

conn.commit()
print(f"[SUCCESS] Fixed encoding and added {len(contractors)} contractor worker data.")

# 확인
cursor.execute("SELECT worker_id, worker_name, company_name FROM contractors_cache LIMIT 5")
rows = cursor.fetchall()
print("\nData check:")
for row in rows:
    print(f"  {row[0]}: {row[1]} - {row[2]}")

conn.close()