# 프론트엔드 연결 분석 보고서

작성일: 2026-06-13  
범위: 템플릿, 정적 JavaScript, 프론트엔드 호출 URL, 백엔드 라우트 정합성  
원칙: 코드 수정 없음, 서버 실행 없음, 브라우저 클릭 검증 없음, 정적 분석 중심

## 0. 사전 기준

이번 단계 전에 다음 문서를 기준으로 다시 확인했다.

- `BASELINE_REPORT.md`
- `RUNTIME_ENTRY_REPORT.md`
- `ROUTE_MAP_REPORT.md`
- `BOARD_FLOW_REPORT.md`
- `SAFE_EXECUTION_PLAN.md`
- `PREFLIGHT_EXECUTION_REPORT.md`
- `ANALYSIS_CHECKLIST.md`

중요한 전제는 그대로 유지된다.

- 기존 사용자 변경 파일은 `app.py`, `config.ini`이며 건드리지 않았다.
- `python app.py` 직접 실행은 하지 않았다.
- WSGI import도 이번 단계에서는 새로 수행하지 않았다.
- URL 정합성은 AST 기반 라우트 목록과 템플릿/JS의 호출 문자열을 대조했다.

## 1. 전체 프론트 구조

### 1.1 기본 레이아웃

- `templates/base.html`은 일반 화면의 공통 레이아웃이다.
  - 메뉴 렌더링, 관리자 드롭다운, Bootstrap/CKEditor CDN, `popup-handler.js` 로딩을 담당한다.
  - 메뉴 링크는 대체로 `url_for('page_view', url=...)`를 통해 catch-all 페이지 라우트로 들어간다.
- `templates/popup-base.html`은 팝업 화면의 공통 레이아웃이다.
  - `popup-handler.js`와 `ckeditor-simple.js`를 로딩한다.
- `templates/index.html`은 `base.html`을 상속하는 진입 화면이다.

### 1.2 게시판 화면 패턴

게시판은 대체로 3종 템플릿으로 구성된다.

- 목록: `*-standards.html`, `partner-accident.html`, `safety-instruction.html`, `follow-sop.html`, `full-process.html`, `safe-workplace.html`, `subcontract-approval.html`, `subcontract-report.html`
- 등록: `*-register.html`
- 상세: `*-detail.html`

현재 프론트엔드 패턴은 세 계열로 나뉜다.

- legacy 직접 구현형: `partner`, `change_request`
- 중간 refactor형: `accident`, `safety_instruction`
- 동적 게시판형: `follow_sop`, `full_process`, `safe_workplace`, `subcontract_approval`, `subcontract_report`

## 2. 공통 JavaScript 역할

### 2.1 `board-form.js`

`static/js/board-form.js`는 동적 폼 데이터 수집의 중심이다.

- `collectDynamicFields()`가 `[data-field]`, `[data-section]` 기반 동적 입력값을 모은다.
- `groupFieldsBySection()`이 동적 필드를 섹션별로 묶는다.
- `appendSectionGroups()`, `appendCustomData()`가 `FormData`에 JSON 구조를 추가한다.
- `appendPendingFiles()`가 임시 첨부파일을 `FormData`에 붙인다.
- 최종적으로 `window.BoardForm` 전역 객체로 노출된다.

근거:

- `static/js/board-form.js:74`
- `static/js/board-form.js:386`
- `static/js/board-form.js:446`
- `static/js/board-form.js:469`
- `static/js/board-form.js:482`
- `static/js/board-form.js:662`
- `static/js/board-form.js:680`

### 2.2 `board-detail.js`

`static/js/board-detail.js`는 상세 화면 저장 흐름의 공통 엔진이다.

- `BoardDetail.createUpdater()`가 저장 함수 생성기 역할을 한다.
- `BoardForm`에서 상세 내용, 동적 필드, 섹션 그룹, 첨부파일 메타데이터를 가져와 `FormData`를 구성한다.
- 최종 저장은 전달받은 `endpoint`로 `POST`한다.
- 비밀번호 확인은 `/verify-password`로 별도 호출한다.

근거:

- `static/js/board-detail.js:101`
- `static/js/board-detail.js:130`
- `static/js/board-detail.js:135`
- `static/js/board-detail.js:159`
- `static/js/board-detail.js:213`
- `static/js/board-detail.js:221`

### 2.3 `list-child-support.js`

`static/js/list-child-support.js`는 관리자 컬럼 설정의 list child schema 팝업을 담당한다.

