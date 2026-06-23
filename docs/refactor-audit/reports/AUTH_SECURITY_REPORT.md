# 권한/SSO/보안 분석 보고서 (2026-06-13)

## 0. 분석 범위와 원칙

- 범위: `app.py`, `permission_helpers.py`, `permission_api.py`, `permission_utils.py`, `scoped_permission_check.py`, `login_id_permission_utils.py`, `add_page_routes.py`, `boards/safety_instruction.py`, `upload_utils.py`, `config.ini`.
- 방식: 정적 코드 분석 중심. 서버 실행, 브라우저 클릭, DB 쓰기, 코드 수정은 하지 않았다.
- 결론 요약: 현재 코드는 “페이지 라우트 일부는 권한 체크가 있으나, 다수의 `/api` 쓰기 엔드포인트가 인증/권한 없이 열려 있는 구조”다.
- 핵심 원인: `auto_sso_redirect()`가 `/api` 전체를 SSO 제외 대상으로 처리하므로, API는 각 라우트에서 직접 보호해야 하는데 보호가 빠진 곳이 많다.

## 1. 현재 설정 기준 보안 상태

`config.ini` 기준 현재 로컬 설정은 개발 모드에 가깝다.

- `SSO.sso_enabled = False`
- `SSO.dev_mode = True`
- `PERMISSION.enabled = false`
- `SECURITY.allowed_extensions`에는 `html`, `htm`, `zip`, 이미지, 문서 파일이 포함된다.
- `DEFAULT.secret_key`, `edit_password`, `admin_password`, PostgreSQL DSN이 config 파일에 평문으로 존재한다. 보고서에는 실제 값은 적지 않는다.

중요한 점은 `PERMISSION.enabled = false`이면 `permission_helpers.py`와 `permission_utils.py`의 권한 체크가 대부분 통과 처리된다는 점이다.

## 2. 권한 구조 분석

### 2.1 권한 엔진이 여러 개 공존한다

현재 권한 관련 코드가 하나의 표준으로 정리되어 있지 않다.

| 영역 | 파일 | 기준 식별자 | 특징 |
|---|---|---|---|
| 메뉴 권한 레벨 | `permission_helpers.py` | `session['user_id']`, `session['deptid']` | `read_level`, `write_level` 기반. `PERMISSION.enabled=false`이면 통과. |
| 권한 관리 API | `permission_api.py` | `login_id`, `deptid` | 관리자 API, 권한 신청/승인 API 포함. 일부만 `_admin_required` 적용. |
| Day 1/Day 2 권한 | `permission_utils.py` | `emp_id`, `user_id` | `can_view/can_create/can_edit/can_delete`, cache 기반. 일부 admin 라우트에만 사용. |
| 범위 권한 | `scoped_permission_check.py` | `login_id`, `dept_id` | 권한 신청 UI/요약 등에 사용. |
| login_id 유틸 | `login_id_permission_utils.py` | `login_id` | `login_id` 기반 유틸이지만 upsert 충돌키가 `(emp_id, menu_code)`라 다른 코드와 어긋난다. |

### 2.2 세션 키가 표준화되어 있지 않다

SSO와 개발 로그인은 여러 호환 키를 동시에 세션에 넣는다.

- 로그인 ID: `user_id`, `loginid`
- 사번/사용자 고유 ID: `emp_id`, `userid`
- 부서: `deptid`, 일부 코드는 `dept_id`도 조회
- 이름: `user_name`, 일부 코드는 `name`도 조회
- 부서명: `deptname`, 일부 코드는 `department`도 조회

이 자체가 당장 오류는 아니지만, 권한 엔진마다 어느 키를 신뢰하는지가 달라서 운영 중 “로그인은 됐는데 권한이 없다/반대로 과하게 열린다” 같은 문제가 생기기 쉽다.

### 2.3 표준 권한 엔진 후보

현재 구조상 표준 후보는 `permission_helpers.py` 쪽이 가장 현실적이다.

- 게시판 페이지/등록/수정 흐름에서 이미 `enforce_permission()`을 사용한다.
- SSO 세션의 `login_id`인 `session['user_id']`와 맞다.
- 메뉴 코드 매핑(`resolve_menu_code`)도 포함한다.

다만 실제 표준으로 쓰려면 다음을 먼저 정해야 한다.

