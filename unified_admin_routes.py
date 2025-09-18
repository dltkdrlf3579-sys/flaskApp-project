#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 5: 통합 관리자 라우트
Flask app.py에 추가해야 할 라우트들
"""

from flask import Blueprint, render_template, jsonify, request, session, abort
from functools import wraps
import psycopg2
from datetime import datetime
from simple_cache import get_cache
from batch_permission import batch_grant_permissions, batch_copy_permissions
import logging

logger = logging.getLogger(__name__)

# Blueprint 생성
admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# 데이터베이스 연결
def get_db_connection():
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    if config.has_option('DATABASE', 'postgres_dsn'):
        dsn = config.get('DATABASE', 'postgres_dsn')
        return psycopg2.connect(dsn)
    else:
        return psycopg2.connect(
            host='localhost',
            database='portal_db',
            user='postgres',
            password='postgres'
        )

# 간단한 권한 체크 데코레이터
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 세션에서 사용자 역할 확인
        user_role = session.get('role', 'user')
        if user_role not in ['admin', 'super_admin']:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# 통합 대시보드
@admin_bp.route('/dashboard')
@admin_required
def unified_dashboard():
    """통합 관리 대시보드"""
    return render_template('admin/unified_dashboard.html')

# 대시보드 통계 API
@admin_bp.route('/dashboard/stats')
def dashboard_stats():
    """대시보드 통계 조회"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        stats = {}

        # 전체 사용자 수
        cursor.execute("SELECT COUNT(*) FROM system_users WHERE is_active = true")
        stats['total_users'] = cursor.fetchone()[0]

        # 활성 세션 (최근 30분)
        cursor.execute("""
            SELECT COUNT(DISTINCT emp_id) FROM access_audit_log
            WHERE created_at > NOW() - INTERVAL '30 minutes'
        """)
        stats['active_sessions'] = cursor.fetchone()[0]

        # 대기 중인 권한 요청
        cursor.execute("""
            SELECT COUNT(*) FROM permission_requests
            WHERE status = 'pending'
        """)
        stats['pending_requests'] = cursor.fetchone()[0]

        # 시스템 건강도 (간단한 계산)
        stats['system_health'] = 95  # 실제로는 여러 메트릭 기반 계산 필요

        # 활성 알림
        cursor.execute("""
            SELECT COUNT(*) FROM access_audit_log
            WHERE success = false AND created_at > NOW() - INTERVAL '1 hour'
        """)
        failed_attempts = cursor.fetchone()[0]
        stats['active_alerts'] = 1 if failed_attempts > 5 else 0

        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error fetching stats: {e}")
        return jsonify({
            'total_users': 0,
            'active_sessions': 0,
            'pending_requests': 0,
            'system_health': 0,
            'active_alerts': 0
        })

    finally:
        cursor.close()
        conn.close()

# 최근 변경사항 API
@admin_bp.route('/recent-changes')
@admin_required
def recent_changes():
    """최근 권한 변경사항"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT
                emp_id,
                menu_code,
                updated_at,
                updated_by
            FROM user_menu_permissions
            WHERE updated_at > NOW() - INTERVAL '24 hours'
            ORDER BY updated_at DESC
            LIMIT 10
        """)

        changes = []
        for emp_id, menu_code, updated_at, updated_by in cursor.fetchall():
            changes.append({
                'time': updated_at.strftime('%Y-%m-%d %H:%M'),
                'description': f"{emp_id}의 {menu_code} 권한 변경 (by {updated_by or 'System'})"
            })

        return jsonify(changes)

    except Exception as e:
        logger.error(f"Error fetching recent changes: {e}")
        return jsonify([])

    finally:
        cursor.close()
        conn.close()

# 캐시 정리 API
@admin_bp.route('/cache/clear', methods=['POST'])
@admin_required
def clear_cache():
    """캐시 정리"""
    try:
        cache = get_cache()

        # 특정 사용자 캐시만 정리할 경우
        emp_id = request.json.get('emp_id') if request.json else None

        if emp_id:
            cache.clear_user(emp_id)
            message = f"Cleared cache for user {emp_id}"
        else:
            # 전체 캐시 정리 (메모리 캐시인 경우)
            cache.cache.clear()
            cache.cache_expiry.clear()
            message = "All cache cleared"

        logger.info(message)
        return jsonify({'success': True, 'message': message})

    except Exception as e:
        logger.error(f"Error clearing cache: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 데이터 동기화 API
@admin_bp.route('/sync', methods=['POST'])
@admin_required
def sync_data():
    """데이터 동기화 (SSO 등)"""
    try:
        # 여기서는 간단한 동기화 시뮬레이션
        # 실제로는 SSO 시스템과 연동 필요

        conn = get_db_connection()
        cursor = conn.cursor()

        # 마지막 동기화 시간 업데이트
        cursor.execute("""
            UPDATE system_users
            SET last_sync = NOW()
            WHERE is_active = true
        """)

        synced_count = cursor.rowcount
        conn.commit()

        cursor.close()
        conn.close()

        return jsonify({
            'success': True,
            'message': f'Synced {synced_count} users'
        })

    except Exception as e:
        logger.error(f"Error syncing data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 배치 권한 부여 API
@admin_bp.route('/permissions/batch-grant', methods=['POST'])
@admin_required
def batch_grant():
    """대량 권한 부여"""
    try:
        data = request.json
        assignments = data.get('assignments', [])

        if not assignments:
            return jsonify({'success': False, 'error': 'No assignments provided'}), 400

        result = batch_grant_permissions(assignments)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in batch grant: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 권한 복사 API
@admin_bp.route('/permissions/copy', methods=['POST'])
@admin_required
def copy_permissions():
    """권한 복사"""
    try:
        data = request.json
        source_emp_id = data.get('source_emp_id')
        target_emp_ids = data.get('target_emp_ids', [])

        if not source_emp_id or not target_emp_ids:
            return jsonify({'success': False, 'error': 'Invalid parameters'}), 400

        result = batch_copy_permissions(source_emp_id, target_emp_ids)

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error copying permissions: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# 캐시 통계 API
@admin_bp.route('/cache/stats')
@admin_required
def cache_stats():
    """캐시 통계"""
    try:
        cache = get_cache()
        stats = cache.get_stats()
        return jsonify(stats)

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({'error': str(e)}), 500

# Flask app.py에 추가할 코드
def register_admin_routes(app):
    """
    Flask 앱에 관리자 라우트 등록

    사용법:
    from unified_admin_routes import register_admin_routes
    register_admin_routes(app)
    """
    app.register_blueprint(admin_bp)
    logger.info("Admin routes registered")

# 또는 app.py에 직접 추가할 수 있는 버전
"""
# app.py에 추가할 코드:

from unified_admin_routes import admin_bp
app.register_blueprint(admin_bp)

# 또는 개별 라우트 추가:

@app.route('/admin/dashboard')
def admin_dashboard():
    # 권한 체크
    if session.get('role') not in ['admin', 'super_admin']:
        abort(403)
    return render_template('admin/unified_dashboard.html')
"""

if __name__ == "__main__":
    # 테스트용
    from flask import Flask
    app = Flask(__name__)
    app.secret_key = 'test-secret-key'

    # Blueprint 등록
    app.register_blueprint(admin_bp)

    print("Admin routes registered:")
    for rule in app.url_map.iter_rules():
        if rule.endpoint.startswith('admin.'):
            print(f"  {rule.rule} -> {rule.endpoint}")

    # 테스트 서버 실행 (실제로는 app.py에서 실행)
    # app.run(debug=True, port=5001)