# 서비스/공통 모듈 분석 보고서 (2026-06-13)

## 0. 분석 범위와 원칙

- 범위: `controllers/*`, `repositories/boards/*`, `repositories/common/*`, `column_service.py`, `board_services.py`, `section_service.py`, `search_popup_service.py`, `common_search.py`, `common_mapping.py`, `table_mappings.py`, `utils/sql_filters.py`, `audit_logger.py`, `notification_service.py`, `access_log_helper.py`, `id_generator.py`, `scoring_service.py`, `scoring_external_service*.py`.
- 방식: 정적 코드 분석. 서버 실행, 브라우저 클릭, DB 쓰기, 코드 수정은 하지 않았다.
- 결론: 1년 전 리팩터링 방향은 꽤 맞았다. 다만 “공통화가 끝난 상태”가 아니라 “공통화 시도 3~4개가 동시에 남아 있는 상태”다.

## 1. 전체 구조 요약

현재 서비스/공통 모듈은 크게 네 층으로 나뉜다.

| 층 | 대표 파일 | 상태 |
|---|---|---|
| Controller 공통화 | `controllers/board_controller.py`, `controllers/dynamic_board_controller.py` | 방향은 좋다. 공통 화면 흐름을 잘 분리했다. |
| Board Repository | `repositories/boards/*_repository.py` | 핵심 비즈니스/DB/첨부/JSON 처리까지 몰려 있어 가장 무겁다. |
| Config/Column/Section Service | `column_service.py`, `board_services.py`, `section_service.py`, `repositories/common/column_config_repository.py` | 기능이 중복된다. 보호 컬럼 정책도 여러 벌이다. |
| 검색/매핑/감사/채점 | `search_popup_service.py`, `common_mapping.py`, `audit_logger.py`, `scoring_*` | 필요한 기능은 있으나 세대가 섞였다. 일부는 현재 런타임과 안 맞는 후보가 있다. |

## 2. 동적 게시판 엔진

### 2.1 Controller 계층

`controllers/board_controller.py`는 공통 컨트롤러 골격이다.

- `BoardControllerConfig`가 템플릿, board_type, per_page, extra_context, filter_fields를 들고 있다.
- `BoardController`는 아직 직접 구현체라기보다 추상 골격이다.
- `_build_template_context()`에서 `permission_code`가 있으면 read/write 권한 레벨을 템플릿 컨텍스트에 넣는다.

`controllers/dynamic_board_controller.py`는 실제 동적 게시판 공통 구현체다.

- `list_view()`가 섹션 보장, 섹션 조회, 동적 컬럼 조회, 목록 조회, custom_data flatten, 매핑 적용, pagination 생성까지 담당한다.
- `detail_view()`와 `register_view()`는 Repository가 만든 컨텍스트를 템플릿에 넘긴다.
- `save()`와 `update()`는 Repository의 `save_from_request()`, `update_from_request()`에 위임한다.

이 구조 자체는 좋다. 단, 컨트롤러가 `smart_apply_mappings()`, popup 타입 보정, custom_data 정리까지 일부 서비스 로직을 들고 있어 완전한 얇은 컨트롤러는 아니다.

### 2.2 DynamicBoardRepository 계열

`repositories/boards/follow_sop_repository.py`의 `DynamicBoardRepository`가 실질적인 공통 동적 게시판 Repository다.

담당 범위가 매우 넓다.

- 테이블 존재 확인과 테이블명 결정
- 컬럼/드롭다운/섹션 조회
- 목록 검색과 pagination
- 상세/등록 컨텍스트 구성
- list child schema 정규화
- 첨부파일 처리
- `custom_data` 정규화
- ID 생성
- 저장/수정

즉 이름은 Repository지만 실제로는 Repository + Service + ViewModel Builder 역할을 동시에 한다.

좋은 점:

- Follow SOP, Subcontract Approval, Subcontract Report가 이 구조를 공유한다.
- `repositories/common/board_config.py`를 통해 board_type별 메타데이터를 주입하려는 방향이 있다.
- Subcontract Repository는 `DynamicBoardRepository`를 상속해 기본 섹션만 최소 오버라이드한다.

