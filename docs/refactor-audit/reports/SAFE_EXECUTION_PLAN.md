# 안전 실행 계획

작성일: 2026-06-13

## 목적

이 문서는 Flask Portal을 실제로 실행하고 브라우저로 확인하기 전에 지켜야 할 안전 절차다.

현재까지의 분석에서 확인된 핵심 위험은 다음이다.

- `python app.py` 직접 실행은 시작 시 `init_db()`를 호출한다.
- WSGI/import 실행도 첫 HTTP 요청 시 `boot_sync_once() -> init_db()`가 실행될 수 있다.
- 현재 DB backend는 PostgreSQL이고, 로컬 PostgreSQL 서비스가 실행 중이다.
- 프론트와 백엔드 URL drift 후보가 있다.
- 일부 버튼은 삭제/최종검토/import처럼 DB 쓰기 가능성이 있다.

따라서 실행 검증은 "백업 → 읽기 검증 → 제한적 브라우저 확인 → 쓰기 검증은 별도 승인" 순서로 진행한다.

## 실행 전 고정 원칙

1. 앱 코드 수정 금지
2. 실행 전 기존 `.md` 분석 문서 재확인
3. `app.py`, `config.ini` 기존 사용자 변경분 덮어쓰기 금지
4. 백업 실패 시 실행 중단
5. 첫 실행은 `python app.py`가 아니라 WSGI import 방식 사용
6. 처음에는 GET 화면과 route map만 확인
7. POST/DELETE/import/final-check 버튼은 사용자가 별도 승인하기 전 클릭 금지
8. 테스트 중 변경이 발생하면 즉시 기록

## 다음 단계 전 문서 재확인 규칙

각 단계 시작 전 반드시 다음 문서를 먼저 읽는다.

- `BASELINE_REPORT.md`
- `RUNTIME_ENTRY_REPORT.md`
- `ROUTE_MAP_REPORT.md`
- `BOARD_FLOW_REPORT.md`
- `SAFE_EXECUTION_PLAN.md`
- `ANALYSIS_CHECKLIST.md`

새 보고서가 추가되면 이 목록에 포함한다.

## 현재 기준선

현재 확인된 상태는 다음과 같다.

- Git 기준 수정 파일: `app.py`, `config.ini`
- 로컬 PostgreSQL 서비스: `postgresql-x64-17`, Running
- PostgreSQL 포트: `5432` listen 중
- 실행 중인 Python/Flask 프로세스: 없음
- `config.ini` DB backend: `postgres`
- `config.ini` DSN: `postgresql://postgres:***@localhost:5432/portal_dev`
- `external_db_enabled = false`
- `initial_sync_on_first_request = false`
- `master_data_daily = false`
- `content_data_once = false`
- `COLUMNS.sync_on_startup = false`
- `SSO.sso_enabled = False`
- `SSO.dev_mode = True`
- HTTP 포트 후보: `5000`
- SSL 포트 후보: `44369`

## 실행 부작용 후보

### `python app.py`

직접 실행은 다음 부작용 가능성이 있다.

- `init_db()` 즉시 실행
- migrations 실행 가능
- 기본 `pages` seed 가능
- 외부 DB 설정이 켜져 있으면 sync 가능
- `COLUMNS.SYNC_ON_STARTUP=true`일 경우 컬럼 설정 sync 가능
- Werkzeug reloader 메인 프로세스에서 scheduler thread 시작 가능
- SSL 인증서 검사 후 HTTPS 또는 HTTP 실행

따라서 첫 실행 방식으로 사용하지 않는다.

### WSGI import 방식

`wsgi.py` 또는 `from wsgi import app` 방식은 `app.py`의 `__main__` 블록을 실행하지 않는다.

장점은 다음과 같다.

- 직접 실행부의 즉시 `init_db()`를 피한다.
- scheduler thread 시작을 피한다.
- SSL 인증서 분기를 피할 수 있다.
- 원하는 포트로 HTTP 실행할 수 있다.

단점은 다음과 같다.

- 첫 HTTP 요청에서 `check_first_request -> boot_sync_once -> init_db()`가 실행될 수 있다.
- 실제 Phase 1 점검 결과, HTTP 요청 전 import-only 단계에서도 `partners_cache` 테이블 구조 확인성 동작이 발생했다.

따라서 WSGI import 방식은 직접 실행보다 안전하지만 완전 무해하지는 않다. WSGI 방식도 백업 후에만 브라우저 접속한다.

