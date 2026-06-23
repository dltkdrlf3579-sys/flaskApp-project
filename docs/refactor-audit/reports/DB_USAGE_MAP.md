# DB와 데이터 흐름 분석 보고서

작성일: 2026-06-13  
범위: DB 연결층, 마이그레이션, 게시판별 테이블, `custom_data`/JSONB 흐름  
원칙: 코드 수정 없음, DB 접속 없음, 서버 실행 없음, 정적 분석만 수행

## 0. 사전 기준

이번 단계 전에 다음 문서를 다시 확인했다.

- `BASELINE_REPORT.md`
- `RUNTIME_ENTRY_REPORT.md`
- `ROUTE_MAP_REPORT.md`
- `BOARD_FLOW_REPORT.md`
- `SAFE_EXECUTION_PLAN.md`
- `PREFLIGHT_EXECUTION_REPORT.md`
- `FRONTEND_CONNECTION_REPORT.md`
- `ANALYSIS_CHECKLIST.md`

이번 단계에서는 PostgreSQL 접속, `pg_dump`, Flask 서버 실행, 브라우저 테스트를 하지 않았다.

## 1. DB 연결 계층

### 1.1 현재 공식 연결入口

공식 연결入口는 `db_connection.py`다.

- `get_db_connection()`은 `config.ini`를 읽고 `DATABASE.db_backend`가 `postgres`인지 강제 확인한다.
- `postgres_dsn`이 비어 있으면 예외를 발생시킨다.
- 실제 연결 객체는 `db.compat.CompatConnection(backend='postgres', dsn=...)`이다.
- `DatabaseConnection`, `DatabaseContextManager`는 기존 코드 호환용 wrapper다.

근거:

- `db_connection.py:20`
- `db_connection.py:33`
- `db_connection.py:44`
- `db_connection.py:60`
- `db_connection.py:105`

판단:

- 설정상 목표는 “PostgreSQL 전용”으로 바뀌었다.
- 하지만 코드 호환을 위해 함수 시그니처에는 여전히 `db_path`, `local_db_path`, `row_factory`, `sqlite3.Row` 개념이 남아 있다.

### 1.2 `database_config.py`

`database_config.py`는 단순 설정 파일이 아니라, 외부 DB 동기화와 로컬 캐시/콘텐츠 동기화 로직까지 포함한다.

- `DatabaseConfig.get_connection()`은 PostgreSQL 연결을 반환한다.
- `get_sqlite_connection()`도 이름만 SQLite이고 실제로는 PostgreSQL 연결을 반환한다.
- `partner_manager = PartnerDataManager()`가 전역 생성된다.
- `maybe_daily_sync`, `maybe_daily_sync_master`, `maybe_one_time_sync_content`가 sync 상태 테이블을 만들고 외부 쿼리 기반 데이터를 적재한다.

근거:

- `database_config.py:2206`
- `database_config.py:2213`
- `database_config.py:2217`
- `database_config.py:2226`
- `database_config.py:2227`
- `database_config.py:2229`
- `database_config.py:2365`
- `database_config.py:2387`
- `database_config.py:2489`

판단:

- 이름만 보면 설정 계층처럼 보이지만 실제로는 “동기화 서비스 + DB 초기화 보조 + 레거시 호환”이 섞인 큰 모듈이다.
- 나중에 리팩터링한다면 설정 로더, 외부 sync, 캐시 적재, 콘텐츠 적재를 분리하는 것이 안전하다.

### 1.3 SQLite 호환 어댑터

`db/compat.py`는 PostgreSQL 위에서 SQLite 스타일 코드를 최대한 계속 돌리기 위한 두꺼운 호환층이다.

주요 기능:

- psycopg3 우선, 없으면 psycopg2 fallback
- PostgreSQL 연결에 `dict_row` 또는 `RealDictCursor` 적용
- `?` placeholder를 `%s`로 변환
- `DATETIME`, `AUTOINCREMENT`, `datetime('now')` 등 일부 SQLite SQL을 PostgreSQL 문법으로 변환
- `PRAGMA table_info(...)`를 `information_schema.columns` 조회로 에뮬레이션
- dict/list 파라미터를 JSONB 어댑터로 변환
- `cursor.lastrowid`를 `RETURNING id`로 에뮬레이션

근거:

- `db/compat.py:76`
- `db/compat.py:89`
- `db/compat.py:153`
- `db/compat.py:210`
- `db/compat.py:264`
- `db/compat.py:364`
- `db/compat.py:434`