아쉬운 점:

- `full_process_repository.py`, `safe_workplace_repository.py`는 `DynamicBoardRepository`를 상속하지 않고 비슷한 코드를 별도로 복제한 형태다.
- `safe_workplace`는 `BOARD_CONFIGS`에 `primary_table`, `section_table`, `detail_table`, `identifier_column`, `id_generator`가 빠져 있어 공통 Repository에 바로 태우기 어렵다.
- 공통화 기준이 “상속 기반 DynamicBoardRepository”인지 “각 보드 Repository 복제 후 점진 수정”인지 아직 갈라져 있다.

### 2.3 Accident/Safety Instruction 계열

`AccidentRepository`와 `SafetyInstructionRepository`는 별도 전용 Repository다.

- 사고/안전지시서는 기존 레거시 필드와 동적 컬럼이 강하게 섞여 있어 전용 구현이 어느 정도 필요하다.
- 둘 다 list child schema, custom_data, 첨부, 상세 본문, 번호 생성 로직을 자체 보유한다.
- `SafetyInstructionRepository`는 사고 Repository와 비슷한 구조지만, 섹션/컬럼/리스트 처리 코드가 다시 한 번 복제되어 있다.

이 둘은 “전용 구현이 필요한 보드”로 남기는 게 맞지만, list child schema/첨부/번호 생성/기본 컨텍스트 생성은 공통 유틸로 더 뺄 수 있다.

## 3. Board Config 분석

`repositories/common/board_config.py`는 좋은 중심축 후보다.

- `follow_sop`, `full_process`, `subcontract_approval`, `subcontract_report`는 primary/detail/section/identifier/id_generator 설정을 비교적 잘 갖고 있다.
- `accident`, `safety_instruction`, `change_request`, `safe_workplace`는 상대적으로 기본 정보만 있다.

특히 `safe_workplace`는 별도 Repository가 있으면서도 공통 config가 덜 채워져 있다. 이 때문에 safe_workplace를 공통 DynamicBoardRepository로 흡수하려면 config 보강이 선행되어야 한다.

## 4. 컬럼/섹션/코드 서비스

### 4.1 컬럼 관리가 세 벌이다

현재 컬럼 설정 관리는 최소 세 계층이 공존한다.

| 파일 | 역할 | 문제 |
|---|---|---|
| `column_service.py` | 가장 기능이 많은 동적 컬럼 서비스. 물리 컬럼 추가, JSONB-only 보드 처리, child_schema 처리 포함. | 기능은 풍부하지만 책임이 크고 런타임 DDL이 있다. |
| `board_services.py::ColumnService` | `/api/<board>/columns` 계열에서 쓰는 보드 컬럼 서비스. | 보호 컬럼 정책이 다른 파일과 불일치한다. |
| `repositories/common/column_config_repository.py` | Repository 패턴으로 분리한 컬럼 설정 CRUD. | 기능은 깔끔하지만 child_schema, JSONB-only, 물리 컬럼 추가 같은 최신 기능이 부족하다. |

즉 “최종 표준 컬럼 API”가 아직 하나로 수렴하지 않았다.

### 4.2 보호 컬럼 정책이 중복/불일치한다

보호 컬럼 목록은 세 곳에 있다.

- `column_service.py`: `accident`, `safety_instruction`, `change_request`, `follow_sop`, `full_process`, `safe_workplace`, `subcontract_approval`, `subcontract_report`, `partner_standards` 포함.
- `board_services.py`: `accident`, `safety_instruction`, `change_request`, `follow_sop`, `full_process`만 포함.
- `repositories/common/column_config_repository.py`: `accident`, `safety_instruction`, `change_request`, `follow_sop`, `full_process`, `subcontract_approval`, `subcontract_report` 포함.

불일치 예시:

- `safe_workplace.safeplace_no`는 `column_service.py`에는 보호되어 있지만 `board_services.py`, `column_config_repository.py`에는 없다.
- `subcontract_approval.approval_number`, `subcontract_report.report_number`는 `column_service.py`, `column_config_repository.py`에는 있지만 `board_services.py`에는 없다.

