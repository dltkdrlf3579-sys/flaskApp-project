# 2단계 라우트 전체 지도 보고서

작성일: 2026-06-13

## 2단계의 의미

2단계는 Flask 앱에 실제로 연결될 URL 후보를 정적으로 추출하고, 백업/테스트/삽입용 파일에 남아 있는 라우트와 분리하는 단계다.

이번 단계에서도 앱 실행, DB 접속, 브라우저 테스트, 코드 수정은 하지 않았다.

## 확인한 명령

```powershell
rg -n "@.*\.route\(" -g "*.py" -g "!venv/**" -g "!.venv/**" -g "!.wslvenv/**" -g "!.git/**"
python -c "AST 기반 route decorator 추출"
python -c "route group/family 집계"
python -c "동일 path+method 중복 및 동적 route overlap 후보 분석"
rg -n "Blueprint\(" -g "*.py"
rg -n "import <route_file>|from <route_file>" -g "*.py"
```

## 실제 런타임 라우트 후보 파일

`app.py` 기준 실제 런타임에 연결되는 것으로 판단한 파일은 다음 4개다.

- `app.py`
- `add_page_routes.py`
- `boards/safety_instruction.py`
- `permission_api.py`

판단 근거는 다음과 같다.

- `app.py`가 직접 `@app.route(...)`를 다수 가진다.
- `app.py`가 `add_page_routes.py`의 Blueprint 5개를 import 후 등록한다.
- `app.py`가 `boards/safety_instruction.py`의 Blueprint를 import 후 등록한다.
- `app.py`가 `permission_api.register_permission_routes(app)`를 직접 호출한다.

## 런타임 라우트 수

정적 AST 분석 기준 실제 런타임 라우트 데코레이터는 총 263개다.

파일별 개수는 다음과 같다.

| 파일 | 라우트 수 | 성격 |
| --- | ---: | --- |
| `app.py` | 212 | 대부분의 레거시/공통/API/관리자/SSO 라우트 |
| `add_page_routes.py` | 25 | follow-sop, safe-workplace, full-process, subcontract 계열 페이지/저장 |
| `permission_api.py` | 21 | 메뉴/부서/권한 요청 API |
| `boards/safety_instruction.py` | 5 | safety-instruction 페이지/등록/수정 |

한 라우트가 `GET,POST`처럼 여러 method를 갖는 경우 method 단위로는 269개가 된다.

## URL 그룹별 개수

| 그룹 | 개수 | 설명 |
| --- | ---: | --- |
| API | 159 | `/api/...` 일반 API |
| 페이지/파일 | 57 | 일반 화면, 다운로드, 업로드, SSO 일부 |
| 관리자 페이지 | 37 | `/admin/...` 화면/관리 기능 |
| SSO/디버그 | 6 | `/SSO`, `/acs`, `/slo`, `/sso/...`, `/debug-session` |
| 관리자 API | 2 | `/api/admin/...` |
| 루트 | 1 | `/` |
| catch-all | 1 | `/<path:url>` |

## API family 지도

API는 다음 묶음으로 나뉜다.

| family | 개수 | 해석 |
| --- | ---: | --- |
| `/api/<board>` | 13 | 보드 공통 API |
| `/api/menu-roles` | 11 | 메뉴 권한 관리 |
| `/api/change-request` | 8 | 변경요청 레거시/관리 API |
| `/api/permission-requests` | 6 | 권한 요청 승인/반려/조회 |
| `/api/*-sections` | 각 5 | 보드별 섹션 관리 |
| `/api/*-columns` | 각 4~5 | 보드별 컬럼 관리 |
| `/api/accidents` | 4 | 사고 삭제/복구/영구삭제 등 |
| `/api/partners` | 4 | 협력사 삭제/복구/export |
| `/api/follow-sop` | 4 | follow-sop 삭제/복구/최종검토 |
| `/api/safe-workplace` | 4 | safe-workplace 삭제/복구/최종검토 |
| `/api/full-process` | 5 | full-process 목록/삭제/복구/최종검토 |
| `/api/person-master` | 5 | 인원 마스터 CRUD |
| `/api/dept-roles` | 2 | 부서 역할 관리 |
| `/api/dept-permissions` | 2 | 부서 권한 tree/apply |
| `/api/admin` | 2 | audit logs, usage dashboard |
| `/api/permissions` | 2 | 권한 grant/cache clear |

