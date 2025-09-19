"""
권한 시스템 실제 구현 방안

현재 상태:
- 권한 테이블과 API는 완성
- 하지만 실제 라우트에는 미적용

구현 방법 2가지:

1. 메뉴 숨기기 방식 (권장)
   - 권한이 없는 메뉴는 아예 안 보임
   - base.html에서 동적으로 메뉴 렌더링

2. 접근 차단 방식
   - 메뉴는 보이지만 클릭시 권한 없음 메시지
   - 각 라우트에 @check_permission 데코레이터 추가
"""

# ========================================
# 방법 1: 메뉴 숨기기 (권장)
# ========================================

def implement_menu_hiding():
    """
    base.html 수정 - 권한 있는 메뉴만 표시
    """

    # 1. app.py에서 사용자 메뉴 조회
    menu_code = """
from permission_utils import get_user_menus

@app.context_processor
def inject_user_menus():
    '''템플릿에 사용자 메뉴 주입'''
    user_menus = get_user_menus()
    return dict(user_menus=user_menus)
    """

    # 2. base.html 메뉴 렌더링 수정
    template_code = """
<!-- 동적 메뉴 렌더링 -->
{% for menu in user_menus %}
    {% if menu.code == 'VENDOR_MGT' %}
        <li class="nav-item">
            <a class="nav-link" href="/vendor-management">
                <i class="fas fa-building"></i> 협력사 기준정보
            </a>
        </li>
    {% elif menu.code == 'ACCIDENT_MGT' %}
        <li class="nav-item">
            <a class="nav-link" href="/accident-management">
                <i class="fas fa-exclamation-triangle"></i> 협력사 사고
            </a>
        </li>
    {% elif menu.code == 'SAFETY_INSTRUCTION' %}
        <li class="nav-item">
            <a class="nav-link" href="/safety-instruction">
                <i class="fas fa-clipboard-check"></i> 환경안전 지시서
            </a>
        </li>
    {% endif %}
{% endfor %}
    """

    return menu_code, template_code

# ========================================
# 방법 2: 접근 차단 (보안 강화)
# ========================================

def implement_access_control():
    """
    각 라우트에 권한 체크 추가
    """

    route_protection = """
# app.py 수정
from permission_utils import check_permission
from combined_permission_check import can_view, can_edit, can_delete

# 협력사 기준정보
@app.route('/vendor-management')
def vendor_management():
    if not can_view('VENDOR_MGT'):
        return render_template('error/403.html'), 403
    return render_template('vendor_management.html')

# 협력사 사고
@app.route('/accident-management')
def accident_management():
    if not can_view('ACCIDENT_MGT'):
        return render_template('error/403.html'), 403

    # 데이터 조회시 권한 레벨 체크
    read_level = get_user_permission_level('ACCIDENT_MGT', 'read')

    if read_level == 0:
        accidents = []  # 권한 없음
    elif read_level == 1:
        accidents = get_my_accidents()  # 본인 것만
    elif read_level == 2:
        accidents = get_dept_accidents()  # 부서 것만
    else:  # level 3
        accidents = get_all_accidents()  # 전체

    return render_template('accident_management.html', accidents=accidents)

# 데이터 수정
@app.route('/accident-edit/<id>', methods=['POST'])
def edit_accident(id):
    write_level = get_user_permission_level('ACCIDENT_MGT', 'write')
    accident = get_accident(id)

    if write_level == 0:
        return jsonify({'error': '수정 권한이 없습니다'}), 403
    elif write_level == 1:
        if accident.created_by != session['user_id']:
            return jsonify({'error': '본인이 작성한 것만 수정 가능합니다'}), 403
    elif write_level == 2:
        if accident.dept_id != session['deptid']:
            return jsonify({'error': '같은 부서 데이터만 수정 가능합니다'}), 403
    # level 3은 모두 수정 가능

    # 수정 처리...
    return jsonify({'success': True})
    """

    return route_protection

# ========================================
# 권한 레벨 체크 함수
# ========================================

def get_user_permission_level(menu_code, permission_type='read'):
    """
    사용자의 권한 레벨 조회 (0-3)
    """
    from db_connection import get_db_connection
    from flask import session

    conn = get_db_connection()
    cursor = conn.cursor()

    login_id = session.get('user_id')
    dept_id = session.get('deptid')

    # 개인 권한 확인
    cursor.execute("""
        SELECT read_level, write_level
        FROM user_menu_permissions
        WHERE login_id = %s AND menu_code = %s
        AND is_active = true
    """, (login_id, menu_code))

    user_perm = cursor.fetchone()

    # 부서 권한 확인
    cursor.execute("""
        SELECT read_level, write_level
        FROM dept_menu_permissions
        WHERE dept_id = %s AND menu_code = %s
        AND is_active = true
    """, (dept_id, menu_code))

    dept_perm = cursor.fetchone()

    # OR 연산 (높은 권한 우선)
    if permission_type == 'read':
        user_level = user_perm[0] if user_perm else 0
        dept_level = dept_perm[0] if dept_perm else 0
    else:  # write
        user_level = user_perm[1] if user_perm else 0
        dept_level = dept_perm[1] if dept_perm else 0

    cursor.close()
    conn.close()

    return max(user_level, dept_level)

# ========================================
# 403 에러 페이지
# ========================================

error_403_template = """
<!-- templates/error/403.html -->
<!DOCTYPE html>
<html>
<head>
    <title>접근 권한 없음</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            background: #f5f5f5;
        }
        .error-container {
            text-align: center;
            padding: 40px;
            background: white;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 { color: #d9534f; }
        .btn {
            display: inline-block;
            margin-top: 20px;
            padding: 10px 20px;
            background: #007bff;
            color: white;
            text-decoration: none;
            border-radius: 5px;
        }
    </style>
</head>
<body>
    <div class="error-container">
        <h1>403 - 접근 권한 없음</h1>
        <p>이 페이지에 접근할 권한이 없습니다.</p>
        <p>필요한 권한이 있다고 생각하시면 관리자에게 문의하세요.</p>
        <a href="/" class="btn">메인으로 돌아가기</a>
        <a href="/permission-request" class="btn">권한 신청하기</a>
    </div>
</body>
</html>
"""

if __name__ == "__main__":
    print("=" * 50)
    print("권한 시스템 구현 가이드")
    print("=" * 50)
    print("\n현재 상황:")
    print("- 권한 DB와 관리 UI는 완성")
    print("- 실제 적용은 안 됨")
    print("\n필요한 작업:")
    print("1. 메뉴 동적 렌더링 (권한 없는 메뉴 숨기기)")
    print("2. 각 라우트에 권한 체크 추가")
    print("3. 데이터 조회시 권한 레벨별 필터링")
    print("4. 403 에러 페이지 생성")
    print("\n권한 레벨별 동작:")
    print("- 0: 접근 불가 (메뉴 안 보임)")
    print("- 1: 본인 데이터만")
    print("- 2: 부서 데이터만")
    print("- 3: 전체 데이터")