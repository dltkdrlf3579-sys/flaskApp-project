"""
사용자 접속 로그 테이블 생성 및 관리
"""
from db_connection import get_db_connection
from datetime import datetime

def create_access_log_table():
    """접속 로그 테이블 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 접속 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_access_logs (
                id SERIAL PRIMARY KEY,
                login_id VARCHAR(100),
                user_name VARCHAR(200),
                dept_id VARCHAR(100),
                dept_name VARCHAR(200),
                action_type VARCHAR(50),  -- login, logout, page_view, api_call
                action_detail VARCHAR(500),
                ip_address VARCHAR(45),
                user_agent TEXT,
                session_id VARCHAR(200),
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                response_code INTEGER,
                response_time_ms INTEGER
            )
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_login_id ON user_access_logs(login_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_accessed_at ON user_access_logs(accessed_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_logs_action_type ON user_access_logs(action_type)")

        # 일일 통계 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_access_stats (
                id SERIAL PRIMARY KEY,
                date DATE,
                total_logins INTEGER DEFAULT 0,
                unique_users INTEGER DEFAULT 0,
                total_page_views INTEGER DEFAULT 0,
                total_api_calls INTEGER DEFAULT 0,
                avg_response_time_ms INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        print("접속 로그 테이블 생성 완료")

    except Exception as e:
        print(f"테이블 생성 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

def add_sample_logs():
    """샘플 로그 데이터 추가"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        sample_logs = [
            ('dev_super', '개발슈퍼관리자', 'DEPT000', '전산팀', 'login', 'SSO 로그인', '192.168.1.100'),
            ('safety_manager', '박안전', 'DEPT100', '안전관리팀', 'login', 'SSO 로그인', '192.168.1.101'),
            ('safety_manager', '박안전', 'DEPT100', '안전관리팀', 'page_view', '/accident', '192.168.1.101'),
            ('normal_user', '홍길동', 'DEPT201', '생산1팀', 'login', 'SSO 로그인', '192.168.1.102'),
            ('normal_user', '홍길동', 'DEPT201', '생산1팀', 'page_view', '/safety-instruction', '192.168.1.102'),
            ('audit_reader', '감사원', 'DEPT400', '감사팀', 'login', 'SSO 로그인', '192.168.1.103'),
            ('new_employee', '신입사원', 'DEPT999', '인사팀', 'login', 'SSO 로그인', '192.168.1.104'),
            ('new_employee', '신입사원', 'DEPT999', '인사팀', 'page_view', '/accident (403 Error)', '192.168.1.104'),
        ]

        for log in sample_logs:
            cursor.execute("""
                INSERT INTO user_access_logs
                (login_id, user_name, dept_id, dept_name, action_type, action_detail, ip_address, response_code, response_time_ms)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, log + (200 if '403' not in log[5] else 403, 150))

        conn.commit()
        print(f"{len(sample_logs)}개 샘플 로그 추가 완료")

    except Exception as e:
        print(f"샘플 데이터 추가 오류: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    create_access_log_table()
    add_sample_logs()