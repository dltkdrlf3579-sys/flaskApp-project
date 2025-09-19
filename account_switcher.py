"""
계정 전환 기능 (개발/테스트용)
슈퍼어드민이 다른 계정으로 전환하여 테스트할 수 있는 기능
"""
from flask import Flask, session, redirect, request, render_template_string, jsonify
import configparser
from access_log_helper import log_user_access

app = Flask(__name__)
app.secret_key = 'account-switcher-2024'

# Config 파일 읽기
config = configparser.ConfigParser()
config.read('config.ini')

def switch_to_account(account_data):
    """계정 전환 및 로그 기록"""
    # 이전 계정 정보 백업
    if 'original_user' not in session:
        session['original_user'] = {
            'user_id': session.get('user_id'),
            'user_name': session.get('user_name'),
            'dept_id': session.get('deptid'),
            'dept_name': session.get('department')
        }

    # 새 계정으로 전환
    session['user_id'] = account_data['login_id']
    session['user_name'] = account_data['user_name']
    session['name'] = account_data['user_name']
    session['deptid'] = account_data['dept_id']
    session['department'] = account_data['dept_name']
    session['emp_id'] = account_data.get('emp_id', '')
    session['email'] = account_data.get('email', '')
    session['position'] = account_data.get('position', '')
    session['is_switched'] = True

    # 접속 로그 기록
    log_user_access(
        action_type='account_switch',
        action_detail=f"Switched to {account_data['login_id']}",
        response_code=200
    )

