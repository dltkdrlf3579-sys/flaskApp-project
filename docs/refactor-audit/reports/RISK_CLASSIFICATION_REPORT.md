# 9단계 위험도 분류 보고서

작성일: 2026-06-13  
범위: 정적 분석 기준. 서버 실행, DB 접속, 테스트 실행, 코드 수정은 하지 않음.

## 1. 분류 기준

이 단계의 목적은 "무엇부터 손대야 안전한가"를 정하는 것이다. 지금 프로젝트는 기능 자체보다도, 예전 SQLite 출발점에서 PostgreSQL 운영 구조로 급하게 넘어오며 생긴 혼합층과 권한/라우트/마이그레이션 불일치가 더 큰 위험으로 보인다.

| 등급 | 의미 | 판단 기준 |
|---|---|---|
| P0 / 즉시 위험 | 실행 전 또는 배포 전 우선 통제 필요 | 보안, 데이터 삭제/노출, 로컬 파일 접근, 권한 우회, 실행 즉시 DB 변경 가능성 |
| P1 / 중기 위험 | 리팩터링 전에 설계 정리 필요 | 기능 불일치, PostgreSQL/SQLite 혼합, 마이그레이션 이원화, 보드별 코드 드리프트 |
| P2 / 리팩터링 후보 | 안정화 후 구조 개선 대상 | 중복 제거, 공통화, 테스트 가능성 개선, 유지보수성 향상 |

## 2. P0 / 즉시 위험

| 항목 | 관찰 | 왜 위험한가 | 우선 대응 |
|---|---|---|---|
| 비밀값/DSN 하드코딩 | `config.ini`에 PostgreSQL DSN, edit password, admin password, chatbot token 등이 있고 여러 스크립트에 `postgres:admin123` 패턴이 남아 있음 | 저장소/백업/공유 과정에서 인증정보가 노출될 수 있음 | `.env` 또는 비공개 로컬 설정으로 분리하고 예시 설정만 저장소에 둠 |
| 권한 누락 가능 API | 동적 보드 등록/수정/삭제, 동적 컬럼 변경, change-request 컬럼 API, permission request approve/reject, 다운로드/업로드 계열에서 보호가 일관되지 않음 | UI에서 막아도 API 직접 호출로 데이터 변경 가능성이 있음 | 모든 쓰기 API에 인증/권한 데코레이터 적용 기준부터 확정 |
| 삭제/복구/permanent-delete API | 보드별 삭제 API가 여러 패턴으로 존재하고 일부는 권한/감사로그/트랜잭션 기준이 불명확함 | 실수 또는 권한 우회로 데이터 손실이 발생할 수 있음 | 삭제 계열을 목록화하고 soft-delete/restore/permanent-delete 정책 통일 |
| 업로드/다운로드 경로 | `/download`, `/partner-attachments`, `/upload-inline-image`, `/api/auto-upload-partner-files`가 특히 민감함. `auto-upload`는 로컬 파일 경로를 받아 복사하고 기존 파일 삭제도 수행함 | 경로 조작, 원치 않는 파일 노출/복사/삭제 가능성이 있음 | 다운로드 권한 검증, 저장 루트 강제, 파일 확장자 축소, auto-upload 비활성 또는 관리자 전용화 |
| SSO debug/diagnostics 노출 | `/debug-session`, `/sso/diagnostics`, `/SSO?debug=1`이 세션/설정/인증서 경로/상태 정보를 드러냄 | 내부망이라도 인증 흐름과 환경정보가 노출됨 | 운영/일반 실행에서 debug 라우트 차단, 최소 관리자 전용화 |
| SSO 검증 완결성 | `/acs`에서 서명/만료는 보지만 audience 검증이 꺼져 있고 nonce mismatch가 실패가 아니라 로그 처리에 머무름 | SSO 신뢰 경계가 느슨해질 수 있음 | audience/nonce/state 실패를 명시적 거부로 바꾸는 계획 수립 |
| broad exception으로 오류 은폐 | import/init/sync/외부채점/일부 DB 작업에서 예외를 잡고 계속 진행하는 흐름이 다수 관찰됨 | 실제 오류가 조용히 묻혀 나중에 화면/데이터에서 이상 증상으로 나타남 | 최소한 P0 경로에서는 실패를 명확히 반환하고 로그 레벨/알림 기준 통일 |
| 전역 테스트/스크립트 실행 위험 | `test_*.py`와 루트 스크립트 중 상당수가 top-level에서 DB/HTTP/write를 수행할 수 있음 | `pytest` 전체 실행만으로 DB 변경/외부 호출 가능성이 있음 | 검증 전 허용 테스트 목록을 분리하고 top-level side effect 제거 |

## 3. P1 / 중기 위험

