"""
SSO 테스트 로그인 시스템
config.ini의 TEST_ACCOUNTS 섹션에서 계정을 읽어와 SSO 인증을 시뮬레이션
"""
from flask import Flask, session, redirect, request, render_template_string, jsonify
import configparser
import os

app = Flask(__name__)
app.secret_key = 'sso-test-secret-key-2024'

# Config 파일 읽기
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

def get_test_accounts():
    """config.ini에서 활성화된 테스트 계정 목록을 가져옴"""
    accounts = []

    # TEST_ACCOUNTS 섹션이 없으면 빈 리스트 반환
    if 'TEST_ACCOUNTS' not in config:
        return accounts

    # test_mode_enabled 확인
    if not config.getboolean('TEST_ACCOUNTS', 'test_mode_enabled', fallback=False):
        return accounts

    # 계정 번호 1부터 20까지 검색
    for i in range(1, 21):
        prefix = f'account{i}_'

        # 계정이 활성화되어 있는지 확인
        if config.getboolean('TEST_ACCOUNTS', f'{prefix}enabled', fallback=False):
            account = {
                'login_id': config.get('TEST_ACCOUNTS', f'{prefix}login_id', fallback=''),
                'user_name': config.get('TEST_ACCOUNTS', f'{prefix}user_name', fallback=''),
                'dept_id': config.get('TEST_ACCOUNTS', f'{prefix}dept_id', fallback=''),
                'dept_name': config.get('TEST_ACCOUNTS', f'{prefix}dept_name', fallback=''),
                'emp_id': config.get('TEST_ACCOUNTS', f'{prefix}emp_id', fallback=''),
                'email': config.get('TEST_ACCOUNTS', f'{prefix}email', fallback=''),
                'position': config.get('TEST_ACCOUNTS', f'{prefix}position', fallback=''),
            }

            # 필수 필드가 있는 경우에만 추가
            if account['login_id'] and account['user_name']:
                accounts.append(account)

    return accounts

LOGIN_PAGE = '''
<!DOCTYPE html>
<html>
<head>
    <title>SSO 테스트 로그인</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%);
            min-height: 100vh;
            display: flex;
            justify-content: center;
            align-items: center;
        }

        .container {
            background: white;
            border-radius: 15px;
            padding: 40px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            max-width: 1200px;
            width: 90%;
        }

        h1 {
            color: #1e3c72;
            text-align: center;
            margin-bottom: 10px;
            font-size: 28px;
        }

        .subtitle {
            text-align: center;
            color: #666;
            margin-bottom: 30px;
            font-size: 14px;
        }

        .warning-box {
            background: #fff3cd;
            border-left: 5px solid #ffc107;
            padding: 15px;
            margin-bottom: 30px;
            border-radius: 5px;
        }

        .warning-box strong {
            color: #856404;
        }

        .accounts-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }

        .account-card {
            border: 2px solid #e0e0e0;
            border-radius: 10px;
            padding: 20px;
            transition: all 0.3s ease;
            cursor: pointer;
            position: relative;
            overflow: hidden;
        }

        .account-card::before {
            content: "";
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 4px;
            background: linear-gradient(90deg, #1e3c72, #2a5298);
            transform: scaleX(0);
            transition: transform 0.3s ease;
        }

        .account-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 30px rgba(0,0,0,0.15);
            border-color: #2a5298;
        }

        .account-card:hover::before {
            transform: scaleX(1);
        }

        .account-name {
            font-size: 18px;
            font-weight: bold;
            color: #1e3c72;
            margin-bottom: 8px;
        }

        .account-info {
            font-size: 13px;
            color: #666;
            margin: 4px 0;
        }

        .account-id {
            background: #f0f4f8;
            padding: 2px 6px;
            border-radius: 3px;
            font-family: monospace;
            color: #2a5298;
        }

        .position-badge {
            display: inline-block;
            padding: 3px 10px;
            border-radius: 15px;
            font-size: 12px;
            margin-top: 10px;
            background: linear-gradient(90deg, #1e3c72, #2a5298);
            color: white;
        }

        .login-btn {
            width: 100%;
            padding: 10px;
            margin-top: 15px;
            background: linear-gradient(90deg, #1e3c72, #2a5298);
            color: white;
            border: none;
            border-radius: 5px;
            cursor: pointer;
            font-size: 14px;
            transition: all 0.3s;
        }

        .login-btn:hover {
            transform: scale(1.02);
            box-shadow: 0 5px 15px rgba(42, 82, 152, 0.3);
        }

        .no-accounts {
            text-align: center;
            padding: 60px;
            color: #999;
        }

        .no-accounts h2 {
            color: #666;
            margin-bottom: 20px;
        }

        .config-info {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 10px;
            margin-top: 20px;
        }

        .config-info h3 {
            color: #1e3c72;
            margin-bottom: 10px;
        }

        .config-info code {
            background: #fff;
            padding: 10px;
            border: 1px solid #ddd;
            border-radius: 5px;
            display: block;
            margin-top: 10px;
            font-size: 12px;
        }

        .dept-indicator {
            font-size: 11px;
            color: #888;
            background: #f8f9fa;
            padding: 2px 6px;
            border-radius: 3px;
            margin-left: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔐 SSO 테스트 로그인 시스템</h1>
        <p class="subtitle">config.ini에 설정된 테스트 계정으로 SSO 인증을 시뮬레이션합니다</p>

        {% if accounts %}
            <div class="warning-box">
                <strong>⚠️ 테스트 모드 활성화됨</strong><br>
                실제 SSO 인증이 아닌 config.ini의 테스트 계정을 사용합니다.<br>
                운영 환경에서는 config.ini의 <code>test_mode_enabled = false</code>로 설정하세요.
            </div>

            <div class="accounts-grid">
                {% for account in accounts %}
                <div class="account-card" onclick="document.getElementById('form-{{ loop.index }}').submit();">
                    <div class="account-name">{{ account.user_name }}</div>
                    <div class="account-info">
                        ID: <span class="account-id">{{ account.login_id }}</span>
                    </div>
                    <div class="account-info">
                        부서: {{ account.dept_name }}
                        <span class="dept-indicator">{{ account.dept_id }}</span>
                    </div>
                    <div class="account-info">
                        이메일: {{ account.email }}
                    </div>
                    <span class="position-badge">{{ account.position }}</span>

                    <form id="form-{{ loop.index }}" method="post" action="/sso-test-login">
                        <input type="hidden" name="login_id" value="{{ account.login_id }}">
                        <button type="submit" class="login-btn">이 계정으로 로그인</button>
                    </form>
                </div>
                {% endfor %}
            </div>
        {% else %}
            <div class="no-accounts">
                <h2>활성화된 테스트 계정이 없습니다</h2>
                <p>config.ini 파일에서 테스트 계정을 설정하세요</p>

                <div class="config-info">
                    <h3>설정 방법:</h3>
                    <ol style="text-align: left; margin: 20px;">
                        <li>config.ini 파일을 엽니다</li>
                        <li>[TEST_ACCOUNTS] 섹션에서 <code>test_mode_enabled = true</code>로 설정</li>
                        <li>원하는 계정의 주석(#)을 제거하고 <code>enabled = true</code>로 변경</li>
                        <li>Flask 앱을 재시작합니다</li>
                    </ol>

                    <h3>예시:</h3>
                    <code>
                        [TEST_ACCOUNTS]<br>
                        test_mode_enabled = true<br>
                        <br>
                        account1_login_id = dev_super<br>
                        account1_user_name = 개발슈퍼관리자<br>
                        account1_dept_id = DEPT000<br>
                        account1_dept_name = 전산팀<br>
                        account1_enabled = true
                    </code>
                </div>
            </div>
        {% endif %}
    </div>
</body>
</html>
'''

