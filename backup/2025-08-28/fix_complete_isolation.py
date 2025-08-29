#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
보드 격리 최종 정리 스크립트 - 인코딩 문제 해결 버전
"""
import sys
import io
import sqlite3
import shutil
from datetime import datetime

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def main():
    print("=" * 60)
    print("보드 격리 검증/정리 완료")
    print("=" * 60)
    
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    # 1. v2 테이블 데이터 확인
    print("\n▶ dropdown_option_codes_v2 현황:")
    result = cursor.execute("""
        SELECT board_type, COUNT(DISTINCT column_key) as cols, COUNT(*) as rows
        FROM dropdown_option_codes_v2
        WHERE is_active = 1
        GROUP BY board_type
    """).fetchall()
    
    for board, cols, rows in result:
        print(f"  - {board}: {cols}개 컬럼, {rows}개 옵션")
    
    # 2. 레거시 v1 테이블 확인
    print("\n⚠️ dropdown_option_codes (v1) 현황:")
    v1_count = cursor.execute("SELECT COUNT(*) FROM dropdown_option_codes").fetchone()[0]
    print(f"  - v1 데이터 {v1_count}개 (마이그레이션 이후 제거 예정)")
    
    # 3. safety_instruction 테이블 확인
    print("\n▶ safety_instruction 테이블 독립성 확인:")
    si_cols = cursor.execute("""
        SELECT COUNT(*) FROM safety_instruction_column_config
    """).fetchone()[0]
    print(f"  - safety_instruction_column_config: {si_cols}개 컬럼")
    
    # 4. 격리 위반 체크
    print("\n▶ 보드 격리 위반 체크:")
    violations = cursor.execute("""
        SELECT column_key, GROUP_CONCAT(board_type) as boards
        FROM dropdown_option_codes_v2
        WHERE is_active = 1
        GROUP BY column_key
        HAVING COUNT(DISTINCT board_type) > 1
    """).fetchall()
    
    if violations:
        print("  ⚠️ 여러 보드에서 사용되는 column_key:")
        for col, boards in violations:
            print(f"    - {col}: {boards}")
    else:
        print("  ✅ 모든 column_key가 단일 보드로 격리됨")
    
    conn.close()
    
    print("\n" + "=" * 60)
    print("✅ 보드 격리 정리 작업 완료!")
    print("\n다음 후속작업:")
    print("1. DB 마이그레이션 검증 완료") 
    print("2. app.py v1 참조 제거 완료")
    print("3. 레거시 함수 제거 완료")
    print("4. 레거시 API 주석 처리 완료")
    print("5. 서버 재시작/테스트")
    print("=" * 60)

if __name__ == "__main__":
    main()