판단:

- 이 호환층 덕분에 레거시 SQLite 코드가 많이 살아남을 수 있었다.
- 반대로 말하면, 실제 쿼리의 PostgreSQL 정합성이 호환층에 강하게 의존한다.
- `PRAGMA table_info`는 처리하지만, 모든 SQLite 시스템 테이블/함수를 처리하는 것은 아니다.

### 1.4 UPSERT 계층

`db/upsert.py`는 `INSERT OR REPLACE`를 PostgreSQL `ON CONFLICT`로 대체하기 위한 유틸리티다.

- 테이블별 conflict key와 update column registry가 있다.
- PostgreSQL이면 `_upsert_postgresql()`로 `ON CONFLICT` SQL을 만든다.
- SQLite이면 `_upsert_sqlite()`로 `INSERT OR REPLACE`를 쓴다.
- registry에는 동적 게시판 main/detail/cache/sync 테이블이 다수 등록되어 있다.

근거:

- `db/upsert.py:11`
- `db/upsert.py:131`
- `db/upsert.py:169`
- `db/upsert.py:221`

주의:

- registry에 `fullprocess_details`는 있으나 `full_process_details` 이름은 보이지 않는다.
- 실제 `full_process` 계열 코드가 detail upsert 시 명시 conflict/update cols를 넘기는지 계속 확인이 필요하다.
- registry fallback은 conflict key를 `id`로 잡으므로, unknown table에서 `id`가 없으면 실패할 수 있다.

## 2. 자동 마이그레이션 구조

### 2.1 앱 시작 시 실행 흐름

`app.py`의 `init_db()`는 `migrations.run_migrations.run_migrations()`를 호출한다.

근거:

- `app.py:505`
- `app.py:509`
- `app.py:510`

`run_migrations.py`는 `migrations` 폴더에서 이름이 `001_*.sql`, `002_*.sql`처럼 세 자리 숫자로 시작하는 SQL만 실행한다.

근거:

- `migrations/run_migrations.py:23`
- `migrations/run_migrations.py:25`
- `migrations/run_migrations.py:44`
- `migrations/run_migrations.py:50`

판단:

- 자동 실행 대상은 번호 붙은 SQL뿐이다.
- `add_dropdown_audit_log.sql`, `add_dropdown_code_mapping.sql`, `add_partner_attachment_columns.sql` 같은 비번호 SQL은 자동 실행되지 않는다.
- `migration_scripts/`와 루트의 `FINAL_*`, `COMPLETE_*`류 스크립트도 자동 실행 경로가 아니다.

### 2.2 번호 SQL 역할

자동 마이그레이션 대상은 현재 5개다.

#### `001_create_core_tables.sql`

생성 테이블:

- `pages`
- `dropdown_option_codes_v2`
- `section_config`
- `accident_column_config`
- `safety_instruction_column_config`
- `follow_sop_column_config`
- `full_process_column_config`
- `partner_standards_column_config`
- `safe_workplace`
- `safe_workplace_sections`
- `safe_workplace_details`

근거:

- `migrations/001_create_core_tables.sql:6`
- `migrations/001_create_core_tables.sql:14`
- `migrations/001_create_core_tables.sql:31`
- `migrations/001_create_core_tables.sql:45`
- `migrations/001_create_core_tables.sql:57`
- `migrations/001_create_core_tables.sql:72`
- `migrations/001_create_core_tables.sql:88`
- `migrations/001_create_core_tables.sql:104`
- `migrations/001_create_core_tables.sql:117`

#### `002_create_board_tables.sql`

생성 테이블:

- `safety_instructions`
- `safety_instruction_details`
- `safety_instruction_sections`
- `follow_sop`
- `follow_sop_sections`
- `follow_sop_details`
- `full_process`
- `full_process_details`
- `full_process_sections`

근거:

- `migrations/002_create_board_tables.sql:6`
- `migrations/002_create_board_tables.sql:37`
- `migrations/002_create_board_tables.sql:44`
- `migrations/002_create_board_tables.sql:54`
- `migrations/002_create_board_tables.sql:64`
- `migrations/002_create_board_tables.sql:73`
- `migrations/002_create_board_tables.sql:81`

#### `003_seed_sections.sql`

초기 섹션 데이터를 넣는다.

- `section_config`
- `follow_sop_sections`
- `safe_workplace_sections`