그 외 단발 API는 다음 성격이다.

- 알림 발송
- 테스트 API
- 검색 팝업
- 자동 파일 업로드
- 테이블 검색
- 건물/부서 검색
- 통합 검색
- Excel export/import
- 메뉴 조회

## 관리자 라우트 지도

관리자 화면은 다음 묶음으로 나뉜다.

| family | 성격 |
| --- | --- |
| `/admin/login`, `/admin/logout` | 관리자 인증 |
| `/admin/sync-now`, `/admin/cache-counts` | 동기화/캐시 관리 |
| `/admin/*-columns` | 게시판별 컬럼 관리 |
| `/admin/*-codes` | 게시판별 코드 관리 |
| `/admin/*-sections` 관련 API | 주로 `/api` 쪽에 존재 |
| `/admin/menu-settings` | 메뉴 설정 |
| `/admin/permission-settings` | 권한 설정 |
| `/admin/permissions...` | Day 2 권한 관리 화면 |
| `/admin/usage-dashboard` | 사용량 대시보드 |
| `/admin/data-management` | 데이터 관리 |
| `/admin/person-master` | 인원 마스터 관리 |

주의할 점은 관리자 권한 체계가 두 갈래로 보인다는 것이다.

- 세션 기반 단순 관리자 비밀번호 흐름
- `permission_utils.check_permission` 기반 권한 데코레이터 흐름

이 둘이 어떻게 공존하는지는 권한/SSO 분석 단계에서 별도 확인해야 한다.

## 페이지 라우트 지도

주요 일반 페이지는 다음 축으로 나뉜다.

| 축 | 대표 URL |
| --- | --- |
| 메인 | `/` |
| 사고 | `/accident`, `/accident-register`, `/accident-detail/<accident_id>` |
| 협력사 | `/partner-standards`, `/partner/<business_number>`, `/partner-detail/<business_number>` |
| 변경요청 | `/partner-change-request`, `/change-request-register`, `/change-request-detail/<int:request_id>` |
| 안전지시서 | `/safety-instruction`, `/safety-instruction-register`, `/safety-instruction-detail/<issue_number>` |
| Follow SOP | `/follow-sop`, `/follow-sop-register`, `/follow-sop-detail/<work_req_no>` |
| Safe Workplace | `/safe-workplace`, `/safe-workplace-register`, `/safe-workplace-detail/<safeplace_no>` |
| Full Process | `/full-process`, `/full-process-register`, `/full-process-detail/<fullprocess_number>` |
| 하도급 승인 | `/subcontract-approval`, `/subcontract-approval-register`, `/subcontract-approval-detail/<approval_number>` |
| 하도급 제보 | `/subcontract-report`, `/subcontract-report-register`, `/subcontract-report-detail/<report_number>` |
| 기타 안전 페이지 | `/work-safety`, `/risk-assessment`, `/qualification-assessment`, `/safety-culture` |
| 파일 | `/download/...`, `/uploads/content/...`, `/upload-inline-image` |
| 권한 요청 | `/permission-request` |
| 검색 팝업 | `/search-popup` |

## SSO/디버그 라우트

SSO와 디버그 관련 라우트는 다음과 같다.

| URL | method | 성격 |
| --- | --- | --- |
| `/sso/dev-login` | GET, POST | 개발용 로그인 |
| `/SSO` | GET | SSO 시작 |
| `/acs` | GET, POST | SSO 응답 처리 |
| `/slo` | GET | 로그아웃 |
| `/debug-session` | GET | 세션 디버그 |
| `/sso/diagnostics` | GET | SSO 설정 진단 |