@app.route('/sso-test-login', methods=['GET', 'POST'])
def sso_test_login():
    """SSO 테스트 로그인 페이지"""
    if request.method == 'POST':
        login_id = request.form.get('login_id')

        # 선택된 계정 찾기
        accounts = get_test_accounts()
        selected_account = None
        for account in accounts:
            if account['login_id'] == login_id:
                selected_account = account
                break

        if selected_account:
            # SSO 세션과 동일한 구조로 세션 설정
            session['user_id'] = selected_account['login_id']
            session['user_name'] = selected_account['user_name']
            session['name'] = selected_account['user_name']
            session['deptid'] = selected_account['dept_id']
            session['department'] = selected_account['dept_name']
            session['emp_id'] = selected_account['emp_id']
            session['email'] = selected_account['email']
            session['position'] = selected_account['position']

            print(f"\n{'='*60}")
            print(f"SSO 테스트 로그인 성공")
            print(f"사용자: {selected_account['user_name']} ({login_id})")
            print(f"부서: {selected_account['dept_name']} ({selected_account['dept_id']})")
            print(f"직급: {selected_account['position']}")
            print(f"{'='*60}\n")

            # 메인 포털로 리다이렉트
            return redirect('http://localhost:5000/')

    # GET 요청시 로그인 페이지 표시
    accounts = get_test_accounts()
    return render_template_string(LOGIN_PAGE, accounts=accounts)

@app.route('/check-config')
def check_config():
    """현재 config.ini 설정 확인"""
    accounts = get_test_accounts()
    test_enabled = config.getboolean('TEST_ACCOUNTS', 'test_mode_enabled', fallback=False)

    return jsonify({
        'test_mode_enabled': test_enabled,
        'accounts_count': len(accounts),
        'accounts': accounts
    })

@app.route('/')
def index():
    """루트 경로는 SSO 테스트 로그인으로 리다이렉트"""
    return redirect('/sso-test-login')

if __name__ == '__main__':
    print("\n" + "="*60)
    print("SSO 테스트 로그인 서버 시작")
    print("="*60)

    # 현재 설정 확인
    accounts = get_test_accounts()
    test_enabled = config.getboolean('TEST_ACCOUNTS', 'test_mode_enabled', fallback=False)

    if test_enabled:
        print(f"\n테스트 모드: 활성화")
        print(f"활성화된 계정 수: {len(accounts)}개")
        if accounts:
            print("\n활성 계정 목록:")
            for acc in accounts:
                print(f"  - {acc['user_name']} ({acc['login_id']}) - {acc['dept_name']}")
    else:
        print("\n테스트 모드: 비활성화")
        print("config.ini에서 test_mode_enabled = true로 설정하세요")

    print("\n접속 방법:")
    print("1. 브라우저에서 http://localhost:5002/sso-test-login 접속")
    print("2. 테스트 계정 선택하여 로그인")
    print("3. 메인 포털(http://localhost:5000)로 자동 이동")
    print("="*60)

    # 서버 실행 (포트 5002)
    app.run(debug=True, port=5002, host='0.0.0.0')