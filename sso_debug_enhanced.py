"""
SSO 문제 진단 도구 - 운영/개발 환경 차이 분석
"""
import os
import configparser

# config.ini 읽기
config = configparser.ConfigParser()
config.read('config.ini')

print("=" * 60)
print("SSO 설정 진단 - 운영환경 문제 분석")
print("=" * 60)
print()

# 1. 핵심 SSO 설정 확인
print("1. SSO 핵심 설정값:")
print("-" * 40)
sso_settings = {
    'sso_enabled': config.get('SSO', 'sso_enabled'),
    'sp_redirect_url': config.get('SSO', 'sp_redirect_url'),
    'idp_entity_id': config.get('SSO', 'idp_entity_id'),
    'ssl_port': config.get('SSO', 'ssl_port'),
    'http_port': config.get('SSO', 'http_port'),
    'dev_mode': config.get('SSO', 'dev_mode'),
}

for key, value in sso_settings.items():
    status = "⚠️" if value == "example" else "✓"
    print(f"{status} {key}: {value}")

print()

# 2. 인증서 파일 확인
print("2. 인증서 파일 존재 확인:")
print("-" * 40)
cert_path = config.get('SSO', 'cert_file_path')
cert_name = config.get('SSO', 'cert_file_name')
ssl_cert = config.get('SSO', 'ssl_cert_file')
ssl_key = config.get('SSO', 'ssl_key_file')

files_to_check = [
    (f"{cert_path}{cert_name}", "IDP 인증서"),
    (ssl_cert, "SSL 인증서"),
    (ssl_key, "SSL 키")
]

for file_path, desc in files_to_check:
    exists = os.path.exists(file_path)
    status = "✓" if exists else "❌"
    print(f"{status} {desc}: {file_path} - {'존재' if exists else '없음'}")

print()

# 3. 문제 가능성 분석
print("3. 문제 진단:")
print("-" * 40)

problems = []

# sp_redirect_url 문제
if 'partnerehs.samsungds.net' in config.get('SSO', 'sp_redirect_url'):
    problems.append("""
⚠️ sp_redirect_url이 운영 도메인으로 고정되어 있음!
  현재: https://partnerehs.samsungds.net/acs

  해결방법:
  - 개발환경: https://localhost:44369/acs
  - 운영환경: https://partnerehs.samsungds.net/acs

  동적으로 변경하도록 app.py 수정 필요
""")

# IDP 설정 문제
if config.get('SSO', 'idp_entity_id') == 'example':
    problems.append("""
❌ idp_entity_id가 'example'로 되어있음!
  실제 SSO 서버의 entity ID로 변경 필요
""")

# 인증서 문제
if not os.path.exists(f"{cert_path}{cert_name}"):
    problems.append("""
❌ IDP 인증서 파일이 없음!
  SSO 서버에서 받은 인증서 파일 필요
""")

# HTTP/HTTPS 혼용 문제
problems.append("""
⚠️ HTTP/HTTPS 프로토콜 혼용 문제
  운영환경: 리버스 프록시가 HTTPS → HTTP로 전달

  해결방법:
  1. app.py에서 동적 프로토콜 감지
  2. 또는 환경변수로 강제 지정
""")

if problems:
    for problem in problems:
        print(problem)
else:
    print("✓ 설정상 특별한 문제 없음")

print()
print("4. 권장 해결 방법:")
print("-" * 40)
print("""
app.py 수정 제안:

# 1. sp_redirect_url 동적 설정
def get_acs_url(request):
    if app.debug or 'localhost' in request.host:
        return f"https://localhost:44369/acs"
    else:
        # 운영환경: 실제 도메인 사용
        return "https://partnerehs.samsungds.net/acs"

# 2. 프로토콜 강제 지정 (환경변수 사용)
import os
FORCE_HTTPS = os.environ.get('FORCE_HTTPS', 'false').lower() == 'true'

def is_secure_request(request):
    if FORCE_HTTPS:
        return True
    return request.is_secure or request.scheme == 'https'

# 3. SSO 응답 처리 시 유연한 URL 매칭
@app.route('/acs', methods=['POST'])
def acs():
    # URL 검증을 느슨하게
    expected_url = get_acs_url(request)
    # 또는 URL 검증 자체를 스킵
""")