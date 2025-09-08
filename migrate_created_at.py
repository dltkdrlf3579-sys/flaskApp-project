#!/usr/bin/env python3
"""
등록일 필드명 통일 마이그레이션 스크립트
- accidents 테이블의 report_date → created_at
- accident_column_config의 report_date → created_at  
- follow_sop_column_config의 created_date → created_at
"""

import sqlite3
from datetime import datetime

def migrate_created_at():
    conn = sqlite3.connect('portal.db')
    cur = conn.cursor()
    
    try:
        print("=" * 50)
        print("등록일 필드명 통일 마이그레이션 시작")
        print("=" * 50)
        
        # 1. accidents_cache 테이블의 report_date → created_at
        print("\n1. accidents_cache 테이블 마이그레이션...")
        cur.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cur.fetchall()]
        
        if 'report_date' in columns and 'created_at' not in columns:
            print("   - report_date를 created_at으로 변경")
            cur.execute("ALTER TABLE accidents_cache RENAME COLUMN report_date TO created_at")
            print("   ✅ 완료")
        elif 'created_at' in columns:
            print("   - 이미 created_at 컬럼 존재")
        else:
            print("   - report_date 컬럼이 없습니다")
        
        # 2. accident_column_config의 report_date → created_at
        print("\n2. accident_column_config 마이그레이션...")
        cur.execute("""
            UPDATE accident_column_config 
            SET column_key = 'created_at', 
                column_name = '등록일',
                updated_at = ?
            WHERE column_key = 'report_date'
        """, (datetime.now().isoformat(),))
        rows_updated = cur.rowcount
        if rows_updated > 0:
            print(f"   ✅ {rows_updated}개 행 업데이트")
        else:
            print("   - 업데이트할 report_date가 없습니다")
        
        # 3. follow_sop_column_config의 created_date → created_at
        print("\n3. follow_sop_column_config 마이그레이션...")
        cur.execute("""
            UPDATE follow_sop_column_config 
            SET column_key = 'created_at',
                column_name = '등록일',
                updated_at = ?
            WHERE column_key = 'created_date'
        """, (datetime.now().isoformat(),))
        rows_updated = cur.rowcount
        if rows_updated > 0:
            print(f"   ✅ {rows_updated}개 행 업데이트")
        else:
            print("   - 업데이트할 created_date가 없습니다")
        
        # 변경사항 저장
        conn.commit()
        print("\n" + "=" * 50)
        print("✅ 마이그레이션 완료!")
        print("=" * 50)
        
        # 결과 확인
        print("\n📊 마이그레이션 결과 확인:")
        
        # accidents_cache 컬럼 확인
        cur.execute("PRAGMA table_info(accidents_cache)")
        cols = [c[1] for c in cur.fetchall() if 'created_at' in c[1] or 'report_date' in c[1]]
        print(f"   accidents_cache 날짜 컬럼: {cols}")
        
        # accident_column_config 확인
        cur.execute("SELECT column_key FROM accident_column_config WHERE column_key IN ('created_at', 'report_date')")
        cols = [c[0] for c in cur.fetchall()]
        print(f"   accident_column_config: {cols}")
        
        # follow_sop_column_config 확인
        cur.execute("SELECT column_key FROM follow_sop_column_config WHERE column_key IN ('created_at', 'created_date')")
        cols = [c[0] for c in cur.fetchall()]
        print(f"   follow_sop_column_config: {cols}")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()
    
    return True

if __name__ == "__main__":
    success = migrate_created_at()
    if success:
        print("\n✨ 다음 단계: 템플릿과 백엔드 코드의 필드명 참조를 업데이트하세요")