근거:

- `migrations/003_seed_sections.sql:5`
- `migrations/003_seed_sections.sql:25`
- `migrations/003_seed_sections.sql:36`

#### `004_create_attachments.sql`

공통 첨부 테이블을 만든다.

- `attachments`

근거:

- `migrations/004_create_attachments.sql:4`
- `migrations/004_create_attachments.sql:19`

#### `005_create_subcontract_tables.sql`

도급승인/도급신고 게시판 테이블을 만든다.

- `subcontract_approval`
- `subcontract_approval_sections`
- `subcontract_approval_details`
- `subcontract_approval_column_config`
- `subcontract_approval_cache`
- `subcontract_report`
- `subcontract_report_sections`
- `subcontract_report_details`
- `subcontract_report_column_config`
- `subcontract_report_cache`

근거:

- `migrations/005_create_subcontract_tables.sql:5`
- `migrations/005_create_subcontract_tables.sql:16`
- `migrations/005_create_subcontract_tables.sql:26`
- `migrations/005_create_subcontract_tables.sql:34`
- `migrations/005_create_subcontract_tables.sql:51`
- `migrations/005_create_subcontract_tables.sql:65`
- `migrations/005_create_subcontract_tables.sql:76`
- `migrations/005_create_subcontract_tables.sql:86`
- `migrations/005_create_subcontract_tables.sql:94`
- `migrations/005_create_subcontract_tables.sql:111`

### 2.3 자동 생성되지 않는 중요 테이블 후보

다음 테이블들은 런타임에서 사용 흔적이 있지만, 번호 SQL 자동 마이그레이션에는 보이지 않는다.

- `permission_requests`
- `user_menu_permissions`
- `dept_menu_roles`
- `menu_names`
- `permission_levels`
- `access_audit_log`
- `user_access_logs`
- `dropdown_code_audit`
- `external_scoring_table`
- `system_users`
- `system_roles`
- `user_role_mapping`
- `role_menu_permissions`

별도 생성 스크립트는 존재한다.

- `scripts/setup_permission_schema.py`
- `create_permission_tables.py`
- `create_access_log_table.py`
- `migrations/add_dropdown_audit_log.sql`
- `setup_external_scoring.py`

근거:

- `scripts/setup_permission_schema.py:53`
- `scripts/setup_permission_schema.py:100`
- `scripts/setup_permission_schema.py:150`
- `scripts/setup_permission_schema.py:194`
- `scripts/setup_permission_schema.py:216`
- `scripts/setup_permission_schema.py:252`
- `create_permission_tables.py:32`
- `create_permission_tables.py:56`
- `create_permission_tables.py:67`
- `create_permission_tables.py:95`
- `access_log_helper.py:31`
- `migrations/add_dropdown_audit_log.sql:4`
- `setup_external_scoring.py:34`

판단:

- 현재 자동 마이그레이션 체계만으로는 앱 전체가 요구하는 모든 테이블이 보장되지 않는다.
- 실제 로컬 DB에는 과거 수동 스크립트 실행으로 이미 존재할 수 있다.
- 하지만 새 환경/운영 재설치에서는 누락 가능성이 높다.

## 3. 게시판별 테이블 지도

### 3.1 공통 보드 설정

`repositories/common/board_config.py`가 동적 게시판의 공식 매핑에 가깝다.

근거:

- `repositories/common/board_config.py:18`
- `repositories/common/board_config.py:23`
- `repositories/common/board_config.py:31`
- `repositories/common/board_config.py:39`
- `repositories/common/board_config.py:47`
- `repositories/common/board_config.py:64`
- `repositories/common/board_config.py:80`
- `repositories/common/board_config.py:96`
- `repositories/common/board_config.py:113`

### 3.2 보드별 현황