- `user_menu_permissions`의 표준 컬럼이 `login_id/read_level/write_level`인지, `emp_id/can_view/can_create/...`인지 결정해야 한다.
- `dept_menu_permissions`와 `dept_menu_roles` 중 어느 테이블이 표준인지 정해야 한다.
- `PERMISSION.enabled=false` 상태에서 운영 서버가 절대 뜨지 않게 해야 한다.

## 3. 라우트/API 권한 체크 분석

### 3.1 보호된 흐름

다음 계열은 권한 체크가 들어가 있다.

- `add_page_routes.py`의 Follow SOP, Full Process, Safe Workplace, Subcontract 계열 페이지/등록/수정 라우트는 `enforce_permission()`을 사용한다.
- `boards/safety_instruction.py`의 환경안전 지시서 페이지/등록/수정 라우트도 `enforce_permission()`을 사용한다.
- `permission_api.py`의 `/api/menu-roles/...` 관리자 권한 관리 API 상당수는 `_admin_required`를 사용한다.
- `app.py`의 일부 관리자 페이지는 `require_admin_auth`를 사용한다.

단, `PERMISSION.enabled=false`이면 `enforce_permission()`은 사실상 통과한다.

### 3.2 미보호 또는 약한 보호가 확인된 주요 API

아래는 정적 분석상 라우트 자체에 인증/권한 보호가 보이지 않는 대표 사례다.

| 위험도 | 엔드포인트 | 위치 | 문제 |
|---|---|---|---|
| 높음 | `/api/<board>/items/register` | `app.py:9249` | 동적 게시판 데이터 등록 API가 인증/권한 체크 없이 호출 가능해 보인다. |
| 높음 | `/api/<board>/items/update/<item_id>` | `app.py:9266` | 동적 게시판 데이터 수정 API가 인증/권한 체크 없이 호출 가능해 보인다. |
| 높음 | `/api/<board>/items/delete` | `app.py:9283` | 동적 게시판 삭제 API가 인증/권한 체크 없이 호출 가능해 보인다. |
| 높음 | `/api/<board>/columns` | `app.py:8989` | 컬럼 설정 조회/추가 API가 인증/권한 체크 없이 호출 가능해 보인다. |
| 높음 | `/api/<board>/columns/<column_id>` | `app.py:9012` | 컬럼 수정/삭제 API가 인증/권한 체크 없이 호출 가능해 보인다. |
| 높음 | `/api/change-request/columns` | `app.py:4817` | 기준정보 변경요청 컬럼 관리 API가 관리자 화면용인데 API 보호가 없다. |
| 높음 | `/api/permission-requests/<id>/approve` | `permission_api.py:1490` | 로그인만 있으면 승인 가능해 보이고, `_admin_required`가 없다. |
| 높음 | `/api/permission-requests/<id>/reject` | `permission_api.py:1601` | 로그인만 있으면 거절 가능해 보이고, `_admin_required`가 없다. |
| 중간 | `/api/permission-requests` GET | `permission_api.py:1408` | 권한 신청 전체 목록 조회에 관리자 보호가 없다. |
| 중간 | `/download/<board_type>/<attachment_id>` | `app.py:3385` | 첨부파일 다운로드에 로그인/권한 체크가 없다. |
| 중간 | `/download/<attachment_id>` | `app.py:3402` | 레거시 다운로드가 여러 게시판을 순회하지만 보호가 없다. |
| 중간 | `/partner-attachments/<business_number>` | `app.py:3431` | 사업자번호 기준 첨부 목록 조회에 보호가 없다. |
| 높음 | `/api/auto-upload-partner-files` | `app.py:3448` | 클라이언트가 넘긴 로컬 파일 경로를 서버가 복사한다. 보호가 없다. |
| 중간 | `/upload-inline-image` | `app.py:9366` | 이미지 업로드에 인증/권한 체크가 없다. |
| 중간 | `/uploads/content/<filename>` | `app.py:9401` | 업로드 콘텐츠 제공 라우트에 인증/권한 체크가 없다. |

가장 중요한 구조적 원인은 `auto_sso_redirect()`가 `/api`를 제외 경로로 둔 점이다. 이 설계라면 API마다 반드시 자체 인증/권한 검사가 있어야 한다.

## 4. 권한 신청 API의 특이 위험

`permission_api.py`의 관리자성 API 중 `/api/menu-roles/...` 계열은 `_admin_required`가 많다. 하지만 권한 신청 처리 API는 보호 수준이 섞여 있다.

