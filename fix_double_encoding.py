#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
이중/삼중 JSON 인코딩된 드롭다운 값 정리 스크립트
"""
import json
import sqlite3

DB = "portal.db"

def clean_json_value(value):
    """재귀적으로 JSON 문자열을 풀어냄"""
    if not isinstance(value, str):
        return value
    
    try:
        # JSON 파싱 시도
        parsed = json.loads(value)
        
        # 파싱 결과가 또 JSON 문자열이면 재귀적으로 풀기
        if isinstance(parsed, str):
            return clean_json_value(parsed)
        elif isinstance(parsed, list) and len(parsed) == 1 and isinstance(parsed[0], str):
            # ["[\"a\",\"b\"]"] 형태인 경우
            return clean_json_value(parsed[0])
        else:
            return parsed
    except:
        return value

def main():
    print("=== 이중 인코딩 문제 해결 시작 ===\n")
    
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    
    # 모든 활성 드롭다운 코드 조회
    rows = cur.execute("""
        SELECT id, column_key, option_code, option_value 
        FROM dropdown_option_codes 
        WHERE is_active = 1
        ORDER BY column_key, display_order
    """).fetchall()
    
    fixed_columns = set()
    
    for id_, col_key, opt_code, opt_value in rows:
        # 이중 인코딩 해제
        cleaned = clean_json_value(opt_value)
        
        # 배열인 경우 처리
        if isinstance(cleaned, list):
            print(f"발견: {col_key} / {opt_code}")
            print(f"  원본: {repr(opt_value)}")
            print(f"  정리: {cleaned}")
            
            fixed_columns.add(col_key)
            
            # 기존 행 비활성화
            cur.execute("""
                UPDATE dropdown_option_codes 
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE column_key = ? AND is_active = 1
            """, (col_key,))
            
            # 개별 행으로 삽입
            for idx, item in enumerate(cleaned, 1):
                new_code = f"{col_key.upper()}_{idx:03d}"
                cur.execute("""
                    INSERT OR REPLACE INTO dropdown_option_codes
                    (column_key, option_code, option_value, display_order, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (col_key, new_code, str(item), idx))
                print(f"    -> {new_code}: {item}")
    
    conn.commit()
    conn.close()
    
    if fixed_columns:
        print(f"\n정리 완료: {len(fixed_columns)}개 컬럼 수정됨")
        print(f"   수정된 컬럼: {', '.join(fixed_columns)}")
    else:
        print("이중 인코딩된 값이 없습니다.")
    
    print("\n=== 이중 인코딩 문제 해결 완료 ===")

if __name__ == "__main__":
    main()