#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 드롭다운 정리 스크립트
배열 문자열을 개별 행으로 분해
"""
import json
import sqlite3

DB = "portal.db"

def fix_dropdowns():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # 모든 활성 드롭다운 코드 조회
    rows = cur.execute("""
        SELECT DISTINCT column_key 
        FROM dropdown_option_codes 
        WHERE is_active = 1
    """).fetchall()
    
    for (col_key,) in rows:
        # 해당 컬럼의 첫 번째 행 확인
        first_row = cur.execute("""
            SELECT option_value 
            FROM dropdown_option_codes 
            WHERE column_key = ? AND is_active = 1
            LIMIT 1
        """, (col_key,)).fetchone()
        
        if not first_row:
            continue
            
        value = first_row[0]
        
        # 배열 문자열인지 확인
        if value and value.strip().startswith('[') and value.strip().endswith(']'):
            try:
                # JSON 파싱 시도
                arr = json.loads(value)
                if isinstance(arr, list) and len(arr) > 1:
                    print(f"수정 필요: {col_key} -> {arr}")
                    
                    # 기존 행 모두 삭제
                    cur.execute("""
                        DELETE FROM dropdown_option_codes 
                        WHERE column_key = ?
                    """, (col_key,))
                    
                    # 개별 행으로 재삽입
                    for idx, item in enumerate(arr, 1):
                        code = f"{col_key.upper()}_{idx:03d}"
                        cur.execute("""
                            INSERT INTO dropdown_option_codes
                            (column_key, option_code, option_value, display_order, is_active)
                            VALUES (?, ?, ?, ?, 1)
                        """, (col_key, code, str(item), idx))
                    
                    print(f"  -> {len(arr)}개 행으로 분해 완료")
            except:
                pass
    
    conn.commit()
    conn.close()
    print("완료!")

if __name__ == "__main__":
    fix_dropdowns()