# 0단계 기준선 보고서

작성일: 2026-06-13

## 0단계의 의미

0단계는 리팩터링이나 수정에 들어가기 전에 현재 프로젝트의 상태를 고정하는 단계다.

이 단계의 목적은 다음과 같다.

- 지금 어떤 파일이 이미 수정되어 있는지 확인한다.
- 어떤 실행 환경과 설정으로 돌아가는 프로젝트인지 확인한다.
- 분석용 문서가 앱 코드와 섞이지 않는지 확인한다.
- 이후 단계에서 문제가 생겼을 때 "원래부터 있던 상태"와 "분석 중 새로 발견한 상태"를 구분할 수 있게 한다.

이번 단계에서는 앱 코드 수정, 서버 실행, DB 접속, 브라우저 테스트를 하지 않았다.

## 확인한 명령

```powershell
git status --short --untracked-files=all
git diff --stat
git diff --name-only
git check-ignore -v ANALYSIS_CHECKLIST.md PROJECT_AUDIT_REPORT_2026.md BASELINE_REPORT.md
Get-ChildItem -Force
python --version
venv\Scripts\python.exe --version
Get-Content requirements.txt
rg -n "app\.run|ssl_port|http_port|host=|debug|run_scheduler|schedule|thread|cert|PORT|FLASK_ENV|APP_ENV|SEND_FILE_MAX_AGE_DEFAULT" app.py wsgi.py config.ini config.ini.production
python -c "configparser 기반 config 섹션/키 확인"
rg -n "secret_key|edit_password|admin_password|postgres_dsn|client_secret|chatbot_auth_token|ssl_port|http_port|cert|permission|enabled|upload_folder|max_upload_size|allowed_extensions|max_rows" config.ini config.ini.production config.ini.prod.template
```

## 저장소 상태

현재 Git 기준으로 이미 수정되어 있던 파일은 다음 2개다.

- `app.py`
- `config.ini`

`git diff --stat` 기준 변경량은 다음과 같다.

- `app.py`: 대량 변경
- `config.ini`: 소량 변경
- 총합: 2 files changed, 1018 insertions(+), 900 deletions(-)

현재 보이는 변경 중 핵심은 엑셀 내보내기 관련 변경으로 보인다.

- 기존 CSV 스트리밍 응답 계열 코드가 제거된 흔적이 있다.
- `openpyxl` 기반 Excel export 계열 함수가 추가된 흔적이 있다.
- `config.ini`에는 `[EXPORT] max_rows = 5000` 설정이 추가되어 있다.

이 변경은 0단계 분석 전에 이미 존재하던 사용자 작업물로 취급한다.

## 분석 문서 추적 상태

루트 `.gitignore`에 `*.md` 규칙이 있다.

따라서 아래 분석 문서는 Git에서 무시된다.

- `ANALYSIS_CHECKLIST.md`
- `PROJECT_AUDIT_REPORT_2026.md`
- `BASELINE_REPORT.md`

장점은 분석 문서가 앱 코드 변경 diff에 섞이지 않는다는 점이다.

주의점은 나중에 이 문서들을 Git에 남기고 싶다면 `.gitignore` 예외 규칙을 추가하거나 강제 추가가 필요하다는 점이다.

## 루트 구조 1차 분류

현재 루트에는 운영 코드, 실험 코드, 백업/임시 산출물이 함께 존재한다.

정식 코드로 보이는 주요 디렉터리는 다음과 같다.

- `boards`
- `columns`
- `config`
- `controllers`
- `db`
- `repositories`
- `static`
- `templates`
- `utils`

운영 또는 개발 보조 성격으로 보이는 디렉터리는 다음과 같다.

- `migrations`
- `migration_scripts`
- `scripts`
- `tools`
- `logs`
- `uploads`
- `reports`
- `cert`

정리/검토 대상 성격으로 보이는 디렉터리는 다음과 같다.

- `backup`
- `deletelist`
- `needtodevelop`
- `.serena`
- `sso_backup_20250116`
- `screenshot`

이 분류는 0단계의 1차 분류다. 실제 삭제 가능 여부나 보존 필요 여부는 이후 단계에서 파일별 참조 관계를 확인해야 한다.

## Python 및 가상환경

확인된 Python 환경은 다음과 같다.

- 시스템 `python`: Python 3.13.7
- `venv\Scripts\python.exe`: Python 3.13.7
- `.venv\Scripts\python.exe`: 존재하지 않음
- `.wslvenv\bin\python`: Windows PowerShell에서 직접 확인은 불명확함

현재 Windows 기준으로는 `venv`가 가장 확실한 로컬 가상환경 후보로 보인다.

## 주요 의존성

`requirements.txt` 기준 주요 의존성은 다음과 같다.

- Flask 3.1.1
- Flask-Migrate 4.0.5
- Flask-SQLAlchemy 3.0.5
- SQLAlchemy 2.0.36
- psycopg 3.2.9
- psycopg-binary 3.2.9
- pandas 2.3.1
- numpy 2.3.2
- openpyxl 3.1.5
- pytest 7.4.2
- cryptography 45.0.6
- PyJWT 2.10.1
- Authlib 1.2.1
- schedule 1.2.2
- python-dotenv 1.0.0

프로젝트 성격상 Flask 웹앱, PostgreSQL, Excel 처리, SSO/JWT/Authlib, 스케줄러, 테스트 도구가 함께 들어간 형태다.

## 실행 진입점

확인된 실행 진입점은 두 갈래다.

### 직접 실행

`app.py` 하단에서 `app.run(...)`을 호출한다.

