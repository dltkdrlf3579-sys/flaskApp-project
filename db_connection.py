"""
데이터베이스 연결 공통 모듈
모든 서비스에서 사용하는 표준 데이터베이스 연결 설정
WAL 모드와 동시성 설정이 적용된 안전한 연결 제공
"""
import sqlite3
import logging
from typing import Optional

class DatabaseConnection:
    """데이터베이스 연결 관리 클래스"""
    
    @staticmethod
    def get_connection(db_path: str, timeout: float = 10.0, row_factory: bool = False) -> sqlite3.Connection:
        """
        WAL 모드와 동시성 설정이 적용된 데이터베이스 연결 생성
        
        Args:
            db_path: 데이터베이스 파일 경로
            timeout: 연결 타임아웃 (기본값: 10초)
            row_factory: Row factory 사용 여부
            
        Returns:
            설정된 데이터베이스 연결
        """
        try:
            # 연결 생성
            conn = sqlite3.connect(db_path, timeout=timeout)
            
            # Row factory 설정 (필요시)
            if row_factory:
                conn.row_factory = sqlite3.Row
            
            cursor = conn.cursor()
            
            # WAL 모드 설정 (Write-Ahead Logging)
            # 동시에 여러 읽기가 가능하고, 쓰기 중에도 읽기가 가능
            cursor.execute("PRAGMA journal_mode=WAL")
            
            # Busy timeout 설정 (밀리초)
            # 다른 연결이 잠금을 해제할 때까지 대기하는 시간
            cursor.execute("PRAGMA busy_timeout=5000")
            
            # 동기화 모드 설정
            # NORMAL: 안전하면서도 성능이 좋음
            cursor.execute("PRAGMA synchronous=NORMAL")
            
            # 캐시 크기 설정 (페이지 단위, 음수는 KB 단위)
            cursor.execute("PRAGMA cache_size=-2000")  # 2MB 캐시
            
            # 외래 키 제약 조건 활성화
            cursor.execute("PRAGMA foreign_keys=ON")
            
            logging.debug(f"Database connection established: {db_path}")
            return conn
            
        except sqlite3.Error as e:
            logging.error(f"Database connection error: {e}")
            raise
    
    @staticmethod
    def execute_query(conn: sqlite3.Connection, query: str, params: tuple = (), 
                      fetch_one: bool = False, fetch_all: bool = True) -> Optional[any]:
        """
        쿼리 실행 헬퍼 함수
        
        Args:
            conn: 데이터베이스 연결
            query: SQL 쿼리
            params: 쿼리 파라미터
            fetch_one: 단일 결과 반환 여부
            fetch_all: 전체 결과 반환 여부
            
        Returns:
            쿼리 결과
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
                
        except sqlite3.Error as e:
            logging.error(f"Query execution error: {e}")
            raise
    
    @staticmethod
    def close_connection(conn: sqlite3.Connection):
        """
        연결 안전하게 종료
        
        Args:
            conn: 데이터베이스 연결
        """
        if conn:
            try:
                conn.commit()
                conn.close()
                logging.debug("Database connection closed")
            except sqlite3.Error as e:
                logging.error(f"Error closing connection: {e}")


def get_db_connection(db_path: str, timeout: float = 10.0, row_factory: bool = False) -> sqlite3.Connection:
    """
    데이터베이스 연결 생성 (간편 함수)
    
    Args:
        db_path: 데이터베이스 파일 경로
        timeout: 연결 타임아웃 (기본값: 10초)
        row_factory: Row factory 사용 여부
        
    Returns:
        설정된 데이터베이스 연결
    """
    return DatabaseConnection.get_connection(db_path, timeout, row_factory)


# 컨텍스트 매니저로 사용하기 위한 클래스
class DatabaseContextManager:
    """with 문과 함께 사용할 수 있는 데이터베이스 컨텍스트 매니저"""
    
    def __init__(self, db_path: str, timeout: float = 10.0, row_factory: bool = False):
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