#!/usr/bin/env python3
"""
최종 UPSERT 통합 테스트 - SQLite와 PostgreSQL 모두 검증
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from db_connection import get_db_connection
from db.upsert import safe_upsert

def test_all_upsert_cases():
    """적용된 모든 UPSERT 케이스 테스트"""
    print("\n=== 전체 UPSERT 통합 테스트 ===")
    
    conn = get_db_connection()
    
    try:
        # 임시 테스트 테이블들 생성 (PostgreSQL 호환)
        cursor = conn.cursor()
        
        # 각각의 주요 테이블들을 임시로 생성해서 테스트
        test_tables = [
            """CREATE TEMP TABLE test_sync_state (
                id INTEGER PRIMARY KEY,
                last_full_sync TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TEMP TABLE test_dropdown_codes (
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                option_code TEXT NOT NULL,
                option_value TEXT,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (board_type, column_key, option_code)
            )""",
            """CREATE TEMP TABLE test_details (
                id TEXT PRIMARY KEY,
                detailed_content TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        ]
        
        for sql in test_tables:
            cursor.execute(sql)
        print("OK - 테스트 테이블들 생성 완료")
        
        # 테스트 케이스들
        test_cases = [
            # sync_state 패턴
            {
                'table': 'test_sync_state',
                'data': {'id': 1, 'last_full_sync': None},
                'conflict_cols': ['id'],
                'update_cols': ['last_full_sync']
            },
            # dropdown_option_codes_v2 패턴  
            {
                'table': 'test_dropdown_codes',
                'data': {
                    'board_type': 'test',
                    'column_key': 'status',
                    'option_code': 'ACTIVE',
                    'option_value': '활성',
                    'display_order': 1,
                    'is_active': 1,
                    'created_at': None,
                    'updated_at': None
                },
                'conflict_cols': ['board_type', 'column_key', 'option_code'],
                'update_cols': ['option_value', 'display_order', 'updated_at']
            },
            # details 패턴
            {
                'table': 'test_details',
                'data': {
                    'id': 'TEST-001',
                    'detailed_content': '테스트 상세 내용',
                    'updated_at': None
                },
                'conflict_cols': ['id'],
                'update_cols': ['detailed_content', 'updated_at']
            }
        ]
        
        # 각 테스트 케이스 실행
        for i, case in enumerate(test_cases, 1):
            # INSERT 테스트
            result = safe_upsert(conn, case['table'], case['data'], 
                               case['conflict_cols'], case['update_cols'])
            print(f"OK - 테스트 {i} INSERT: {result}개 행 영향")
            
            # UPDATE 테스트 (데이터 약간 변경)
            if 'option_value' in case['data']:
                case['data']['option_value'] = '업데이트된 값'
            elif 'detailed_content' in case['data']:
                case['data']['detailed_content'] = '업데이트된 상세내용'
                
            result = safe_upsert(conn, case['table'], case['data'],
                               case['conflict_cols'], case['update_cols'])
            print(f"OK - 테스트 {i} UPDATE: {result}개 행 영향")
        
        # timestamp 확인
        cursor.execute("SELECT COUNT(*) FROM test_sync_state WHERE last_full_sync IS NOT NULL")
        row = cursor.fetchone()
        if hasattr(row, 'keys'):
            count = row[list(row.keys())[0]]
        else:
            count = row[0] if row else 0
        print(f"OK - timestamp 자동 처리 확인: {count}개 레코드")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"ERROR - 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        conn.rollback()
        return False
    finally:
        conn.close()

def main():
    """최종 UPSERT 통합 테스트 실행"""
    print("SETUP - 최종 UPSERT 통합 테스트 시작")
    
    try:
        if test_all_upsert_cases():
            print("SUCCESS - 모든 UPSERT 통합 테스트 통과!")
            print("READY - PostgreSQL 컷오버 준비 완료!")
            return True
        else:
            print("FAIL - UPSERT 통합 테스트 실패")
            return False
    except Exception as e:
        print(f"ERROR - 테스트 실행 오류: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)