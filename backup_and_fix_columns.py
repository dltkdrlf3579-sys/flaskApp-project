#!/usr/bin/env python3
"""
Column Config 백업 및 정리 스크립트
BOARD_STANDARDIZATION_PLAN.md에 따른 구현
"""

import sqlite3
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_db_connection():
    """데이터베이스 연결"""
    from db_connection import get_db_connection as get_conn
    conn = get_conn(row_factory=True)
    return conn

def backup_column_configs(conn):
    """모든 column config 테이블 백업"""
    cursor = conn.cursor()
    backup_date = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    tables = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'accident_column_config',
        'change_request_column_config'
    ]
    
    for table in tables:
        backup_table = f"{table}_backup_{backup_date}"
        try:
            # 백업 테이블 생성
            cursor.execute(f"""
                CREATE TABLE {backup_table} AS 
                SELECT * FROM {table}
            """)
            logging.info(f"✅ 백업 완료: {table} → {backup_table}")
        except Exception as e:
            logging.error(f"❌ 백업 실패 {table}: {e}")
    
    conn.commit()
    return backup_date

def clean_column_configs(conn):
    """detailed_content와 attachments를 column config에서 제거 또는 시스템 필드로 표시"""
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'accident_column_config',
        'change_request_column_config'
    ]
    
    for table in tables:
        try:
            # is_system 컬럼이 없으면 추가
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            if 'is_system' not in columns:
                cursor.execute(f"ALTER TABLE {table} ADD COLUMN is_system INTEGER DEFAULT 0")
                logging.info(f"✅ {table}에 is_system 컬럼 추가")
            
            # detailed_content와 attachments는 시스템 필드로 표시하고 비활성화
            cursor.execute(f"""
                UPDATE {table}
                SET is_system = 1, is_active = 0
                WHERE column_key IN ('detailed_content', 'attachments')
            """)
            
            # created_at은 시스템 필드로 표시하되 활성 상태 유지
            cursor.execute(f"""
                UPDATE {table}
                SET is_system = 1
                WHERE column_key = 'created_at'
            """)
            
            logging.info(f"✅ {table} 정리 완료")
            
        except Exception as e:
            logging.error(f"❌ {table} 정리 실패: {e}")
    
    conn.commit()