- 컬럼 키를 기준으로 `list-builder` 팝업 URL을 만든다.
- `window.openListChildBuilder*` 함수를 전역에 노출한다.
- 팝업에서 저장된 `LIST_CHILD_SCHEMA_SAVED` 메시지를 받아 부모 화면의 컬럼 상태에 반영한다.

근거:

- `static/js/list-child-support.js:147`
- `static/js/list-child-support.js:253`
- `static/js/list-child-support.js:260`

### 2.4 팝업 핸들러

팝업 계열은 두 파일로 나뉘어 있다.

- `static/js/popup-handler.js`
  - 현재 `base.html`, `popup-base.html`에서 실제 로딩되는 기본 팝업 핸들러다.
  - `openPersonSearch`, `openCompanySearch`, `openBuildingSearch`, `openDepartmentSearch`, `receivePersonSelection` 등을 제공한다.
- `static/js/universal-popup-handler.js`
  - 더 범용적인 `UniversalPopupManager`와 `openUniversalPopup`을 제공하지만, 현재 템플릿 검색에서는 직접 include가 확인되지 않았다.
  - `templates/includes/list_field_v3.html`은 `openUniversalPopup`이 있으면 사용하고, 없으면 fallback으로 직접 팝업을 연다.

근거:

- `templates/base.html:572`
- `templates/popup-base.html:179`
- `static/js/popup-handler.js:154`
- `static/js/popup-handler.js:367`
- `static/js/universal-popup-handler.js:7`
- `static/js/universal-popup-handler.js:433`
- `templates/includes/list_field_v3.html:309`

### 2.5 채점 스크립트

- `static/js/scoring-system.js`는 클라이언트 측 점수 합산 UI를 담당한다.
- `static/js/scoring-external.js`는 full process 외부 채점 값을 `/api/full-process/external-scoring/<번호>`로 조회하려고 한다.
- 현재 정적 라우트 목록에서는 `/api/full-process/external-scoring/<...>` 백엔드 라우트가 확인되지 않았다.

근거:

- `templates/full-process-register.html:15`
- `templates/full-process-detail.html:15`
- `static/js/scoring-external.js:109`

## 3. UI 흐름 매핑

### 3.1 목록 화면

일반적인 목록 화면 흐름은 다음과 같다.

1. 검색 조건을 쿼리스트링으로 구성한다.
2. 정렬/페이지 이동도 쿼리스트링 갱신으로 처리한다.
3. 등록 버튼은 `*-register?popup=1` 팝업을 연다.
4. 상세 행 클릭은 `*-detail/<번호>?popup=1` 팝업을 연다.
5. 삭제는 목록별 API 또는 공통 동적 API로 `POST`한다.
6. export는 게시판마다 URL 규칙이 다르다.

### 3.2 등록/상세 화면

등록/상세 화면은 두 방식이 섞여 있다.

- legacy 화면은 템플릿 안에서 직접 `fetch('/register-*')`, `fetch('/update-*')`를 호출한다.
- 동적 게시판 계열은 `board_form_scripts.html`을 통해 `BoardForm`, `BoardDetail`을 공통 사용한다.

공통 include:

- `templates/includes/board_form_scripts.html:1`
- `templates/includes/board_form_scripts.html:2`
- `templates/includes/board_form_scripts.html:3`

### 3.3 관리자 컬럼 설정 화면

관리자 컬럼 설정은 게시판별로 별도 템플릿이 많지만, 구조는 비슷하다.

- 컬럼 목록 조회
- 컬럼 추가/수정/삭제
- 섹션 목록 조회 및 섹션 순서 변경
- 드롭다운 코드 편집
- list 타입의 child schema 팝업 편집

이 영역은 공통화가 일부 되어 있지만, 템플릿별 중복 코드가 여전히 많다.

## 4. URL 정합성 주요 발견

### 4.1 Change Request 컬럼 API 불일치

프론트 일부는 `/api/change-request-columns`를 호출한다.

- `templates/admin-change-request-columns.html:427`
- `templates/admin-change-request-columns.html:1195`
- `templates/admin-change-request-columns.html:1223`
- `templates/admin-change-request-columns.html:1249`
- `templates/partner-change-request.html:1376`

하지만 백엔드 실제 라우트는 `/api/change-request/columns` 계열이다.

- `app.py:4817`
- `app.py:4828`
- `app.py:4839`
- `app.py:4850`
- `app.py:4861`

판단:

