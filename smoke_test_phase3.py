#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 3 권장 스모크 테스트 (수정 없음, 검토 목적)
PostgreSQL 모드에서 핵심 UPSERT 경로들 검증
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
from db.upsert import safe_upsert
import configparser
import logging

# 디버깅 로깅 비활성화 (스모크 테스트용)
logging.basicConfig(level=logging.WARNING)

def check_config():
    """현재 설정 확인"""
    print("\n=== 현재 설정 확인 ===")
    
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    db_backend = config.get('DATABASE', 'DB_BACKEND', fallback='sqlite')
    external_db = config.get('DATABASE', 'EXTERNAL_DB_ENABLED', fallback='false')
    
    print(f"DB_BACKEND: {db_backend}")
    print(f"EXTERNAL_DB_ENABLED: {external_db}")
    
    return db_backend, external_db

def smoke_safety_instructions():
    """안전지시서 UPSERT 경로 검증"""
    print("\n=== 안전지시서 UPSERT 스모크 ===")
    
    conn = get_db_connection()
    db_type = 'PostgreSQL' if hasattr(conn, 'is_postgres') and conn.is_postgres else 'SQLite'
    print(f"DB 연결: {db_type}")
    
    try:
        # safety_instructions_cache 테스트 (실제 테이블 스키마에 맞게)
        cache_data = {
            'issue_number': 'SMOKE-001',
            'detailed_content': '스모크 테스트',
            'custom_data': '{}',
            # updated_at 컬럼이 없으므로 제외
        }
        result1 = safe_upsert(conn, 'safety_instructions_cache', cache_data)
        print(f"✅ safety_instructions_cache UPSERT: {result1}행")
        
        # safety_instruction_details 테스트
        detail_data = {
            'issue_number': 'SMOKE-001',
            'detailed_content': '상세 내용',
            'updated_at': None
        }
        result2 = safe_upsert(conn, 'safety_instruction_details', detail_data)
        print(f"✅ safety_instruction_details UPSERT: {result2}행")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ 안전지시서 UPSERT 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def smoke_dropdown_codes():
    """드롭다운 코드 UPSERT 검증"""
    print("\n=== 드롭다운 코드 UPSERT 스모크 ===")
    
    conn = get_db_connection()
    
    try:
        # dropdown_option_codes_v2 테스트
        dropdown_data = {
            'board_type': 'smoke_test',
            'column_key': 'status',
            'option_code': 'TESTING',
            'option_value': '테스트중',
            'display_order': 1,
            'is_active': 1,
            'updated_at': None
        }
        result = safe_upsert(conn, 'dropdown_option_codes_v2', dropdown_data)
        print(f"✅ dropdown_option_codes_v2 UPSERT: {result}행")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ 드롭다운 코드 UPSERT 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def smoke_details_tables():
    """상세 테이블들 UPSERT 검증"""
    print("\n=== 상세 테이블 UPSERT 스모크 ===")
    
    conn = get_db_connection()
    
    try:
        # partner_details 테스트
        partner_data = {
            'business_number': '999-99-99999',
            'detailed_content': '협력사 상세',
            'updated_at': None
        }
        result1 = safe_upsert(conn, 'partner_details', partner_data)
        print(f"✅ partner_details UPSERT: {result1}행")
        
        # accident_details 테스트  
        accident_data = {
            'accident_number': 'ACC-SMOKE-001',
            'detailed_content': '사고 상세',
            'updated_at': None
        }
        result2 = safe_upsert(conn, 'accident_details', accident_data)
        print(f"✅ accident_details UPSERT: {result2}행")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ 상세 테이블 UPSERT 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def smoke_sync_tables():
    """동기화 테이블 UPSERT 검증"""
    print("\n=== 동기화 테이블 UPSERT 스모크 ===")
    
    conn = get_db_connection()
    
    try:
        # sync_state 테스트
        sync_data = {
            'id': 1,
            'last_full_sync': None  # timestamp 자동 처리
        }
        result1 = safe_upsert(conn, 'sync_state', sync_data)
        print(f"✅ sync_state UPSERT: {result1}행")
        
        # content_sync_state 테스트
        content_data = {
            'name': 'smoke_test',
            'first_sync_done': 1,
            'first_sync_at': None
        }
        result2 = safe_upsert(conn, 'content_sync_state', content_data)
        print(f"✅ content_sync_state UPSERT: {result2}행")
        
        conn.commit()
        return True
        
    except Exception as e:
        print(f"❌ 동기화 테이블 UPSERT 실패: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_timestamp_handling():
    """timestamp 처리 확인"""
    print("\n=== Timestamp 처리 확인 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # 방금 삽입한 데이터의 timestamp 확인 (실제 컬럼에 맞게)
        cursor.execute("""
            SELECT issue_number, created_at, synced_at
            FROM safety_instructions_cache 
            WHERE issue_number = 'SMOKE-001'
        """)
        row = cursor.fetchone()
        
        if row:
            if hasattr(row, 'keys'):
                issue_number = row['issue_number']
                created_at = row['created_at']
                synced_at = row['synced_at']
            else:
                issue_number, created_at, synced_at = row[0], row[1], row[2]
                
            print(f"✅ issue_number: {issue_number}")
            print(f"✅ created_at: {created_at}")
            print(f"✅ synced_at: {synced_at}")
            
            if created_at:  # synced_at은 NULL일 수 있음
                print("✅ Timestamp 처리 확인됨!")
                return True
            else:
                print("❌ created_at가 NULL로 설정됨")
                return False
        else:
            print("❌ 테스트 데이터를 찾을 수 없음")
            return False
            
    except Exception as e:
        print(f"❌ Timestamp 확인 실패: {e}")
        return False
    finally:
        conn.close()

def main():
    print("SETUP - Phase 3 권장 스모크 테스트 시작")
    print("목적: 수정 없이 PostgreSQL 호환성 검증")
    
    # 설정 확인
    db_backend, external_db = check_config()
    
    # 스모크 테스트들
    tests = [
        smoke_safety_instructions,
        smoke_dropdown_codes,
        smoke_details_tables,
        smoke_sync_tables,
        check_timestamp_handling
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
    
    print(f"\n=== 스모크 테스트 결과 ===")
    print(f"통과: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 3 완벽 작동!")
        print("🚀 PostgreSQL 컷오버 준비 완료!")
        print("💡 권장: Phase 4(lastrowid) 진행 또는 운영 배포")
        return True
    else:
        print("⚠️  일부 테스트 실패 - 추가 검토 필요")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)