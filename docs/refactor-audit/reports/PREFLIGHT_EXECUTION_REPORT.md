# 사전 실행 점검 결과

작성일: 2026-06-13

## 목적

`SAFE_EXECUTION_PLAN.md`의 Phase 0과 Phase 1만 수행했다.

이번 점검에서는 다음을 하지 않았다.

- Flask 서버 실행 안 함
- 브라우저 접속 안 함
- HTTP 요청 안 함
- DB 백업 전 POST/DELETE/import/final-check 실행 안 함
- 앱 코드 수정 안 함

## Phase 0. 무해 확인 결과

### Git 상태

현재 Git 기준 수정 파일은 기존과 동일하다.

- `app.py`
- `config.ini`

변경량도 기존 기준선과 동일하다.

- 2 files changed
- 1018 insertions
- 900 deletions

### Python

확인된 Python:

- `venv\Scripts\python.exe`
- Python 3.13.7

### 문법 컴파일

다음 명령이 성공했다.

```powershell
venv\Scripts\python.exe -m py_compile app.py wsgi.py
```

결과:

- `app.py` 문법 OK
- `wsgi.py` 문법 OK

### PostgreSQL 상태

확인 결과:

- 서비스명: `postgresql-x64-17`
- 상태: Running
- StartType: Automatic
- 포트: `5432` listen 중

### 실행 중 Python 프로세스

점검 당시 실행 중인 Python/Flask 프로세스는 없었다.

## Phase 1. Flask app import-only 결과

다음 방식으로 서버를 띄우지 않고 Flask app만 import했다.

```powershell
from wsgi import app
```

결과:

- import 성공
- `rule_count = 264`
- `endpoint_count = 263`
- `app.debug = False`
- `app.testing = False`
- `SEND_FILE_MAX_AGE_DEFAULT = 31536000`

정적 분석의 라우트 수 263개와 import 결과의 rule 264개가 다른 이유는 Flask 기본 static route가 포함되기 때문으로 보인다.

## import-only 중 새로 발견한 사실

import-only 과정에서 다음 로그가 출력됐다.

- `IQADB_CONNECT310` 모듈 import 실패: `No module named 'psycopg2'`
- `partners_cache` 테이블 구조 확인 완료

이것은 중요하다.

기존 안전 계획에서는 import-only가 서버/요청 실행보다 안전하다고 봤지만, 실제로는 `app.py` import 과정에서 DB 구조 확인성 동작이 발생한다.

현재까지는 HTTP 요청이나 명시적 DB write를 실행하지 않았고, Git 상태 및 로그 파일 timestamp는 변하지 않았다. 하지만 앞으로는 import-only도 "완전 무해"가 아니라 "낮은 위험의 DB read/check 가능 단계"로 분류해야 한다.

## 핵심 페이지 라우트 확인

다음 핵심 페이지 라우트는 import된 `app.url_map`에서 확인됐다.

| URL | 결과 | endpoint |
| --- | --- | --- |
| `/` | FOUND | `index` |
| `/accident` | FOUND | `accident_route` |
| `/safety-instruction` | FOUND | `safety_instruction.safety_instruction_route` |
| `/follow-sop` | FOUND | `follow_sop.follow_sop_route` |
| `/full-process` | FOUND | `full_process.full_process_route` |
| `/safe-workplace` | FOUND | `safe_workplace.safe_workplace_route` |
| `/subcontract-approval` | FOUND | `subcontract_approval.subcontract_approval_route` |
| `/subcontract-report` | FOUND | `subcontract_report.subcontract_report_route` |
| `/partner-standards` | FOUND | `partner_standards_route` |
| `/partner-change-request` | FOUND | `partner_change_request_route` |
| `/<path:url>` | FOUND | `page_view` |

## URL drift 후보 확인 결과

서버 요청을 보내지 않고 `app.url_map.bind(...).match(...)`로 매칭만 확인했다.

| method | URL | 매칭 결과 |
| --- | --- | --- |
| GET | `/api/follow-sop/export` | `page_view`로 매칭됨 |
| GET | `/api/follow-sop-export` | `export_follow_sop_excel` |
| GET | `/api/subcontract-approval/export` | `page_view`로 매칭됨 |
| GET | `/api/subcontract-report/export` | `page_view`로 매칭됨 |
| POST | `/api/subcontract-approval/final-check` | 405 Method Not Allowed |
| POST | `/api/subcontract-report/final-check` | 405 Method Not Allowed |
| POST | `/api/subcontract-approval/delete` | `delete_items`, `board_type='subcontract-approval'` |
| POST | `/api/subcontract-report/delete` | `delete_items`, `board_type='subcontract-report'` |
| POST | `/api/accident-import` | `import_accidents` |
| POST | `/api/safety-instruction-import` | 405 Method Not Allowed |
| POST | `/api/full-process-import` | 405 Method Not Allowed |