이건 관리자 컬럼 화면/API 경로에 따라 기본키 컬럼이 노출·수정·삭제 가능해지는 차이를 만들 수 있다.

### 4.3 `column_service.py`의 장단점

장점:

- `JSONB_ONLY_BOARDS = {subcontract_report, subcontract_approval}` 정책이 명확하다.
- `child_schema`, `list_item_type`, `table_group`, `table_type`, `table_name`, `scoring_config`까지 처리한다.
- 추가 컬럼 생성 시 물리 테이블 ALTER까지 시도한다.

위험:

- 컬럼 추가 API가 런타임에 `ALTER TABLE`을 실행할 수 있다.
- PostgreSQL 전용처럼 보이지만 일부 호환/과도기 코드가 남아 있다.
- JSONB-only 보드와 물리 컬럼 보드의 차이가 이 파일에만 있다. 다른 컬럼 서비스 경로는 이 정책을 모를 수 있다.

### 4.4 `section_service.py`의 과도기 흔적

`section_service.py`는 보드별 섹션을 조회/추가/수정/삭제/정렬한다.

- `section_config` 공통 테이블과 `{board}_sections` 개별 테이블을 모두 지원한다.
- PostgreSQL `information_schema`와 SQLite `PRAGMA table_info`를 모두 쓴다.
- 같은 파일 안에서 `%s`와 `?` placeholder가 섞여 있다.

현재 `db/compat.py`가 이런 혼합을 상당 부분 흡수하는 것으로 보이지만, PostgreSQL 전용으로 안정화하려면 이 파일은 정리 대상이다.

## 5. 검색/팝업/매핑

### 5.1 SearchPopupService

`search_popup_service.py`는 협력사/사람/부서/건물/도급업체/사업부 팝업 검색의 중심이다.

좋은 점:

- 검색 타입별 `search_configs`가 명확하다.
- 로컬 캐시 테이블과 외부 DB 연결을 모두 고려한다.
- PostgreSQL JSONB 검색과 SQLite `json_extract` 검색을 모두 처리하려고 한다.
- 메모리 캐시가 있다.

위험:

- `_load_dynamic_columns()`에서 `sqlite_master`를 직접 조회한다. PostgreSQL 환경에서는 동적 컬럼 로드가 실패하거나 건너뛰어질 가능성이 있다.
- 검색 SQL에서 field/table/order_by를 설정값 기반 f-string으로 조립한다. 현재는 내부 config 기반이라 즉시 취약점이라고 단정하지는 않지만, 화이트리스트 검증이 더 명시적이어야 한다.
- 외부 DB가 없으면 샘플 데이터를 반환하는 흐름이 있다. 운영에서 조용히 샘플 데이터로 대체되면 문제 발견이 늦어질 수 있다.

### 5.2 common_search.py

`common_search.py`는 동적 검색 조건 빌더다.

- SQLite `json_extract`와 PostgreSQL JSONB 문법을 둘 다 생성한다.
- 다만 파일 설명과 코드 형태가 “SQLite 시대 + PostgreSQL 미래 대비”에 가깝다.
- 현재 실제 주요 검색은 `SearchPopupService`와 각 Repository에 흩어져 있어, 이 빌더가 표준 검색 엔진으로 자리 잡았는지는 불명확하다.

### 5.3 common_mapping.py / table_mappings.py

`table_mappings.py`는 popup preset을 정의한다.

- person/company/department/building/contractor/division 등의 popup + linked field 조합이 있다.
- accident와 safety_instruction은 follow_sop 매핑을 deepcopy해서 재사용한다.

`common_mapping.py`는 목록 조회 후 custom_data/코드값을 사람이 읽는 표시값으로 매핑한다.

이 방향은 좋다. 다만 popup 타입 보정이 `DynamicBoardController`, `column_utils.py`, `table_mappings.py`, Repository별 처리에 흩어져 있어 “popup/linked 필드의 단일 표준”은 아직 아니다.