SWITCHER_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>계정 전환 (개발자용)</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: 'Segoe UI', sans-serif;
            background: #1a1a2e;
            color: white;
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .container {
            background: #16213e;
            border-radius: 15px;
            padding: 30px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.5);
            max-width: 1200px;
            width: 90%;
        }

        h1 {
            color: #f39c12;
            margin-bottom: 10px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .current-user {
            background: #0f3460;
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 30px;
            border-left: 4px solid #f39c12;
        }

        .accounts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }

        .account-card {
            background: #0f3460;
            padding: 15px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s;
            border: 2px solid transparent;
        }

        .account-card:hover {
            transform: translateY(-3px);
            border-color: #f39c12;
            box-shadow: 0 5px 20px rgba(243, 156, 18, 0.3);
        }

        .account-card.super-admin {
            background: linear-gradient(135deg, #e74c3c, #c0392b);
        }

        .account-card.manager {
            background: linear-gradient(135deg, #3498db, #2980b9);
        }

        .account-card.readonly {
            background: linear-gradient(135deg, #95a5a6, #7f8c8d);
        }

        .account-card.no-perm {
            background: linear-gradient(135deg, #34495e, #2c3e50);
        }

        .account-name {
            font-weight: bold;
            color: white;
            margin-bottom: 5px;
        }

        .account-info {
            font-size: 12px;
            color: #bdc3c7;
        }

        .switch-btn {
            margin-top: 10px;
            padding: 8px 15px;
            background: #f39c12;
            color: #1a1a2e;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
        }

        .switch-btn:hover {
            background: #e67e22;
        }

        .back-btn {
            background: #e74c3c;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }

        .back-btn:hover {
            background: #c0392b;
        }

        .warning {
            background: #e74c3c;
            padding: 10px;
            border-radius: 5px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }

        .badge {
            display: inline-block;
            padding: 2px 8px;
            border-radius: 3px;
            font-size: 11px;
            background: rgba(255,255,255,0.2);
            margin-left: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔄 계정 전환 시스템 (개발자 전용)</h1>

        {% if is_switched %}
        <div class="warning">
            ⚠️ 현재 전환된 계정으로 작동 중입니다!
            <button class="back-btn" onclick="restoreOriginal()">원래 계정으로 복귀</button>
        </div>
        {% endif %}

        <div class="current-user">
            <strong>현재 계정:</strong> {{ current_user.user_name }} ({{ current_user.login_id }})
            <span class="badge">{{ current_user.dept_name }}</span>
            {% if original_user %}
            <br><small>원래 계정: {{ original_user.user_name }}</small>
            {% endif %}
        </div>

        <h3 style="margin-bottom: 15px;">테스트 계정 선택</h3>
        <div class="accounts-grid">
            <div class="account-card super-admin" onclick="switchAccount('dev_super')">
                <div class="account-name">🛡️ 개발 슈퍼관리자</div>
                <div class="account-info">dev_super</div>
                <div class="account-info">모든 권한</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>

            <div class="account-card manager" onclick="switchAccount('safety_manager')">
                <div class="account-name">👷 안전관리팀장</div>
                <div class="account-info">safety_manager</div>
                <div class="account-info">부서 전체 권한</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>

            <div class="account-card" onclick="switchAccount('normal_user')">
                <div class="account-name">👤 일반 직원</div>
                <div class="account-info">normal_user</div>
                <div class="account-info">제한된 권한</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>

            <div class="account-card readonly" onclick="switchAccount('audit_reader')">
                <div class="account-name">👁️ 감사팀</div>
                <div class="account-info">audit_reader</div>
                <div class="account-info">읽기 전용</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>

            <div class="account-card no-perm" onclick="switchAccount('new_employee')">
                <div class="account-name">🚫 신입사원</div>
                <div class="account-info">new_employee</div>
                <div class="account-info">권한 없음</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>

            <div class="account-card" onclick="switchAccount('external_user')">
                <div class="account-name">🏢 외부 협력사</div>
                <div class="account-info">external_user</div>
                <div class="account-info">외부 접근</div>
                <button class="switch-btn">이 계정으로 전환</button>
            </div>
        </div>

        <div style="margin-top: 30px; text-align: center;">
            <button onclick="window.location.href='/'" style="padding: 10px 30px; background: #27ae60; color: white; border: none; border-radius: 5px; cursor: pointer; font-weight: bold;">
                메인 포털로 이동 →
            </button>
        </div>
    </div>

    <script>
        function switchAccount(loginId) {
            if (confirm(`${loginId} 계정으로 전환하시겠습니까?`)) {
                fetch('/api/switch-account', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({ login_id: loginId })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('계정 전환 완료!');
                        window.location.href = '/';
                    } else {
                        alert('전환 실패: ' + data.error);
                    }
                });
            }
        }

        function restoreOriginal() {
            if (confirm('원래 계정으로 복귀하시겠습니까?')) {
                fetch('/api/restore-account', {
                    method: 'POST'
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        alert('원래 계정으로 복귀했습니다.');
                        window.location.href = '/';
                    }
                });
            }
        }
    </script>
</body>
</html>
'''

@app.route('/admin/account-switcher')
def account_switcher():
    """계정 전환 페이지"""
    # 슈퍼어드민 체크
    if session.get('user_id') not in ['dev_super', 'dev_user']:
        return "권한이 없습니다", 403

    current_user = {
        'login_id': session.get('user_id'),
        'user_name': session.get('user_name'),
        'dept_name': session.get('department')
    }

    original_user = session.get('original_user')
    is_switched = session.get('is_switched', False)

    return render_template_string(
        SWITCHER_PAGE,
        current_user=current_user,
        original_user=original_user,
        is_switched=is_switched
    )

@app.route('/api/switch-account', methods=['POST'])
def api_switch_account():
    """계정 전환 API"""
    if session.get('user_id') not in ['dev_super', 'dev_user']:
        return jsonify({'success': False, 'error': '권한 없음'}), 403

    login_id = request.json.get('login_id')

    # 테스트 계정 정보 (setup_test_permissions.py와 동일)
    test_accounts = {
        'dev_super': {
            'login_id': 'dev_super',
            'user_name': '개발슈퍼관리자',
            'dept_id': 'DEPT000',
            'dept_name': '전산팀'
        },
        'safety_manager': {
            'login_id': 'safety_manager',
            'user_name': '박안전',
            'dept_id': 'DEPT100',
            'dept_name': '안전관리팀'
        },
        'normal_user': {
            'login_id': 'normal_user',
            'user_name': '홍길동',
            'dept_id': 'DEPT201',
            'dept_name': '생산1팀'
        },
        'audit_reader': {
            'login_id': 'audit_reader',
            'user_name': '감사원',
            'dept_id': 'DEPT400',
            'dept_name': '감사팀'
        },
        'new_employee': {
            'login_id': 'new_employee',
            'user_name': '신입사원',
            'dept_id': 'DEPT999',
            'dept_name': '인사팀'
        },
        'external_user': {
            'login_id': 'external_user',
            'user_name': '외부협력',
            'dept_id': 'EXT001',
            'dept_name': '외부협력사A'
        }
    }

    if login_id in test_accounts:
        switch_to_account(test_accounts[login_id])
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': '계정을 찾을 수 없습니다'})

@app.route('/api/restore-account', methods=['POST'])
def api_restore_account():
    """원래 계정으로 복귀"""
    original = session.get('original_user')
    if original:
        session['user_id'] = original['user_id']
        session['user_name'] = original['user_name']
        session['deptid'] = original['dept_id']
        session['department'] = original['dept_name']
        session.pop('original_user', None)
        session.pop('is_switched', None)

        log_user_access(
            action_type='account_restore',
            action_detail=f"Restored to original account",
            response_code=200
        )

        return jsonify({'success': True})
    return jsonify({'success': False, 'error': '원래 계정 정보 없음'})