이 라우트들은 `auto_sso_redirect` 훅의 제외 경로와 직접 연결된다.

## catch-all 라우트

catch-all 라우트는 다음 위치에 있다.

- `app.py:9304`
- URL: `/<path:url>`
- 함수: `page_view`

이 라우트 이후에도 여러 구체 라우트가 정의되어 있다.

catch-all 이후에 정의된 주요 라우트는 다음과 같다.

- `/upload-inline-image`
- `/uploads/content/<path:filename>`
- `/api/menus`
- `/api/admin/audit-logs`
- `/api/admin/usage-dashboard`
- `/sso/dev-login`
- `/SSO`
- `/acs`
- `/slo`
- `/debug-session`
- `/sso/diagnostics`
- `/admin/permissions...`
- `/api/permissions/...`

Flask/Werkzeug는 일반적으로 더 구체적인 rule을 우선할 수 있지만, catch-all은 실제 `app.url_map`으로 우선순위를 확인해야 한다.

이 부분은 2단계의 정적 위험 후보이며, 실행 검증 전에는 단정하지 않는다.

## 백업/테스트/삽입용 라우트 파일

전체 저장소에서 route처럼 보이는 파일은 더 많았다.

실제 런타임 연결 흔적이 없는 라우트 후보 파일은 다음과 같다.

| 파일 | route 수/성격 | 판단 |
| --- | ---: | --- |
| `add_api_endpoints.py` | 18 | app.py에 통합되지 않은 추가 API 후보 |
| `add_page_routes_backup.py` | 8 | 백업 파일 |
| `admin_permission_routes.py` | 8 | 별도 관리자 권한 route 후보 |
| `dept_permission_api.py` | 6 | 독립 Blueprint, 메인 앱 미등록 후보 |
| `integrated_monitoring.py` | 5 | 별도 monitoring route 후보 |
| `account_switcher.py` | 3 | 별도 계정 전환 route 후보 |
| `sso_test_login.py` | 3 | 테스트 로그인 route 후보 |
| `test_login.py` | 2 | 테스트 로그인 route 후보 |

또한 다음 파일에는 route처럼 보이는 문자열/삽입용 조각이 있다.

- `app_integration_day6.py`
- `create_safe_workplace_routes.py`
- `sso_debug_enhanced.py`

이 파일들은 `@app.route` 문자열이 보이지만 AST 기준 실제 데코레이터로는 잡히지 않았다. 즉 실행 코드라기보다 예시/삽입용/진단용 코드 조각으로 보는 편이 맞다.

## 중복 라우트 분석

정적 AST 기준으로 `동일 path + 동일 method`의 명백한 중복은 0개였다.

단, 다음은 정상 패턴으로 많이 존재한다.

- 같은 path에 GET/POST 분리
- 같은 path에 PUT/DELETE 분리
- 같은 resource path에 method별 CRUD 분리

## 동적 라우트 overlap 후보

정확한 중복은 아니지만, 동적 route가 특정 route와 같은 형태를 가질 수 있는 후보가 있다.

대표 후보는 다음과 같다.

### 컬럼 order 경로

- `PUT /api/accident-columns/<int:column_id>`
- `PUT /api/accident-columns/order`

`order`는 int converter에 걸리지 않으므로 실제 충돌 가능성은 낮다.

비슷한 구조가 `change-request/columns`에도 있다.

### 공통 delete API와 보드별 delete API

- `POST /api/<board_type>/delete`
- `POST /api/accidents/delete`
- `POST /api/safety-instructions/delete`
- `POST /api/follow-sop/delete`
- `POST /api/safe-workplace/delete`
- `POST /api/full-process/delete`
- `POST /api/partners/delete`
- `POST /api/change-requests/delete`

이 구조는 공통 API와 보드별 레거시 API가 공존하는 흔적으로 보인다.

