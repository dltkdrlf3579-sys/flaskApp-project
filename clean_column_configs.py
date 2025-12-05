#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Column Config 정리 스크립트
핵심 필드(detailed_content, attachments) 제거
created_at은 시스템 필드로 표시
"""

from database_config import get_db_connection
from datetime import datetime

def clean_column_configs():
    """핵심 필드 제거 및 시스템 필드 설정"""
    
    tables = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'accident_column_config'
    ]
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        for table in tables:
            print(f"\n[{table}] 처리 중...")
            
            # 1. detailed_content, attachments 필드 제거
            cursor.execute(f"""
                DELETE FROM {table} 
                WHERE column_key IN ('detailed_content', 'attachments')
            """)
            deleted_count = cursor.rowcount
            print(f"  - 삭제된 필드: {deleted_count}개")
            
            # 2. created_at은 시스템 필드로 표시 (is_active = 0)
            # 주의: is_system 컬럼이 없으므로 is_active를 0으로 설정하여 비활성화
            cursor.execute(f"""
                UPDATE {table} 
                SET is_active = 0
                WHERE column_key = 'created_at'
            """)
            updated_count = cursor.rowcount
            print(f"  - 시스템 필드로 설정: {updated_count}개")
            
            # 3. 현재 상태 확인
            cursor.execute(f"""
                SELECT column_key, column_name, is_active 
                FROM {table}
                WHERE column_key IN ('created_at', 'detailed_content', 'attachments')
                ORDER BY column_key
            """)
            
            remaining = cursor.fetchall()
            if remaining:
                print(f"  - 남은 필드 상태:")
                for row in remaining:
                    print(f"    * {row[0]}: {row[1]} (active={row[2]})")
        
        conn.commit()
        print("\n[SUCCESS] 모든 테이블 정리 완료!")
        
        # 정리 결과 요약
        print("\n=== 정리 결과 요약 ===")
        for table in tables:
            cursor.execute(f"""
                SELECT COUNT(*) as total,
                       SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active
                FROM {table}
            """)
            result = cursor.fetchone()
            print(f"{table}: 전체 {result[0]}개, 활성 {result[1]}개")
        
    except Exception as e:
        conn.rollback()
        print(f"[ERROR] 정리 중 오류 발생: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def verify_cleanup():
    """정리 결과 검증"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'change_request_column_config',
        'accident_column_config'
    ]
    
    print("\n=== 정리 결과 검증 ===")
    
    try:
        for table in tables:
            cursor.execute(f"""
                SELECT column_key, column_name, is_active
                FROM {table}
                WHERE column_key IN ('created_at', 'detailed_content', 'attachments')
                ORDER BY column_key
            """)
            
            results = cursor.fetchall()
            print(f"\n{table}:")
            if results:
                for row in results:
                    status = "시스템" if row[2] == 0 else "활성"
                    print(f"  - {row[0]}: {row[1]} [{status}]")
            else:
                print(f"  - detailed_content, attachments 제거 완료")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    print("=" * 60)
    print("Column Config 정리 스크립트")
    print("=" * 60)
    
    # 정리 실행
    clean_column_configs()
    
    # 결과 검증
    verify_cleanup()