def fix_null_tabs(conn):
    """NULL인 tab 값을 적절한 기본 섹션으로 업데이트"""
    cursor = conn.cursor()
    
    # Safety Instruction
    cursor.execute("""
        UPDATE safety_instruction_column_config 
        SET tab = CASE
            WHEN column_key IN ('issue_number', 'company_name', 'business_number', 
                               'issue_date', 'improvement_deadline', 'status', 
                               'issuer', 'recipient') THEN 'basic_info'
            WHEN column_key IN ('violation_type', 'violation_details', 'legal_basis', 
                               'penalty', 'violation_location', 'violation_date', 
                               'violation_severity') THEN 'violation_info'
            ELSE 'additional'
        END
        WHERE (tab IS NULL OR tab = '') 
          AND is_active = 1 
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND column_key NOT IN ('detailed_content', 'attachments')
    """)
    logging.info("✅ safety_instruction_column_config tab 매핑 수정")
    
    # Follow SOP
    cursor.execute("""
        UPDATE follow_sop_column_config 
        SET tab = CASE
            WHEN column_key IN ('work_req_no', 'company_name', 'business_number', 
                               'request_date', 'department', 'requester') THEN 'basic_info'
            WHEN column_key IN ('work_type', 'work_location', 'work_content', 
                               'work_status', 'worker_count', 'work_duration', 
                               'safety_measures') THEN 'work_info'
            ELSE 'additional'
        END
        WHERE (tab IS NULL OR tab = '') 
          AND is_active = 1 
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND column_key NOT IN ('detailed_content', 'attachments')
    """)
    logging.info("✅ follow_sop_column_config tab 매핑 수정")
    
    # Full Process
    cursor.execute("""
        UPDATE full_process_column_config 
        SET tab = CASE
            WHEN column_key IN ('fullprocess_number', 'company_name', 'business_number', 
                               'process_date', 'department') THEN 'basic_info'
            WHEN column_key IN ('process_type', 'process_name', 'process_status', 
                               'process_owner', 'process_steps', 'process_duration', 
                               'process_output') THEN 'process_info'
            ELSE 'additional'
        END
        WHERE (tab IS NULL OR tab = '') 
          AND is_active = 1 
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND column_key NOT IN ('detailed_content', 'attachments')
    """)
    logging.info("✅ full_process_column_config tab 매핑 수정")
    
    # Accident
    cursor.execute("""
        UPDATE accident_column_config 
        SET tab = CASE
            WHEN column_key IN ('accident_number', 'company_name', 'business_number', 
                               'accident_date', 'reporter', 'department') THEN 'basic_info'
            WHEN column_key IN ('accident_type', 'accident_cause', 'injury_type', 
                               'injury_severity', 'accident_description', 'victim_name', 
                               'victim_age') THEN 'accident_info'
            WHEN column_key IN ('accident_location', 'location_detail', 'building', 
                               'floor') THEN 'location_info'
            ELSE 'additional'
        END
        WHERE (tab IS NULL OR tab = '') 
          AND is_active = 1 
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND column_key NOT IN ('detailed_content', 'attachments')
    """)
    logging.info("✅ accident_column_config tab 매핑 수정")
    
    # Change Request
    cursor.execute("""
        UPDATE change_request_column_config 
        SET tab = CASE
            WHEN column_key IN ('change_number', 'company_name', 'business_number', 
                               'request_date', 'requester', 'department') THEN 'basic_info'
            WHEN column_key IN ('change_type', 'change_reason', 'change_impact', 
                               'change_priority', 'change_status') THEN 'change_info'
            ELSE 'additional'
        END
        WHERE (tab IS NULL OR tab = '') 
          AND is_active = 1 
          AND (is_deleted = 0 OR is_deleted IS NULL)
          AND column_key NOT IN ('detailed_content', 'attachments')
    """)
    logging.info("✅ change_request_column_config tab 매핑 수정")
    
    conn.commit()

def fix_created_at_defaults(conn):
    """created_at 필드에 DEFAULT 추가 및 NULL 값 수정"""
    cursor = conn.cursor()
    
    cache_tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accident_cache',
        'change_request_cache'
    ]
    
    # PostgreSQL인지 SQLite인지 확인
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    backend = config.get('DATABASE', 'db_backend', fallback='sqlite')
    
    for table in cache_tables:
        try:
            if backend == 'postgres':
                # PostgreSQL: CURRENT_TIMESTAMP 사용
                cursor.execute(f"""
                    UPDATE {table}
                    SET created_at = CURRENT_TIMESTAMP
                    WHERE created_at IS NULL OR created_at = ''
                """)
            else:
                # SQLite: datetime('now') 사용
                cursor.execute(f"""
                    UPDATE {table}
                    SET created_at = datetime('now', 'localtime')
                    WHERE created_at IS NULL OR created_at = ''
                """)
            
            affected = cursor.rowcount
            if affected > 0:
                logging.info(f"✅ {table}: {affected}개 레코드의 created_at 수정")
            
        except Exception as e:
            logging.error(f"❌ {table} created_at 수정 실패: {e}")
    
    conn.commit()

def main():
    """메인 실행 함수"""
    conn = get_db_connection()
    
    try:
        # 1. 백업
        logging.info("=" * 50)
        logging.info("1. Column Config 백업 시작")
        backup_date = backup_column_configs(conn)
        
        # 2. Column Config 정리
        logging.info("=" * 50)
        logging.info("2. Column Config 정리 시작")
        clean_column_configs(conn)
        
        # 3. NULL tab 수정
        logging.info("=" * 50)
        logging.info("3. NULL tab 매핑 수정")
        fix_null_tabs(conn)
        
        # 4. created_at 수정
        logging.info("=" * 50)
        logging.info("4. created_at 필드 수정")
        fix_created_at_defaults(conn)
        
        logging.info("=" * 50)
        logging.info(f"✅ 모든 작업 완료! 백업 날짜: {backup_date}")
        logging.info(f"문제 발생 시 _backup_{backup_date} 테이블에서 복원 가능")
        
    except Exception as e:
        logging.error(f"작업 중 오류 발생: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    main()