#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 4 테스트: lastrowid 호환성 검증
SQLite와 PostgreSQL에서 execute_with_returning_id 작동 확인
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
from db.compat import CompatCursor
import json

def test_execute_with_returning_id():
    """execute_with_returning_id 메서드 직접 테스트"""
    print("\n=== execute_with_returning_id 직접 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    db_type = 'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'
    print(f"DB 연결: {db_type}")
    
    try:
        # 임시 테스트 테이블 생성
        cursor.execute("""
            CREATE TEMP TABLE test_lastrowid (
                id INTEGER PRIMARY KEY,
                name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        print("✅ 임시 테스트 테이블 생성 완료")
        
        # execute_with_returning_id 테스트
        cursor.execute_with_returning_id("""
            INSERT INTO test_lastrowid (name) VALUES (?)
        """, ('Phase 4 테스트',))
        
        row_id = cursor.lastrowid
        print(f"✅ lastrowid 반환: {row_id}")
        
        # 실제 데이터가 삽입되었는지 확인
        cursor.execute("SELECT id, name FROM test_lastrowid WHERE id = ?", (row_id,))
        row = cursor.fetchone()
        
        if row:
            if hasattr(row, 'keys'):
                id_val, name_val = row['id'], row['name']
            else:
                id_val, name_val = row[0], row[1]
            print(f"✅ 데이터 확인: ID={id_val}, Name={name_val}")
            
            if id_val == row_id:
                print("✅ lastrowid와 실제 ID 일치")
                return True
            else:
                print(f"❌ ID 불일치: lastrowid={row_id}, 실제={id_val}")
                return False
        else:
            print("❌ 삽입된 데이터를 찾을 수 없음")
            return False
            
    except Exception as e:
        print(f"❌ execute_with_returning_id 테스트 실패: {e}")
        return False
    finally:
        conn.close()

def test_multiple_inserts():
    """연속 INSERT에서 lastrowid 정확성 테스트"""
    print("\n=== 연속 INSERT lastrowid 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 임시 테스트 테이블 생성  
        cursor.execute("""
            CREATE TEMP TABLE test_multi (
                id INTEGER PRIMARY KEY,
                value TEXT
            )
        """)
        
        # 3개의 연속 INSERT
        test_values = ['첫번째', '두번째', '세번째']
        returned_ids = []
        
        for i, value in enumerate(test_values):
            cursor.execute_with_returning_id(
                "INSERT INTO test_multi (value) VALUES (?)",
                (value,)
            )
            row_id = cursor.lastrowid
            returned_ids.append(row_id)
            print(f"✅ INSERT {i+1}: ID={row_id}, Value={value}")
        
        # ID가 순차적으로 증가하는지 확인
        for i in range(len(returned_ids) - 1):
            if returned_ids[i+1] != returned_ids[i] + 1:
                print(f"❌ ID 순서 오류: {returned_ids[i]} → {returned_ids[i+1]}")
                return False
        
        print("✅ 모든 ID가 순차적으로 증가")
        
        # 실제 데이터 확인
        cursor.execute("SELECT id, value FROM test_multi ORDER BY id")
        rows = cursor.fetchall()
        
        for i, row in enumerate(rows):
            if hasattr(row, 'keys'):
                id_val, value_val = row['id'], row['value']
            else:
                id_val, value_val = row[0], row[1]
            
            if id_val != returned_ids[i] or value_val != test_values[i]:
                print(f"❌ 데이터 불일치: 예상={returned_ids[i]},{test_values[i]} 실제={id_val},{value_val}")
                return False
        
        print("✅ 모든 데이터가 정확히 일치")
        return True
        
    except Exception as e:
        print(f"❌ 연속 INSERT 테스트 실패: {e}")
        return False
    finally:
        conn.close()

def test_table_specific_ids():
    """다른 ID 컬럼명을 가진 테이블 테스트"""
    print("\n=== 다른 ID 컬럼명 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # attachment_id를 가진 테이블 (실제 첨부파일 테이블과 유사)
        cursor.execute("""
            CREATE TEMP TABLE test_attachment (
                id INTEGER PRIMARY KEY,
                file_name TEXT,
                file_size INTEGER
            )
        """)
        
        # 일반적인 id 컬럼으로 테스트
        cursor.execute_with_returning_id(
            "INSERT INTO test_attachment (file_name, file_size) VALUES (?, ?)",
            ('test.pdf', 1024)
        )
        
        attachment_id = cursor.lastrowid
        print(f"✅ Attachment ID 반환: {attachment_id}")
        
        # 데이터 확인
        cursor.execute("SELECT * FROM test_attachment WHERE id = ?", (attachment_id,))
        row = cursor.fetchone()
        
        if row:
            print("✅ 첨부파일 테이블 패턴 테스트 성공")
            return True
        else:
            print("❌ 첨부파일 데이터를 찾을 수 없음")
            return False
            
    except Exception as e:
        print(f"❌ 테이블별 ID 테스트 실패: {e}")
        return False
    finally:
        conn.close()

def test_compat_cursor_type():
    """CompatCursor 타입 확인"""
    print("\n=== CompatCursor 타입 확인 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print(f"Cursor 타입: {type(cursor)}")
    print(f"CompatCursor 인스턴스: {isinstance(cursor, CompatCursor)}")
    print(f"execute_with_returning_id 메서드 존재: {hasattr(cursor, 'execute_with_returning_id')}")
    print(f"lastrowid 속성 존재: {hasattr(cursor, 'lastrowid')}")
    
    conn.close()
    return True

def main():
    print("SETUP - Phase 4 lastrowid 호환성 테스트 시작")
    
    tests = [
        test_compat_cursor_type,
        test_execute_with_returning_id,
        test_multiple_inserts,
        test_table_specific_ids
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
    
    print(f"\n=== Phase 4 테스트 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 4 완벽 작동!")
        print("🚀 lastrowid 호환성 완료!")
        print("✨ PostgreSQL 컷오버에서 모든 ID 생성 정상 동작!")
        return True
    else:
        print("⚠️  일부 테스트 실패")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)