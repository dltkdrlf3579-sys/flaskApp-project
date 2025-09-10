#!/usr/bin/env python3
"""
모든 게시판의 섹션 문제를 한 번에 해결하는 스크립트
"""
import sqlite3
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def fix_all_sections():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    try:
        # 1. safety_instruction_sections 테이블 생성 및 데이터 이관
        logging.info("=== 1. Safety Instruction 섹션 테이블 생성 ===")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS safety_instruction_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        
        # section_config에서 데이터 이관
        cursor.execute('''
            INSERT OR REPLACE INTO safety_instruction_sections (section_key, section_name, section_order, is_active)
            SELECT section_key, section_name, section_order, is_active
            FROM section_config
            WHERE board_type = 'safety_instruction'
        ''')
        logging.info(f"  - Safety Instruction: {cursor.rowcount}개 섹션 이관")
        
        # 2. accident_sections 테이블 생성 및 데이터 이관
        logging.info("=== 2. Accident 섹션 테이블 생성 ===")
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS accident_sections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0
            )
        ''')
        
        # section_config에서 데이터 이관
        cursor.execute('''
            INSERT OR REPLACE INTO accident_sections (section_key, section_name, section_order, is_active)
            SELECT section_key, section_name, section_order, is_active
            FROM section_config
            WHERE board_type = 'accident'
        ''')
        logging.info(f"  - Accident: {cursor.rowcount}개 섹션 이관")
        
        # 3. NULL tab 값 수정
        logging.info("=== 3. NULL tab 값 수정 ===")
        
        # Safety Instruction NULL tab 수정
        cursor.execute('''
            UPDATE safety_instruction_column_config
            SET tab = 'basic_info'
            WHERE (tab IS NULL OR tab = '') AND is_active = 1
        ''')
        logging.info(f"  - Safety Instruction: {cursor.rowcount}개 컬럼 tab 수정")
        
        # Accident NULL tab 수정
        cursor.execute('''
            UPDATE accident_column_config
            SET tab = 'basic_info'
            WHERE (tab IS NULL OR tab = '') AND is_active = 1
        ''')
        logging.info(f"  - Accident: {cursor.rowcount}개 컬럼 tab 수정")
        
        # 4. 섹션이 없는 경우 기본 섹션 추가
        logging.info("=== 4. 누락된 기본 섹션 추가 ===")
        
        # Safety Instruction 기본 섹션
        cursor.execute("SELECT COUNT(*) FROM safety_instruction_sections")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO safety_instruction_sections (section_key, section_name, section_order, is_active)
                VALUES 
                    ('basic_info', '기본정보', 1, 1),
                    ('violation_info', '위반정보', 2, 1),
                    ('additional', '추가정보', 3, 1)
            ''')
            logging.info("  - Safety Instruction 기본 섹션 추가")
        
        # Accident 기본 섹션
        cursor.execute("SELECT COUNT(*) FROM accident_sections")
        if cursor.fetchone()[0] == 0:
            cursor.execute('''
                INSERT INTO accident_sections (section_key, section_name, section_order, is_active)
                VALUES 
                    ('basic_info', '기본정보', 1, 1),
                    ('accident_info', '사고정보', 2, 1),
                    ('location_info', '장소정보', 3, 1),
                    ('additional', '추가정보', 4, 1)
            ''')
            logging.info("  - Accident 기본 섹션 추가")
        
        # 5. 검증
        logging.info("\n=== 5. 최종 검증 ===")
        
        tables = [
            ('safety_instruction_sections', 'safety_instruction_column_config'),
            ('accident_sections', 'accident_column_config'),
            ('follow_sop_sections', 'follow_sop_column_config'),
            ('full_process_sections', 'full_process_column_config')
        ]
        
        for section_table, column_table in tables:
            try:
                # 섹션 수
                sections = cursor.execute(f'SELECT COUNT(*) FROM {section_table} WHERE is_active = 1').fetchone()[0]
                
                # 컬럼 수와 NULL tab
                result = cursor.execute(f'''
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN tab IS NULL OR tab = '' THEN 1 ELSE 0 END) as null_tabs
                    FROM {column_table}
                    WHERE is_active = 1
                ''').fetchone()
                
                board_name = section_table.replace('_sections', '').replace('_', ' ').title()
                status = "✓" if sections > 0 and result[1] == 0 else "✗"
                logging.info(f"  {status} {board_name}: {sections}개 섹션, {result[0]}개 컬럼 (NULL: {result[1]})")
            except Exception as e:
                logging.error(f"  ✗ {section_table}: 오류 - {e}")
        
        conn.commit()
        logging.info("\n✅ 모든 수정 완료!")
        
    except Exception as e:
        conn.rollback()
        logging.error(f"오류 발생: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    fix_all_sections()