| 보드 | 메인/캐시 | 컬럼 설정 | 섹션 | 상세 | 비고 |
|---|---|---|---|---|---|
| `partner` | `partners_cache`, `partners`, `partner_standards_cache` 등 혼재 | `partner_standards_column_config` | 불명확 | `partner_details` | legacy 중심 |
| `change_request` | `change_requests`, `partner_change_requests` | `change_request_column_config` | `section_config` | `change_request_details` | API URL drift 있음 |
| `accident` | `accidents_cache`, 일부 `accidents` | `accident_column_config` | `section_config` 또는 `accident_sections` fallback | `accident_details` | K사고 원본 + custom_data 병합 |
| `safety_instruction` | `safety_instructions` | `safety_instruction_column_config` | `safety_instruction_sections`, fallback `section_config` | `safety_instruction_details` | 일부 정적 컬럼 + JSONB |
| `follow_sop` | `follow_sop`, 후보 `follow_sop_cache`, `followsop_cache` | `follow_sop_column_config` | `follow_sop_sections` | `follow_sop_details` | table 후보 fallback 존재 |
| `full_process` | `full_process`, 후보 `full_process_cache`, `fullprocess_cache` | `full_process_column_config` | `full_process_sections` | `full_process_details` | 외부 scoring 후보 |
| `safe_workplace` | `safe_workplace`, 후보 `safe_workplace_cache` | `safe_workplace_column_config` | `safe_workplace_sections` | `safe_workplace_details` | `board_config`에는 세부 테이블 누락 |
| `subcontract_approval` | `subcontract_approval`, `subcontract_approval_cache` | `subcontract_approval_column_config` | `subcontract_approval_sections` | `subcontract_approval_details` | JSONB-only 보드 |
| `subcontract_report` | `subcontract_report`, `subcontract_report_cache` | `subcontract_report_column_config` | `subcontract_report_sections` | `subcontract_report_details` | JSONB-only 보드 |

### 3.3 `safe_workplace` 설정 분산

`board_config.py`에서 `safe_workplace`는 `cache_table`, `column_table`, `upload_path`만 가진다.

근거:

- `repositories/common/board_config.py:109`
- `repositories/common/board_config.py:113`
- `repositories/common/board_config.py:114`

하지만 `SafeWorkplaceRepository`는 자체적으로 다음 후보를 사용한다.

- `safe_workplace`
- `safe_workplace_cache`
- `safe_workplace_sections`
- `safe_workplace_details`

근거:

- `repositories/boards/safe_workplace_repository.py:117`
- `repositories/boards/safe_workplace_repository.py:173`

판단:

- 설정과 구현이 분산되어 있다.
- 이후 공통화 시 `safe_workplace`도 `board_config.py`에 `primary_table`, `section_table`, `detail_table`, `identifier_column`을 명시하는 편이 안전하다.

## 4. `custom_data` / JSONB 저장 흐름

### 4.1 기본 방향

현대화된 게시판들은 대부분 `custom_data`에 동적 필드를 저장한다.

- `BoardForm`이 프론트에서 동적 필드를 수집한다.
- 백엔드는 `custom_data` JSON을 파싱한다.
- PostgreSQL에서는 dict/list 파라미터가 `db/compat.py`의 JSONB adapter로 전달될 수 있다.
- 일부 코드는 명시적으로 `json.dumps()` 문자열을 저장한다.

근거:

- `static/js/board-form.js:74`
- `static/js/board-form.js:482`
- `db/compat.py:264`
- `db/compat.py:270`
- `repositories/boards/follow_sop_repository.py:1009`
- `repositories/boards/follow_sop_repository.py:1075`
- `repositories/boards/safety_instruction_repository.py:259`
- `repositories/boards/safety_instruction_repository.py:1053`

판단:

- DB에는 JSONB로 들어가는 경로와 JSON 문자열로 들어가는 경로가 섞여 있다.
- 조회 시 dict이면 그대로 쓰고, 문자열이면 `json.loads()` 하는 방어 코드가 많다.

### 4.2 `subcontract_*`는 JSONB-only

`column_service.py`는 다음 보드를 JSONB-only로 취급한다.

- `subcontract_report`
- `subcontract_approval`

근거:

- `column_service.py:18`
- `column_service.py:533`
- `column_service.py:534`
- `column_service.py:560`

의미:

- 이 두 보드는 관리자에서 새 컬럼을 추가해도 실제 메인 테이블에 물리 컬럼을 추가하지 않는다.
- 동적 값은 `custom_data`에만 저장된다.
- 이 설계는 깔끔하지만 export/search/final-check가 반드시 JSONB 접근을 알아야 한다.

### 4.3 다른 보드는 물리 컬럼 추가 시도

`column_service.py`는 JSONB-only가 아닌 보드에서는 동적 컬럼 추가 시 데이터 테이블에 `ALTER TABLE ADD COLUMN`을 시도한다.

근거:

- `column_service.py:533`
- `column_service.py:554`
- `column_service.py:555`

판단:

