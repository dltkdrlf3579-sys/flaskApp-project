"""
IQADB_CONNECT310 Module - External Database Connection
외부 전사 DB 연동 모듈 (config.ini의 쿼리 사용)
실제로는 동일한 PostgreSQL을 사용하지만 별도 스키마(iqadb)를 통해 격리
"""

import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import logging
import os
import configparser

# 로깅 설정
logger = logging.getLogger(__name__)

class IQADBConnection:
    """IQADB 연결 클래스"""

    def __init__(self):
        # PostgreSQL 연결 (iqadb 스키마 사용)
        self.dsn = os.getenv(
            'IQADB_DSN',
            'postgresql://postgres:admin123@localhost:5432/portal_dev'
        )
        self.schema = 'iqadb'
        self.conn = None
        self._connect()

    def _connect(self):
        """데이터베이스 연결"""
        try:
            self.conn = psycopg2.connect(self.dsn)
            # iqadb 스키마 설정
            with self.conn.cursor() as cur:
                cur.execute(f"SET search_path TO {self.schema}, public")
                self.conn.commit()
            logger.info(f"IQADB 연결 성공 (스키마: {self.schema})")
        except Exception as e:
            logger.error(f"IQADB 연결 실패: {e}")
            raise

    def cursor(self):
        """커서 반환"""
        if not self.conn or self.conn.closed:
            self._connect()
        return self.conn.cursor(cursor_factory=RealDictCursor)

    def close(self):
        """연결 종료"""
        if self.conn:
            self.conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def iqadb1():
    """
    database_config.py에서 사용하는 연결 함수
    conn = iqadb1()
    """
    return IQADBConnection()


def iqaconn():
    """
    search_popup_service.py에서 사용하는 연결 함수
    from IQADB_CONNECT310 import iqaconn
    """
    return IQADBConnection()


def execute_SQL(query):
    """
    database_config.py의 execute_SQL 함수와 호환
    DataFrame 반환
    """
    try:
        with iqadb1() as conn:
            df = pd.read_sql_query(query, conn.conn)
            logger.info(f"쿼리 실행 성공: {len(df)} 건 조회")
            return df
    except Exception as e:
        logger.error(f"쿼리 실행 실패: {e}")
        raise


