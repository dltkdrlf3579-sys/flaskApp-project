# Flask Portal 전체 감사 보고서

작성일: 2026-06-13  
범위: 코드 수정 없이 정적 분석, 기존 문서 대조, 구조 계량, 숨김 메모리 확인

## 1. 한 줄 진단

이 프로젝트는 단순한 Flask CRUD 앱이 아니라, **동적 컬럼/섹션 기반의 사내 안전·협력사 포털**로 성장한 시스템이다. 다만 초기 SQLite 기반으로 빠르게 시작한 뒤 PostgreSQL, 권한, SSO, 첨부파일, 엑셀, 신규 게시판, 리스트 서브폼이 순차적으로 얹히면서 현재는 “작동 가능한 업무 시스템 + 미완성 리팩터링 흔적 + 복구/검증 스크립트 더미”가 한 저장소에 섞인 상태다.

## 2. 사용자가 만들려던 의도

기존 문서와 코드 구조를 종합하면 원래 의도는 다음에 가깝다.

1. 협력사 기준정보, 사고, 안전지시서, Follow SOP, Full Process, Safe Workplace, 도급승인/도급신고를 관리하는 사내 포털.
2. 관리자가 게시판별 컬럼과 섹션을 동적으로 바꿀 수 있는 “노코드/로우코드형 게시판 엔진”.
3. 외부 기준정보 또는 IQADB 성격의 원천 데이터를 가져와 로컬 캐시 테이블에 적재하고, 포털에서는 캐시 기반으로 검색·상세·수정·첨부를 제공.
4. 처음에는 SQLite로 빠르게 구현했으나, 실제 사내 시스템 성격에 맞춰 PostgreSQL로 급히 전환.
5. 비밀번호 기반 수정 보호에서 메뉴/행위 권한 기반 접근 제어로 이동하려는 중간 단계.
6. 각 게시판의 복붙 구현을 줄이기 위해 Controller/Repository/Service 구조로 리팩터링하려 했지만, 모든 영역이 동일 수준으로 이전되지는 않음.

## 3. 현재 구조 요약

### 3.1 핵심 런타임 축

- `app.py`: Flask 앱 생성, Blueprint 등록, 다수의 레거시 라우트, 공통 API, SSO, 권한, 엑셀 export, 첨부, catch-all 라우팅이 모두 섞여 있는 중심 파일.
- `add_page_routes.py`: Follow SOP, Full Process, Safe Workplace, Subcontract 계열 라우트를 Blueprint로 등록하고 Controller에 위임하는 비교적 신형 구조.
- `controllers/boards/*`: 게시판별 컨트롤러. 일부는 `DynamicBoardController`를 사용하고, 일부는 개별 `BoardController` 파생 구조.
- `repositories/boards/*`: 게시판별 DB 접근과 템플릿 컨텍스트 조립 담당. 리팩터링의 핵심 산출물.
- `column_service.py`, `section_service.py`, `board_services.py`: 동적 컬럼/섹션/코드/첨부 등 공통 서비스. 다만 역할이 겹치거나 오래된 호환 코드가 남아 있음.
- `db_connection.py`, `db/compat.py`, `db/upsert.py`: PostgreSQL 연결과 SQLite API 호환층. PostgreSQL 전용을 지향하지만 SQLite 시대의 추상화가 여전히 핵심 경로에 남아 있음.

### 3.2 문서와 메모리

- `.serena/memories/project_overview.md`: 초기 프로젝트 개요. SQLite, `portal.db`, `python app.py` 중심의 과거 상태를 설명한다.
- `APP_ROUTE_REFACTOR_ANALYSIS.md`: 과거 리팩터링 분석 문서. 단일 `app.py` 문제, Blueprint/Repository 이전, PostgreSQL 전용화 계획을 다룬다.
- `COMPETENCY_EVAL_MENU_PLAN.md`: 도급승인/도급신고 추가 당시의 계획. 신규 보드를 Follow SOP 기반으로 확장하려는 의도가 보인다.
- `PERMISSION_EXPECTATION_NOTES.md`: 비밀번호 보호를 제거하고 메뉴/행위 권한으로 통합하려는 목표를 설명한다.
- `docs/accident-si-issues.md`: 사고/안전지시서 쪽 custom_data 병합, `[]` 문자열, 상세 내용 저장 문제 등 실제 운영 이슈를 기록한다.

