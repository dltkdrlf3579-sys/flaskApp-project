#!/usr/bin/env python3
"""
팝업 시스템 통합 리팩토링 스크립트
모든 detail 템플릿을 통합 팝업 시스템으로 자동 변환

Usage:
    python refactor_popup_templates.py
    
Features:
- 기존 팝업 코드 패턴 자동 감지
- 통합 컴포넌트로 자동 변환
- 백업 파일 생성
- 리팩토링 보고서 생성
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path
import json

class PopupTemplateRefactor:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.backup_dir = self.templates_dir / 'backups' / f'popup_refactor_{datetime.now().strftime("%Y%m%d_%H%M%S")}'
        self.report = {
            'timestamp': datetime.now().isoformat(),
            'files_processed': [],
            'patterns_found': {},
            'changes_made': [],
            'errors': []
        }
        
        # 변환할 팝업 패턴들
        self.popup_patterns = {
            # 기존 팝업 필드 패턴들
            'popup_person_old': r'<div class="input-group">.*?onclick="openPersonSearch\(\'([^\']+)\'\)".*?</div>',
            'popup_company_old': r'<div class="input-group">.*?onclick="openCompanySearch\(\'([^\']+)\'\)".*?</div>',
            'popup_building_old': r'<div class="input-group">.*?onclick="openBuildingSearch\(\'([^\']+)\'\)".*?</div>',
            'popup_department_old': r'<div class="input-group">.*?onclick="openDepartmentSearch\(\'([^\']+)\'\)".*?</div>',
            'popup_contractor_old': r'<div class="input-group">.*?onclick="openContractorSearch\(\'([^\']+)\'\)".*?</div>',
            'popup_generic_old': r'<div class="input-group">.*?onclick="openPopup\(\'([^\']+)\'\)".*?</div>',
            
            # 조건부 팝업 패턴
            'conditional_popup': r'{% elif col\.column_type == \'(popup_\w+)\' %}.*?</div>',
            'popup_type_check': r'{% if col\.column_type.*?popup.*?%}',
            
            # 스크립트 패턴들
            'duplicate_functions': r'function open\w+Search\([^}]+}\s*popup\.focus\(\);\s*}',
            'duplicate_callbacks': r'window\.receive\w+Selection = function[^}]+};',
            'inline_popup_scripts': r'<script>.*?function open.*?</script>',
        }

    def create_backup(self, file_path: Path):
        """파일 백업 생성"""
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        backup_file = self.backup_dir / file_path.name
        shutil.copy2(file_path, backup_file)
        return backup_file

    def analyze_template(self, file_path: Path) -> dict:
        """템플릿 분석"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        analysis = {
            'file': str(file_path),
            'popup_fields': [],
            'duplicate_scripts': [],
            'callback_functions': [],
            'needs_refactor': False
        }
        
        # 팝업 필드 패턴 찾기
        for pattern_name, pattern in self.popup_patterns.items():
            matches = re.findall(pattern, content, re.DOTALL | re.IGNORECASE)
            if matches:
                analysis['popup_fields'].extend([
                    {'type': pattern_name, 'match': match} for match in matches
                ])
                analysis['needs_refactor'] = True
        
        # 중복 스크립트 감지
        script_patterns = [
            r'function openPersonSearch',
            r'function openCompanySearch', 
            r'window\.receivePersonSelection',
            r'window\.receiveCompanySelection'
        ]
        
        for pattern in script_patterns:
            if re.search(pattern, content):
                analysis['duplicate_scripts'].append(pattern)
                analysis['needs_refactor'] = True
        
        return analysis

    def refactor_popup_fields(self, content: str) -> str:
        """팝업 필드를 통합 컴포넌트로 변환"""
        
        # 1. 조건부 팝업 필드 변환 (column_type 체크)
        popup_condition_pattern = r'{% elif col\.column_type == \'(popup_\w+)\' %}.*?{% endif %}'
        
        def replace_popup_condition(match):
            popup_type = match.group(1)
            return f'''{{%- elif col.column_type == '{popup_type}' -%}}
                    {{%- from 'includes/popup_field_component.html' import render_popup_field -%}}
                    {{{{ render_popup_field(col, section.section_key, col_value, 'edit') }}}}'''
        
        content = re.sub(popup_condition_pattern, replace_popup_condition, content, flags=re.DOTALL)
        
        # 2. startswith 팝업 패턴 변환
        startswith_pattern = r'{% elif col\.column_type and col\.column_type\.startswith\(\'popup\'\) %}.*?</div>'
        
        startswith_replacement = '''{% elif col.column_type and col.column_type.startswith('popup') %}
                    {%- from 'includes/popup_field_component.html' import render_popup_field -%}
                    {{ render_popup_field(col, section.section_key, col_value, 'edit') }}'''
        
        content = re.sub(startswith_pattern, startswith_replacement, content, flags=re.DOTALL)
        
        # 3. 테이블 팝업 변환
        table_pattern = r'{% elif col\.column_type == \'table\' or col\.input_type == \'table\' %}.*?</div>'
        
        table_replacement = '''{% elif col.column_type == 'table' or col.input_type == 'table' %}
                    {%- from 'includes/popup_field_component.html' import render_table_popup_field -%}
                    {{ render_table_popup_field(col, section.section_key, col_value, 'edit') }}'''
        
        content = re.sub(table_pattern, table_replacement, content, flags=re.DOTALL)
        
        return content

    def remove_duplicate_scripts(self, content: str) -> str:
        """중복 스크립트 제거"""
        
        # 중복 함수들 제거
        duplicate_functions = [
            r'function openPersonSearch\([^}]+}\s*popup\.focus\(\);\s*}',
            r'function openCompanySearch\([^}]+}\s*popup\.focus\(\);\s*}',
            r'function openBuildingSearch\([^}]+}\s*popup\.focus\(\);\s*}',
            r'function openDepartmentSearch\([^}]+}\s*popup\.focus\(\);\s*}',
            r'function openContractorSearch\([^}]+}\s*popup\.focus\(\);\s*}',
        ]
        
        for pattern in duplicate_functions:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        # 중복 콜백 제거
        duplicate_callbacks = [
            r'window\.receivePersonSelection = function[^}]+};',
            r'window\.receiveCompanySelection = function[^}]+};',
            r'window\.receiveBuildingSelection = function[^}]+};',
            r'window\.receiveDepartmentSelection = function[^}]+};',
            r'window\.receiveContractorSelection = function[^}]+};',
        ]
        
        for pattern in duplicate_callbacks:
            content = re.sub(pattern, '', content, flags=re.DOTALL)
        
        return content

    def add_universal_popup_script(self, content: str) -> str:
        """통합 팝업 스크립트 추가"""
        
        # 기존 popup-handler.js 스크립트 태그 찾기
        popup_script_pattern = r'<script src="/static/js/popup-handler\.js"></script>'
        
        if re.search(popup_script_pattern, content):
            # 기존 스크립트를 새로운 스크립트로 교체
            content = re.sub(
                popup_script_pattern,
                '<script src="/static/js/universal-popup-handler.js"></script>',
                content
            )
        else:
            # 스크립트 섹션 끝에 추가
            script_section = r'(</script>\s*{% endblock %})'
            replacement = r'</script>\n\n<!-- 통합 팝업 핸들러 -->\n<script src="/static/js/universal-popup-handler.js"></script>\n\n{% endblock %}'
            content = re.sub(script_section, replacement, content)
        
        return content

    def refactor_file(self, file_path: Path) -> bool:
        """단일 파일 리팩토링"""
        try:
            # 백업 생성
            backup_file = self.create_backup(file_path)
            
            # 원본 내용 읽기
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()
            
            # 분석
            analysis = self.analyze_template(file_path)
            
            if not analysis['needs_refactor']:
                print(f"SKIP {file_path.name}: No refactoring needed")
                return False
            
            # 변환 시작
            content = original_content
            
            # 1. 팝업 필드 변환
            content = self.refactor_popup_fields(content)
            
            # 2. 중복 스크립트 제거
            content = self.remove_duplicate_scripts(content)
            
            # 3. 통합 팝업 스크립트 추가
            content = self.add_universal_popup_script(content)
            
            # 변경사항 적용
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # 보고서 업데이트
            self.report['files_processed'].append(str(file_path))
            self.report['changes_made'].append({
                'file': str(file_path),
                'backup': str(backup_file),
                'popup_fields_converted': len(analysis['popup_fields']),
                'scripts_removed': len(analysis['duplicate_scripts'])
            })
            
            print(f"SUCCESS {file_path.name}: Refactored ({len(analysis['popup_fields'])} popup fields)")
            return True
            
        except Exception as e:
            error_msg = f"Error refactoring {file_path}: {str(e)}"
            self.report['errors'].append(error_msg)
            print(f"ERROR {error_msg}")
            return False

    def refactor_all_templates(self):
        """모든 detail 템플릿 리팩토링"""
        detail_files = list(self.templates_dir.glob("*-detail.html"))
        
        print(f"Popup System Refactoring Started")
        print(f"Target Directory: {self.templates_dir}")
        print(f"Found detail files: {len(detail_files)}")
        print(f"Backup Directory: {self.backup_dir}")
        print("-" * 60)
        
        success_count = 0
        
        for file_path in detail_files:
            if self.refactor_file(file_path):
                success_count += 1
        
        print("-" * 60)
        print(f"Refactoring Complete: {success_count}/{len(detail_files)} files")
        
        # 보고서 생성
        self.generate_report()

    def generate_report(self):
        """리팩토링 보고서 생성"""
        report_file = self.backup_dir / 'refactoring_report.json'
        
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)
        
        # 요약 보고서
        summary_file = self.backup_dir / 'refactoring_summary.md'
        
        summary_content = f"""# 팝업 시스템 통합 리팩토링 보고서

## 요약
- **실행 시간**: {self.report['timestamp']}
- **처리된 파일**: {len(self.report['files_processed'])}개
- **성공한 변환**: {len(self.report['changes_made'])}개
- **발생한 오류**: {len(self.report['errors'])}개

## 변경된 파일 목록
"""
        
        for change in self.report['changes_made']:
            summary_content += f"""
### {Path(change['file']).name}
- **백업 파일**: {change['backup']}
- **변환된 팝업 필드**: {change['popup_fields_converted']}개
- **제거된 중복 스크립트**: {change['scripts_removed']}개
"""
        
        if self.report['errors']:
            summary_content += "\n## 발생한 오류\n"
            for error in self.report['errors']:
                summary_content += f"- {error}\n"
        
        summary_content += f"""
## 리팩토링 내용

### 1. 통합 팝업 컴포넌트 적용
- 기존 개별 팝업 필드 → `render_popup_field()` 매크로
- 테이블 팝업 필드 → `render_table_popup_field()` 매크로

### 2. 중복 스크립트 제거
- 각 템플릿의 중복된 `openXxxSearch()` 함수 제거
- 중복된 `receiveXxxSelection()` 콜백 제거

### 3. 통합 팝업 핸들러 적용
- `popup-handler.js` → `universal-popup-handler.js`
- 일관된 팝업 동작 보장

## 다음 단계
1. 리팩토링된 파일들 테스트
2. 에러가 발생한 파일들 수동 수정
3. 백업 파일 확인 및 정리
"""
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write(summary_content)
        
        print(f"Report file: {report_file}")
        print(f"Summary file: {summary_file}")

def main():
    # 템플릿 디렉토리 경로
    templates_dir = "C:/Users/sanggil/flask-portal/templates"
    
    # 리팩토링 실행
    refactor = PopupTemplateRefactor(templates_dir)
    refactor.refactor_all_templates()

if __name__ == "__main__":
    main()