#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
데이터베이스 인코딩 문제 수정 스크립트
"""
import sqlite3
import sys

def fix_column_names():
    try:
        conn = sqlite3.connect('portal.db')
        cursor = conn.cursor()
        
        # 깨진 컬럼명을 정상적인 한글로 수정
        updates = [
            ('incharge_person', '귀책담당자(임직원)'),
            ('incharge_person_id', '귀책담당자 ID'),
            ('incharge_person_dept', '귀책담당자 부서'),
            ('injured_person', '부상자명단')
        ]
        
        for column_key, column_name in updates:
            cursor.execute('''
                UPDATE accident_column_config 
                SET column_name = ? 
                WHERE column_key = ?
            ''', (column_name, column_key))
            
            # 확인
            cursor.execute('''
                SELECT column_name 
                FROM accident_column_config 
                WHERE column_key = ?
            ''', (column_key,))
            result = cursor.fetchone()
            if result:
                print(f"Updated {column_key}: {result[0]}")
        
        conn.commit()
        print("\n✅ 컬럼명이 성공적으로 수정되었습니다.")
        
        # 모든 accident_column_config 확인
        cursor.execute('''
            SELECT column_key, column_name, column_type
            FROM accident_column_config
            WHERE column_key LIKE '%person%' OR column_key LIKE '%injured%'
            ORDER BY column_order
        ''')
        
        print("\n현재 담당자/부상자 관련 컬럼:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]} ({row[2]})")
        
        conn.close()
        
    except Exception as e:
        print(f"오류 발생: {e}", file=sys.stderr)
        return False
    
    return True

if __name__ == '__main__':
    # stdout 인코딩 설정
    if sys.stdout.encoding != 'utf-8':
        sys.stdout.reconfigure(encoding='utf-8')
    
    fix_column_names()