- `accident`, `safety_instruction`, `follow_sop`, `full_process`, `safe_workplace` 등은 “물리 컬럼 + custom_data” 혼합형이 될 수 있다.
- 이 구조가 장기적으로 가장 헷갈리는 부분이다.

### 4.4 list / popup / scoring 저장

- list 타입은 `custom_data`에 배열 또는 JSON 문자열 형태로 저장될 수 있어 normalize 코드가 많다.
- popup linked field도 동적 필드로 들어와 `custom_data` 또는 물리 컬럼에 분산될 수 있다.
- scoring은 `scoring_config`가 컬럼 설정 테이블에 저장되고, 실제 값은 대체로 `custom_data`에 저장된다.
- final-check는 `custom_data`의 `final_check_yn`, `final_check_yn_label`을 `jsonb_set`으로 갱신한다.

근거:

- `repositories/boards/follow_sop_repository.py:463`
- `repositories/boards/follow_sop_repository.py:530`
- `repositories/boards/safety_instruction_repository.py:596`
- `column_service.py:503`
- `app.py:5698`
- `app.py:5776`
- `app.py:5779`
- `app.py:5781`

판단:

- `custom_data` 타입 정규화가 매우 중요하다.
- 특히 `[]` 문자열, 실제 배열, `{}` 문자열, 실제 dict가 섞일 수 있다.

## 5. import/export/final-check 데이터 흐름

### 5.1 Export

확인된 export 라우트:

- `/api/accident-export` → `accidents_cache`, `section_config`, `accident_column_config`
- `/api/follow-sop-export` → `follow_sop`, `follow_sop_sections`, `follow_sop_column_config`
- `/api/safe-workplace-export` → `safe_workplace_sections`, `safe_workplace_column_config`, `safe_workplace`
- `/api/full-process-export` → `full_process`, `full_process_sections`, `full_process_column_config`
- `/api/safety-instruction-export` → `safety_instructions`, `safety_instruction_sections`, `safety_instruction_column_config`
- `/api/change-requests/export` → `change_request_column_config`, `section_config`, change request data

근거:

- `app.py:6588`
- `app.py:6607`
- `app.py:6622`
- `app.py:6644`
- `app.py:7096`
- `app.py:7111`
- `app.py:7126`
- `app.py:7147`
- `app.py:7351`
- `app.py:7366`
- `app.py:7381`
- `app.py:7602`
- `app.py:7882`
- `app.py:7897`
- `app.py:7924`
- `app.py:7946`
- `app.py:8083`

주의:

- `subcontract_approval`, `subcontract_report` export 라우트는 확인되지 않았다.
- 프론트는 `/api/${slug}/export`를 호출하므로 URL drift가 확정 후보다.

### 5.2 Import

확인된 import 라우트:

- `/api/accident-import`

근거:

- `app.py:6787`
- `app.py:6788`

주의:

- 내부에서 `sqlite_master`를 직접 조회한다.
- `db/compat.py`는 `PRAGMA table_info`는 에뮬레이션하지만 `sqlite_master` 전체를 에뮬레이션하지 않는다.

근거:

- `app.py:6818`
- `app.py:6820`
- `db/compat.py:364`

판단:

- PostgreSQL 환경에서 `/api/accident-import`는 `relation "sqlite_master" does not exist`류 오류가 날 가능성이 있다.
- 이는 safety-instruction/full-process 템플릿이 같은 `/api/accident-import`를 호출하는 문제와 결합하면 더 위험하다.

### 5.3 Final Check

확인된 final-check 라우트:

- `/api/full-process/final-check`
- `/api/follow-sop/final-check`
- `/api/safe-workplace/final-check`

근거:

- `app.py:5793`
- `app.py:5847`
- `app.py:5900`

공통 업데이트 함수는 `custom_data`에 JSONB로 상태를 넣는다.

근거:

- `app.py:5698`
- `app.py:5776`

주의:

- `subcontract_approval`, `subcontract_report` final-check 라우트는 없다.
- 이 부분은 `FRONTEND_CONNECTION_REPORT.md`의 URL drift와 일치한다.

## 6. 권한/감사/접속 로그 테이블

### 6.1 권한 요청 API

`permission_api.py`는 `permission_requests`, `user_menu_permissions`, `dept_menu_roles`, `menu_names`, `system_users`, `departments_external` 등에 의존한다.

근거:

