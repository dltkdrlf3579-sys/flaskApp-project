#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import sys
import io

# stdout을 UTF-8로 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 데이터베이스 연결
conn = sqlite3.connect('portal.db')
conn.execute("PRAGMA encoding='UTF-8'")
conn.text_factory = lambda x: x.decode('utf-8') if isinstance(x, bytes) else x
cursor = conn.cursor()

# 기존 데이터 삭제
cursor.execute("DELETE FROM contractors_cache")

# 한글 데이터 제대로 삽입
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
    ('W014', '하동훈', '안전관리(주)', '456-78-90123'),
    ('W015', '전소민', '청소용역(주)', '567-89-01234'),
    ('W016', '양세찬', '경비용역(주)', '678-90-12345'),
    ('W017', '이광수', '한국건설(주)', '123-45-67890'),
    ('W018', '송강호', '시설관리(주)', '789-01-23456'),
    ('W019', '김태희', '대한전기(주)', '234-56-78901'),
    ('W020', '이병헌', '서울설비(주)', '345-67-89012')
]

# 데이터 삽입
for contractor in contractors:
    cursor.execute('''
        INSERT INTO contractors_cache (worker_id, worker_name, company_name, business_number)
        VALUES (?, ?, ?, ?)
    ''', contractor)

conn.commit()
print(f"[SUCCESS] {len(contractors)}개의 협력사 근로자 데이터를 한글로 추가했습니다.")

# 확인
cursor.execute("SELECT worker_id, worker_name, company_name FROM contractors_cache LIMIT 5")
rows = cursor.fetchall()
print("\n데이터 확인:")
for row in rows:
    print(f"  {row[0]}: {row[1]} - {row[2]}")

conn.close()