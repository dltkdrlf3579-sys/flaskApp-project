#!/usr/bin/env python3
"""
통합 팝업 시스템 테스트 스크립트
리팩토링된 템플릿들의 팝업 기능 동작을 자동으로 검증

Usage:
    python test_popup_integration.py
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Tuple
import json

class PopupIntegrationTester:
    def __init__(self, templates_dir: str):
        self.templates_dir = Path(templates_dir)
        self.test_results = {
            'timestamp': None,
            'files_tested': [],
            'integration_status': {},
            'issues_found': [],
            'recommendations': []
        }
        
        # 검증할 패턴들
        self.validation_patterns = {
            'component_import': r'{%-?\s*from\s+[\'"]includes/popup_field_component\.html[\'"]',
            'render_popup_field': r'render_popup_field\(',
            'render_table_popup_field': r'render_table_popup_field\(',
            'universal_handler_script': r'universal-popup-handler\.js',
            'old_popup_handlers': [
                r'function\s+openPersonSearch',
                r'function\s+openCompanySearch',
                r'function\s+openBuildingSearch',
                r'function\s+openDepartmentSearch',
                r'function\s+openContractorSearch',
            ],
            'old_callbacks': [
                r'window\.receivePersonSelection\s*=\s*function',
                r'window\.receiveCompanySelection\s*=\s*function',
                r'window\.receiveBuildingSelection\s*=\s*function',
                r'window\.receiveDepartmentSelection\s*=\s*function',
                r'window\.receiveContractorSelection\s*=\s*function',
            ]
        }

    def test_file_integration(self, file_path: Path) -> Dict:
        """단일 파일의 통합 상태 테스트"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        results = {
            'file': str(file_path),
            'integrated': False,
            'component_usage': {
                'import_found': False,
                'render_popup_used': 0,
                'render_table_used': 0,
            },
            'script_integration': {
                'universal_handler': False,
                'old_popup_handler': False,
            },
            'cleanup_status': {
                'old_functions_removed': True,
                'old_callbacks_removed': True,
                'remaining_old_code': []
            },
            'issues': [],
            'score': 0
        }
        
        # 1. 컴포넌트 import 확인
        if re.search(self.validation_patterns['component_import'], content):
            results['component_usage']['import_found'] = True
        
        # 2. render 함수 사용 횟수
        results['component_usage']['render_popup_used'] = len(
            re.findall(self.validation_patterns['render_popup_field'], content)
        )
        results['component_usage']['render_table_used'] = len(
            re.findall(self.validation_patterns['render_table_popup_field'], content)
        )
        
        # 3. 스크립트 통합 상태
        if re.search(self.validation_patterns['universal_handler_script'], content):
            results['script_integration']['universal_handler'] = True
            
        if re.search(r'popup-handler\.js', content):
            results['script_integration']['old_popup_handler'] = True
            results['issues'].append('여전히 기존 popup-handler.js를 사용 중입니다')
        
        # 4. 기존 코드 정리 상태 확인
        for pattern in self.validation_patterns['old_popup_handlers']:
            if re.search(pattern, content):
                results['cleanup_status']['old_functions_removed'] = False
                results['cleanup_status']['remaining_old_code'].append(pattern)
                results['issues'].append(f'중복 팝업 함수 발견: {pattern}')
        
        for pattern in self.validation_patterns['old_callbacks']:
            if re.search(pattern, content):
                results['cleanup_status']['old_callbacks_removed'] = False
                results['cleanup_status']['remaining_old_code'].append(pattern)
                results['issues'].append(f'중복 콜백 함수 발견: {pattern}')
        
        # 5. 통합 점수 계산 (100점 만점)
        score = 0
        if results['component_usage']['import_found']:
            score += 20
        if results['component_usage']['render_popup_used'] > 0:
            score += 20
        if results['script_integration']['universal_handler']:
            score += 20
        if not results['script_integration']['old_popup_handler']:
            score += 10
        if results['cleanup_status']['old_functions_removed']:
            score += 15
        if results['cleanup_status']['old_callbacks_removed']:
            score += 15
        
        results['score'] = score
        results['integrated'] = score >= 70  # 70점 이상을 통합 완료로 판단
        
        return results

    def test_universal_handler_exists(self) -> bool:
        """universal-popup-handler.js 파일 존재 확인"""
        handler_path = self.templates_dir.parent / 'static' / 'js' / 'universal-popup-handler.js'
        return handler_path.exists()

    def test_component_exists(self) -> bool:
        """popup_field_component.html 존재 확인"""
        component_path = self.templates_dir / 'includes' / 'popup_field_component.html'
        return component_path.exists()

    def run_comprehensive_test(self) -> Dict:
        """포괄적 통합 테스트 실행"""
        from datetime import datetime
        self.test_results['timestamp'] = datetime.now().isoformat()
        
        print("=" * 60)
        print("Popup Integration Test Started")
        print("=" * 60)
        
        # 1. 필수 파일 존재 확인
        print("\n1. Required Files Check")
        print("-" * 30)
        
        if not self.test_universal_handler_exists():
            print("ERROR: universal-popup-handler.js file missing")
            self.test_results['issues_found'].append("universal-popup-handler.js file missing")
        else:
            print("OK: universal-popup-handler.js file found")
            
        if not self.test_component_exists():
            print("ERROR: popup_field_component.html file missing")
            self.test_results['issues_found'].append("popup_field_component.html file missing")
        else:
            print("OK: popup_field_component.html file found")
        
        # 2. detail 파일들 개별 테스트
        print("\n2. Detail Template Integration Status")
        print("-" * 30)
        
        detail_files = list(self.templates_dir.glob("*-detail.html"))
        total_score = 0
        integration_count = 0
        
        for file_path in detail_files:
            results = self.test_file_integration(file_path)
            self.test_results['files_tested'].append(str(file_path))
            self.test_results['integration_status'][file_path.name] = results
            
            status_icon = "OK" if results['integrated'] else "FAIL"
            print(f"{status_icon} {file_path.name}: {results['score']}/100 points")
            
            if results['issues']:
                for issue in results['issues']:
                    print(f"   WARNING: {issue}")
            
            total_score += results['score']
            if results['integrated']:
                integration_count += 1
                
            # 개별 파일 이슈들을 전체 이슈 목록에 추가
            self.test_results['issues_found'].extend([
                f"{file_path.name}: {issue}" for issue in results['issues']
            ])
        
        # 3. 전체 요약
        print(f"\n3. Integration Summary")
        print("-" * 30)
        
        if detail_files:
            avg_score = total_score / len(detail_files)
            integration_rate = (integration_count / len(detail_files)) * 100
            
            print(f"Average Score: {avg_score:.1f}/100")
            print(f"Integration Rate: {integration_rate:.1f}% ({integration_count}/{len(detail_files)})")
            
            if avg_score >= 90:
                print("EXCELLENT: Integration status is excellent!")
                grade = "A"
            elif avg_score >= 80:
                print("GOOD: Integration status is good")
                grade = "B"
            elif avg_score >= 70:
                print("WARNING: Some improvements needed")
                grade = "C"
            else:
                print("ERROR: Additional integration work required")
                grade = "D"
                
            self.test_results['overall_score'] = avg_score
            self.test_results['overall_grade'] = grade
            self.test_results['integration_rate'] = integration_rate
        
        # 4. 권장사항 생성
        self.generate_recommendations()
        
        return self.test_results

    def generate_recommendations(self):
        """개선 권장사항 생성"""
        recommendations = []
        
        # 파일별 권장사항
        for filename, results in self.test_results['integration_status'].items():
            if not results['integrated']:
                recommendations.append(f"{filename}: 통합 작업 필요 (현재 {results['score']}/100점)")
                
                if not results['component_usage']['import_found']:
                    recommendations.append(f"  - popup_field_component.html import 추가")
                    
                if results['script_integration']['old_popup_handler']:
                    recommendations.append(f"  - popup-handler.js → universal-popup-handler.js 교체")
                    
                if not results['cleanup_status']['old_functions_removed']:
                    recommendations.append(f"  - 중복 팝업 함수 제거")
                    
                if not results['cleanup_status']['old_callbacks_removed']:
                    recommendations.append(f"  - 중복 콜백 함수 제거")
        
        # 전체적 권장사항
        if hasattr(self.test_results, 'overall_score'):
            if self.test_results['overall_score'] < 100:
                recommendations.append("전체 시스템 최적화를 위한 추가 정리 작업 권장")
        
        self.test_results['recommendations'] = recommendations

    def save_test_report(self, output_file: str = None):
        """테스트 보고서 저장"""
        if not output_file:
            output_file = self.templates_dir.parent / 'popup_integration_test_report.json'
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(self.test_results, f, ensure_ascii=False, indent=2)
        
        print(f"\nReport saved: {output_file}")

def main():
    templates_dir = "C:/Users/sanggil/flask-portal/templates"
    
    tester = PopupIntegrationTester(templates_dir)
    results = tester.run_comprehensive_test()
    tester.save_test_report()
    
    # 간단한 결과 표시
    if results.get('overall_grade'):
        print(f"\nFinal Grade: {results['overall_grade']} ({results['overall_score']:.1f}/100)")
        
        if results['recommendations']:
            print("\nRecommendations:")
            for rec in results['recommendations']:
                print(f"  - {rec}")

if __name__ == "__main__":
    main()