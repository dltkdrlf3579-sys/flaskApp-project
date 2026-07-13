"""
Mock IQADB module for development testing
Provides sample data for safety_instructions, follow_sop, and full_process boards
"""

import os
from datetime import datetime, timedelta
import random

class MockIQADB:
    """Mock database for IQADB when in development mode"""
    
    def __init__(self):
        # Sample data for safety_instructions
        self.safety_instructions = [
            {
                'id': 'SI-2025-001',
                'issuer_dept': '생산부',
                'issuer_user_name': '김철수',
                'issued_date': '2025-01-10',
                'subject': '화학물질 취급 안전 지침',
                'safety_type': '화학물질',
                'location': 'A동 2층',
                'target_audience': '전체 작업자',
                'violation_type': '미착용',
                'violation_details': '보호장비 미착용 적발',
                'corrective_action': '즉시 시정 및 재교육',
                'risk_level': '높음',
                'department': '생산1팀',
                'team': 'A조',
                'primary_company_bizno': '123-45-67890',
                'primary_company_name': '안전제일(주)',
                'memo': '재발 방지 교육 실시',
                'reviewed_by': '이영희',
                'review_date': '2025-01-11',
                'status': '완료'
            },
            {
                'id': 'SI-2025-002', 
                'issuer_dept': '안전관리팀',
                'issuer_user_name': '박민수',
                'issued_date': '2025-01-12',
                'subject': '고소작업 안전 절차 위반',
                'safety_type': '고소작업',
                'location': 'B동 옥상',
                'target_audience': '시설팀',
                'violation_type': '절차위반',
                'violation_details': '안전고리 미체결 작업',
                'corrective_action': '작업 중지 및 안전교육',
                'risk_level': '매우높음',
                'department': '시설관리팀',
                'team': 'B조',
                'primary_company_bizno': '234-56-78901',
                'primary_company_name': '건설안전(주)',
                'memo': '중대재해 위험 경고',
                'reviewed_by': '최정우',
                'review_date': '2025-01-13',
                'status': '진행중'
            }
        ]
        
        # Sample data for follow_sop
        self.follow_sop = [
            {
                'id': 'SOP-2025-001',
                'created_date': '2025-01-08',
                'creator_name': '정수진',
                'department': '품질관리팀',
                'process_name': '제품 검사 프로세스',
                'sop_number': 'QC-001',
                'sop_version': 'v2.1',
                'work_type': '품질검사',
                'work_location': 'QC실',
                'equipment_used': '검사장비 A-100',
                'materials_used': '시약 B-200',
                'compliance_status': '준수',
                'deviation_details': '',
                'corrective_action': '',
                'inspector_name': '김검사',
                'inspection_date': '2025-01-09',
                'approval_status': '승인',
                'notes': '정기 검사 완료'
            },
            {
                'id': 'SOP-2025-002',
                'created_date': '2025-01-10',
                'creator_name': '이준호',
                'department': '생산2팀',
                'process_name': '조립 공정',
                'sop_number': 'PRD-002',
                'sop_version': 'v1.5',
                'work_type': '조립작업',
                'work_location': '생산라인 2',
                'equipment_used': '조립기 C-300',
                'materials_used': '부품 D-400',
                'compliance_status': '부분준수',
                'deviation_details': '작업 순서 일부 변경',
                'corrective_action': 'SOP 개정 검토',
                'inspector_name': '박감독',
                'inspection_date': '2025-01-11',
                'approval_status': '검토중',
                'notes': '효율성 개선 필요'
            }
        ]
        
        # Sample data for full_process
        self.full_process = [
            {
                'id': 'FP-2025-001',
                'process_id': 'PRO-2025-001',
                'process_name': '신제품 개발 프로세스',
                'start_date': '2025-01-01',
                'end_date': '2025-03-31',
                'responsible_dept': '연구개발팀',
                'process_owner': '홍길동',
                'current_stage': '프로토타입',
                'completion_rate': 45,
                'milestone_1': '개념설계 완료',
                'milestone_2': '프로토타입 제작',
                'milestone_3': '테스트 진행',
                'milestone_4': '양산 준비',
                'risk_assessment': '중간',
                'budget_allocated': 50000000,
                'budget_used': 22500000,
                'team_members': '홍길동, 김개발, 이연구',
                'status': '진행중',
                'review_comments': '일정 준수 중'
            },
            {
                'id': 'FP-2025-002',
                'process_id': 'PRO-2025-002',
                'process_name': '품질 개선 프로젝트',
                'start_date': '2024-12-15',
                'end_date': '2025-02-28',
                'responsible_dept': '품질혁신팀',
                'process_owner': '나품질',
                'current_stage': '실행단계',
                'completion_rate': 70,
                'milestone_1': '현황 분석 완료',
                'milestone_2': '개선안 도출 완료',
                'milestone_3': '실행 중',
                'milestone_4': '효과 검증 예정',
                'risk_assessment': '낮음',
                'budget_allocated': 30000000,
                'budget_used': 21000000,
                'team_members': '나품질, 박개선, 최혁신',
                'status': '정상',
                'review_comments': '목표 달성 가능'
            }
        ]
    
    def get_safety_instructions(self, limit=100):
        """Return mock safety instructions data"""
        return self.safety_instructions[:limit]
    
    def get_follow_sop(self, limit=100):
        """Return mock follow SOP data"""
        return self.follow_sop[:limit]
    
    def get_full_process(self, limit=100):
        """Return mock full process data"""
        return self.full_process[:limit]
    
    def get_safety_instruction_by_id(self, instruction_id):
        """Get single safety instruction by ID"""
        for item in self.safety_instructions:
            if item['id'] == instruction_id:
                return item
        return None
    
    def get_follow_sop_by_id(self, sop_id):
        """Get single follow SOP by ID"""
        for item in self.follow_sop:
            if item['id'] == sop_id:
                return item
        return None
    
    def get_full_process_by_id(self, process_id):
        """Get single full process by ID"""
        for item in self.full_process:
            if item['id'] == process_id:
                return item
        return None


# Singleton instance
_mock_db = None

def get_mock_iqadb():
    """Get singleton instance of MockIQADB"""
    global _mock_db
    if _mock_db is None:
        _mock_db = MockIQADB()
    return _mock_db


# Mock the IQADB functions used in board_services.py
def mock_get_safety_instructions_from_iqadb():
    """Mock function to replace real IQADB query"""
    db = get_mock_iqadb()
    return db.get_safety_instructions()

def mock_get_follow_sop_from_iqadb():
    """Mock function to replace real IQADB query"""
    db = get_mock_iqadb()
    return db.get_follow_sop()

def mock_get_full_process_from_iqadb():
    """Mock function to replace real IQADB query"""
    db = get_mock_iqadb()
    return db.get_full_process()