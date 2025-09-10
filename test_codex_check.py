#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
코덱스 지적사항 정밀 검증
PostgreSQL timestamp 처리와 INSERT OR REPLACE 잔존 확인
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
from db.upsert import safe_upsert, _upsert_postgresql
import logging

# 디버깅 로깅 활성화
logging.basicConfig(level=logging.DEBUG)

def test_postgresql_timestamp_handling():
    """PostgreSQL timestamp 처리 검증"""
    print("\n=== PostgreSQL timestamp 처리 검증 ===")
    
    # Mock PostgreSQL cursor
    class MockPGCursor:
        def __init__(self):
            self.executed_sql = None
            self.executed_values = None
            self.rowcount = 1
            
        def execute(self, sql, values=None):
            self.executed_sql = sql
            self.executed_values = values
            print(f"EXECUTED SQL: {sql}")
            print(f"EXECUTED VALUES: {values}")
    
    cursor = MockPGCursor()
    
    # 테스트 데이터 (timestamp 컬럼들이 None)
    test_data = {
        'issue_number': 'TEST-001',
        'detailed_content': '테스트 내용',
        'updated_at': None,  # 이게 PostgreSQL에서 제대로 처리되는가?
        'created_at': None,
        'sync_date': None
    }
    
    conflict_cols = ['issue_number']
    update_cols = ['detailed_content', 'updated_at']
    
    # PostgreSQL UPSERT 실행
    result = _upsert_postgresql(cursor, 'test_table', test_data, conflict_cols, update_cols)
    
    # 검증
    sql = cursor.executed_sql
    values = cursor.executed_values
    
    # INSERT VALUES 부분에서 timestamp 컬럼이 제외되었는지 확인
    insert_part = sql.split('VALUES')[0]  # INSERT INTO table (columns) 부분
    assert 'updated_at' not in insert_part, f"updated_at이 INSERT 컬럼에 포함됨: {insert_part}"
    assert 'created_at' not in insert_part, f"created_at이 INSERT 컬럼에 포함됨: {insert_part}"
    assert 'sync_date' not in insert_part, f"sync_date이 INSERT 컬럼에 포함됨: {insert_part}"
    
    # UPDATE SET에 CURRENT_TIMESTAMP가 있는지 확인
    assert 'updated_at = CURRENT_TIMESTAMP' in sql, f"UPDATE에 CURRENT_TIMESTAMP 없음: {sql}"
    
    # VALUES에 None이 바인딩되지 않았는지 확인
    assert None not in values, f"VALUES에 None이 포함됨: {values}"
    
    # VALUES의 개수가 INSERT 컬럼 개수와 일치하는지 확인
    placeholders = sql.split('VALUES')[1].split('ON CONFLICT')[0].strip()
    placeholder_count = placeholders.count('%s')
    assert len(values) == placeholder_count, f"VALUES 개수 불일치: {len(values)} vs {placeholder_count}"
    
    print("✅ PostgreSQL timestamp 처리 정상 작동!")
    return True

def test_insert_or_replace_residue():
    """INSERT OR REPLACE 잔존 검증"""
    print("\n=== INSERT OR REPLACE 잔존 검증 ===")
    
    # 운영 파일들에서 INSERT OR REPLACE 검색
    production_files = [
        'app.py', 'board_services.py', 'column_sync_service.py', 
        'database_config.py', 'update_change_request_columns.py'
    ]
    
    found_issues = []
    
    for filename in production_files:
        if not os.path.exists(filename):
            continue
            
        with open(filename, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        for i, line in enumerate(lines, 1):
            if 'INSERT OR REPLACE' in line:
                # 조건부 SQLite 경로인지 확인
                context = lines[max(0, i-5):i+3]  # 앞뒤 5줄 컨텍스트
                context_str = ''.join(context)
                
                if 'else:' in context_str or 'SQLite' in context_str:
                    print(f"✅ {filename}:{i} - 조건부 SQLite 경로")
                else:
                    found_issues.append(f"{filename}:{i}")
                    print(f"❌ {filename}:{i} - 무조건 실행되는 INSERT OR REPLACE")
    
    if found_issues:
        print(f"❌ 문제있는 INSERT OR REPLACE: {found_issues}")
        return False
    else:
        print("✅ 모든 INSERT OR REPLACE가 조건부 처리됨!")
        return True

def test_safe_upsert_coverage():
    """safe_upsert 적용 범위 검증"""
    print("\n=== safe_upsert 적용 범위 검증 ===")
    
    from db.upsert import UPSERT_REGISTRY
    
    print(f"✅ UPSERT 레지스트리 테이블: {len(UPSERT_REGISTRY)}개")
    
    # 주요 테이블 확인
    critical_tables = [
        'safety_instructions_cache', 'dropdown_option_codes_v2',
        'safety_instruction_details', 'sync_state', 'content_sync_state'
    ]
    
    missing = []
    for table in critical_tables:
        if table in UPSERT_REGISTRY:
            config = UPSERT_REGISTRY[table]
            print(f"✅ {table}: {config['conflict_cols']} / {len(config['update_cols'])}개 업데이트")
        else:
            missing.append(table)
            print(f"❌ {table}: 레지스트리 누락")
    
    if missing:
        print(f"❌ 레지스트리 누락 테이블: {missing}")
        return False
    else:
        print("✅ 모든 중요 테이블이 레지스트리에 등록됨!")
        return True

def main():
    print("SETUP - 코덱스 지적사항 정밀 검증 시작")
    
    tests = [
        test_postgresql_timestamp_handling,
        test_insert_or_replace_residue, 
        test_safe_upsert_coverage
    ]
    
    results = []
    for test_func in tests:
        try:
            result = test_func()
            results.append(result)
        except Exception as e:
            print(f"❌ {test_func.__name__} 실패: {e}")
            results.append(False)
    
    if all(results):
        print("\n🎉 SUCCESS - 모든 코덱스 지적사항 해결 완료!")
        print("🚀 READY - PostgreSQL 컷오버 문제없음!")
        return True
    else:
        print(f"\n❌ FAIL - 일부 문제 발견: {results}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)