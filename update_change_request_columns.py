#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
변경요청(change_request) 컬럼 순서 재배치 및 설정 업데이트
"""

import sqlite3
import json
import sys

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

DB_PATH = 'portal.db'

def update_columns():
    """변경요청 컬럼 재배치 및 설정 업데이트"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # 1. 테이블 생성 (없을 경우)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS change_request_column_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT NOT NULL,
            column_order INTEGER DEFAULT 999,
            is_active INTEGER DEFAULT 1,
            is_required INTEGER DEFAULT 0,
            dropdown_options TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            linked_key TEXT,
            tab TEXT DEFAULT 'basic',
            is_display_list INTEGER DEFAULT 1
        )
    """)
    
    # 테이블에 linked_key 컬럼이 없으면 추가
    cursor.execute("PRAGMA table_info(change_request_column_config)")
    columns = [col[1] for col in cursor.fetchall()]
    if 'linked_key' not in columns:
        cursor.execute("ALTER TABLE change_request_column_config ADD COLUMN linked_key TEXT")
    if 'tab' not in columns:
        cursor.execute("ALTER TABLE change_request_column_config ADD COLUMN tab TEXT DEFAULT 'basic'")
    if 'is_display_list' not in columns:
        cursor.execute("ALTER TABLE change_request_column_config ADD COLUMN is_display_list INTEGER DEFAULT 1")
    
    # 2. 기존 컬럼 모두 비활성화
    cursor.execute("UPDATE change_request_column_config SET is_active = 0")
    
    # 3. 새로운 컬럼 구성 (순서대로)
    columns = [
        # 1-2칸: 협력사명(팝업선택) & 사업자번호(연동)
        {
            'column_key': 'company_name',
            'column_name': '협력사명',
            'column_type': 'popup_company',
            'column_order': 1,
            'is_active': 1,
            'is_required': 1,
            'linked_key': 'business_number',
            'tab': 'basic'
        },
        {
            'column_key': 'business_number',
            'column_name': '사업자번호',
            'column_type': 'linked_text',
            'column_order': 2,
            'is_active': 1,
            'is_required': 1,
            'linked_key': 'company_name',
            'tab': 'basic'
        },
        # 3-4칸: 의뢰인(팝업선택) & 의뢰인부서(연동)
        {
            'column_key': 'requester_name',
            'column_name': '의뢰인',
            'column_type': 'popup_person',
            'column_order': 3,
            'is_active': 1,
            'is_required': 1,
            'linked_key': 'requester_department',
            'tab': 'basic'
        },
        {
            'column_key': 'requester_department',
            'column_name': '의뢰인부서',
            'column_type': 'linked_dept',
            'column_order': 4,
            'is_active': 1,
            'is_required': 1,
            'linked_key': 'requester_name',
            'tab': 'basic'
        },
        # 5-7칸: 변경유형, 현재값, 변경값
        {
            'column_key': 'change_type',
            'column_name': '변경유형',
            'column_type': 'dropdown',
            'column_order': 5,
            'is_active': 1,
            'is_required': 1,
            'dropdown_options': json.dumps(['기본정보', '계약정보', '평가정보', '기타']),
            'tab': 'basic'
        },
        {
            'column_key': 'current_value',
            'column_name': '현재값',
            'column_type': 'text',
            'column_order': 6,
            'is_active': 1,
            'is_required': 1,
            'tab': 'basic'
        },
        {
            'column_key': 'new_value',
            'column_name': '변경값',
            'column_type': 'text',
            'column_order': 7,
            'is_active': 1,
            'is_required': 1,
            'tab': 'basic'
        },
        # 8칸: 상태 (드롭다운)
        {
            'column_key': 'status',
            'column_name': '상태',
            'column_type': 'dropdown',
            'column_order': 8,
            'is_active': 1,
            'is_required': 0,
            'dropdown_options': json.dumps(['requested', 'pending', 'approved', 'rejected', 'completed']),
            'tab': 'basic'
        },
        # 변경사유는 비활성화 (별도 섹션에서 처리)
        {
            'column_key': 'change_reason',
            'column_name': '변경사유',
            'column_type': 'textarea',
            'column_order': 99,
            'is_active': 0,  # 비활성화
            'is_required': 0,
            'tab': 'basic'
        }
    ]
    
    # 4. 컬럼 추가 또는 업데이트
    for col in columns:
        cursor.execute("""
            INSERT OR REPLACE INTO change_request_column_config 
            (column_key, column_name, column_type, column_order, is_active, 
             is_required, dropdown_options, linked_key, tab, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (
            col['column_key'],
            col['column_name'],
            col['column_type'],
            col['column_order'],
            col['is_active'],
            col.get('is_required', 0),
            col.get('dropdown_options'),
            col.get('linked_key'),
            col.get('tab', 'basic')
        ))
    
    # 5. dropdown_option_codes_v2 테이블에 드롭다운 옵션 추가
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_type TEXT NOT NULL,
            column_key TEXT NOT NULL,
            option_code TEXT NOT NULL,
            option_value TEXT NOT NULL,
            display_order INTEGER DEFAULT 999,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(board_type, column_key, option_code)
        )
    """)
    
    # 변경유형 드롭다운 옵션
    change_types = [
        ('basic_info', '기본정보'),
        ('contract_info', '계약정보'),
        ('eval_info', '평가정보'),
        ('other', '기타')
    ]
    
    cursor.execute("DELETE FROM dropdown_option_codes_v2 WHERE board_type='change_request' AND column_key='change_type'")
    for i, (code, value) in enumerate(change_types, 1):
        cursor.execute("""
            INSERT OR REPLACE INTO dropdown_option_codes_v2 
            (board_type, column_key, option_code, option_value, display_order, is_active)
            VALUES ('change_request', 'change_type', ?, ?, ?, 1)
        """, (code, value, i))
    
    # 상태 드롭다운 옵션
    statuses = [
        ('requested', '요청'),
        ('pending', '검토중'),
        ('approved', '승인'),
        ('rejected', '반려'),
        ('completed', '완료')
    ]
    
    cursor.execute("DELETE FROM dropdown_option_codes_v2 WHERE board_type='change_request' AND column_key='status'")
    for i, (code, value) in enumerate(statuses, 1):
        cursor.execute("""
            INSERT OR REPLACE INTO dropdown_option_codes_v2 
            (board_type, column_key, option_code, option_value, display_order, is_active)
            VALUES ('change_request', 'status', ?, ?, ?, 1)
        """, (code, value, i))
    
    conn.commit()
    conn.close()
    print("[완료] 변경요청 컬럼 재배치 완료")
    print("  - company_name: 협력사명 (팝업선택)")
    print("  - business_number: 사업자번호 (연동)")
    print("  - requester_name: 의뢰인 (팝업선택)")
    print("  - requester_department: 의뢰인부서 (연동)")
    print("  - change_type: 변경유형 (드롭다운)")
    print("  - current_value: 현재값")
    print("  - new_value: 변경값")
    print("  - status: 상태 (드롭다운)")
    print("  - change_reason: 변경사유 (비활성화)")
    print("\n[완료] 드롭다운 옵션 설정 완료")
    print("  - change_type: 기본정보, 계약정보, 평가정보, 기타")
    print("  - status: 요청, 검토중, 승인, 반려, 완료")

if __name__ == '__main__':
    update_columns()