#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Phase 1: DB 스키마 설정 및 초기 데이터 입력
사고 페이지 동적 컬럼 관리를 위한 DB 구조 구축
"""

import sqlite3
import json
from datetime import datetime

DB_PATH = "portal.db"

def setup_phase1_schema():
    """Phase 1 DB 스키마 설정"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        print("=" * 60)
        print("Phase 1: 사고 페이지 동적 컬럼 관리 DB 설정")
        print("=" * 60)
        
        # 1. accidents_cache 테이블에 custom_data 컬럼 추가
        print("\n1. accidents_cache 테이블 확인 및 custom_data 컬럼 추가...")
        cursor.execute("PRAGMA table_info(accidents_cache)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'custom_data' not in columns:
            cursor.execute("ALTER TABLE accidents_cache ADD COLUMN custom_data TEXT")
            print("   [SUCCESS] custom_data 컬럼 추가 완료")
        else:
            print("   [INFO] custom_data 컬럼이 이미 존재합니다")
        
        # 2. 기본 컬럼 설정 데이터 입력
        print("\n2. 기본 동적 컬럼 설정 데이터 입력...")
        
        # 기존 컬럼1~10을 동적 컬럼으로 변환
        default_columns = [
            ('column1', '조치사항', 'text', 1, 1, None),
            ('column2', '재발방지대책', 'text', 2, 1, None),
            ('column3', '처리상태', 'dropdown', 3, 1, json.dumps(['진행중', '완료', '보류', '취소'])),
            ('column4', '담당부서', 'text', 4, 1, None),
            ('column5', '담당자', 'popup_person', 5, 1, None),
            ('column6', '완료예정일', 'date', 6, 1, None),
            ('column7', '원인분석', 'text', 7, 1, None),
            ('column8', '관련업체', 'popup_company', 8, 1, None),
            ('column9', '비고', 'text', 9, 1, None),
            ('column10', '첨부문서', 'text', 10, 1, None),
        ]
        
        for col_key, col_name, col_type, col_order, is_active, options in default_columns:
            cursor.execute('''
                INSERT OR IGNORE INTO accident_column_config 
                (column_key, column_name, column_type, column_order, is_active, dropdown_options)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (col_key, col_name, col_type, col_order, is_active, options))
        
        print("   [SUCCESS] 기본 컬럼 설정 완료")
        
        # 3. 샘플 담당자 데이터 입력
        print("\n3. 샘플 담당자 마스터 데이터 입력...")
        
        sample_persons = [
            ('김철수', '안전환경팀', '팀장', '삼성전자', '010-1234-5678', 'kim.cs@samsung.com'),
            ('이영희', '안전환경팀', '과장', '삼성전자', '010-2345-6789', 'lee.yh@samsung.com'),
            ('박민수', '시설관리팀', '대리', '삼성전자', '010-3456-7890', 'park.ms@samsung.com'),
            ('정수진', '품질관리팀', '차장', '협력사A', '010-4567-8901', 'jung.sj@partner.com'),
            ('최동훈', '생산관리팀', '부장', '협력사B', '010-5678-9012', 'choi.dh@partner.com'),
        ]
        
        for name, dept, pos, company, phone, email in sample_persons:
            cursor.execute('''
                INSERT OR IGNORE INTO person_master 
                (name, department, position, company_name, phone, email)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (name, dept, pos, company, phone, email))
        
        print("   [SUCCESS] 샘플 담당자 데이터 입력 완료")
        
        # 4. 기존 사고 데이터에 샘플 custom_data 추가 (테스트용)
        print("\n4. 기존 사고 데이터에 샘플 custom_data 추가...")
        
        # 첫 번째 사고 데이터에 샘플 custom_data 추가
        sample_custom_data = {
            "column1": "즉시 안전조치 실시",
            "column2": "안전교육 강화 및 작업절차 개선",
            "column3": "진행중",
            "column4": "안전환경팀",
            "column5": {"name": "김철수", "department": "안전환경팀"},
            "column6": "2025-02-15",
            "column7": "작업자 부주의 및 안전수칙 미준수",
            "column8": {"name": "협력사A", "business_number": "123-45-67890"},
            "column9": "추가 조사 필요",
            "column10": "사고보고서.pdf"
        }
        
        cursor.execute('''
            UPDATE accidents_cache 
            SET custom_data = ?
            WHERE id = (SELECT MIN(id) FROM accidents_cache)
        ''', (json.dumps(sample_custom_data, ensure_ascii=False),))
        
        print("   [SUCCESS] 샘플 custom_data 추가 완료")
        
        conn.commit()
        print("\n" + "=" * 60)
        print("[완료] Phase 1 DB 설정이 성공적으로 완료되었습니다!")
        print("=" * 60)
        
        # 설정된 컬럼 목록 확인
        print("\n설정된 동적 컬럼 목록:")
        cursor.execute('''
            SELECT column_key, column_name, column_type, column_order 
            FROM accident_column_config 
            WHERE is_active = 1 
            ORDER BY column_order
        ''')
        for row in cursor.fetchall():
            print(f"  {row[3]:2d}. [{row[0]:10s}] {row[1]:15s} (타입: {row[2]})")
            
    except Exception as e:
        print(f"\n[ERROR] 오류 발생: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    setup_phase1_schema()