## 6. 감사/접속/알림

### 6.1 audit_logger.py

감사 로그는 비교적 잘 분리되어 있다.

- `record_audit_log()`가 중심이고, 메뉴 보기/게시판 액션/권한 이벤트/시스템 이벤트 래퍼가 있다.
- `request`, `session`에서 사용자/경로/IP/User-Agent 등을 수집한다.
- 실패해도 앱 본 흐름을 깨지 않도록 예외를 잡는 방향이다.

다만 감사 로그 테이블이 자동 마이그레이션에 완전히 포함되는지는 DB 분석 단계에서 이미 위험 후보로 잡혔다.

### 6.2 access_log_helper.py

`access_log_helper.py`는 별도의 사용자 접속 로그 유틸이다.

- `user_access_logs` 테이블을 직접 INSERT/SELECT 한다.
- `audit_logger.py`와 목적이 겹친다.
- 실제 라우트에서는 `audit_logger` 기반 `audit_request_activity`가 이미 있어서, 접속 로그 체계가 둘로 나뉜 상태다.

### 6.3 notification_service.py

`notification_service.py`는 알림 발송 구조가 깔끔하다.

- 채널 adapter 구조가 있다.
- 현재 활성 채널은 chatbot webhook 중심이다.
- `notification_logs` 테이블을 자체 보장하려는 `_ensure_log_table()`이 있다.

주의점:

- `requests.post()`로 외부 webhook을 호출하므로 운영에서는 timeout/token/실패 로깅 정책이 중요하다.
- 테이블 생성 책임이 서비스 내부에 있어 마이그레이션 책임과 섞인다.

## 7. ID 생성과 채점

### 7.1 id_generator.py

`id_generator.py`는 날짜+prefix+순번 방식 ID를 만든다.

- `generate_unique_id()`가 공통 함수다.
- Follow SOP, Full Process, Subcontract Approval, Subcontract Report는 공통 함수를 쓴다.
- Safe Workplace는 별도 구현이다.

주의점:

- PostgreSQL에서도 SQL placeholder `?`를 사용하는 구간이 있다. 현재 compat layer가 변환해줄 수 있지만, PostgreSQL 전용 안정화 목표라면 `%s`로 통일하는 편이 낫다.
- `generate_unique_id()`는 트랜잭션을 시작하지만 실제 row lock/advisory lock은 없다. 동시에 여러 사용자가 등록하면 같은 번호 생성 경쟁이 생길 가능성이 있다.

### 7.2 scoring_service.py

`scoring_service.py`는 현재 컬럼 설정의 `scoring_config`를 읽어 점수를 계산한다.

- `scoring` 컬럼과 `score_total` 컬럼을 기준으로 base score, grade criteria, total delta를 계산한다.
- 단순하고 내부 계산용으로는 나쁘지 않다.

### 7.3 scoring_external_service 계열

외부 채점 서비스 파일은 세대가 갈라져 있다.

| 파일 | 상태 |
|---|---|
| `scoring_external_service.py` | 하드코딩된 외부 컬럼 목록이 많고, `get_scoring_data_for_template()`에서 정의되지 않은 `apply_external_scoring()`을 호출한다. |
| `scoring_external_service_v2.py` | `SELECT *` 기반으로 더 동적이지만 테스트 함수에 로컬 DSN이 평문 하드코딩되어 있다. |
| `scoring_external_service_v3.py` | config 기반 동적 매핑과 `ENABLE_EXTERNAL_SCORING` 플래그가 있어 가장 정리된 버전으로 보인다. |

프론트엔드 분석에서 이미 `/api/full-process/external-scoring/<number>` 호출은 발견됐지만 실제 라우트는 확인되지 않았다. 외부 채점 기능은 “서비스 파일은 여러 버전이 있으나 런타임 연결은 불완전”으로 보는 게 맞다.

## 8. 주요 위험 정리

### 8.1 공통화가 끝나지 않은 상태

현재 프로젝트는 공통화가 안 된 게 아니라, 공통화 시도들이 여러 갈래로 남아 있다.

