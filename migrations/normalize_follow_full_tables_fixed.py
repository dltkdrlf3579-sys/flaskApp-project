#!/usr/bin/env python3
"""
Normalize table names - PostgreSQL 전용 수정 버전
db_connection 의존성 제거
"""
import logging
import psycopg
import configparser
import sys
import os

# 상위 디렉토리 경로 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_postgres_connection():
    """PostgreSQL 직접 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
    return psycopg.connect(dsn)

def table_exists(cur, table: str) -> bool:
    try:
        cur.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name = %s",
            (table.lower(),)
        )
        return cur.fetchone() is not None
    except Exception:
        return False

def column_exists(cur, table: str, column: str) -> bool:
    try:
        cur.execute(
            "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
            (table.lower(), column.lower())
        )
        return cur.fetchone() is not None
    except Exception:
        return False

def safe_rename_table(conn, cur, old: str, new: str):
    if old == new:
        return
    if table_exists(cur, new):
        logging.info(f"[SKIP] {new} already exists")
        return
    if not table_exists(cur, old):
        logging.info(f"[SKIP] {old} not found")
        return
    try:
        cur.execute(f"ALTER TABLE IF EXISTS {old} RENAME TO {new}")
        logging.info(f"[OK] Renamed {old} -> {new}")
    except Exception as e:
        logging.error(f"[ERROR] Rename {old} -> {new}: {e}")

def ensure_timestamp_columns(cur, table: str):
    # created_at
    if not column_exists(cur, table, 'created_at'):
        try:
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
            logging.info(f"[OK] {table}: added created_at")
        except Exception as e:
            logging.error(f"[ERROR] {table}: cannot add created_at - {e}")

    # updated_at
    if not column_exists(cur, table, 'updated_at'):
        try:
            cur.execute(
                f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
            )
            logging.info(f"[OK] {table}: added updated_at")
        except Exception as e:
            logging.error(f"[ERROR] {table}: cannot add updated_at - {e}")

def main():
    print("PostgreSQL 테이블 정규화 시작...")
    
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()

        # Normalize table names
        pairs = [
            ('followsop', 'follow_sop'),
            ('followsop_column_config', 'follow_sop_column_config'),
            ('followsop_details', 'follow_sop_details'),
            ('followsop_attachments', 'follow_sop_attachments'),
            ('fullprocess', 'full_process'),
            ('fullprocess_column_config', 'full_process_column_config'),
            ('fullprocess_details', 'full_process_details'),
            ('fullprocess_attachments', 'full_process_attachments'),
            # accidents 관련
            ('accident', 'accidents'),  # accident -> accidents로 통일
            ('safety_instruction', 'safety_instructions'),  # 복수형으로 통일
        ]

        # Begin transaction
        cur.execute("START TRANSACTION")

        print("\n=== 테이블명 정규화 ===")
        for old, new in pairs:
            safe_rename_table(conn, cur, old, new)

        # Ensure timestamp columns on key tables
        print("\n=== 타임스탬프 컬럼 확인 ===")
        for table in ['safety_instructions', 'accidents', 'follow_sop', 'full_process']:
            if table_exists(cur, table):
                ensure_timestamp_columns(cur, table)
            else:
                logging.info(f"[SKIP] {table}: table not found")

        conn.commit()
        print("\n[완료] 정규화 완료!")
        
        # 결과 확인
        print("\n=== 현재 테이블 목록 ===")
        cur.execute("""
            SELECT table_name FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND (table_name LIKE '%follow%' OR table_name LIKE '%full%' 
                 OR table_name LIKE '%accident%' OR table_name LIKE '%safety%')
            ORDER BY table_name
        """)
        tables = cur.fetchall()
        for table in tables:
            print(f"  - {table[0]}")
            
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        logging.error(f"[FAILED] {e}")
        raise
    finally:
        try:
            conn.close()
        except:
            pass

if __name__ == '__main__':
    main()