"""
데이터베이스 연결 통합 모듈 - v7 (SQLite/PostgreSQL 통합)
v7 계획에 따라 CompatConnection을 반환하여 투명한 호환성 제공
"""
import sqlite3
import logging
import configparser
from typing import Optional
from db.compat import CompatConnection


def get_db_connection(db_path: str = None, timeout: float = 10.0, row_factory: bool = False):
    """
    통합 DB 연결 함수 - v7 호환 레이어
    
    Args:
        db_path: SQLite DB 경로 (PostgreSQL일 때는 무시)
        timeout: 연결 타임아웃
        row_factory: sqlite3.Row 사용 여부
    
    Returns:
        CompatConnection 객체 (SQLite/PostgreSQL 투명 처리)
    """
    
    # config.ini에서 설정 읽기
    config = configparser.ConfigParser()
    try:
        config.read('config.ini', encoding='utf-8')
    except Exception as e:
        logging.warning(f"config.ini 읽기 실패, 기본값 사용: {e}")
    
    # 백엔드 결정
    backend = config.get('DATABASE', 'db_backend', fallback='sqlite')
    
    # 로깅 설정 확인
    log_backend = config.getboolean('LOGGING', 'log_db_backend', fallback=False)
    if log_backend:
        logging.info(f"DB Backend: {backend}")
    
    if backend == 'postgres':
        # PostgreSQL 연결
        try:
            dsn = config.get('DATABASE', 'postgres_dsn')
            conn = CompatConnection(backend='postgres', dsn=dsn, timeout=timeout)
            logging.debug(f"PostgreSQL connection established: {dsn}")
        except Exception as e:
            logging.error(f"PostgreSQL connection error: {e}")
            logging.warning("Falling back to SQLite")
            # Fallback to SQLite
            backend = 'sqlite'
        else:
            # PostgreSQL 연결 성공 시 row_factory 설정
            if row_factory:
                conn.row_factory = sqlite3.Row
            return conn
    
    # SQLite 연결 (기본 또는 fallback)
    if db_path is None:
        db_path = config.get('DATABASE', 'local_db_path', fallback='portal.db')
    
    try:
        conn = CompatConnection(backend='sqlite', database=db_path, timeout=timeout)
        logging.debug(f"SQLite connection established: {db_path}")
        
        # row_factory 설정
        if row_factory:
            conn.row_factory = sqlite3.Row
        
        return conn
        
    except Exception as e:
        logging.error(f"SQLite connection error: {e}")
        raise


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
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    backend = config.get('DATABASE', 'db_backend', fallback='sqlite')
    
    print(f"Current DB Backend: {backend}")
    
    if backend == 'postgres':
        dsn = config.get('DATABASE', 'postgres_dsn', fallback='Not configured')
        print(f"PostgreSQL DSN: {dsn}")
        
        # 연결 테스트
        try:
            conn = get_db_connection()
            print("OK - PostgreSQL connection: SUCCESS")
            conn.close()
        except Exception as e:
            print(f"ERROR - PostgreSQL connection: FAILED - {e}")
    else:
        db_path = config.get('DATABASE', 'local_db_path', fallback='portal.db')
        print(f"SQLite Path: {db_path}")
        
        # 연결 테스트
        try:
            conn = get_db_connection()
            print("OK - SQLite connection: SUCCESS")
            conn.close()
        except Exception as e:
            print(f"ERROR - SQLite connection: FAILED - {e}")


if __name__ == "__main__":
    # 테스트 실행
    check_backend_status()