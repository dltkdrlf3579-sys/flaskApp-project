"""
접속 로그 헬퍼 함수
"""
from flask import request, session
from db_connection import get_db_connection
from datetime import datetime
import time

def log_user_access(action_type='page_view', action_detail=None, response_code=200, response_time_ms=None):
    """사용자 접속 로그 기록"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # 세션에서 사용자 정보 가져오기
        login_id = session.get('user_id', 'anonymous')
        user_name = session.get('user_name', 'Anonymous')
        dept_id = session.get('deptid', '')
        dept_name = session.get('department', '')

        # 요청 정보
        ip_address = request.remote_addr or '0.0.0.0'
        user_agent = request.headers.get('User-Agent', '')[:500]
        session_id = session.get('session_id', '')

        # action_detail이 없으면 현재 경로 사용
        if not action_detail:
            action_detail = request.path

        cursor.execute("""
            INSERT INTO user_access_logs
            (login_id, user_name, dept_id, dept_name, action_type, action_detail,
             ip_address, user_agent, session_id, response_code, response_time_ms)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (login_id, user_name, dept_id, dept_name, action_type, action_detail,
              ip_address, user_agent, session_id, response_code, response_time_ms))

        conn.commit()
        cursor.close()
        conn.close()

    except Exception as e:
        print(f"로그 기록 오류: {e}")

def get_access_logs(limit=100, login_id=None, date_from=None):
    """접속 로그 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT login_id, user_name, dept_name, action_type, action_detail,
               ip_address, accessed_at, response_code
        FROM user_access_logs
        WHERE 1=1
    """
    params = []

    if login_id:
        query += " AND login_id = %s"
        params.append(login_id)

    if date_from:
        query += " AND accessed_at >= %s"
        params.append(date_from)

    query += " ORDER BY accessed_at DESC LIMIT %s"
    params.append(limit)

    cursor.execute(query, params)

    logs = []
    for row in cursor.fetchall():
        logs.append({
            'login_id': row[0],
            'user_name': row[1],
            'dept_name': row[2],
            'action_type': row[3],
            'action_detail': row[4],
            'ip_address': row[5],
            'accessed_at': row[6].strftime('%Y-%m-%d %H:%M:%S') if row[6] else '',
            'response_code': row[7]
        })

    cursor.close()
    conn.close()
    return logs

def get_access_statistics():
    """접속 통계 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()

    stats = {}

    # 오늘 통계
    cursor.execute("""
        SELECT COUNT(DISTINCT login_id) as unique_users,
               COUNT(*) as total_actions,
               COUNT(CASE WHEN action_type = 'login' THEN 1 END) as total_logins,
               COUNT(CASE WHEN action_type = 'page_view' THEN 1 END) as page_views
        FROM user_access_logs
        WHERE DATE(accessed_at) = CURRENT_DATE
    """)

    row = cursor.fetchone()
    stats['today'] = {
        'unique_users': row[0] or 0,
        'total_actions': row[1] or 0,
        'total_logins': row[2] or 0,
        'page_views': row[3] or 0
    }

    # 현재 활성 사용자 (최근 30분)
    cursor.execute("""
        SELECT DISTINCT login_id, user_name, dept_name, MAX(accessed_at) as last_activity
        FROM user_access_logs
        WHERE accessed_at > NOW() - INTERVAL '30 minutes'
        GROUP BY login_id, user_name, dept_name
        ORDER BY last_activity DESC
    """)

    stats['active_users'] = []
    for row in cursor.fetchall():
        stats['active_users'].append({
            'login_id': row[0],
            'user_name': row[1],
            'dept_name': row[2],
            'last_activity': row[3].strftime('%H:%M:%S') if row[3] else ''
        })

    # 가장 많이 접근한 페이지
    cursor.execute("""
        SELECT action_detail, COUNT(*) as access_count
        FROM user_access_logs
        WHERE action_type = 'page_view' AND DATE(accessed_at) = CURRENT_DATE
        GROUP BY action_detail
        ORDER BY access_count DESC
        LIMIT 10
    """)

    stats['top_pages'] = []
    for row in cursor.fetchall():
        stats['top_pages'].append({
            'page': row[0],
            'count': row[1]
        })

    cursor.close()
    conn.close()
    return stats