- `/api/permission-requests` POST: 로그인 필요. 신청 생성이므로 자연스럽다.
- `/api/permission-requests` GET: 관리자 보호 없이 신청 목록 전체를 조회한다.
- `/api/permission-requests/<id>/approve`: `session['user_id']`만 있으면 승인 처리로 진행한다.
- `/api/permission-requests/<id>/reject`: `session['user_id']`만 있으면 거절 처리로 진행한다.
- `/api/permission-requests/<id>/cancel`: 신청자 본인 여부를 확인한다. 이쪽은 상대적으로 자연스럽다.

즉 “권한 신청 생성/취소”와 “관리자 승인/거절”의 보호 모델이 구분되어야 하는데, 현재 승인/거절 쪽에 관리자 확인이 빠져 있다.

## 5. SSO 흐름 분석

### 5.1 개발 로그인

`/sso/dev-login`은 개발용 SSO 시뮬레이터다.

- `_sso_dev_flags()`는 `dev_mode`와 `dev_simulate_flow`가 모두 켜져야 dev-login을 허용한다.
- POST 시 `session['user_id']`, `session['emp_id']`, `session['deptid']`, `session['authenticated']` 등을 직접 설정한다.
- `login_id`가 `SUPER_ADMIN_USERS`에 있으면 `session['role']='super_admin'`도 설정한다.

현재 `config.ini`에는 `dev_mode=True`가 있으나, 분석 범위에서 보인 `_sso_dev_flags()` 기준으로는 `dev_simulate_flow`도 켜져야 실제 dev-login이 열린다. 운영 환경에서는 두 값을 명확히 꺼야 한다.

### 5.2 SSO 시작과 콜백

- `/SSO`는 `state`, `nonce`를 세션에 저장하고 IdP authorize URL로 이동한다.
- `/acs`는 `id_token`을 인증서 공개키로 검증한다.
- 만료 검증은 켜져 있다: `verify_exp=True`.
- audience 검증은 꺼져 있다: `verify_aud=False`.
- nonce 불일치가 발생해도 예외를 던지지 않고 출력만 한다. 이건 보안적으로 약하다.
- state는 값이 들어온 경우에만 비교한다. state가 누락되면 강제 실패하지 않는다.

### 5.3 SSO/디버그 노출

다음 라우트는 로그인 전에도 접근 가능하도록 제외 경로에 들어가 있다.

- `/debug-session`: 현재 세션 키 목록과 일부 값을 HTML로 표시한다.
- `/sso/diagnostics`: 인증서 경로, IdP URL, client_id, redirect URI, Host 헤더 등을 표시한다.
- `/SSO?debug=1`: SSO 파라미터, state, nonce 등을 표시한다.

개발 중에는 편리하지만 운영에서는 반드시 닫아야 하는 라우트다.

## 6. 파일 업로드/다운로드 분석

### 6.1 업로드 검증 유틸

`upload_utils.py`는 다음을 제공한다.

- 파일명 sanitize: 경로 구분자 제거, 허용 문자 외 `_` 치환
- 확장자 제한: `config.ini [SECURITY] allowed_extensions`
- 개별 파일 크기 제한: `max_upload_size_mb`

유틸 자체는 기본적인 방어를 갖고 있다.

### 6.2 허용 확장자 정책

현재 config는 `html`, `htm`, `zip`을 허용한다.

- HTML을 업로드하고 같은 도메인에서 열 수 있으면 XSS/피싱 위험이 생길 수 있다.
- ZIP은 압축 폭탄/악성 파일 운반 리스크가 있다.
- 문서 파일은 내부 시스템 성격상 필요할 수 있으나, 다운로드/열람 권한과 저장 위치 통제가 중요하다.

### 6.3 다운로드 경로 검증

`_resolve_storage_path()`는 DB에 저장된 경로를 실제 파일 경로 후보로 넓게 해석한다.

- 원본 경로 그대로
- 절대 경로
- 현재 작업 디렉터리 기준 상대 경로
- Flask 루트 기준 상대 경로
- `uploads` 폴더 후보
- Windows/WSL 경로 변환 후보

이 함수는 “기존 저장 경로 호환성”에는 유리하지만, DB에 악성/외부 경로가 들어가면 서버 로컬 파일을 다운로드시킬 수 있는 표면이 넓다. 다운로드 라우트가 보호되지 않은 점과 결합하면 위험도가 올라간다.

### 6.4 자동 업로드 API

`/api/auto-upload-partner-files`는 특히 조심해야 한다.