| 항목 | 관찰 | 왜 문제가 되는가 | 정리 방향 |
|---|---|---|---|
| SQLite 호환층 잔존 | `db/compat.py`가 placeholder, AUTOINCREMENT, PRAGMA, JSONB adapter 등을 두껍게 처리함 | PostgreSQL 전용으로 보이지만 내부에서는 SQLite 문법을 계속 허용해 오류 위치가 흐려짐 | 새 코드부터 PostgreSQL SQL로 고정하고 호환층 사용 범위를 축소 |
| 보드별 구현 불일치 | follow_sop/subcontract는 `DynamicBoardRepository`, full_process/safe_workplace는 forked repository, accident/safety_instruction은 별도 구조 | 같은 기능도 보드별로 버그/권한/검색/첨부 처리 방식이 다름 | 보드 유형별 차이를 config로 빼고 controller/repository 패턴을 하나로 수렴 |
| dynamic column schema 불일치 | `column_service.py`, `board_services.ColumnService`, `column_config_repository.py`가 병존하고 protected column 목록도 서로 다름 | 컬럼 추가/삭제/표시 정책이 화면마다 다르게 동작할 수 있음 | protected column, column metadata, physical/jsonb 정책의 단일 소스 확정 |
| `custom_data` 타입 오염 | JSONB dict/list와 JSON 문자열이 동시에 고려되고, 여러 곳에서 방어적으로 파싱함 | 데이터 형태가 일정하지 않아 검색/렌더링/엑셀/마이그레이션에서 깨질 수 있음 | DB 저장 타입을 JSONB object로 고정하고 boundary에서만 변환 |
| migration 체계 이원화 | `init_db()`는 numbered migration만 실행하지만 권한/감사/외부채점 등은 별도 스크립트와 런타임 DDL에 흩어짐 | 새 환경 구축 시 빠지는 테이블이 생기고 실행 순서가 불명확함 | 모든 schema 변경을 numbered migration으로 통합 |
| 루트 스크립트 난립 | 루트와 scripts/migrations 아래에 진단/수정/마이그레이션/테스트 성격 파일이 섞여 있음 | 어떤 파일이 안전한지 판단하기 어렵고 실수 실행 위험이 큼 | `scripts/maintenance`, `scripts/diagnostics`, `tests` 등으로 성격별 재배치 |
| 프론트엔드-백엔드 라우트 드리프트 | `/api/change-request-columns`, `/api/${slug}/export`, `/api/full-process/external-scoring/<number>` 등 여러 불일치가 있음 | 버튼은 있는데 API가 없거나 다른 API를 호출하는 사용자 경험 문제가 생김 | route inventory를 기준으로 템플릿/JS 호출 경로를 대조 |
| 외부채점 계열 버전 드리프트 | `scoring_external_service.py`, `v2`, `v3`가 공존하고 일부는 undefined 함수 또는 하드코딩 DSN을 가짐 | 실제 사용 경로와 최신 구현을 구분하기 어려움 | v3 기준으로 단일 진입점을 정하고 나머지는 archive/deprecated 처리 |

## 4. P2 / 리팩터링 후보

| 후보 | 현재 상태 | 추천 순서 |
|---|---|---|
| `change_request` Controller/Repository 분리 | `app.py` 내부 라우트/쿼리/컬럼 처리가 크게 남아 있음 | P0 권한 보호 후 분리 |
| `partner` 계열 분리 | 협력사/첨부/검색/상세/자동업로드가 여러 영역에 걸쳐 있음 | 파일 경로 보안 정리 후 분리 |
| export/import 공통화 | 보드별 export/import 라우트와 프론트 호출이 불일치함 | route drift 수정 후 공통화 |
| 권한 엔진 단일화 | `permission_helpers`, `permission_utils`, `login_id_permission_utils`, scoped check가 병존 | API 보호 정책 확정 직후 단일화 |
| 설정 로더 정리 | config.ini 직접 의존과 환경별 비밀값이 섞임 | secret 분리와 함께 진행 |
| SQLite 호환층 축소 | 호환층 덕분에 돌아가는 코드와 PostgreSQL 전용 코드가 섞임 | 테스트 확보 후 점진 축소 |
| 템플릿/JS 공통화 | 동적 보드 템플릿은 공통화됐지만 일부 보드 JS/URL/컬럼 정책이 다름 | route map 고정 후 진행 |
| 테스트 체계 재구성 | 기존 `test_*.py`는 pytest 테스트와 점검 스크립트가 섞임 | 리팩터링 전에 smoke/API/unit 최소 세트 작성 |

## 5. 안전한 작업 순서 제안

1. 현재 상태 백업과 DB 백업을 먼저 고정한다.
2. `config.ini`의 비밀값/DSN을 로컬 전용으로 분리한다.
3. debug/diagnostics/auto-upload/inline-upload 같은 P0 노출면을 먼저 잠근다.
4. 모든 쓰기 API와 삭제 API의 권한 정책을 하나의 표로 확정한다.
5. pytest 전체 실행 금지 상태를 유지하고, 안전한 smoke 테스트만 별도 지정한다.
6. route drift와 migration drift를 문서 기준으로 하나씩 제거한다.
7. 그 다음에야 Controller/Repository/Service 리팩터링으로 들어간다.

## 6. 이번 단계에서 하지 않은 것

- 코드 수정 없음.
- 서버 실행 없음.
- DB 접속 없음.
- 테스트 실행 없음.
- 파일 삭제/이동 없음.

## 7. 결론

현재 프로젝트의 핵심 위험은 "코드가 낡았다"보다 "기능을 급히 붙이는 동안 안전 경계가 여러 군데로 흩어졌다"에 가깝다. 따라서 대규모 리팩터링을 바로 시작하면 작년처럼 겉으로는 정리된 것처럼 보여도 실행 시점에 깨질 가능성이 높다.

우선순위는 명확하다.

1. P0 보안/삭제/업로드/권한/디버그 노출을 먼저 막는다.
2. P1 마이그레이션/라우트/DB 혼합 문제를 정리한다.
3. 그 뒤 P2 구조 리팩터링을 작은 단위로 진행한다.
