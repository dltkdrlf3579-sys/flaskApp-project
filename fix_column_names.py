#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3

# 올바른 컬럼 이름 매핑
column_name_mapping = {
    'issue_number': '발부번호',
    'violation_date': '위반일자',
    'issuer_department': '발부부서',
    'discipline_date': '징계일자',
    'primary_company': '1차업체',
    'secondary_company': '2차업체',
    'violation_company': '위반업체',
    'employment_type': '고용형태',
    'violation_employee': '위반자',
    'disciplined_person': '징계대상자',
    'discipline_type': '징계유형',
    'accident_type': '사고유형',
    'accident_grade': '사고등급',
    'safety_violation_grade': '환경안전수칙 위반등급',
    'violation_type': '위반유형',
    'work_grade': '작업등급',
    'instruction_number': '지시번호',
    'instruction_date': '발부일자',
    'title': '제목',
    'aa1': 'a1',
    'aa4': 'aa3'
}

def fix_column_names():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    # follow_sop_column_config 업데이트
    for key, name in column_name_mapping.items():
        cursor.execute("""
            UPDATE follow_sop_column_config 
            SET column_name = ? 
            WHERE column_key = ?
        """, (name, key))
    
    # full_process_column_config 업데이트
    for key, name in column_name_mapping.items():
        cursor.execute("""
            UPDATE full_process_column_config 
            SET column_name = ? 
            WHERE column_key = ?
        """, (name, key))
    
    conn.commit()
    
    # 결과 확인
    cursor.execute("""
        SELECT column_key, column_name, tab 
        FROM follow_sop_column_config 
        WHERE is_active = 1 
        ORDER BY column_order 
        LIMIT 10
    """)
    
    print("Follow SOP columns after fix:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} (tab: {row[2]})")
    
    cursor.execute("""
        SELECT column_key, column_name, tab 
        FROM full_process_column_config 
        WHERE is_active = 1 
        ORDER BY column_order 
        LIMIT 10
    """)
    
    print("\nFull Process columns after fix:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} (tab: {row[2]})")
    
    conn.close()
    print("\nColumn names fixed successfully!")

if __name__ == "__main__":
    fix_column_names()