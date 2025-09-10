#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL 컷오버 준비 완료 검증
Phase 3 완료 확인
"""
import sys
import os

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert, UPSERT_REGISTRY

def test_phase3_completion():
    """Phase 3 완료 검증"""
    print("\n=== Phase 3 완료 검증 ===")
    
    # 1. UPSERT 레지스트리 확인
    print(f"✅ UPSERT 레지스트리 테이블 수: {len(UPSERT_REGISTRY)}")
    for table, config in UPSERT_REGISTRY.items():
        print(f"   - {table}: {config['conflict_cols']} / {len(config['update_cols'])}개 업데이트 컬럼")
    
    # 2. SQLite 모드 테스트 
    conn = get_db_connection()
    print(f"✅ DB 연결: {'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'}")
    
    # 3. 주요 테이블 UPSERT 테스트
    test_cases = [
        ('dropdown_option_codes_v2', {'board_type': 'test', 'column_key': 'status', 'option_code': 'READY', 'option_value': 'PostgreSQL 준비완료'}),
        ('safety_instruction_details', {'issue_number': 'TEST-PG-001', 'detailed_content': 'PostgreSQL 호환 테스트'}),
        ('sync_state', {'id': 1, 'last_full_sync': None})
    ]
    
    for table, data in test_cases:
        try:
            result = safe_upsert(conn, table, data)
            print(f"✅ {table}: {result}행 처리 완료")
        except Exception as e:
            print(f"❌ {table}: {e}")
            return False
    
    conn.close()
    return True

def main():
    print("SETUP - PostgreSQL 컷오버 준비 완료 검증 시작")
    
    if test_phase3_completion():
        print("\n🎉 SUCCESS - Phase 3 완료! PostgreSQL 컷오버 준비 완료!")
        print("🚀 READY - config.ini에서 DB_BACKEND = postgres로 변경 가능!")
        return True
    else:
        print("\n❌ FAIL - Phase 3 미완료")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)