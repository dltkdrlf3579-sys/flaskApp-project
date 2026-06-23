# 운영 안정화 계획

작성일: 2026-06-13  
범위: 사내 웹사이트 기준의 안정화 계획. 외부 서비스 수준의 보안 강화는 이번 계획의 주목표가 아님.

## 1. 목표

이 계획의 목표는 리팩터링 전에 프로젝트를 “안전하게 실행하고, 작은 단위로 고치고, 고친 뒤 확인할 수 있는 상태”로 만드는 것이다.

핵심은 보안 대공사가 아니라 운영 사고 방지다.

- 버튼을 눌렀는데 API가 없어서 깨지는 문제를 줄인다.
- 새 환경에서 DB 테이블이 빠지는 문제를 줄인다.
- import/export/delete/upload 같은 데이터 영향 기능을 예측 가능하게 만든다.
- `pytest`나 임시 스크립트 실행으로 DB가 바뀌는 사고를 막는다.
- 이후 리팩터링을 작게 나눠서 진행할 수 있게 한다.

## 2. 작업 원칙

- 코드 수정 전에는 관련 `.md` 분석 문서를 다시 읽는다.
- `app.py` 대규모 분리는 가장 나중에 한다.
- 한 번에 여러 게시판을 고치지 않는다.
- 전체 테스트 실행 대신 안전하다고 분류된 테스트부터 사용한다.
- DB에 쓰기 작업을 하기 전에는 백업 계획을 먼저 확인한다.
- 보안 강화가 아니라 운영 안정화에 필요한 최소 보호만 적용한다.

## 3. Phase 0: 현상 보존

목표: 현재 상태를 잃지 않는다.

작업:

- 현재 `app.py`, `config.ini`의 사용자 변경 상태를 보존한다.
- PostgreSQL DB 백업 절차를 문서화한다.
- 업로드 파일 저장 폴더를 확인하고 백업 대상에 포함한다.
- 현재 실행 가능한 명령과 실행하면 안 되는 명령을 분리한다.

완료 조건:

- DB 백업 명령이 확정되어 있다.
- 업로드 파일 백업 위치가 확정되어 있다.
- `SAFE_EXECUTION_PLAN.md` 기준으로 실행 전 체크리스트가 준비되어 있다.

관련 문서:

- `SAFE_EXECUTION_PLAN.md`
- `PREFLIGHT_EXECUTION_REPORT.md`
- `BASELINE_REPORT.md`

## 4. Phase 1: 안전 검증 루틴 확정

목표: 고치기 전에 “깨졌는지 확인하는 최소 방법”을 만든다.

작업:

- `pytest` 전체 실행 금지를 유지한다.
- 순수 문법 확인, import-only 확인, route count 확인을 안전 검증으로 둔다.
- DB write 가능성이 있는 테스트와 스크립트는 별도 격리한다.
- 브라우저 검증은 읽기 화면 중심으로 시작한다.

권장 안전 검증:

- Python 문법 컴파일.
- WSGI import-only.
- route map 출력.
- 특정 GET 화면 접속.
- 특정 API의 존재 여부 확인.

피해야 할 검증:

- 전체 `pytest`.
- 이름만 `test_`인 임시 DB 수정 스크립트 실행.
- import/export/delete/upload 쓰기 테스트를 백업 없이 실행.

완료 조건:

- “안전 실행 가능” 명령 목록이 문서화되어 있다.
- “승인 필요” 명령 목록이 문서화되어 있다.
- 최소 smoke test 후보가 정리되어 있다.

관련 문서:

- `TEST_ASSET_REPORT.md`
- `SAFE_EXECUTION_PLAN.md`

## 5. Phase 2: 프론트-API 불일치 수정

목표: 사용자가 실제로 누르는 기능이 백엔드와 맞게 한다.

우선 대상:

1. change-request 컬럼 API 경로.
2. 403/error 화면의 login/permission request 경로.
3. 보드별 export API 경로.
4. final-check API가 없는 보드의 버튼/호출 정리.
5. 잘못된 import API를 공유하는 보드 템플릿.
6. 외부채점 JS와 실제 백엔드 API 연결.

작업 방식:

- 한 번에 하나의 화면 또는 하나의 API family만 수정한다.
- 수정 전 `ROUTE_MAP_REPORT.md`와 `FRONTEND_CONNECTION_REPORT.md`를 확인한다.
- 수정 후 route 존재 여부와 화면 버튼 동작만 확인한다.
- 이 단계에서는 큰 구조 변경을 하지 않는다.

완료 조건:

- 템플릿/JS에서 호출하는 주요 API가 실제 route map에 존재한다.
- 존재하지 않는 API 호출이 문서상 제거 또는 보류 처리되어 있다.
- 사용자가 누르는 주요 버튼의 404 가능성이 줄어든다.

관련 문서:

- `ROUTE_MAP_REPORT.md`
- `FRONTEND_CONNECTION_REPORT.md`
- `BOARD_FLOW_REPORT.md`