## URL drift 결론

3단계에서 발견한 후보 중 일부는 import-only route map에서 더 강하게 확인됐다.

### 확인된 불일치

- Follow SOP export
  - 프론트 후보: `/api/follow-sop/export`
  - 실제 백엔드: `/api/follow-sop-export`
  - 현재 매칭: `page_view`

- Subcontract Approval export
  - 프론트 후보: `/api/subcontract-approval/export`
  - 실제 백엔드: 없음
  - 현재 매칭: `page_view`

- Subcontract Report export
  - 프론트 후보: `/api/subcontract-report/export`
  - 실제 백엔드: 없음
  - 현재 매칭: `page_view`

- Subcontract Approval final-check
  - 프론트 후보: `/api/subcontract-approval/final-check`
  - 실제 백엔드: 없음
  - 현재 매칭: 405

- Subcontract Report final-check
  - 프론트 후보: `/api/subcontract-report/final-check`
  - 실제 백엔드: 없음
  - 현재 매칭: 405

- Safety Instruction import
  - 화면에 `/api/accident-import` 호출 흔적
  - 안전지시서 전용 `/api/safety-instruction-import` 없음

- Full Process import
  - 화면에 `/api/accident-import` 호출 흔적
  - Full Process 전용 `/api/full-process-import` 없음

### 삭제 API

`subcontract-approval`과 `subcontract-report`의 delete는 전용 route가 없지만, 동적 route가 받는다.

- `/api/subcontract-approval/delete` -> `delete_items`
- `/api/subcontract-report/delete` -> `delete_items`

따라서 삭제는 "라우트 없음"이 아니라 "공통 동적 삭제 라우트 사용"으로 정정한다.

단, 실제 DB 삭제 동작은 백업 전 테스트 금지다.

## catch-all 확인

다음 라우트가 확인됐다.

- `GET /<path:url>` -> `page_view`

이 때문에 존재하지 않는 GET API형 URL도 `page_view`로 매칭될 수 있다.

확인 예:

- `GET /api/follow-sop/export` -> `page_view`
- `GET /api/subcontract-approval/export` -> `page_view`
- `GET /not-a-real-page` -> `page_view`

즉 GET 요청에서는 404가 아니라 `page_view` 로직으로 들어갈 수 있다. 이 부분은 브라우저/네트워크 확인 때 중요하다.

## 401 login endpoint 확인

1단계에서 의심한 `login` endpoint는 실제 `app.view_functions`에 없었다.

확인 결과:

- `login`: 없음
- 관련 endpoint 후보: `admin_login`, `sso_dev_login`

따라서 `401` 에러 핸들러의 `url_for('login', ...)`는 실제 401 일반 페이지 요청에서 추가 오류를 만들 가능성이 있다.

## 로그/파일 상태

import-only 이후 Git 상태는 변하지 않았다.

계속 보이는 수정 파일:

- `app.py`
- `config.ini`

확인한 로그 파일 timestamp도 변하지 않았다.

- `app.log`
- `app_debug.log`
- `server.log`

## 안전 계획 업데이트 필요점

`SAFE_EXECUTION_PLAN.md`의 Phase 1은 다음처럼 해석을 보정한다.

기존:

- import-only는 DB write 없이 route map만 확인하는 단계

보정:

- import-only는 서버/HTTP 요청은 없지만, app import 과정에서 DB 구조 확인성 read/check가 발생할 수 있는 단계

따라서 다음부터는 Phase 1도 "DB 백업 전 수행 가능한 최소 확인"으로는 유지하되, 완전 무해 단계로 표현하지 않는다.

## 다음 추천 단계

다음으로는 두 선택지가 있다.

### 선택 A. 브라우저 전 백업 진행

안전 원칙대로 PostgreSQL 백업과 파일 백업을 만든 뒤, WSGI 방식으로 서버를 띄우고 읽기 전용 브라우저 확인으로 넘어간다.

### 선택 B. 4단계 프론트엔드 정적 분석 진행

아직 백업 없이도 가능한 프론트엔드 정적 분석을 더 진행한다.

추천은 선택 B다.

이유:

- import-only에서도 DB 구조 확인이 발생했다.
- 아직 브라우저 테스트 전에 프론트 JS 구조를 더 읽을 수 있다.
- URL drift 후보가 이미 충분히 나왔으므로, 먼저 4단계에서 원인을 정적으로 좁히는 편이 안전하다.