- `DynamicBoardRepository`
- `FullProcessRepository` 복제형
- `SafeWorkplaceRepository` 복제형
- `AccidentRepository` 전용형
- `SafetyInstructionRepository` 전용형
- `board_services.ItemService` 범용형

새 기능을 추가할 때 어느 축을 기준으로 할지 잘못 고르면 중복이 더 늘어난다.

### 8.2 컬럼 관리 표준 불명확

컬럼 관리 API가 여러 벌이라 같은 “컬럼 추가/수정/삭제”라도 호출 경로에 따라 동작이 다를 수 있다.

- 어떤 경로는 물리 컬럼을 만든다.
- 어떤 경로는 column_config만 바꾼다.
- 어떤 경로는 child_schema를 모른다.
- 어떤 경로는 보호 컬럼 목록이 다르다.

### 8.3 PostgreSQL 전용화 미완료

DB 분석에서 본 것처럼 PostgreSQL을 쓰는 상태지만, 서비스 계층에는 여전히 SQLite 흔적이 있다.

- `sqlite_master`
- `PRAGMA table_info`
- `json_extract`
- `?` placeholder
- SQLite row_factory 가정

compat layer 덕분에 돌아가는 부분이 많지만, “왜 되는지”가 숨겨져 있어 디버깅 난도가 올라간다.

### 8.4 런타임 DDL과 마이그레이션 책임 혼합

`column_service.py`, `board_services.AttachmentService`, `notification_service.py`는 실행 중 테이블/컬럼 보강을 시도한다.

이는 개발 중에는 편하지만 운영 안정성 측면에서는 위험하다.

- 서버 실행 중 schema가 바뀔 수 있다.
- 실패 시 일부만 반영될 수 있다.
- 마이그레이션 파일과 실제 런타임 schema가 어긋날 수 있다.

## 9. 좋은 점

분명히 좋은 구조도 많다.

- `BoardControllerConfig`와 `DynamicBoardController` 방향은 맞다.
- `board_config.py`가 중심축이 될 수 있다.
- `list_schema_utils.py`는 list child schema 처리를 꽤 깔끔하게 분리했다.
- `audit_logger.py`와 `notification_service.py`는 서비스로 분리하려는 방향이 좋다.
- `scoring_external_service_v3.py`는 v1/v2보다 확실히 정리된 형태다.

즉 이 프로젝트는 “다 엉망”이 아니라, 리팩터링 도중 좋은 조각과 옛 조각이 공존하는 상태다.

## 10. 다음 개선 순서 제안

코드 수정 단계로 들어간다면 다음 순서가 안전하다.

1. `board_config.py`를 표준 메타데이터 원천으로 확정한다.
2. 보호 컬럼 정책을 `board_config.py` 또는 단일 `board_policy.py`로 통합한다.
3. 컬럼 관리 표준을 하나로 정한다: 추천은 `ColumnConfigService` 기능을 살리되 Repository 스타일로 정리.
4. `FullProcessRepository`, `SafeWorkplaceRepository`를 바로 합치지 말고 `DynamicBoardRepository`와 diff를 먼저 만든다.
5. `SearchPopupService._load_dynamic_columns()`의 `sqlite_master`부터 PostgreSQL 호환 방식으로 고친다.
6. 외부 채점은 v3를 표준으로 정하고 v1/v2/테스트 import 불일치를 정리한다.
7. 런타임 DDL은 마이그레이션 파일로 옮기는 계획을 세운다.

## 11. 7단계 결론

서비스/공통 모듈의 핵심 진단은 다음이다.

> 이 프로젝트는 기능을 덕지덕지 붙인 것처럼 보이지만, 사실 중간중간 좋은 공통화 시도가 있다. 문제는 그 시도들이 하나의 표준으로 수렴하기 전에 다음 기능이 계속 붙어서, 공통화 계층이 여러 벌 생겼다는 점이다.

따라서 다음 단계에서 바로 코드를 고치는 것보다, 먼저 테스트/검증 자산을 분류해 “고친 뒤 무엇으로 안전을 확인할지” 정하는 게 맞다.