Flask rule matching에서 어느 함수가 선택되는지는 실제 `app.url_map`과 test request로 확인해야 한다.

### 공통 board API와 change-request API

- `/api/<board>/columns`
- `/api/change-request/columns`
- `/api/<board>/dropdown-codes`
- `/api/change-request/dropdown-codes`

`change-request`가 공통 board API의 board 이름처럼도 해석될 수 있다.

이 부분은 실제 의도가 다음 둘 중 하나인지 확인이 필요하다.

1. `change-request`를 공통 board 체계로 편입하려던 흔적
2. 기존 전용 API와 새 공통 API가 동시에 남은 상태

### catch-all

- `GET /<path:url>`

모든 일반 페이지 URL과 형태상 겹칠 수 있다.

정적 분석만으로는 문제라고 단정하지 않지만, 라우트 우선순위 검증 대상이다.

## 레거시/과도기 흔적

라우트 이름과 URL 기준으로 볼 때, 다음 영역은 레거시와 신형 구조가 섞여 있다.

### 사고

사고는 Controller/Repository로 일부 분리되어 있다.

- `AccidentController`
- `AccidentRepository`

그러나 `app.py`에는 사고 관련 페이지, 저장, 수정, 삭제, export/import, 컬럼/섹션 API가 여전히 대량으로 남아 있다.

즉 "부분 분리 + 레거시 app.py 잔존" 상태다.

### 안전지시서

안전지시서는 Blueprint와 Controller/Repository가 모두 존재한다.

- `boards/safety_instruction.py`
- `SafetyInstructionController`
- `SafetyInstructionRepository`

구조는 사고보다 분리 의도가 더 선명하지만, 컬럼/섹션/export/delete 등은 여전히 `app.py`에 많다.

### change-request

`change-request`는 레거시성이 가장 강하게 보인다.

- 전용 페이지 라우트
- 전용 컬럼 API
- 전용 dropdown API
- 전용 save/export/delete API
- 공통 `/api/<board>/...` API와 형태상 overlap 가능

이 영역은 향후 리팩터링 시 바로 건드리기보다, 먼저 데이터 모델과 화면 의도를 확인해야 한다.

### partner

협력사도 레거시성이 강하다.

- `/partner-standards`
- `/partner/<business_number>`
- `/partner-detail/<business_number>`
- `/update-partner`
- `/api/partners/...`
- `/api/partner-change-request`
- `/api/partner-change-requests`

협력사 기준정보와 협력사 변경요청이 섞여 있으므로, 라우트 그룹을 먼저 명확히 나눠야 한다.

### 권한

권한 관련 route는 최소 세 흐름이 보인다.

1. `permission_api.py`의 menu/dept/permission-request API
2. `app.py` 하단의 `/admin/permissions...`, `/api/permissions/...`
3. 미등록 후보 `dept_permission_api.py`

권한 시스템은 "Day 2/Day 3 식으로 기능을 덧붙인 흔적"이 강하다.

## 2단계 결론

라우트 구조는 크게 다음 세 시대가 겹쳐 있다.

1. 초기 대형 `app.py` 직접 라우트
2. 게시판별 Blueprint/Controller로 옮겨가는 중간 구조
3. 권한/SSO/부서권한 기능을 나중에 덧붙인 구조

현재 가장 위험한 지점은 코드를 고치는 것보다, "어떤 URL이 현재 진짜 기준인지"를 잘못 판단하는 것이다.

따라서 다음 단계에서는 게시판별 흐름을 하나씩 따라가며, 화면 URL과 저장 API가 어떤 조합으로 연결되는지 확인해야 한다.

추천 순서는 다음과 같다.

1. 사고
2. 안전지시서
3. Follow SOP
4. Safe Workplace
5. Full Process
6. 하도급 승인/제보
7. 협력사/변경요청
8. 권한/SSO

다음 단계는 3단계 게시판별 흐름 분석이다.
