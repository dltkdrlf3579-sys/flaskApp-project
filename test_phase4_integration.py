#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4 통합 테스트: 실제 서비스들의 ID 생성 테스트
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
import json

def test_phase4_integration():
    """Phase 4 변경사항이 실제로 작동하는지 통합 테스트"""
    print("\n=== Phase 4 통합 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    db_type = 'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'
    print(f"DB 연결: {db_type}")
    
    try:
        # 1. 임시 테이블들 생성 (실제 구조와 유사하게)
        test_tables = [
            """CREATE TEMP TABLE test_partner_change_requests (
                id INTEGER PRIMARY KEY,
                request_number TEXT,
                requester_name TEXT,
                company_name TEXT,
                status TEXT DEFAULT 'requested',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TEMP TABLE test_person_master (
                id INTEGER PRIMARY KEY,
                name TEXT,
                department TEXT,
                company_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )""",
            """CREATE TEMP TABLE test_attachments (
                id INTEGER PRIMARY KEY,
                item_id INTEGER,
                file_name TEXT,
                file_size INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )"""
        ]
        
        for sql in test_tables:
            cursor.execute(sql)
        print("✅ 테스트 테이블 생성 완료")
        
        # 2. 실제 사용 패턴 테스트들
        test_cases = [
            # app.py pattern: partner_change_requests
            {
                'name': 'Partner Change Request',
                'table': 'test_partner_change_requests',
                'sql': """INSERT INTO test_partner_change_requests 
                         (request_number, requester_name, company_name, status)
                         VALUES (?, ?, ?, ?)""",
                'values': ('REQ-2025-001', '홍길동', '테스트회사', 'requested')
            },
            # app.py pattern: person_master
            {
                'name': 'Person Master',
                'table': 'test_person_master', 
                'sql': """INSERT INTO test_person_master (name, department, company_name)
                         VALUES (?, ?, ?)""",
                'values': ('김테스트', '개발팀', '테스트회사')
            },
            # board_services pattern: attachments
            {
                'name': 'File Attachment',
                'table': 'test_attachments',
                'sql': """INSERT INTO test_attachments (item_id, file_name, file_size)
                         VALUES (?, ?, ?)""",
                'values': (1, 'test.pdf', 1024)
            }
        ]
        
        all_ids = []
        for case in test_cases:
            # execute_with_returning_id 사용
            cursor.execute_with_returning_id(case['sql'], case['values'])
            returned_id = cursor.lastrowid
            
            print(f"✅ {case['name']}: ID={returned_id}")
            
            # 실제 데이터 확인
            cursor.execute(f"SELECT id FROM {case['table']} WHERE id = ?", (returned_id,))
            row = cursor.fetchone()
            
            if row:
                actual_id = row[0] if not hasattr(row, 'keys') else row['id']
                if actual_id == returned_id:
                    print(f"   ✓ 데이터 검증 성공")
                    all_ids.append(returned_id)
                else:
                    print(f"   ❌ ID 불일치: {returned_id} vs {actual_id}")
                    return False
            else:
                print(f"   ❌ 데이터를 찾을 수 없음")
                return False
        
        # 3. 모든 ID가 유니크한지 확인 (다른 테이블이므로 중복 가능)
        print(f"✅ 생성된 ID들: {all_ids}")
        print("✅ 모든 실제 사용 패턴 테스트 통과")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ 통합 테스트 실패: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def test_error_handling():
    """에러 처리 확인"""
    print("\n=== 에러 처리 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 존재하지 않는 테이블에 INSERT 시도
        try:
            cursor.execute_with_returning_id(
                "INSERT INTO nonexistent_table (name) VALUES (?)",
                ('테스트',)
            )
            print("❌ 에러가 발생해야 하는데 성공함")
            return False
        except Exception as e:
            print(f"✅ 예상된 에러 처리: {type(e).__name__}")
            
        # lastrowid가 설정되지 않은 상태 확인
        print(f"✅ 에러 후 lastrowid: {cursor.lastrowid}")
        return True
        
    except Exception as e:
        print(f"❌ 에러 처리 테스트 실패: {e}")
        return False
    finally:
        conn.close()

def main():
    print("SETUP - Phase 4 통합 테스트 시작")
    
    tests = [
        test_phase4_integration,
        test_error_handling
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_func.__name__} 예외: {e}")
            results.append(False)
    
    # 결과
    passed = sum(results)
    total = len(results)
    
    print(f"\n=== Phase 4 통합 테스트 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 4 통합 테스트 완료!")
        print("🚀 모든 실제 사용 패턴에서 lastrowid 정상 작동!")
        print("✨ PostgreSQL 전환 완료 준비!")
        return True
    else:
        print("⚠️  일부 통합 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)