## 4. 객관 계량

정적 분석 기준 주요 수치는 다음과 같다.

- Python 파일: 425개
- HTML 파일: 115개
- JavaScript 파일: 14개
- SQL 파일: 32개
- Markdown 파일: 23개
- `app.py`: 약 10,541줄, `@app.route` 212개, `cursor.execute` 137회, `conn.execute` 33회
- 전체 `@app.route` 사용: 300개 수준. 단, 테스트/백업/삭제 예정 파일까지 포함된 수치다.
- `app.py` 라우트 그룹: `/api` 140개, `/admin` 37개, 나머지 페이지/SSO/다운로드 라우트가 혼재.
- 테스트 파일: `test_*.py` 및 `test.py` 기준 81개. 다만 상당수는 실험/마이그레이션 검증용에 가까워 보인다.
- 민감 문자열: `admin123`은 93개 파일에서 129회, `postgresql://postgres`는 74개 파일에서 91회 발견됨.

## 5. 게시판별 성숙도

| 영역 | 현재 상태 | 진단 |
| --- | --- | --- |
| Follow SOP | Controller/Repository/Blueprint 존재 | 신형 구조에 가장 가까운 기준 보드 |
| Full Process | Controller/Repository/Blueprint 존재 | Follow SOP와 유사한 구조 |
| Safe Workplace | Controller/Repository/Blueprint 존재 | 신형 구조이나 설정 누락/불균형 가능성 있음 |
| Subcontract Approval/Report | 공통 Subcontract Controller/Repository 존재 | 신규 보드 확장 흔적, 비교적 구조적 |
| Safety Instruction | Controller/Repository/Blueprint 존재 | 별도 구현이 많고 사고 보드와 얽힘 |
| Accident | Controller/Repository 존재하지만 `app.py` 레거시 라우트도 큼 | 사고 관련 직접 SQL, custom_data 이슈, export/import가 복잡 |
| Change Request | 별도 Controller/Repository 쌍 없음 | 아직 `app.py` 중심 레거시 영역 |
| Partner | 별도 Repository 계층 미흡 | 협력사 기준정보, 변경요청, 사고 연결이 `app.py`에 많이 남아 있음 |

## 6. 핵심 문제점

### 6.1 `app.py`가 여전히 너무 많은 책임을 가진다

과거보다 줄어든 흔적은 있지만, `app.py`는 아직 앱 초기화, 라우팅, DB 쿼리, 권한, SSO, export/import, 파일 다운로드, 관리자 API, catch-all 라우팅을 동시에 담당한다. 이 구조에서는 작은 기능 수정도 예상 밖의 영역을 건드릴 가능성이 높다.

특히 `/api/<board>/columns`, `/api/<board>/items` 같은 공통 API가 이미 존재하는데, 동시에 보드별 API도 많이 남아 있어 “새 표준과 옛 표준이 공존”한다.

### 6.2 SQLite에서 PostgreSQL로 넘어간 과도기 코드가 남아 있다

`db_connection.py`는 PostgreSQL만 허용하도록 바뀌었지만, 실제 하위 계층에는 SQLite 호환 코드가 많다.

- `db/compat.py`: `PRAGMA`, `AUTOINCREMENT`, placeholder 변환, SQLite row 호환을 담당.
- `db/upsert.py`: PostgreSQL `ON CONFLICT`와 SQLite `INSERT OR REPLACE`를 동시에 지원.
- `column_service.py`, `board_services.py`, 일부 repository: `sqlite3.Row`, `PRAGMA`, SQLite식 DDL 호환 흔적이 남아 있음.

이 호환층은 급한 마이그레이션 당시에는 생존 장치였지만, 지금은 버그 원인을 감추는 층이 될 수 있다. 단, 한 번에 제거하면 위험하다.

### 6.3 설정과 비밀값이 코드/스크립트에 퍼져 있다

