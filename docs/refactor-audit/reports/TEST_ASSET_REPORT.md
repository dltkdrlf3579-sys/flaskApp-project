# 테스트/검증 자산 분류 보고서 (2026-06-13)

## 0. 분석 범위와 원칙

- 범위: 루트, `tools/`, `scripts/`, `migration_scripts/`, `migrations/`, `sql/` 아래의 테스트/디버그/검증/마이그레이션/수리성 파일.
- 방식: 파일명과 코드 패턴 기반 정적 분류. `pytest`, Flask 서버, 브라우저, DB 쓰기 테스트는 실행하지 않았다.
- 목적: 리팩터링 전에 “어떤 테스트를 믿고 돌릴 수 있는지”와 “절대 테스트처럼 실행하면 안 되는 파일”을 구분한다.

## 1. 한 줄 결론

현재 저장소에는 테스트 파일이 많지만, 대부분은 자동 회귀 테스트가 아니라 과거 문제를 해결하기 위한 단발성 진단/수리/마이그레이션 스크립트다.

따라서 `pytest` 전체 실행이나 `test_*.py` 일괄 실행은 금지해야 한다.

## 2. 자동 분류 요약

정적 분류 기준으로 테스트/검증/수리성 파일 후보는 총 291개였다.

| 분류 | 개수 | 의미 |
|---|---:|---|
| write/mutation script | 136 | DB 쓰기, DDL, 파일 쓰기, 데이터 수정 가능성이 있는 스크립트 |
| migration/schema script | 51 | 마이그레이션, 테이블 생성/수정, 스키마 보강 계열 |
| DB read/integration script | 48 | DB 연결은 하지만 정적 패턴상 명시적 쓰기는 적은 진단 스크립트 |
| HTTP/browser script | 37 | localhost 요청, Flask test client, 서버/브라우저 전제 스크립트 |
| diagnostic/misc script | 12 | 기타 진단/보조 스크립트 |
| restore/rollback script | 4 | 복원/롤백 계열. 실행 시 기존 데이터를 덮을 수 있음 |
| local candidate script | 3 | DB/HTTP 없이 실행 가능해 보이는 로컬 후보 |

## 3. 실제 회귀 테스트 후보

현재 “안전한 회귀 테스트”로 바로 믿을 수 있는 파일은 거의 없다.

### 3.1 로컬 후보

| 파일 | 상태 | 판단 |
|---|---|---|
| `test_sql_parse.py` | 로컬 파일 파싱 | DB/HTTP는 없지만 top-level script라 pytest용은 아니다. SQL 파서 확인용 보조 스크립트. |
| `test_super_admin.py` | config/권한 설정 출력 | DB 연결은 없어 보이나 Flask session 실제 테스트는 아니다. 설명/확인용 스크립트에 가깝다. |
| `test_upload_validation.py` | 업로드 검증 로직 | 가장 단위 테스트화하기 좋은 후보. 다만 현재 `config.ini`는 `zip/html/htm`을 허용하므로, 스크립트의 “zip은 실패” 기대값은 현재 설정과 안 맞을 수 있다. |

즉 현재 바로 신뢰할 수 있는 것은 “문법 검사/정적 검사”이고, 기능 회귀 테스트는 정비가 필요하다.

### 3.2 단위 테스트로 승격하기 좋은 후보

다음은 DB 없이 또는 작은 fixture로 바꾸면 진짜 회귀 테스트가 될 가능성이 있다.

- `test_upload_validation.py`: `upload_utils.py` 검증. config 의존성을 fixture로 분리해야 한다.
- `test_sql_parse.py`: SQL split helper로 함수화하면 순수 테스트 가능.
- `test_super_admin.py`: `permission_helpers.SUPER_ADMIN_USERS` 파싱 테스트로 바꾸면 가능.
- `test_column_normalization.py`: 현재 DB 연결 후보라 fixture/mock로 바꾸면 컬럼 타입 정규화 테스트가 될 수 있다.
- `test_linked_types.py`: popup/linked 타입 정책 단위 테스트로 전환 가능.

## 4. 단발성 디버그 테스트

다음 계열은 이름은 `test` 또는 `debug`지만 자동 회귀 테스트로 보면 안 된다.

- `debug_*`: 특정 시점 문제를 확인하기 위한 출력/재현 스크립트.
- `check_*`: 대부분 DB 상태 조회 또는 일부는 보강/수정까지 수행.
- `analyze_*`: 읽기 분석처럼 보이나 일부는 파일 쓰기/HTTP/DB 연결을 포함.
- `verify_*`: 운영/마이그레이션 상태 확인용. 실제 DB 연결 전제.
- `smoke_test_phase3.py`: smoke라는 이름이지만 DB write 후보다.

