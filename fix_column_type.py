#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
incharge_person 컬럼 타입 수정 스크립트
"""
import sqlite3

def fix_column_type():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    try:
        # incharge_person 컬럼 타입을 popup_person으로 수정
        cursor.execute('''
            UPDATE accident_column_config 
            SET column_type = 'popup_person'
            WHERE column_key = 'incharge_person'
        ''')
        
        # 컬럼명도 다시 한번 수정 (인코딩 문제 해결)
        cursor.execute('''
            UPDATE accident_column_config 
            SET column_name = '귀책담당자(임직원)'
            WHERE column_key = 'incharge_person'
        ''')
        
        conn.commit()
        
        # 확인
        cursor.execute('''
            SELECT column_key, column_name, column_type 
            FROM accident_column_config 
            WHERE column_key = 'incharge_person'
        ''')
        result = cursor.fetchone()
        
        print("수정 완료:")
        print(f"  - Column Key: {result[0]}")
        print(f"  - Column Name: {result[1]}")
        print(f"  - Column Type: {result[2]}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"오류 발생: {e}")
        conn.rollback()
        conn.close()
        return False

if __name__ == '__main__':
    fix_column_type()