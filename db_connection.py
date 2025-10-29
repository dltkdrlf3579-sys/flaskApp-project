"""PostgreSQL 전용 DB 연결 모듈."""

import logging
import configparser
import sqlite3  # sqlite3.Row 재사용용 (커서 결과 dict 변환)
from typing import Optional

from db.compat import CompatConnection


def _load_config() -> configparser.ConfigParser:
    config = configparser.ConfigParser()
    try:
        config.read('config.ini', encoding='utf-8')
    except Exception as exc:
        logging.warning("config.ini 읽기 실패 (기본값 사용): %s", exc)
    return config


def _require_postgres_backend(config: configparser.ConfigParser) -> str:
    backend = config.get('DATABASE', 'db_backend', fallback='postgres').strip().lower()
    if backend != 'postgres':
        raise RuntimeError(
            "DATABASE.db_backend 는 이제 'postgres' 만 지원합니다. "
            "config.ini 를 수정하거나 Postgres 연결을 점검하세요."
        )
    dsn = config.get('DATABASE', 'postgres_dsn', fallback='').strip()
    if not dsn:
        raise RuntimeError("DATABASE.postgres_dsn 값이 비어 있습니다. Postgres DSN을 설정하세요.")
    return dsn


def get_db_connection(db_path: str = None, timeout: float = 10.0, row_factory: bool = False):
    """PostgreSQL 연결을 생성한다. 실패 시 예외를 그대로 전파한다."""

    config = _load_config()

    log_backend = config.getboolean('LOGGING', 'log_db_backend', fallback=False)
    if log_backend:
        logging.info("DB Backend: postgres")

    dsn = _require_postgres_backend(config)

    conn = CompatConnection(backend='postgres', dsn=dsn, timeout=timeout)
    logging.debug("PostgreSQL connection established: %s", dsn)

    if row_factory:
        conn.row_factory = sqlite3.Row

    return conn


def get_postgres_dsn() -> str:
    """config.ini에서 PostgreSQL DSN을 읽어온다."""

    config = _load_config()
    return _require_postgres_backend(config)


class DatabaseConnection:
    """기존 코드 호환용 클래스 - 내부에서 get_db_connection 사용"""

    @staticmethod
    def get_connection(db_path: str, timeout: float = 10.0, row_factory: bool = False):
        """
        기존 코드 호환용 - 내부적으로 새로운 get_db_connection 사용
        """
        return get_db_connection(db_path, timeout, row_factory)
    
    @staticmethod
    def execute_query(conn, query: str, params: tuple = (), 
                      fetch_one: bool = False, fetch_all: bool = True) -> Optional[any]:
        """
        쿼리 실행 헬퍼 함수 - CompatConnection에서도 동작
        """
        try:
            cursor = conn.cursor()
            cursor.execute(query, params)
            
            if fetch_one:
                return cursor.fetchone()
            elif fetch_all:
                return cursor.fetchall()
            else:
                return cursor.rowcount
                
        except Exception as e:
            logging.error(f"Query execution error: {e}")
            raise
    
    @staticmethod
    def close_connection(conn):
        """
        연결 안전하게 종료 - CompatConnection에서도 동작
        """
        if conn:
            try:
                conn.commit()
                conn.close()
                logging.debug("Database connection closed")
            except Exception as e:
                logging.error(f"Error closing connection: {e}")


class DatabaseContextManager:
    """with 문과 함께 사용할 수 있는 데이터베이스 컨텍스트 매니저 - v7 호환"""
    
    def __init__(self, db_path: str = None, timeout: float = 10.0, row_factory: bool = False):
        self.db_path = db_path
        self.timeout = timeout
        self.row_factory = row_factory
        self.conn = None
    
    def __enter__(self):
        self.conn = get_db_connection(self.db_path, self.timeout, self.row_factory)
        return self.conn
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.conn:
            if exc_type:
                self.conn.rollback()
            else:
                self.conn.commit()
            self.conn.close()


# v7: 백엔드 상태 확인 함수 (디버그용)
def check_backend_status():
    """현재 설정된 백엔드 상태 확인"""
    config = _load_config()

    try:
        dsn = _require_postgres_backend(config)
    except RuntimeError as exc:
        print(f"ERROR: {exc}")
        return

    print("Current DB Backend: postgres")
    print(f"PostgreSQL DSN: {dsn}")

    try:
        conn = get_db_connection()
        print("OK - PostgreSQL connection: SUCCESS")
        conn.close()
    except Exception as exc:
        print(f"ERROR - PostgreSQL connection: FAILED - {exc}")


if __name__ == "__main__":
    # 테스트 실행
    check_backend_status()