`config.ini`에는 다음 성격의 값이 평문으로 존재한다.

- Flask secret key placeholder
- 관리자/수정 비밀번호
- PostgreSQL DSN

또한 분석/마이그레이션/테스트 스크립트 다수에 `postgres:admin123` 또는 로컬 DSN이 직접 박혀 있다. 현재 노트북 개발환경이라고 해도, 장기적으로는 `.env`, 로컬 전용 config, 샘플 config 분리가 필요하다.

### 6.4 권한 시스템이 전환 중이다

문서상 목표는 비밀번호 기반 보호 제거 후 메뉴/행위 권한으로 통일하는 것이다. 실제 코드에는 다음이 공존한다.

- `permission_helpers.py`의 메뉴 권한 매핑과 `enforce_permission`
- `permission_api.py`의 관리 API
- `scoped_permission_check.py`, `permission_utils.py`, `login_id_permission_utils.py` 등 별도 권한 관련 모듈
- `/verify-password` 및 password modal 기반 보호

즉 “권한 통합 방향”은 맞지만, 최종 권한 엔진이 하나로 정리되지는 않은 상태다.

### 6.5 동적 컬럼/섹션 시스템은 강력하지만 복잡하다

이 프로젝트의 핵심 경쟁력은 게시판 컬럼과 섹션을 관리자 UI에서 바꾸는 기능이다. 하지만 이 기능 때문에 다음 복잡도가 생겼다.

- 컬럼 정의 테이블과 실제 데이터 테이블 간 동기화
- `custom_data` JSONB 병합 정책
- list 타입 필드의 child schema 전환
- popup 기반 linked field 처리
- 동적 컬럼 export/import
- 섹션별 렌더링 순서
- 시스템 보호 컬럼 편집/삭제 방지

이 영역은 기능 가치가 크므로 제거 대상이 아니라 “표준화 대상”이다.

### 6.6 실제 잠재 오류 후보가 보인다

정적 분석 중 `board_services.py`에서 `existing_columns`를 정의하기 전에 참조하는 흐름이 보인다. 문법 오류는 아니지만 해당 경로가 실행되면 `NameError`가 날 가능성이 있다.

또한 `app.py`에는 여전히 많은 `print`, 넓은 `except Exception`, `pass`가 남아 있어 장애가 조용히 묻히거나 로그가 과도하게 섞일 수 있다.

### 6.7 백업/실험/운영 파일이 루트에 섞여 있다

루트에는 `check_*`, `fix_*`, `verify_*`, `test_*`, `COMPLETE_MIGRATION*`, `FINAL_*`, `RUN_THIS_ON_PRODUCTION.py` 같은 파일이 많다. 이들은 당시 문제를 해결하는 데 유용했지만, 지금은 “무엇이 현재 정식 경로인지” 판단을 어렵게 한다.

## 7. 위험도 분류

### 즉시 위험

1. 평문 비밀번호/DSN 확산.
2. `app.py`의 export/import/삭제/복구 API가 커지고 직접 SQL이 많음.
3. 권한 전환 중 상태로 인해 어떤 라우트는 메뉴 권한, 어떤 라우트는 비밀번호, 어떤 API는 직접 체크를 쓸 가능성.
4. `change_request`와 `partner` 계열이 아직 신형 구조로 분리되지 않음.

### 중기 위험

1. SQLite 호환층이 PostgreSQL 문제를 감추거나 변환 중 예외 케이스를 만들 수 있음.
2. 동적 컬럼 정의와 실제 JSONB 데이터의 불일치가 누적될 수 있음.
3. 복구/마이그레이션 스크립트가 너무 많아 잘못된 스크립트를 실행할 위험.
4. 문서 일부가 오래되었거나 인코딩이 깨져 보여 유지보수성이 떨어짐.

### 낮은 위험이지만 정리 필요

1. 오래된 백업 HTML, 백업 Python, `deletelist`, `needtodevelop` 문서 정리.
2. 테스트 파일의 성격 분류.
3. 루트의 임시 출력물, 로그, 샘플 HTML 분리.

## 8. 좋은 점

나쁜 점만 있는 프로젝트는 아니다. 오히려 중요한 기반은 이미 있다.