## 백업 계획

실행 전 다음 백업을 만든다.

백업 폴더 형식:

```powershell
backup\codex_preflight_YYYYMMDD_HHMMSS
```

필수 백업 대상:

- `app.py`
- `config.ini`
- `requirements.txt`
- `*.db`
- `logs` 폴더 목록
- 현재 `git status`, `git diff --stat`, `git diff -- app.py config.ini`

PostgreSQL 백업 후보:

```powershell
pg_dump -h localhost -p 5432 -U postgres -d portal_dev -F c -f backup\codex_preflight_YYYYMMDD_HHMMSS\portal_dev.dump
```

주의:

- `pg_dump`가 PATH에 없으면 PostgreSQL 설치 경로의 `pg_dump.exe`를 찾아야 한다.
- 비밀번호 입력이 필요할 수 있다.
- `pg_dump` 실패 시 브라우저 실행으로 넘어가지 않는다.

## 단계별 실행 계획

### Phase 0. 실행 전 무해 확인

목적: 코드를 실행하지 않고 상태만 확인한다.

명령 후보:

```powershell
git status --short --untracked-files=all
git diff --stat
venv\Scripts\python.exe --version
venv\Scripts\python.exe -m py_compile app.py wsgi.py
Get-Service postgresql-x64-17
Get-NetTCPConnection -LocalPort 5432
```

허용 범위:

- 파일 읽기
- 문법 컴파일
- 서비스 상태 확인

중단 조건:

- `app.py` 또는 `wsgi.py` 문법 오류
- PostgreSQL 서비스 중지
- 예상치 못한 추가 Git 변경 파일 발견

### Phase 1. Flask app import-only 확인

목적: 서버를 띄우지 않고 `app.url_map`만 확인한다.

명령 후보:

```powershell
venv\Scripts\python.exe -c "from wsgi import app; print(len(list(app.url_map.iter_rules()))); print(app.url_map)"
```

예상 부작용:

- `app.py` import 시 전역 객체/route 등록
- logging 초기화
- DB write는 없어야 함
- 단, 실제 점검 결과 DB 구조 확인성 read/check가 발생할 수 있음

확인 항목:

- 앱 import 성공 여부
- 실제 route 수
- catch-all 우선순위
- URL drift 후보의 실제 route 존재 여부

중단 조건:

- import 실패
- import 중 DB write 의심 로그 발생
- route map에서 핵심 페이지 라우트 누락

### Phase 2. DB 백업

목적: 첫 HTTP 요청 전 PostgreSQL과 로컬 파일을 복구 가능 상태로 만든다.

작업:

1. 백업 폴더 생성
2. 앱/설정/SQLite 파일 복사
3. `pg_dump` 실행
4. 백업 파일 크기 확인
5. 백업 로그 저장

중단 조건:

- 백업 폴더 생성 실패
- `pg_dump` 실패
- 백업 파일 크기 0 또는 비정상

### Phase 3. 안전 서버 실행

목적: 직접 `python app.py` 대신 WSGI import 방식으로 HTTP 서버를 띄운다.

추천 방식:

```powershell
venv\Scripts\python.exe -c "from wsgi import app; app.run(host='127.0.0.1', port=5050, debug=False, use_reloader=False)"
```

이 방식의 장점:

- `app.py`의 직접 실행부를 피한다.
- scheduler thread를 피한다.
- SSL 인증서 분기를 피한다.
- `127.0.0.1:5050`으로 고정한다.

주의:

- 첫 브라우저 요청에서 `boot_sync_once()`가 실행될 수 있다.
- 따라서 Phase 2 백업 전에는 이 단계로 가지 않는다.

중단 조건:

- 서버 시작 실패
- 첫 요청에서 500 에러
- 로그에 migration 실패
- 로그에 예상치 못한 외부 DB sync 시도

### Phase 4. 브라우저 읽기 전용 확인

목적: GET 화면만 열어 UI가 살아있는지 본다.

첫 접속:

- `http://127.0.0.1:5050/`
- SSO redirect 발생 시 `/sso/dev-login` 확인

읽기 전용 확인 대상:

- `/`
- `/partner-standards`
- `/partner-change-request`
- `/accident`
- `/safety-instruction`
- `/follow-sop`
- `/full-process`
- `/safe-workplace`
- `/subcontract-approval`
- `/subcontract-report`

확인 항목:

