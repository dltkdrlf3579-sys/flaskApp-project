#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
게시판 표준화 테스트 스크립트
각 게시판의 핵심 필드가 제대로 하드코딩되었는지 검증
"""

import json
from database_config import get_db_connection
from datetime import datetime

def test_column_configs():
    """Column Config 테이블 검증"""
    print("\n=== Column Config 테이블 검증 ===")
    
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
            print(f"\n[{table}]")
            
            # detailed_content, attachments가 없는지 확인
            cursor.execute(f"""
                SELECT column_key, column_name, is_active
                FROM {table}
                WHERE column_key IN ('detailed_content', 'attachments', 'created_at')
                ORDER BY column_key
            """)
            
            results = cursor.fetchall()
            
            # 검증
            has_detailed_content = any(r[0] == 'detailed_content' for r in results)
            has_attachments = any(r[0] == 'attachments' for r in results)
            created_at_info = next((r for r in results if r[0] == 'created_at'), None)
            
            print(f"  detailed_content 존재: {'[ERROR] 문제!' if has_detailed_content else '[OK] 정상 (없음)'}")
            print(f"  attachments 존재: {'[ERROR] 문제!' if has_attachments else '[OK] 정상 (없음)'}")
            
            if created_at_info:
                is_inactive = created_at_info[2] == 0
                print(f"  created_at 상태: {'[OK] 정상 (비활성)' if is_inactive else '[ERROR] 문제! (활성상태)'}")
            else:
                print(f"  created_at 상태: [OK] 정상 (컬럼 자체가 없음)")
                
    finally:
        cursor.close()
        conn.close()

def test_template_structure():
    """템플릿 구조 검증"""
    print("\n=== 템플릿 구조 검증 ===")
    
    templates = [
        'templates/safety-instruction-register.html',
        'templates/follow-sop-register.html',
        'templates/full-process-register.html',
        'templates/accident-register.html',
        'templates/change-request-register.html'
    ]
    
    for template_path in templates:
        print(f"\n[{template_path}]")
        try:
            with open(template_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # 핵심 요소 체크
            has_detailed_content = 'detailed_content' in content or 'detailed-content' in content
            has_attachment_import = 'attachment_section.html' in content
            has_include_detailed = 'detailed_content_section.html' in content
            
            print(f"  detailed_content 처리: {'[OK] 있음' if has_detailed_content else '[ERROR] 없음'}")
            print(f"  attachment_section import: {'[OK] 있음' if has_attachment_import else '[ERROR] 없음'}")
            print(f"  detailed_content_section include: {'[OK] 있음' if has_include_detailed else '[ERROR] 없음'}")
            
            # 경고 체크 - 동적 섹션에서 제외되는지
            if 'detailed_content' in content and 'not in' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    if 'detailed_content' in line and 'not in' in line:
                        print(f"  [OK] 라인 {i}: 동적 섹션에서 제외됨")
                        break
                        
        except Exception as e:
            print(f"  [ERROR] 파일 읽기 실패: {e}")

def test_backend_logic():
    """백엔드 로직 검증"""
    print("\n=== 백엔드 로직 검증 ===")
    
    files_to_check = [
        ('app.py', 'register_safety_instruction'),
        ('app.py', 'register_accident'),
        ('add_page_routes.py', 'register_follow_sop'),
        ('add_page_routes.py', 'register_full_process'),
        ('app.py', 'register_change_request')
    ]
    
    for file_path, function_name in files_to_check:
        print(f"\n[{file_path} - {function_name}]")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            if f'def {function_name}' in content:
                print(f"  [OK] 함수 존재")
                
                # created_at 처리 확인
                if 'created_at' in content and 'get_korean_time' in content:
                    print(f"  [OK] created_at 자동 설정")
                else:
                    print(f"  [WARNING] created_at 처리 확인 필요")
                    
                # custom_data 처리 확인
                if 'custom_data' in content and 'json.dumps' in content:
                    print(f"  [OK] custom_data JSON 처리")
                else:
                    print(f"  [WARNING] custom_data 처리 확인 필요")
                    
            else:
                print(f"  [ERROR] 함수를 찾을 수 없음")
                
        except Exception as e:
            print(f"  [ERROR] 파일 읽기 실패: {e}")

def test_common_template():
    """공통 템플릿 검증"""
    print("\n=== 공통 템플릿 검증 ===")
    
    template_path = 'templates/includes/detailed_content_section.html'
    
    try:
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        print(f"[{template_path}]")
        print(f"  파일 크기: {len(content)} bytes")
        
        # 필수 요소 체크
        checks = [
            ('textarea', 'textarea 태그'),
            ('detailed-content', 'detailed-content ID'),
            ('detailed_content', 'detailed_content name'),
            ('section-title', '섹션 타이틀'),
            ('상세내용', '상세내용 텍스트')
        ]
        
        for keyword, description in checks:
            if keyword in content:
                print(f"  [OK] {description} 존재")
            else:
                print(f"  [ERROR] {description} 없음")
                
    except Exception as e:
        print(f"  [ERROR] 파일 읽기 실패: {e}")

def main():
    print("=" * 60)
    print("게시판 표준화 테스트")
    print("=" * 60)
    
    # 1. Column Config 검증
    test_column_configs()
    
    # 2. 템플릿 구조 검증
    test_template_structure()
    
    # 3. 백엔드 로직 검증
    test_backend_logic()
    
    # 4. 공통 템플릿 검증
    test_common_template()
    
    print("\n" + "=" * 60)
    print("테스트 완료!")
    print("=" * 60)

if __name__ == "__main__":
    main()