- Controller/Repository 구조가 이미 일부 보드에 적용되어 있다.
- `DynamicBoardController`라는 공통화 방향이 존재한다.
- `ColumnConfigService`, `SectionConfigService`, `SearchPopupService`, `UploadValidator` 같은 분리 시도가 있다.
- `migrations/001~005_*.sql`로 핵심 마이그레이션을 정리하려는 시도가 있다.
- 권한, 감사 로그, 메뉴 필터링, SSO, 알림 등 사내 포털로 필요한 기능을 고려했다.
- 사고/안전지시서 문제처럼 실제 운영 이슈를 문서로 남긴 흔적이 있다.

즉 “처음부터 다시 만들기”보다 “현재 작동 상태를 기준선으로 고정하고, 위험 영역부터 작게 안정화”하는 편이 맞다.

## 9. 앞으로의 분석/정리 전략

대규모 리팩터링은 금지하는 것이 좋다. 이 프로젝트는 기능 면적이 넓고 동적 데이터 구조가 많아서, 한 번에 구조를 바꾸면 예전처럼 실행 시점에 터질 가능성이 높다.

권장 순서는 다음과 같다.

### Phase 0. 기준선 고정

- 현재 서버 실행 방법 확인.
- 로컬 PostgreSQL 연결 확인.
- 핵심 화면 접속 체크리스트 작성.
- 현재 수정 중인 `app.py`, `config.ini` diff를 보존.
- 어떤 테스트가 현재 신뢰 가능한지 분류.

### Phase 1. 문서 최신화

- `PROJECT_OVERVIEW.md` 최신 작성.
- `STABILIZATION_PLAN.md` 작성.
- “현재 정식 파일 / 백업 파일 / 실험 파일 / 삭제 후보” 목록 작성.
- 보드별 구조 상태표 작성.

### Phase 2. 설정 안정화

- `config.ini`에서 비밀값을 `.env` 또는 로컬 비공개 설정으로 분리.
- `config.ini.example` 또는 `config.ini.template` 정리.
- 보조 스크립트의 하드코딩 DSN을 공통 설정 로더로 변경.

### Phase 3. 보드별 소규모 안정화

- `change_request`부터 Controller/Repository 후보로 분리 검토.
- `partner` 계열은 기준정보/변경요청/사고 연결을 분리해 분석.
- `accident`는 custom_data 병합 정책과 export/import를 먼저 테스트로 고정.
- Follow SOP 계열은 신형 구조의 기준점으로 삼는다.

### Phase 4. 호환층 축소

- SQLite 호환 제거는 마지막에 한다.
- 먼저 PostgreSQL 전용 쿼리와 DDL이 모든 핵심 경로에서 통과하는지 확인.
- `CompatConnection` 제거 여부는 별도 실험 브랜치에서만 검토.

## 10. 다음 액션 제안

코드 수정 없이 이어갈 수 있는 다음 작업은 세 가지다.

1. **실행 기준선 문서 작성**
   - 서버 실행, DB 연결, SSO dev-login, 주요 메뉴 URL, 확인 순서 정리.

2. **보드별 상태 매트릭스 작성**
   - 각 게시판의 라우트, 템플릿, 컨트롤러, 레포지토리, API, 권한 코드, DB 테이블을 한 표로 정리.

3. **정식/임시 파일 분류**
   - 루트의 `fix_*`, `check_*`, `verify_*`, `test_*`, `FINAL_*`, `backup`, `deletelist`를 “현재 사용/참고/보관/삭제 후보”로 분류.

가장 추천하는 다음 단계는 2번이다. 보드별 매트릭스가 있어야 이후 어떤 수정이 어떤 화면을 건드리는지 예측할 수 있다.

## 11. 이번 분석에서 하지 않은 것

- 코드 수정 없음.
- DB 접속 없음.
- Flask 서버 실행 없음.
- 브라우저 화면 검증 없음.
- 테스트 전체 실행 없음.

이번 보고서는 정적 분석과 문서 대조에 기반한 1차 감사 보고서다. 다음 단계에서는 실제 실행 기준선을 잡아야 한다.