- 실제 클릭 시 해당 화면의 컬럼 조회/저장/수정/삭제가 실패할 가능성이 높다.
- `admin-change-request-columns-simplified.html`은 `/api/change-request/columns`를 쓰고 있어, 새 규칙과 옛 규칙이 공존한다.

### 4.2 403 화면 권한 요청 URL 불일치

`templates/errors/403.html`은 다음을 사용한다.

- `window.location.href = '/login'`
- `fetch('/api/permissions/request')`

근거:

- `templates/errors/403.html:36`
- `templates/errors/403.html:41`

하지만 백엔드에는 `/login` endpoint가 없고, 실제 권한 요청 API는 `/api/permission-requests` 계열이다.

- `app.py:3693`
- `app.py:9829`
- `permission_api.py:1253`
- `permission_api.py:1408`
- `permission_api.py:1490`
- `permission_api.py:1601`
- `permission_api.py:1664`
- `permission_api.py:1723`

판단:

- 403 페이지에서 로그인 이동 또는 권한 요청 버튼이 깨질 가능성이 높다.
- 이 문제는 `PREFLIGHT_EXECUTION_REPORT.md`의 `login endpoint absent` 결과와도 일치한다.

### 4.3 Export URL 규칙 불일치

동적 게시판 목록 템플릿 중 일부는 `/api/${boardPageConfig.slug}/export` 형태를 사용한다.

- `templates/follow-sop.html:685`
- `templates/subcontract-approval.html:685`
- `templates/subcontract-report.html:685`

하지만 백엔드 export 라우트는 하이픈 suffix 방식이다.

- `app.py:7096` `/api/follow-sop-export`
- `app.py:7351` `/api/safe-workplace-export`
- `app.py:7602` `/api/full-process-export`
- `app.py:7882` `/api/safety-instruction-export`
- `app.py:6588` `/api/accident-export`

판단:

- `follow-sop` export는 프론트 `/api/follow-sop/export`와 백엔드 `/api/follow-sop-export`가 어긋난다.
- `subcontract-approval`, `subcontract-report`는 현재 백엔드 export 라우트 자체가 확인되지 않는다.

### 4.4 Final Check 지원 범위 불일치

템플릿은 다음 URL을 호출한다.

- `templates/follow-sop.html:758`
- `templates/subcontract-approval.html:758`
- `templates/subcontract-report.html:758`

백엔드에서 확인된 final-check 라우트는 세 개다.

- `app.py:5793` `/api/full-process/final-check`
- `app.py:5847` `/api/follow-sop/final-check`
- `app.py:5900` `/api/safe-workplace/final-check`

판단:

- `follow-sop` final-check는 정상 라우트가 있다.
- `subcontract-approval`, `subcontract-report` final-check는 라우트가 확인되지 않는다.
- `PREFLIGHT_EXECUTION_REPORT.md`의 route matching 결과에서도 두 subcontract final-check는 `405 Method Not Allowed`로 확인되었다.

### 4.5 Delete API는 동적 라우트로 흡수됨

`subcontract-approval.html`, `subcontract-report.html`은 `/api/${boardPageConfig.slug}/delete`를 호출한다.

- `templates/subcontract-approval.html:801`
- `templates/subcontract-report.html:801`

백엔드에는 공통 동적 삭제 라우트가 있다.

- `app.py:5481` `/api/<board_type>/delete`

판단:

- 정적 문자열만 보면 누락처럼 보일 수 있으나, preflight route matching 결과상 subcontract 삭제는 `delete_items`로 매칭된다.
- 이 항목은 현재 “문제”가 아니라 “동적 라우트 의존”으로 분류한다.

### 4.6 Import API 재사용 의심

다음 화면은 모두 `/api/accident-import`를 사용한다.

- `templates/partner-accident.html:762`
- `templates/safety-instruction.html:809`
- `templates/full-process.html:802`

백엔드 실제 라우트도 `/api/accident-import` 하나다.

- `app.py:6787`

판단:

- accident 화면은 자연스럽다.
- safety-instruction, full-process에서 같은 import API를 쓰는 것은 의도적 재사용일 수도 있지만, 이름상 drift 가능성이 있다.
- 실제 엑셀 컬럼/저장 대상 검증 전까지는 “주의 후보”로 둔다.

### 4.7 Full Process 외부 채점 API 후보

`static/js/scoring-external.js`는 다음 API를 호출한다.

- `static/js/scoring-external.js:109`

현재 정적 라우트 목록에서는 `/api/full-process/external-scoring/<번호>` 라우트가 확인되지 않았다.

판단:

