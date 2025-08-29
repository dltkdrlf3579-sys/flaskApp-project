#!/usr/bin/env python3
"""
app.py 보드 격리 후반부 정리 스크립트
- dropdown_option_codes v1 → v2 참조 변경
- 제거된 API 엔드포인트 제거
- 레거시 함수 제거
"""
import re
import os
import shutil
from datetime import datetime

def backup_file(filepath):
    """파일 백업 생성"""
    backup_path = f"{filepath}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    shutil.copy2(filepath, backup_path)
    print(f"✅ 백업 생성: {backup_path}")
    return backup_path

def fix_dropdown_v1_to_v2(content):
    """dropdown_option_codes v1 참조를 v2로 변경"""
    changes = 0
    
    # v1 테이블 참조 패턴들
    patterns = [
        # SELECT FROM dropdown_option_codes (column_key, option_code)
        (r'SELECT\s+(.+?)\s+FROM\s+dropdown_option_codes\s+WHERE\s+column_key\s*=\s*\?\s+AND\s+option_code\s*=\s*\?',
         r'SELECT \1 FROM dropdown_option_codes_v2 WHERE board_type = ? AND column_key = ? AND option_code = ?'),
        
        # SELECT FROM dropdown_option_codes (column_key만)
        (r'SELECT\s+(.+?)\s+FROM\s+dropdown_option_codes\s+WHERE\s+column_key\s*=\s*\?',
         r'SELECT \1 FROM dropdown_option_codes_v2 WHERE board_type = ? AND column_key = ?'),
        
        # INSERT INTO dropdown_option_codes
        (r'INSERT\s+INTO\s+dropdown_option_codes\s*\(\s*column_key,\s*option_code,\s*option_value,\s*display_order,\s*is_active\s*\)',
         r'INSERT INTO dropdown_option_codes_v2 (board_type, column_key, option_code, option_value, display_order, is_active)'),
        
        # UPDATE dropdown_option_codes
        (r'UPDATE\s+dropdown_option_codes\s+SET',
         r'UPDATE dropdown_option_codes_v2 SET'),
         
        # DELETE FROM dropdown_option_codes
        (r'DELETE\s+FROM\s+dropdown_option_codes\s+WHERE',
         r'DELETE FROM dropdown_option_codes_v2 WHERE'),
    ]
    
    modified_content = content
    for pattern, replacement in patterns:
        matches = re.findall(pattern, modified_content, re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if matches:
            modified_content = re.sub(pattern, replacement, modified_content, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
            changes += len(matches)
            print(f"  - {pattern[:50]}... → {len(matches)}개 변경")
    
    # 파라미터 정합성 주의 안내
    if changes > 0:
        print(f"\n⚠️  주의: board_type 파라미터 추가가 필요한 곳이 있을 수 있습니다.")
        print("  자동으로 확인해야 할 패턴:")
        print("  - cursor.execute() 호출 시 파라미터에 board_type 추가")
        print("  - (column_key, code) → (board_type, column_key, code)")
    
    return modified_content, changes

def remove_legacy_endpoints(content):
    """레거시 API 엔드포인트 제거"""
    legacy_endpoints = [
        '/api/accident-columns',
        '/api/safety-instruction-columns', 
        '/api/change-request-columns',
        '/api/dropdown-codes'
    ]
    
    # 엔드포인트 블록을 찾아 주석 처리
    lines = content.split('\n')
    modified_lines = []
    in_legacy_route = False
    indent_level = 0
    removed_count = 0
    
    for i, line in enumerate(lines):
        # 제거할 엔드포인트 라우트 시작 감지
        if any(endpoint in line for endpoint in legacy_endpoints) and '@app.route' in line:
            in_legacy_route = True
            indent_level = len(line) - len(line.lstrip())
            modified_lines.append(f"# REMOVED_LEGACY: {line}")
            removed_count += 1
            continue
        
        # 라우트 블록 처리
        if in_legacy_route:
            current_indent = len(line) - len(line.lstrip())
            # 같은 레벨의 새로운 데코레이터나 함수가 나오면 종료
            if line.strip() and (current_indent <= indent_level) and (line.strip().startswith('@') or line.strip().startswith('def ')):
                in_legacy_route = False
                # 현재 라인이 또 다른 레거시 라우트인지 확인 후 처리
                if any(endpoint in line for endpoint in legacy_endpoints) and '@app.route' in line:
                    in_legacy_route = True
                    indent_level = current_indent
                    modified_lines.append(f"# REMOVED_LEGACY: {line}")
                    removed_count += 1
                    continue
                else:
                    modified_lines.append(line)
            else:
                modified_lines.append(f"# REMOVED_LEGACY: {line}")
        else:
            modified_lines.append(line)
    
    print(f"→ {removed_count}개 레거시 엔드포인트 제거")
    return '\n'.join(modified_lines), removed_count

def remove_legacy_function(content):
    """레거시 convert_code_to_value 함수 제거"""
    # 함수 본문의 찾기 후 제거
    pattern = r'def convert_code_to_value\(column_key, code\):.*?(?=\ndef |\Z)'
    
    matches = re.findall(pattern, content, re.DOTALL)
    if matches:
        content = re.sub(pattern, '# REMOVED_LEGACY: convert_code_to_value function removed\n', content, flags=re.DOTALL)
        print(f"→ convert_code_to_value 레거시 함수 제거")
        return content, 1
    
    return content, 0

def fix_safety_instruction_fallback(content):
    """safety_instruction 폴백 로직 제거"""
    # safety_instruction API에서 accident_column_config 참조 제거
    pattern = r'''
        # safety_instruction_column_config가 없을 때 accident 사용하는 패턴
        if\s+not\s+columns:.*?
        columns\s*=\s*conn\.execute\(.*?accident_column_config.*?\)\.fetchall\(\)
    '''
    
    matches = re.findall(pattern, content, re.VERBOSE | re.DOTALL)
    if matches:
        content = re.sub(pattern, 
                         '# REMOVED_LEGACY: Fallback to accident_column_config removed',
                         content, 
                         flags=re.VERBOSE | re.DOTALL)
        print(f"→ safety_instruction 폴백 로직 {len(matches)}개 제거")
        return content, len(matches)
    
    return content, 0

def add_board_type_parameters(content):
    """board_type 파라미터 추가가 필요한지 분석"""
    # convert_code_to_value_scoped 호출 내 board_type 확인
    pattern = r"convert_code_to_value_scoped\('([^']+)',\s*([^,]+),\s*([^)]+)\)"
    matches = re.findall(pattern, content)
    
    board_types_used = set()
    for match in matches:
        board_types_used.add(match[0])
    
    print(f"\n현재 사용 중인 board_type:")
    for board_type in sorted(board_types_used):
        count = len([m for m in matches if m[0] == board_type])
        print(f"  - {board_type}: {count}개")
    
    return content

def main():
    """메인 실행 함수"""
    print("=" * 60)
    print("▶ app.py 보드 격리 정리 작업")
    print("=" * 60)
    
    app_path = "app.py"
    
    if not os.path.exists(app_path):
        print(f"❌ {app_path} 파일을 찾을 수 없습니다.")
        return
    
    # 1. 백업 생성
    backup_path = backup_file(app_path)
    
    # 2. 파일 읽기
    with open(app_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    total_changes = 0
    
    # 3. dropdown v1 → v2 변경
    print("\n[1] dropdown_option_codes v1 → v2 변경")
    content, changes = fix_dropdown_v1_to_v2(content)
    total_changes += changes
    
    # 4. 레거시 엔드포인트 제거
    print("\n[2] 레거시 API 엔드포인트 제거:")
    content, changes = remove_legacy_endpoints(content)
    total_changes += changes
    
    # 5. 레거시 함수 제거
    print("\n[3] 레거시 함수 제거:")
    content, changes = remove_legacy_function(content)
    total_changes += changes
    
    # 6. safety_instruction 폴백 제거
    print("\n[4] safety_instruction 폴백 로직 제거:")
    content, changes = fix_safety_instruction_fallback(content)
    total_changes += changes
    
    # 7. board_type 사용 현황 분석
    content = add_board_type_parameters(content)
    
    # 8. 파일 쓰기
    if total_changes > 0:
        with open(app_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print("\n" + "=" * 60)
        print(f"✅ 총 {total_changes}개 변경 완료!")
        print(f"📄 백업 파일: {backup_path}")
        print("\n📝  후속 확인 필요:")
        print("1. dropdown_option_codes_v2 쿼리에 board_type 파라미터 추가 여부")
        print("2. REMOVED_LEGACY 주석 확인 및 정리")
        print("3. 서버 재시작/테스트")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("ℹ️ 변경사항이 없습니다.")
        print("=" * 60)

if __name__ == "__main__":
    main()