- 페이지 로드 성공
- 메뉴 렌더링
- 템플릿 오류 여부
- 브라우저 콘솔 오류
- 네트워크 404/500
- 버튼 표시 여부

금지 항목:

- 삭제 클릭
- 최종검토 클릭
- import 실행
- 저장/수정 submit
- 권한 변경
- 관리자 sync 실행

### Phase 5. URL drift 후보 확인

목적: 3단계에서 찾은 프론트/백엔드 불일치 후보를 실제 화면과 route map으로 확인한다.

대상:

- Follow SOP export
- Subcontract Approval export
- Subcontract Report export
- Subcontract Approval final-check
- Subcontract Report final-check
- Safety Instruction import
- Full Process import

원칙:

- export는 GET이지만 DB와 파일 생성 가능성이 있으므로 먼저 route 존재 여부만 확인한다.
- final-check는 상태 변경이므로 클릭하지 않는다.
- import는 데이터 삽입 가능성이 있으므로 클릭하지 않는다.

확인 방법:

1. route map으로 백엔드 존재 여부 확인
2. 브라우저에서 버튼/JS URL 확인
3. 네트워크 요청은 사용자가 승인한 항목만 실행

### Phase 6. 쓰기 테스트는 별도 승인 후 진행

쓰기 테스트 대상:

- 저장
- 수정
- 삭제
- 복구
- 최종검토
- import
- 권한 변경
- 관리자 sync

원칙:

- 테스트 데이터 1건만 사용
- 실행 전 해당 테이블 row count 기록
- 실행 후 row count와 변경 row 기록
- 실패 시 즉시 중단
- 필요하면 백업에서 복구

## 버튼별 클릭 허용 등급

| 등급 | 예시 | 기본 허용 여부 |
| --- | --- | --- |
| 읽기 | 메뉴 이동, 상세 보기, 검색 | 허용 |
| 약한 읽기 | export 다운로드 | route 확인 후 제한 허용 |
| 쓰기 | 등록, 수정, 삭제, 복구 | 별도 승인 필요 |
| 강한 쓰기 | import, final-check, 권한 변경, sync | 별도 승인 필요 |

## 우선 검증할 URL drift 후보

| 우선순위 | 후보 | 이유 |
| --- | --- | --- |
| 1 | Follow SOP export | 프론트 `/api/follow-sop/export`, 백엔드 `/api/follow-sop-export` |
| 2 | Subcontract Approval export/final-check | 프론트 버튼 후보는 있으나 백엔드 라우트 미확인 |
| 3 | Subcontract Report export/final-check | 프론트 버튼 후보는 있으나 백엔드 라우트 미확인 |
| 4 | Safety Instruction import | 안전지시서 화면에서 `/api/accident-import` 호출 흔적 |
| 5 | Full Process import | Full Process 화면에서 `/api/accident-import` 호출 흔적 |

## 로그 확인 계획

실행 중 확인할 로그:

- 터미널 stdout/stderr
- `app.log`
- 브라우저 콘솔
- 브라우저 네트워크 요청

감시할 키워드:

- `ERROR`
- `Traceback`
- `Migration execution failed`
- `Initial sync error`
- `maybe_daily_sync`
- `external DB`
- `permission denied`
- `404`
- `500`

## 중단 조건 전체 목록

다음 중 하나라도 발생하면 즉시 중단한다.

- 백업 실패
- 서버 import 실패
- 서버 시작 실패
- 첫 요청 500
- migration 실패
- 외부 DB sync 시도
- 알 수 없는 대량 DB write 로그
- 삭제/최종검토/import가 실수로 실행됨
- Git 변경 파일이 예상보다 늘어남
- `app.py`, `config.ini`가 사용자 동의 없이 바뀜

## 실행 후 기록할 것

각 실행 후 다음을 기록한다.

- 실행 시각
- 실행 명령
- 서버 포트
- 접속 URL
- 성공/실패
- 에러 로그
- 브라우저 콘솔 오류
- 네트워크 404/500
- DB write 여부
- Git 상태

## 다음 추천 행동

다음 턴에서 바로 실행하지 말고, 먼저 Phase 0과 Phase 1만 수행한다.

권장 순서:

1. `py_compile`로 문법 확인
2. `from wsgi import app` import-only 확인
3. `app.url_map`으로 route 존재 여부 확인
4. 이상 없으면 PostgreSQL 백업 계획을 실제 실행할지 사용자에게 확인

브라우저 실행은 백업 완료 후 진행한다.