이 파일들은 “필요하면 사람이 읽고 선택 실행”해야지, 자동 테스트 묶음에 넣으면 안 된다.

## 5. DB 연결이 필요한 테스트/검증

DB read/integration 후보는 48개였다. 대표적으로 다음이다.

- `check_all_columns.py`
- `check_attachment_tables.py`
- `check_boolean_columns.py`
- `check_follow_sop_data.py`
- `check_safety_instruction_column.py`
- `check_scoring_columns.py`
- `test_attachment_retrieval.py`
- `test_board_standardization.py`
- `test_pg_ready.py`
- `verify_attachment_tables.py`
- `verify_section_tables.py`

주의:

- 정적 패턴상 쓰기 SQL이 안 보인다는 뜻이지, 완전 무해하다는 뜻은 아니다.
- DB 연결 자체가 현재 로컬 PostgreSQL 상태와 config에 의존한다.
- 실행 전에는 최소한 현재 DB가 테스트용인지 확인해야 한다.

## 6. 외부 서비스가 필요한 테스트/검증

다음 계열은 외부 DB/IQADB/webhook/scoring table 등에 의존한다.

- `search_popup_service.py` 관련 검사 스크립트들
- `setup_external_scoring.py`
- `test_scoring_mapping.py`
- `test_scoring_setup.py`
- `test_scoring_setup_v2.py`
- `test_scoring_verify.py`
- `migrate_safety_instructions.py`
- `migrate_to_single_tables.py`
- `RUN_FORCE_SYNC.py`

이 계열은 개발 PC 단독 실행으로 결과를 신뢰하기 어렵다. 외부 서비스 연결 여부, 샘플 데이터 fallback 여부, config 상태를 먼저 봐야 한다.

## 7. 실행하면 데이터 변경 가능성이 있는 파일

데이터 변경 가능성이 큰 파일은 크게 네 부류다.

### 7.1 수리/fix 계열

- `fix_*`
- `FIX_*`
- `simple_fix_boolean.py`
- `backup_and_fix_columns.py`
- `fix_partner_change_requests_complete.py`
- `fix_login_id_permission.py`

이름 그대로 DB/파일을 고치기 위한 스크립트다. 테스트로 실행하면 안 된다.

### 7.2 create/setup/init 계열

- `create_*`
- `setup_*`
- `init_*`
- `initial_permissions.py`
- `INIT_APP_BASE_TABLES.py`

테이블 생성, 초기 데이터 삽입, 권한 데이터 생성 가능성이 크다.

### 7.3 migration 계열

- `COMPLETE_MIGRATION.py`
- `COMPLETE_MIGRATION_FIXED.py`
- `FINAL_COMPLETE_MIGRATION.py`
- `FINAL_MIGRATION_TO_PRODUCTION.py`
- `migrations/run_migrations.py`
- `migration_scripts/*`
- `tools/RUN_SCHEMA_REPAIR.py`
- `tools/ONE_TIME_MIGRATE_CACHE_TO_MAIN.py`

이 파일들은 실행 전 백업과 목적 확인이 필수다. “혹시 되나?” 하고 돌리면 안 된다.

### 7.4 restore/reset 계열

- `restore_all_columns.py`
- `restore_follow_full_configs.py`
- `scripts/restore_follow_sop_sample.py`
- `tools/RESTORE_COLUMN_CONFIGS_FROM_BACKUP_TABLES.py`
- `reset_test001.py`

기존 데이터를 삭제/덮어쓰기/복원할 수 있으므로 강한 쓰기 등급이다.

## 8. 폐기 또는 격리 후보

다음 파일군은 루트에 남아 있으면 혼란을 만든다.

- `COMPLETE_*`, `FINAL_*` 계열 마이그레이션 스크립트
- 루트의 오래된 `fix_*`, `create_*`, `setup_*`, `migrate_*` 스크립트
- `add_page_routes_backup.py`
- `migration_scripts/`의 중복 마이그레이션 파일
- `deletelist/` 아래 과거 권한 체크 파일
- 외부 채점 v1/v2 테스트 파일 중 현재 v3와 맞지 않는 것

지금 삭제하라는 뜻은 아니다. 나중에 `archive/legacy_scripts/` 같은 격리 폴더로 옮기고, 실제 운영 경로와 분리하는 것이 좋다.

## 9. 검증 명령 후보