- 기본 HTTP 포트 후보: `5000`
- SSL 인증서가 있으면 HTTPS 포트 후보: `44369`
- host: `0.0.0.0`
- `schedule` 기반 백그라운드 스케줄러 시작 코드가 존재한다.

### WSGI 실행

`wsgi.py`는 배포용 진입점으로 보인다.

- `APP_ENV=prod`
- `FLASK_ENV=production`
- `SEND_FILE_MAX_AGE_DEFAULT=31536000`
- `app.debug=False`

직접 실행과 WSGI 실행의 캐시/debug 설정이 다르므로 이후 런타임 분석에서 두 경로를 분리해서 봐야 한다.

## 설정 파일 기준선

확인한 설정 파일은 다음 3개다.

- `config.ini`
- `config.ini.production`
- `config.ini.prod.template`

### `config.ini`

현재 개발/로컬 실행 중심 설정으로 보인다.

주요 섹션은 다음과 같다.

- `DATABASE`
- `SECURITY`
- `EXPORT`
- `LOGGING`
- `NOTIFICATION`
- `DASHBOARD`
- `USAGE_DASHBOARD`
- `SQL_QUERIES`
- `COLUMNS`
- `PERMISSION`
- `MASTER_DATA_QUERIES`
- `CONTENT_DATA_QUERIES`
- 게시판별 설정 섹션
- `SSO`
- `PERMISSION_REQUEST_GRANTS_EMP`
- `PERMISSION_REQUEST_GRANTS_PARTNER`
- `APPLICATION`
- `REDIS`

핵심 값은 다음과 같다.

- DB backend: `postgres`
- 로컬 PostgreSQL DSN 존재
- `external_db_enabled = false`
- 권한 시스템: `PERMISSION.enabled = false`
- SSO: `sso_enabled = False`
- SSO 개발 모드 관련 값 존재
- 업로드 폴더: `uploads`
- 업로드 허용 확장자가 넓음
- Excel export 제한: `EXPORT.max_rows = 5000`
- HTTP/SSL 포트 설정 존재

### `config.ini.production`

운영 후보 설정으로 보이지만 placeholder가 남아 있다.

- 운영용 secret/password placeholder 존재
- 운영 PostgreSQL DSN placeholder 존재
- SSO client secret placeholder 존재
- SSO enabled true
- 인증서 관련 설정 존재

실제 운영 적용 전에는 민감값, SSO, DB, 인증서 경로를 별도로 검증해야 한다.

### `config.ini.prod.template`

운영 템플릿 또는 배포용 가이드 성격으로 보인다.

- `PERMISSION`
- `MONITORING`
- `BACKUP`
- `EMERGENCY`

같은 운영 보조 섹션이 포함되어 있다.

현재 실제 `config.ini`와 production/template 간 섹션 구성이 다르므로, 설정 키 drift가 있을 가능성이 있다.

## 민감값 및 보안 기준선

다음 유형의 값이 설정 파일에 평문으로 존재한다.

- Flask secret key
- edit/admin password
- PostgreSQL DSN
- SSO client secret placeholder
- chatbot auth token 항목
- 긴 업로드 허용 확장자 목록

이 단계에서는 값을 수정하지 않았다.

이후 보안 분석 단계에서는 다음을 별도 위험 항목으로 다뤄야 한다.

- 로컬 개발용 값과 운영용 값의 분리
- 평문 비밀번호 제거 또는 환경변수화
- 업로드 허용 확장자 축소
- SSO/권한 설정 간 충돌 가능성

## 아직 실행하지 않은 것

0단계에서는 의도적으로 아래 검증을 하지 않았다.

- Flask 서버 실행
- PostgreSQL 접속
- SQLite 파일 열기
- 브라우저 화면 확인
- pytest 실행
- 마이그레이션 실행
- 앱 코드 수정

이유는 기준선 단계에서 부작용을 만들지 않기 위해서다.

## 0단계에서 발견한 위험

1. `app.py`와 `config.ini`가 이미 수정 중이다.
   - 이 상태를 모른 채 분석하거나 리팩터링하면 나중에 변경 출처가 섞일 수 있다.

2. `*.md`가 Git에서 무시된다.
   - 분석 문서가 편하게 쌓이는 장점은 있지만, 보존하려면 별도 조치가 필요하다.

3. Python 환경 후보가 여러 개다.
   - `venv`는 확인됐지만 `.venv`는 Windows 실행 파일이 없고 `.wslvenv`는 별도 검증이 필요하다.

4. 설정 파일 간 drift 가능성이 높다.
   - `config.ini`, `config.ini.production`, `config.ini.prod.template`의 섹션 구성이 서로 다르다.

5. 로컬 설정에 민감값이 평문으로 있다.
   - 개발용이라도 장기적으로는 분리 대상이다.

6. 직접 실행과 WSGI 실행의 런타임 조건이 다르다.
   - debug, cache, scheduler, SSL 경로를 분리해서 봐야 한다.

7. 루트에 실험/백업/임시 파일이 많다.
   - 실제 참조 중인 파일과 과거 산출물을 구분해야 한다.

## 다음 단계

다음은 1단계 런타임 진입 분석이다.

1단계에서는 다음을 확인한다.

- `app.py` import 순서
- 앱 생성과 전역 초기화 흐름
- DB 초기화 흐름
- config 로딩 흐름
- scheduler 시작 조건
- `wsgi.py`와 직접 실행의 차이
- 앱 시작 시 부작용이 생기는 코드

이후에도 앱 코드는 수정하지 않고 분석 문서만 갱신한다.