- full-process 등록/상세에서 외부 채점 기능을 쓰는 경우 실패 가능성이 있다.
- 다음 DB/서비스 단계에서 `scoring_external_service*.py`와 함께 확인해야 한다.

## 5. 중복 로딩/구조상 주의점

### 5.1 `board_form_scripts.html` 중복 include

`accident-register.html`은 공통 보드 스크립트를 두 번 include한다.

- `templates/accident-register.html:9`
- `templates/accident-register.html:439`

판단:

- `board-form.js`, `board-detail.js`가 중복 로딩될 수 있다.
- 현재 JS가 어느 정도 idempotent하게 작성되어 있어 즉시 치명적이지 않을 수 있지만, 이벤트 중복 등록 가능성은 있다.

### 5.2 `scoring-system.js` 중복 로딩

일부 등록 화면은 `head`와 하단에서 `scoring-system.js`를 다시 로딩한다.

- `templates/full-process-register.html:14`
- `templates/full-process-register.html:536`
- `templates/safety-instruction-register.html:14`
- `templates/safety-instruction-register.html:670`

판단:

- 점수 계산 이벤트가 중복 바인딩될 가능성이 있다.
- 단순 합산 함수라면 영향이 작을 수 있지만, UI 이벤트가 늘어나면 디버깅이 어려워진다.

### 5.3 `ckeditor-simple.js` 중복 가능성

`popup-base.html`이 이미 `ckeditor-simple.js`를 로딩한다.

- `templates/popup-base.html:196`

그런데 여러 팝업 상세/등록 템플릿도 하단에서 다시 로딩한다.

- `templates/partner-detail.html:1130`
- `templates/accident-register.html:519`
- `templates/accident-detail.html:622`
- `templates/change-request-register.html:823`
- `templates/change-request-detail.html:1304`
- `templates/safety-instruction-detail.html:522`
- `templates/follow-sop-detail.html:639`
- `templates/full-process-detail.html:710`
- `templates/subcontract-approval-detail.html:647`
- `templates/subcontract-report-detail.html:647`

판단:

- 팝업 화면에서 CKEditor 초기화가 중복될 수 있다.
- 실제 영향은 `ckeditor-simple.js` 내부의 중복 방지 로직 확인 후 판단해야 한다.

## 6. 현재 결론

프론트엔드는 “작동한 화면을 계속 복붙 확장한 흔적”이 강하다. 의도 자체는 분명하다.

- 목록/등록/상세 3단 구조
- 팝업 중심 업무 입력
- 동적 컬럼/섹션 기반 확장
- 게시판별 export/import/delete/final-check
- 관리자 화면에서 컬럼과 드롭다운을 직접 설정

다만 문제도 꽤 선명하다.

- URL 규칙이 게시판마다 통일되지 않았다.
- 일부 화면은 예전 API 이름을 아직 호출한다.
- 공통 JS가 생겼지만, 템플릿 중복 include와 legacy 직접 구현이 같이 남아 있다.
- “없는 API를 호출하는 프론트” 후보가 여럿 있다.
- catch-all 페이지 라우트 때문에 잘못된 GET API가 명확한 404가 아니라 페이지 라우트로 흡수될 수 있다.

## 7. 우선순위 후보

수정은 아직 하지 않는다. 나중에 고친다면 우선순위는 다음 순서가 안전하다.

1. `403.html`의 `/login`, `/api/permissions/request` 불일치
2. `change-request` 컬럼 API URL 불일치
3. `follow-sop`, `subcontract-*` export URL 불일치
4. `subcontract-*` final-check 버튼/라우트 불일치
5. `scoring-external.js`의 full-process 외부 채점 API 존재 여부
6. `board_form_scripts`, `scoring-system`, `ckeditor-simple` 중복 로딩 정리
7. `accident-import` 재사용이 의도인지 drift인지 검증

## 8. 다음 단계 제안

다음 분석 단계는 DB와 데이터 흐름이다.

- `db_connection.py`, `db/compat.py`, `database_config.py`를 먼저 확인한다.
- PostgreSQL 전환 이후에도 남아 있는 SQLite 호환층을 분류한다.
- 게시판별 실제 테이블, cache/detail/section/column_config/custom_data 저장 위치를 매핑한다.
- import/export/final-check가 어느 테이블을 건드리는지 확인한다.

이 단계는 실제 데이터 변경 위험이 커질 수 있으므로, 계속 정적 분석 위주로 진행하고 실행 검증은 별도 승인 후 수행하는 편이 안전하다.
