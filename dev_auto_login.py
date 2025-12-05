"""
개발 모드 자동 로그인
SSO 없이 개발자 세션 자동 생성
"""
from flask import session
import configparser

def initialize_dev_session(app):
    """개발 모드에서 자동으로 세션 생성"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    # SSO가 비활성화되고 dev_mode가 true일 때만 작동
    sso_enabled = config.get('SSO', 'enabled', fallback='true').lower() == 'true'
    dev_mode = config.get('SSO', 'dev_mode', fallback='false').lower() == 'true'

    if not sso_enabled and dev_mode:
        # 개발자 정보 설정
        dev_user_id = config.get('SSO', 'dev_user_id', fallback='dev_user')
        dev_user_name = config.get('SSO', 'dev_user_name', fallback='개발자')
        dev_department = config.get('SSO', 'dev_department', fallback='개발팀')
        dev_grade = config.get('SSO', 'dev_grade', fallback='과장')

        @app.before_request
        def auto_dev_login():
            """세션이 없으면 자동으로 개발자 세션 생성"""
            # 제외 경로
            excluded_paths = ['/static', '/uploads', '/api']

            for path in excluded_paths:
                if request.path.startswith(path):
                    return None

            # 세션이 없으면 자동 생성
            if not session.get('user_name'):
                session['user_id'] = dev_user_id
                session['user_name'] = dev_user_name
                session['department'] = dev_department
                session['deptid'] = 'DEV001'
                session['grade'] = dev_grade
                session['authenticated'] = True
                print(f"[DEV MODE] Auto-login as {dev_user_id}")

            return None

if __name__ == "__main__":
    print("개발 모드 자동 로그인 설정")
    print("config.ini에서 다음 설정 확인:")
    print("[SSO]")
    print("enabled = false")
    print("dev_mode = true")
    print("dev_user_id = dev_user")