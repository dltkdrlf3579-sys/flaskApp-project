#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DB 정리 스크립트: 배열 문자열로 저장된 잘못된 행 자동 탐지/정리
모든 드롭다운 컬럼에 대해 자동 처리합니다.
"""
import json
import sqlite3
import re

DB = "portal.db"

def main():
    print("=== 드롭다운 배열 문자열 정리 시작 ===\n")
    
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # 배열 문자열처럼 보이는 활성 행 찾기
    suspects = cur.execute("""
        SELECT id, column_key, option_code, option_value, display_order
        FROM dropdown_option_codes
        WHERE is_active = 1 AND TRIM(option_value) LIKE '[%' AND TRIM(option_value) LIKE '%]'
    """).fetchall()

    if not suspects:
        print("OK: 배열 문자열로 저장된 잘못된 행이 없습니다.")
        conn.close()
        return

    print(f"발견: 의심스러운 행 {len(suspects)}개")
    
    processed_columns = set()
    
    for id_, col, code, val, _ in suspects:
        print(f"- {col} / {code} / {val}")
        try:
            arr = json.loads(val.strip())
            if not isinstance(arr, list):
                print(f"  경고: 배열이 아님, 건너뜀")
                continue
        except Exception as e:
            print(f"  경고: JSON 파싱 실패: {e}")
            continue

        if col in processed_columns:
            continue
            
        processed_columns.add(col)
        
        print(f"  처리: {col} 컬럼 정리 시작 ({len(arr)}개 항목으로 분해)")

        # 같은 column_key의 기존 활성 행을 비활성화
        cur.execute("""
            UPDATE dropdown_option_codes
            SET is_active = 0, updated_at = CURRENT_TIMESTAMP
            WHERE column_key = ? AND is_active = 1
        """, (col,))
        print(f"     - 기존 활성 행 비활성화")

        # 분해 삽입
        for idx, item in enumerate(arr, 1):
            oc = f"{col.upper()}_{idx:03d}"
            cur.execute("""
                INSERT OR REPLACE INTO dropdown_option_codes
                (column_key, option_code, option_value, display_order, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, 1, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """, (col, oc, str(item), idx))
            print(f"     - {oc}: {str(item)}")

    conn.commit()
    conn.close()
    
    print(f"\n완료: 정리 완료! {len(processed_columns)}개 컬럼 처리됨")
    print("=== 드롭다운 배열 문자열 정리 완료 ===")

if __name__ == "__main__":
    main()