### 9.1 현재 즉시 가능한 무해 검증

코드 import 없이 문법만 확인한다.

```powershell
python -m py_compile app.py wsgi.py db_connection.py db/compat.py controllers/board_controller.py controllers/dynamic_board_controller.py
```

특정 순수 유틸만 문법 확인:

```powershell
python -m py_compile upload_utils.py column_utils.py list_schema_utils.py utils/sql_filters.py
```

주의: `compileall .`은 실행은 아니지만 파일 수가 많고 백업/레거시 스크립트까지 모두 훑으므로 지금은 제한된 파일만 지정하는 편이 낫다.

### 9.2 낮은 위험의 정적 구조 확인

AST 기반 라우트/함수 목록 확인은 안전하다.

```powershell
python - <<'PY'
import ast
from pathlib import Path
for path in ['app.py', 'add_page_routes.py', 'permission_api.py']:
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    routes = sum(1 for n in ast.walk(tree) if isinstance(n, ast.FunctionDef))
    print(path, routes)
PY
```

PowerShell에서는 heredoc 문법이 다르므로 실제 실행 시에는 `@' ... '@ | python -` 형태로 바꿔야 한다.

### 9.3 DB 읽기 검증 후보

백업 전에도 가능은 하지만, DB 연결과 로그 부작용이 있으므로 “낮은 위험”으로 분류한다.

```powershell
python check_pg_ready.py
python check_attachment_tables.py
python verify_section_tables.py
```

단, 실행 전 파일 내용을 다시 확인해야 한다. 이 보고서의 분류는 정적 패턴 기반이다.

### 9.4 DB 쓰기/마이그레이션 검증 후보

다음은 백업 전 실행 금지다.

```powershell
python migrations/run_migrations.py
python tools/RUN_SCHEMA_REPAIR.py
python setup_permission_schema.py
python create_permission_tables.py
python test_upsert.py
```

이들은 검증 명령이 아니라 “변경 작업”에 가깝다.

### 9.5 브라우저 smoke test 후보

브라우저 확인은 DB 백업 후에만 한다.

읽기 전용 후보 URL:

- `/`
- `/partner-standards`
- `/accident`
- `/safety-instruction`
- `/follow-sop`
- `/full-process`
- `/safe-workplace`
- `/subcontract-approval`
- `/subcontract-report`
- `/admin/menu-settings`는 관리자 인증 흐름 때문에 별도 주의

금지 또는 별도 승인:

- 등록/수정/삭제 버튼
- import/export 중 import
- final-check
- 권한 승인/거절
- sync 계열

## 10. 추천 테스트 전략

### Phase A: 현재 그대로 가능한 것

1. 핵심 파일 `py_compile`.
2. AST 기반 라우트/URL 지도 재생성.
3. DB 연결 없는 유틸 후보만 수동 실행 또는 단위 테스트화.

### Phase B: 테스트 정비

1. `tests/` 폴더를 새로 만들고 진짜 pytest만 이동한다.
2. 기존 `test_*.py`는 바로 이동하지 말고 안전성 검토 후 선별한다.
3. DB 쓰기 테스트는 `pytest.mark.db_write` 같은 표시를 붙인다.
4. HTTP 테스트는 서버/DB 백업/테스트 데이터 조건을 명시한다.
5. 과거 수리 스크립트는 `legacy_scripts/`로 격리한다.

### Phase C: 리팩터링 전 최소 회귀 세트

리팩터링 전에 최소한 다음은 갖추는 게 좋다.

- `upload_utils` 순수 단위 테스트
- `list_schema_utils` 순수 단위 테스트
- `column_utils` 순수 단위 테스트
- `permission_helpers.resolve_menu_code` 단위 테스트
- `db.compat` SQL 변환 단위 테스트. 실제 DB 쓰기 없는 방식으로 전환 필요
- Flask route map import-only 스냅샷 테스트. 단, import 부작용 주의

## 11. 8단계 결론

현재 테스트 자산은 “자동으로 돌려 안전을 보장하는 테스트”라기보다 “1년간 문제를 추적하며 남긴 수리 도구와 재현 스크립트”에 가깝다.

이건 실패가 아니라 자연스러운 흔적이다. 비개발자 상태에서 바이브코딩으로 빠르게 기능을 붙이면 이런 스크립트가 쌓이는 게 정상이다. 이제 해야 할 일은 이 스크립트들을 믿고 실행하는 게 아니라, 안전한 것과 위험한 것을 나눠서 진짜 회귀 테스트로 승격하는 것이다.
