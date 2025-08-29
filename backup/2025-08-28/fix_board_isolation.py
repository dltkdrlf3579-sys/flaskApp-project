#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
보드 격리 원칙 후반 정리 스크립트
- dropdown_option_codes v1 → v2 이전 마이그레이션
- 보드별 격리 검증
"""
import sqlite3
import json
import logging
import sys
import io
from datetime import datetime

# Windows 콘솔 인코딩 문제 해결
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('board_isolation_fix.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)

DB_PATH = 'portal.db'

# 보드 타입 매핑
BOARD_TYPES = {
    'accident': 'accident',
    'safety_instruction': 'safety_instruction',
    'safety-instruction': 'safety_instruction',  # URL 표기 지원
    'change_request': 'change_request',
    'change-request': 'change_request'  # URL 표기 지원
}

def create_v2_table_if_not_exists(conn):
    """dropdown_option_codes_v2 테이블 생성"""
    logging.info("▶ dropdown_option_codes_v2 테이블 확인/생성 중...")
    
    conn.execute("""
        CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            board_type TEXT NOT NULL,
            column_key TEXT NOT NULL,
            option_code TEXT NOT NULL,
            option_value TEXT NOT NULL,
            display_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_by TEXT,
            updated_by TEXT,
            UNIQUE(board_type, column_key, option_code)
        )
    """)
    conn.commit()
    logging.info("✅ dropdown_option_codes_v2 테이블 준비 완료")

def migrate_v1_to_v2(conn):
    """v1 데이터를 v2로 마이그레이션"""
    logging.info("▶ v1 → v2 마이그레이션 시작...")
    
    cursor = conn.cursor()
    
    # v1 테이블이 있는지 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dropdown_option_codes'")
    if not cursor.fetchone():
        logging.warning("⚠️ dropdown_option_codes (v1) 테이블이 없습니다.")
        return
    
    # v1 데이터 조회
    v1_data = cursor.execute("""
        SELECT column_key, option_code, option_value, display_order, is_active
        FROM dropdown_option_codes
    """).fetchall()
    
    if not v1_data:
        logging.info("ℹ️ v1 테이블에 데이터가 없습니다.")
        return
    
    logging.info(f"→ v1 데이터 {len(v1_data)}개 발견")
    
    # 각 컬럼의 어느 보드인지 매핑
    column_board_mapping = {}
    
    # accident_column_config 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accident_column_config'")
    if cursor.fetchone():
        accident_columns = cursor.execute("SELECT column_key FROM accident_column_config").fetchall()
        for col in accident_columns:
            column_board_mapping[col[0]] = 'accident'
        logging.info(f"  - accident 보드: {len(accident_columns)}개 컬럼")
    
    # safety_instruction_column_config 확인  
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='safety_instruction_column_config'")
    if cursor.fetchone():
        safety_columns = cursor.execute("SELECT column_key FROM safety_instruction_column_config").fetchall()
        for col in safety_columns:
            column_board_mapping[col[0]] = 'safety_instruction'
        logging.info(f"  - safety_instruction 보드: {len(safety_columns)}개 컬럼")
    
    # change_request_column_config 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='change_request_column_config'")
    if cursor.fetchone():
        change_columns = cursor.execute("SELECT column_key FROM change_request_column_config").fetchall()
        for col in change_columns:
            column_board_mapping[col[0]] = 'change_request'
        logging.info(f"  - change_request 보드: {len(change_columns)}개 컬럼")
    
    # v2로 마이그레이션
    migrated_count = 0
    skipped_count = 0
    
    for column_key, option_code, option_value, display_order, is_active in v1_data:
        board_type = column_board_mapping.get(column_key)
        
        if not board_type:
            # 보드 타입을 알 수 없는 경우, 모든 보드에 복사 (예외적)
            logging.warning(f"⚠️ column_key '{column_key}'의 보드타입 미상. 모든 보드로 복사...")
            for board in ['accident', 'safety_instruction', 'change_request']:
                try:
                    cursor.execute("""
                        INSERT OR IGNORE INTO dropdown_option_codes_v2
                        (board_type, column_key, option_code, option_value, display_order, is_active, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """, (board, column_key, option_code, option_value, display_order, is_active))
                    migrated_count += 1
                except Exception as e:
                    logging.error(f"  - 복사 실패: {column_key}/{option_code} @ {board}: {e}")
                    skipped_count += 1
        else:
            try:
                cursor.execute("""
                    INSERT OR IGNORE INTO dropdown_option_codes_v2
                    (board_type, column_key, option_code, option_value, display_order, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (board_type, column_key, option_code, option_value, display_order, is_active))
                migrated_count += 1
            except Exception as e:
                logging.error(f"  - 마이그레이션 실패: {column_key}/{option_code} @ {board_type}: {e}")
                skipped_count += 1
    
    conn.commit()
    logging.info(f"✅ 마이그레이션 완료: {migrated_count}개, 실패 {skipped_count}개")

def verify_board_isolation(conn):
    """보드별 column_key 격리 검증"""
    logging.info("▶ 보드 격리 검증...")
    cursor = conn.cursor()
    
    duplicates = cursor.execute("""
        SELECT column_key, GROUP_CONCAT(DISTINCT board_type), COUNT(DISTINCT board_type) as cnt
        FROM dropdown_option_codes_v2
        WHERE is_active = 1
        GROUP BY column_key
        HAVING cnt > 1
        ORDER BY column_key
    """).fetchall()
    
    if duplicates:
        logging.warning("⚠️ 여러 보드에서 사용되는 column_key 발견:")
        for column_key, boards, count in duplicates:
            logging.warning(f"  - {column_key}: {boards}")
    else:
        logging.info("✅ 모든 column_key가 단일 보드로 격리됨")
    
    return len(duplicates) == 0

def add_missing_columns(conn):
    """컬럼 설정 테이블에 누락된 필드 추가"""
    logging.info("\n▶ 컬럼 설정 테이블 구조 확인/업데이트 중...")
    
    cursor = conn.cursor()
    
    tables_to_check = [
        'accident_column_config',
        'safety_instruction_column_config', 
        'change_request_column_config'
    ]
    
    for table in tables_to_check:
        # 테이블이 있는지 확인
        cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table}'")
        if not cursor.fetchone():
            logging.info(f"ℹ️ {table} 테이블이 없습니다. 생성 중...")
            
            # 테이블 생성
            cursor.execute(f"""
                CREATE TABLE {table} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    column_key TEXT UNIQUE NOT NULL,
                    column_name TEXT NOT NULL,
                    column_type TEXT NOT NULL,
                    column_order INTEGER DEFAULT 0,
                    is_active INTEGER DEFAULT 1,
                    dropdown_options TEXT,
                    table_name TEXT,
                    table_type TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            logging.info(f"✅ {table} 테이블 생성 완료")
            continue
        
        # 테이블 구조 확인
        columns_info = cursor.execute(f"PRAGMA table_info({table})").fetchall()
        existing_columns = {col[1] for col in columns_info}
        
        # 필요한 컬럼들
        required_columns = {
            'table_name': 'TEXT',
            'table_type': 'TEXT'
        }
        
        # 누락된 컬럼 추가
        for col_name, col_type in required_columns.items():
            if col_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                    logging.info(f"✅ {table}에 {col_name} 컬럼 추가 완료")
                except sqlite3.OperationalError as e:
                    if "duplicate column name" not in str(e).lower():
                        logging.error(f"❌ {table}에 {col_name} 컬럼 추가 실패: {e}")
    
    conn.commit()

def create_backup(conn):
    """데이터베이스 백업 생성"""
    import shutil
    from datetime import datetime
    
    backup_path = f"portal_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
    
    try:
        # 연결을 잠시 닫고 백업
        conn.close()
        shutil.copy2(DB_PATH, backup_path)
        logging.info(f"✅ 백업 생성 완료: {backup_path}")
        # 재연결
        return sqlite3.connect(DB_PATH)
    except Exception as e:
        logging.error(f"❌ 백업 생성 실패: {e}")
        return conn

def main():
    """메인 실행 함수"""
    logging.info("=" * 60)
    logging.info("▶ 보드 격리 정리 스크립트 시작")
    logging.info("=" * 60)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # 1. 백업 생성
        conn = create_backup(conn)
        
        # 2. v2 테이블 생성
        create_v2_table_if_not_exists(conn)
        
        # 3. 컬럼 설정 테이블 구조 업데이트
        add_missing_columns(conn)
        
        # 4. v1 → v2 마이그레이션
        migrate_v1_to_v2(conn)
        
        # 5. 격리 검증
        is_isolated = verify_board_isolation(conn)
        
        if is_isolated:
            logging.info("\n" + "=" * 60)
            logging.info("✅ 모든 정리 작업 완료!")
            logging.info("다음 단계: app.py에서 레거시 코드 제거")
            logging.info("=" * 60)
        else:
            logging.warning("\n" + "=" * 60)
            logging.warning("⚠️ 일부 격리 문제가 있습니다. 로그를 확인하세요")
            logging.warning("=" * 60)
        
        conn.close()
        
    except Exception as e:
        logging.error(f"❗ 오류 발생: {e}")
        raise

if __name__ == "__main__":
    main()
