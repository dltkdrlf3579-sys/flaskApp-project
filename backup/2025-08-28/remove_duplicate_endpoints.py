#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
중복 엔드포인트 제거 스크립트
"""
import re
import shutil
from datetime import datetime
import sys
import io

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def backup_file(filepath):
    """파일 백업 생성"""
    backup_path = f"{filepath}.backup_duplicate_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ 백업 생성: {backup_path}")
    return backup_path

def remove_duplicates():
    """중복 엔드포인트 제거"""
    
    # app.py 백업
    backup_path = backup_file("app.py")
    
    with open('app.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # 제거할 범위 (스크립트가 추적한 중복 함수들)
    # 2674번째 줄 이후부터 시작하는 update_safety_instruction와 update_change_request 제거
    
    new_lines = []
    skip_mode = False
    skip_until_next_route = False
    removed_functions = []
    
    for i, line in enumerate(lines, 1):
        # 2674줄 이후의 중복 함수들 제거
        if i >= 2674:
            # 중복된 update_safety_instruction 시작
            if '@app.route("/update-safety-instruction"' in line:
                skip_mode = True
                skip_until_next_route = True
                removed_functions.append('update_safety_instruction (line 2675)')
                continue
            
            # 중복된 update_change_request 시작  
            if '@app.route("/update-change-request"' in line:
                skip_mode = True
                skip_until_next_route = True
                removed_functions.append('update_change_request (line 2790)')
                continue
            
            # 새로운 라우트나 파일 끝을 만나면 스킵 종료
            if skip_until_next_route:
                # 다음 @app.route를 만나거나 파일 끝
                if line.strip().startswith('@app.route') or line.strip().startswith('if __name__'):
                    skip_mode = False
                    skip_until_next_route = False
                    new_lines.append(line)
                elif skip_mode:
                    continue  # 스킵
                else:
                    new_lines.append(line)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
    
    # 파일 저장
    with open('app.py', 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    
    print("\n제거된 중복 함수:")
    for func in removed_functions:
        print(f"  - {func}")
    
    print(f"\n✅ 중복 엔드포인트 제거 완료")
    print(f"📄 백업 파일: {backup_path}")
    print("\n🔎 기존 엔드포인트 위치:")
    print("  - update_safety_instruction (line 765)")
    print("  - update_change_request (line 1151)")
    
    # 기존 함수들이 파일 경로로 잘 작동하는지 확인 안내
    print("\n⚠️ 주의사항:")
    print("기존 함수들이 첨부파일 경로로 잘 작동하는지 확인 필요")
    print("필요시 기존 함수의 파일 경로 처리 로직 추적 필요")

if __name__ == "__main__":
    remove_duplicates()
