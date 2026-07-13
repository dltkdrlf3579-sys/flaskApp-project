#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Day 6: Flask 앱 통합 코드 샘플
app.py에 추가해야 할 코드들을 정리한 파일
"""

# ========================================
# 1. Import 추가 (app.py 상단에 추가)
# ========================================
"""
# Day 5-6 권한 시스템 imports
from unified_admin_routes import admin_bp
from simple_cache import get_cache
from simplified_permission_check import simple_check_permission, is_admin, is_manager, has_role
from simple_session import init_session_management, get_session_info, extend_session
from datetime import timedelta
"""

# ========================================
# 2. 앱 초기화 코드 (Flask 앱 생성 직후 추가)
# ========================================
def init_permission_system(app):
    """
    권한 시스템 초기화
    app.py의 app = Flask(__name__) 다음에 추가
    """
    # Blueprint 등록
    from unified_admin_routes import admin_bp
    app.register_blueprint(admin_bp)

    # 세션 관리 초기화
    from simple_session import init_session_management
    init_session_management(app)

    # 전역 캐시 인스턴스
    from simple_cache import get_cache
    app.cache = get_cache()

    # 템플릿에서 권한 체크 함수 사용
    @app.context_processor
    def inject_permission_check():
        from simplified_permission_check import is_admin, is_manager, has_role
        return dict(
            is_admin=is_admin,
            is_manager=is_manager,
            has_role=has_role
        )

    print("✅ Permission system initialized")

# ========================================
# 3. 중요 라우트에 권한 체크 추가
# ========================================

# 예시 1: 사고 삭제 (관리자만)
"""
@app.route('/accident-delete/<int:id>', methods=['POST'])
@simple_check_permission('admin')
def delete_accident(id):
    # 기존 삭제 로직...
    return jsonify({'success': True})
"""

# 예시 2: 변경 요청 승인 (매니저 이상)
"""
@app.route('/change-request-approve/<int:id>', methods=['POST'])
@simple_check_permission('manager')
def approve_change_request(id):
    # 기존 승인 로직...
    return jsonify({'success': True})
"""

# 예시 3: 협력사 등록 (매니저 이상)
"""
@app.route('/partner-register', methods=['POST'])
@simple_check_permission('manager')
def register_partner():
    # 기존 등록 로직...
    return jsonify({'success': True})
"""

# 예시 4: 마스터 데이터 관리 (관리자만)
"""
@app.route('/masterdata')
@simple_check_permission('admin')
def masterdata():
    # 기존 마스터데이터 페이지...
    return render_template('masterdata.html')
"""

# ========================================
# 4. 템플릿 수정 예시
# ========================================

# base.html 또는 navigation 템플릿에 추가
TEMPLATE_NAV_EXAMPLE = """
<!-- 관리자 메뉴 추가 -->
{% if is_admin() %}
<li class="nav-item dropdown">
    <a class="nav-link dropdown-toggle" href="#" role="button" data-bs-toggle="dropdown">
        <i class="bi bi-shield-lock"></i> 관리자
    </a>
    <ul class="dropdown-menu">
        <li><a class="dropdown-item" href="/admin/dashboard">통합 대시보드</a></li>
        <li><a class="dropdown-item" href="/admin/permissions">권한 관리</a></li>
        <li><a class="dropdown-item" href="/admin/audit">감사 로그</a></li>
    </ul>
</li>
{% endif %}
"""

# 버튼에 권한 체크 추가
TEMPLATE_BUTTON_EXAMPLE = """
<!-- 삭제 버튼 (관리자만 표시) -->
{% if is_admin() %}
<button class="btn btn-danger" onclick="deleteItem({{ item.id }})">
    <i class="bi bi-trash"></i> 삭제
</button>
{% endif %}

<!-- 승인 버튼 (매니저 이상만 표시) -->
{% if is_manager() %}
<button class="btn btn-success" onclick="approveRequest({{ request.id }})">
    <i class="bi bi-check-circle"></i> 승인
</button>
{% endif %}
"""

# ========================================
# 5. API 라우트 추가
# ========================================

# 세션 정보 조회 API
"""
@app.route('/api/session-info')
def session_info_api():
    from simple_session import get_session_info
    return jsonify(get_session_info())
"""

# 세션 연장 API (AJAX용)
"""
@app.route('/api/extend-session', methods=['POST'])
def extend_session_api():
    from simple_session import extend_session
    extend_session()
    return jsonify({'success': True, 'message': 'Session extended'})
"""

# 캐시 상태 API
"""
@app.route('/api/cache-status')
@simple_check_permission('admin')
def cache_status_api():
    cache = app.cache
    stats = cache.get_stats()
    return jsonify(stats)
"""

# ========================================
# 6. JavaScript 세션 관리 (템플릿에 추가)
# ========================================

JAVASCRIPT_SESSION_EXAMPLE = """
<script>
// 세션 타임아웃 경고 (25분 후)
let sessionWarningShown = false;

setInterval(function() {
    fetch('/api/session-info')
        .then(response => response.json())
        .then(data => {
            if (data.remaining_minutes < 5 && !sessionWarningShown) {
                sessionWarningShown = true;
                if (confirm('세션이 곧 만료됩니다. 연장하시겠습니까?')) {
                    fetch('/api/extend-session', {method: 'POST'})
                        .then(() => {
                            sessionWarningShown = false;
                            console.log('세션이 연장되었습니다.');
                        });
                }
            }
        });
}, 60000); // 1분마다 체크

// 사용자 활동시 자동 세션 연장
document.addEventListener('click', function() {
    fetch('/api/extend-session', {method: 'POST'});
}, {passive: true});
</script>
"""

# ========================================
# 7. 실제 app.py 적용 예시 (최소 버전)
# ========================================

MINIMAL_INTEGRATION = """
# app.py 최소 통합 버전

# 1. Import 추가
from unified_admin_routes import admin_bp
from simplified_permission_check import simple_check_permission
from simple_session import init_session_management

# 2. Flask 앱 생성 직후
app = Flask(__name__)
app.register_blueprint(admin_bp)
init_session_management(app)

# 3. 중요 라우트 2-3개만 권한 적용
@app.route('/admin')
@simple_check_permission('admin')
def admin_page():
    return render_template('admin.html')

# 4. 완료!
"""

if __name__ == "__main__":
    print("=" * 60)
    print("Day 6 Flask Integration Guide")
    print("=" * 60)
    print("\n이 파일은 app.py에 추가할 코드 샘플입니다.")
    print("\n필요한 부분만 복사해서 사용하세요:")
    print("1. Import 문 추가")
    print("2. Blueprint 등록")
    print("3. 세션 관리 초기화")
    print("4. 중요 라우트 5-10개에 @simple_check_permission 추가")
    print("5. 템플릿에 {% if is_admin() %} 추가")
    print("\n✅ 총 예상 작업 시간: 1시간")