- `permission_api.py:1253`
- `permission_api.py:1313`
- `permission_api.py:1347`
- `permission_api.py:1355`
- `permission_api.py:1363`
- `permission_api.py:1408`
- `permission_api.py:1562`

하지만 이 테이블들의 생성은 자동 번호 마이그레이션이 아니라 별도 스크립트에 있다.

근거:

- `scripts/setup_permission_schema.py:53`
- `scripts/setup_permission_schema.py:100`
- `scripts/setup_permission_schema.py:150`
- `scripts/setup_permission_schema.py:194`

판단:

- 현재 로컬 DB에 테이블이 있으면 동작하겠지만, 새 DB에서는 권한 API가 먼저 깨질 가능성이 있다.

### 6.2 감사 로그

감사 로그 기록은 `audit_logger.py`가 `access_audit_log`에 기록한다.

근거:

- `audit_logger.py:154`
- `audit_logger.py:181`

사용자 접속 로그는 `access_log_helper.py`가 `user_access_logs`에 기록한다.

근거:

- `access_log_helper.py:31`
- `access_log_helper.py:53`

주의:

- `access_audit_log` 생성은 `scripts/setup_permission_schema.py`와 `create_permission_tables.py`에 보인다.
- `user_access_logs` 생성은 `create_access_log_table.py`에 별도로 있다.
- 자동 번호 마이그레이션에는 둘 다 보이지 않는다.

## 7. 주요 위험 정리

### 7.1 자동 마이그레이션 불완전

현재 `init_db()`가 자동 실행하는 것은 `migrations/[0-9][0-9][0-9]_*.sql`뿐이다.

문제:

- 앱 런타임이 요구하는 권한/감사/접속로그/드롭다운 감사/외부 scoring 테이블이 자동 생성되지 않을 수 있다.
- 로컬에서는 과거 수동 스크립트 덕분에 우연히 존재할 수 있다.
- 새 환경에서 “왜 되는 PC와 안 되는 PC가 다른지”의 원인이 될 수 있다.

### 7.2 PostgreSQL 전용 선언과 SQLite 호환층 공존

겉으로는 PostgreSQL 전용이다.

하지만 여전히 남아 있는 것:

- `sqlite3.Row`
- `PRAGMA table_info`
- `sqlite_master`
- `AUTOINCREMENT`
- `datetime('now')`
- `INSERT OR REPLACE`
- `get_sqlite_connection`
- `local_db_path`

판단:

- 일부는 의도된 호환층으로 처리된다.
- 일부는 처리되지 않을 수 있다. 특히 `sqlite_master` 직접 조회는 위험하다.

### 7.3 물리 컬럼 + JSONB 혼합

게시판별 저장 방식이 다르다.

- `subcontract_*`: JSONB-only
- 그 외 다수: 물리 컬럼 추가 시도 + `custom_data` 병행
- legacy: 별도 테이블/상세 테이블/첨부 테이블 직접 처리

판단:

- export/search/detail 표시에서 “컬럼값 우선인가, custom_data 우선인가” 규칙이 보드마다 다를 수 있다.
- 대규모 리팩터링 전에는 보드별 저장 우선순위를 표준화해야 한다.

### 7.4 외부 scoring 테이블 미보장

`scoring_external_service*.py`는 `external_scoring_table`을 조회한다.

근거:

- `scoring_external_service.py:128`
- `scoring_external_service_v2.py:21`
- `scoring_external_service_v3.py:100`

하지만 생성은 `setup_external_scoring.py` 또는 테스트 스크립트에 있다.

근거:

- `setup_external_scoring.py:34`
- `test_scoring_setup.py:115`

판단:

- full-process 외부 채점 기능은 DB 준비 상태에 따라 깨질 수 있다.

## 8. 다음 단계 제안

다음 분석은 권한/SSO/보안이 자연스럽다.

특히 우선 확인할 것:

1. `scripts/setup_permission_schema.py`가 실제 실행된 적이 있는지
2. `permission_api.py`가 테이블 누락 시 얼마나 안전하게 실패하는지
3. `access_audit_log`, `user_access_logs` 생성 보장 여부
4. SSO dev/prod 설정과 `/sso/dev-login` 노출 범위
5. 업로드/다운로드 경로 검증

수정은 아직 하지 않는다. 다만 추후 안정화 단계에서는 먼저 “자동 마이그레이션이 앱 필수 테이블을 모두 보장하도록 통합”하는 작업이 가장 효과가 클 가능성이 높다.