- 요청 JSON의 `file_paths`를 받아 `Path(file_path).expanduser().resolve()` 한다.
- 해당 경로가 존재하면 `uploads` 폴더로 `shutil.copy2()` 한다.
- 같은 description의 기존 첨부 파일은 DB의 `file_path`를 기준으로 실제 파일을 삭제한다.
- 인증/권한 체크가 없다.

로컬 서버라 해도 브라우저 또는 같은 네트워크에서 접근 가능한 상태라면, 임의 경로 파일 복사/기존 파일 삭제성 동작으로 이어질 수 있다.

### 6.5 Inline image 업로드

`/upload-inline-image`는 이미지 확장자와 10MB 크기 제한은 직접 검사한다.

- 허용 확장자: `png`, `jpg`, `jpeg`, `gif`, `webp`, `bmp`
- 저장 위치: `uploads/content`
- 반환 URL: `/uploads/content/<filename>`
- 업로드/제공 양쪽 모두 인증/권한 체크가 없다.

이미지 전용이라 상대적으로 낮지만, 저장 공간 남용과 공개 파일 호스팅 문제가 생길 수 있다.

## 7. CSRF 분석

정적 검색에서 일반 폼/API POST에 대한 일관된 CSRF 방어는 확인되지 않았다.

- `/SSO` 흐름에는 state/nonce 개념이 있다.
- `static/js/ckeditor-simple.js`에서 `X-CSRF-TOKEN` 헤더를 넣으려는 코드가 보이지만, 앱 전반의 Flask CSRF 검증 구조는 확인되지 않았다.
- 다수의 POST/PUT/DELETE API가 세션 쿠키 기반으로 동작한다면 CSRF 대책이 필요하다.

## 8. 우선순위별 개선 권고

### P0: 운영 전 반드시 막아야 할 것

1. `/api` 전체가 SSO 제외인 구조를 유지할지 재검토한다.
2. 유지한다면 모든 쓰기 API에 공통 인증/권한 데코레이터를 적용한다.
3. `/api/permission-requests/<id>/approve|reject`에 `_admin_required` 또는 표준 관리자 권한 체크를 적용한다.
4. `/api/auto-upload-partner-files`는 관리자 전용으로 묶고, 허용 base directory 밖 파일 경로는 거부한다.
5. `/debug-session`, `/sso/diagnostics`, `/SSO?debug=1`은 운영에서 비활성화한다.
6. 운영 config에서 `PERMISSION.enabled=true`, SSO dev 관련 값 false를 강제한다.

### P1: 구조 정리

1. 권한 엔진을 하나로 정한다: `login_id/read_level/write_level` 방식 또는 `emp_id/can_*` 방식 중 하나.
2. 세션 키 표준을 정한다: 예를 들어 `login_id`, `emp_id`, `dept_id`, `user_name`.
3. `require_admin_auth`, `_admin_required`, `check_permission('permission_admin')`의 역할을 통합한다.
4. 동적 게시판 API(`/api/<board>/...`)에 board별 메뉴 코드와 action을 매핑하는 공통 권한 체크를 만든다.
5. 다운로드 라우트에 board별 view 권한 또는 첨부 소유/범위 권한을 적용한다.

### P2: 방어 강화

1. 업로드 허용 확장자에서 `html`, `htm`을 제거하거나 별도 격리 도메인/다운로드 전용 처리한다.
2. 다운로드는 DB 경로를 그대로 신뢰하지 말고 저장 루트 하위 여부를 확인한다.
3. CSRF 보호를 Flask 전역 또는 API 토큰 방식으로 도입한다.
4. `secret_key`, DB DSN, 관리자 비밀번호는 환경변수/비밀 설정으로 옮긴다.
5. SSO에서 `verify_aud=True`, nonce/state 누락 또는 불일치 시 실패 처리로 바꾼다.

## 9. 리팩토링 전 안전 결론

지금 당장 대규모 리팩토링으로 들어가면 위험하다. 먼저 “보호막”부터 얇고 확실하게 씌우는 순서가 좋다.

추천 순서:

1. 운영/개발 config 분리와 dev/debug 라우트 차단.
2. 공통 `api_auth_required` 또는 `board_permission_required` 데코레이터 설계.
3. 동적 게시판 쓰기 API와 권한 승인 API부터 보호.
4. 다운로드/업로드 경로 제한.
5. 그 다음에 권한 엔진 통합 리팩토링.

이 단계에서는 코드 수정 없이 분석만 완료했다.
