#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
사고 테이블 스키마 업데이트 스크립트
- 대분류, 장소구분 필드 추가
- 기본정보/추가정보 구분을 위한 재구성
"""

import sqlite3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def update_accident_schema():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    try:
        # 1. 새로운 컬럼 추가 (대분류, 장소구분)
        new_columns = [
            ('major_category', 'TEXT'),  # 대분류
            ('location_category', 'TEXT'),  # 장소구분
        ]
        
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE accidents_cache ADD COLUMN {col_name} {col_type}")
                logger.info(f"Added column: {col_name}")
            except sqlite3.OperationalError as e:
                if "duplicate column" in str(e).lower():
                    logger.info(f"Column {col_name} already exists")
                else:
                    raise
        
        # 2. 기본 컬럼 설정 초기화 (기본정보 필드만)
        basic_columns = [
            ('accident_number', '사고번호', 'text', 1, 1),
            ('accident_name', '사고명', 'text', 2, 1),
            ('workplace', '사업장', 'text', 3, 1),
            ('accident_grade', '등급', 'dropdown', 4, 1),
            ('major_category', '대분류', 'dropdown', 5, 1),
            ('injury_form', '재해형태', 'dropdown', 6, 1),
            ('injury_type', '재해유형', 'dropdown', 7, 1),
            ('accident_date', '재해날짜', 'date', 8, 1),
            ('day_of_week', '요일', 'text', 9, 1),
            ('report_date', '등록일', 'date', 10, 1),
            ('building', '건물', 'popup_building', 11, 1),
            ('floor', '층', 'text', 12, 1),
            ('location_category', '장소구분', 'dropdown', 13, 1),
            ('location_detail', '세부장소', 'text', 14, 1),
        ]
        
        # 추가정보로 이동할 필드들
        additional_columns = [
            ('business_number', '사업자번호', 'text', 15, 1),
            ('accident_time', '사고시간', 'text', 16, 1),
            ('responsible_company1', '귀책협력사(1차)', 'popup_company', 17, 0),  # 비활성화
            ('responsible_company1_no', '귀책협력사(1차) 사업자번호', 'text', 18, 0),  # 비활성화
            ('responsible_company2', '귀책협력사(2차)', 'popup_company', 19, 0),  # 비활성화
            ('responsible_company2_no', '귀책협력사(2차) 사업자번호', 'text', 20, 0),  # 비활성화
        ]
        
        # 3. accident_column_config 테이블 재구성
        cursor.execute("DELETE FROM accident_column_config WHERE column_key IN (SELECT column_key FROM accident_column_config)")
        
        # 기본정보 필드 삽입
        for col_key, col_name, col_type, col_order, is_active in basic_columns:
            cursor.execute("""
                INSERT INTO accident_column_config 
                (column_key, column_name, column_type, column_order, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (col_key, col_name, col_type, col_order, is_active))
        
        # 추가정보 필드 삽입
        for col_key, col_name, col_type, col_order, is_active in additional_columns:
            cursor.execute("""
                INSERT INTO accident_column_config 
                (column_key, column_name, column_type, column_order, is_active)
                VALUES (?, ?, ?, ?, ?)
            """, (col_key, col_name, col_type, col_order, is_active))
        
        conn.commit()
        logger.info("Schema update completed successfully")
        
    except Exception as e:
        conn.rollback()
        logger.error(f"Error updating schema: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    update_accident_schema()
    print("사고 테이블 스키마 업데이트 완료!")