## 6. Phase 3: DB와 마이그레이션 정리

목표: 새 DB나 새 PC에서 빠지는 테이블/컬럼을 줄인다.

우선 대상:

- `init_db()`가 실행하는 numbered migration.
- 별도 setup script로만 만들어지는 테이블.
- 런타임에 생성되는 테이블/컬럼.
- PostgreSQL 환경에서 SQLite 문법이 남아 있는 쿼리.

작업 방식:

- 바로 migration을 실행하지 않는다.
- 먼저 “현재 DB schema”와 “코드가 기대하는 schema”를 비교한다.
- 누락 테이블은 numbered migration 후보로 정리한다.
- 런타임 DDL은 즉시 제거하지 말고 migration 이전 후보로 분류한다.

완료 조건:

- 신규 환경 구축에 필요한 schema 생성 순서가 하나로 정리된다.
- setup script와 numbered migration의 역할이 분리된다.
- PostgreSQL에서 실패할 가능성이 높은 SQLite 문법 후보가 줄어든다.

관련 문서:

- `DB_USAGE_MAP.md`
- `RUNTIME_ENTRY_REPORT.md`

## 7. Phase 4: 게시판별 구조 정리

목표: 보드별로 같은 기능이 다르게 동작하는 문제를 줄인다.

권장 순서:

1. `follow_sop`과 `subcontract` 계열의 동적 보드 흐름 확인.
2. `full_process`와 `safe_workplace`의 forked Repository 비교.
3. `accident`와 `safety_instruction`의 독자 흐름 정리.
4. `change_request`와 `partner`는 별도 분리 대상으로 유지.

작업 방식:

- 게시판 하나씩 진행한다.
- CRUD, 검색, 첨부, export/import, final-check를 같은 표로 비교한다.
- 공통화는 기능 검증이 되는 범위에서만 진행한다.

완료 조건:

- 각 보드가 어느 Controller/Repository/Service를 쓰는지 명확하다.
- 공통화 가능한 부분과 그대로 둘 부분이 구분되어 있다.
- 보드 하나를 고쳤을 때 다른 보드가 깨질 가능성이 줄어든다.

관련 문서:

- `BOARD_FLOW_REPORT.md`
- `SERVICE_COMMON_REPORT.md`

## 8. Phase 5: 작은 리팩터링

목표: 안정화된 부분부터 작은 단위로 구조를 정리한다.

추천 순서:

1. route drift 수정.
2. export/import 공통 helper 정리.
3. 컬럼 protected policy 단일화.
4. `change_request` 일부 route 분리.
5. `partner` 첨부/검색 흐름 분리.
6. 중복 Repository 비교 후 병합.

금지할 것:

- 검증 루틴 없이 대규모 파일 이동.
- `app.py` 전체를 한 번에 쪼개기.
- 사용하지 않는다고 추정한 파일을 바로 삭제.
- 보드 여러 개를 동시에 리팩터링.

완료 조건:

- 각 리팩터링마다 변경 파일과 검증 방법이 작다.
- 실패하면 되돌릴 수 있는 단위로 나뉘어 있다.
- 기존 사용 흐름이 유지된다.

## 9. Phase 6: 내부망 기준 최소 안전장치

목표: 보안 대공사가 아니라 운영 사고를 막기 위한 최소 장치만 둔다.

이번 계획에서 후순위인 것:

- SSO 전체 재설계.
- CSRF 전체 도입.
- 권한 엔진 전면 재작성.
- 외부 공격 대응 수준의 보안 강화.

그래도 최소 확인할 것:

- 삭제/복구/permanent-delete는 실수 방지와 로그 기준을 확인한다.
- upload/download는 저장 루트 밖으로 나가지 않는지만 확인한다.
- debug/diagnostics 화면은 운영 중 노출 필요성이 있는지 확인한다.
- 데이터 변경 API는 내부 사용자라도 오동작을 줄일 최소 기준만 둔다.

완료 조건:

- 사내 운영에 필요한 수준의 사고 방지선만 정리되어 있다.
- 과한 보안 작업으로 코드 복잡도를 늘리지 않는다.

## 10. 당장 다음에 할 일

가장 현실적인 다음 작업 순서는 다음과 같다.

1. DB와 업로드 파일 백업 방법을 실제 명령으로 확정한다.
2. 안전 검증 명령 목록을 만든다.
3. 프론트-API 불일치 중 404가 확실한 것부터 하나씩 고친다.
4. 변경마다 화면/route 단위로 검증한다.
5. 그 다음 migration 누락을 정리한다.
6. 이후 보드별 리팩터링으로 들어간다.

## 11. 최종 결론

지금 필요한 것은 “새로 만들기”가 아니라 “작년의 시행착오를 보존하면서 망가지지 않게 정리하기”다.

따라서 다음 코드 수정은 큰 구조 변경이 아니라, 작고 확인 가능한 안정화 작업부터 시작해야 한다.