def init_iqadb_schema():
    """iqadb 스키마 초기화 (한 번만 실행)"""
    try:
        conn = psycopg2.connect('postgresql://postgres:admin123@localhost:5432/portal_dev')
        conn.autocommit = True

        with conn.cursor() as cur:
            # 스키마 생성
            cur.execute("CREATE SCHEMA IF NOT EXISTS iqadb AUTHORIZATION postgres")

            # iqadb 스키마로 전환
            cur.execute("SET search_path TO iqadb")

            # 테이블 생성 (config.ini의 쿼리와 매칭되도록)

            # 1. partners 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS partners (
                    business_number VARCHAR(20) PRIMARY KEY,
                    company_name VARCHAR(200),
                    partner_class VARCHAR(50),
                    business_type_major VARCHAR(100),
                    business_type_minor VARCHAR(100),
                    hazard_work_flag BOOLEAN DEFAULT false,
                    representative VARCHAR(100),
                    address TEXT,
                    average_age INTEGER,
                    annual_revenue BIGINT,
                    transaction_count INTEGER,
                    permanent_workers INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 2. accidents 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS accidents (
                    accident_number VARCHAR(50) PRIMARY KEY,
                    accident_name VARCHAR(200),
                    workplace VARCHAR(100),
                    accident_grade VARCHAR(20),
                    major_category VARCHAR(100),
                    injury_form VARCHAR(100),
                    injury_type VARCHAR(100),
                    accident_date DATE,
                    day_of_week VARCHAR(10),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    building VARCHAR(50),
                    floor VARCHAR(20),
                    location_category VARCHAR(100),
                    location_detail TEXT
                )
            """)

            # 3. buildings 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS buildings (
                    building_code VARCHAR(50) PRIMARY KEY,
                    building_name VARCHAR(100),
                    SITE VARCHAR(100),
                    SITE_TYPE VARCHAR(50)
                )
            """)

            # 4. departments 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS departments (
                    dept_code VARCHAR(50) PRIMARY KEY,
                    dept_name VARCHAR(100),
                    parent_dept_code VARCHAR(50)
                )
            """)

            # 5. contractors 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS contractors (
                    worker_id VARCHAR(50) PRIMARY KEY,
                    worker_name VARCHAR(100),
                    company_name VARCHAR(200),
                    business_number VARCHAR(20)
                )
            """)

            # 6. employees 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS employees (
                    employee_id VARCHAR(50) PRIMARY KEY,
                    employee_name VARCHAR(100),
                    department_name VARCHAR(100)
                )
            """)

            # 7. divisions 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS divisions (
                    division_code VARCHAR(50) PRIMARY KEY,
                    division_name VARCHAR(100),
                    parent_division_code VARCHAR(50),
                    division_level INTEGER,
                    division_manager VARCHAR(100),
                    division_location VARCHAR(200)
                )
            """)

            # 8. safety_instructions 테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS safety_instructions (
                    issue_number VARCHAR(50) PRIMARY KEY,
                    issuer_dept VARCHAR(100),
                    issuer_user_name VARCHAR(100),
                    issued_date DATE,
                    subject TEXT,
                    safety_type VARCHAR(100),
                    location VARCHAR(200),
                    target_audience TEXT,
                    violation_type VARCHAR(100),
                    violation_content TEXT,
                    corrective_action TEXT,
                    risk_level VARCHAR(50),
                    department VARCHAR(100),
                    team VARCHAR(100),
                    primary_company_bizno VARCHAR(20),
                    primary_company_name VARCHAR(200),
                    memo TEXT,
                    reviewed_by VARCHAR(100),
                    review_date DATE,
                    status VARCHAR(50),
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 9. 외부_followsop_테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "외부_followsop_테이블" (
                    id SERIAL PRIMARY KEY,
                    work_req_no VARCHAR(50),
                    created_date DATE,
                    creator_name VARCHAR(100),
                    department VARCHAR(100),
                    process_name VARCHAR(200),
                    sop_number VARCHAR(50),
                    sop_version VARCHAR(20),
                    work_type VARCHAR(100),
                    work_location VARCHAR(200),
                    equipment_used TEXT,
                    materials_used TEXT,
                    compliance_status VARCHAR(50),
                    deviation_details TEXT,
                    corrective_action TEXT,
                    inspector_name VARCHAR(100),
                    inspection_date DATE,
                    approval_status VARCHAR(50),
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 10. 외부_fullprocess_테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "외부_fullprocess_테이블" (
                    id SERIAL PRIMARY KEY,
                    fullprocess_number VARCHAR(50),
                    process_id VARCHAR(50),
                    process_name VARCHAR(200),
                    start_date DATE,
                    end_date DATE,
                    responsible_dept VARCHAR(100),
                    process_owner VARCHAR(100),
                    current_stage VARCHAR(100),
                    completion_rate INTEGER,
                    milestone_1 TEXT,
                    milestone_2 TEXT,
                    milestone_3 TEXT,
                    milestone_4 TEXT,
                    risk_assessment VARCHAR(50),
                    budget_allocated BIGINT,
                    budget_used BIGINT,
                    team_members TEXT,
                    status VARCHAR(50),
                    review_comments TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 11. 외부_partner_change_requests_테이블
            cur.execute("""
                CREATE TABLE IF NOT EXISTS "외부_partner_change_requests_테이블" (
                    id SERIAL PRIMARY KEY,
                    request_number VARCHAR(50),
                    requester_name VARCHAR(100),
                    requester_department VARCHAR(100),
                    company_name VARCHAR(200),
                    business_number VARCHAR(20),
                    change_type VARCHAR(100),
                    current_value TEXT,
                    new_value TEXT,
                    change_reason TEXT,
                    status VARCHAR(50),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            logger.info("iqadb 스키마 및 테이블 생성 완료")

        conn.close()
        return True

    except Exception as e:
        logger.error(f"스키마 초기화 실패: {e}")
        return False


if __name__ == "__main__":
    # 테스트 코드
    logging.basicConfig(level=logging.INFO)

    print("=" * 50)
    print("IQADB_CONNECT310 모듈 테스트")
    print("=" * 50)

    # 스키마 초기화
    if init_iqadb_schema():
        print("[OK] Schema initialization success")

    # 연결 테스트
    try:
        with iqadb1() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT current_schema()")
                schema = cur.fetchone()
                print(f"[OK] Current schema: {schema['current_schema']}")
    except Exception as e:
        print(f"[ERROR] Connection test failed: {e}")