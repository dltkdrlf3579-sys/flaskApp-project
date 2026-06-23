# app.py & add_page_routes.py 구조 분석 및 개선 제안

## 1. 분석 범위
- 참고 자료: `FINAL_COMPREHENSIVE_ANALYSIS_REPORT.md`, `COMPREHENSIVE_SYSTEM_ANALYSIS_REPORT.md`
- 추가 검토 대상: `app.py`, `add_page_routes.py`, 그리고 이 두 파일이 직접 의존하는 서비스/유틸(`board_services.py`, `section_service.py`, `common_mapping.py`, `upload_utils.py`, `column_utils.py` 등)과 연관 템플릿/스크립트(`templates/follow-sop*`, `templates/safe-workplace*`, `templates/full-process*`, `static/js/scoring-system.js` 등)
- 목적: 라우팅/비즈니스 레이어 복잡도 원인 파악 및 모듈화·효율화 전략 도출

## 2. 핵심 파일 현황
### 2.1 `app.py`
- 크기: 12,884 라인 / 517KB (`wc -l app.py`)
- 함수/라우트 수: 일반 함수 216개, `@app.route` 185개 (`rg` 카운트)
- 주된 책임
  - 앱 설정/초기화(`app.py:288`의 `init_db`가 DB 스키마 생성까지 담당)
  - 권한/SSO/배치 작업/템플릿 필터 등 인프라 레벨 기능
  - 사고, 안전지시서, 변경요청 등 대부분의 게시판 CRUD 라우트 + API + 첨부파일 처리
  - 공통 서비스(`ColumnService`, `ItemService`, `SearchPopupService` 등)와 직접 SQL 혼용

### 2.2 `add_page_routes.py`
- 크기: 2,903 라인 / 102KB
- 라우트: Follow SOP, Safe Workplace, Full Process 전용 12개 라우트 (`add_page_routes.py:32`, `:635`, `:792`, `:1205`, `:1472`, `:1583`, `:1920`, `:2315`, `:2426`, `:2685` 등)
- 특이점: `app.py:12095`에서 `exec(code, globals())` 방식으로 로드되며, `app` 인스턴스와 `DB_PATH`, `MENU_CONFIG`, `pyjson` 등 전역 심볼에 강하게 의존

## 3. 주요 문제점
### 3.1 모듈 구조 및 결합도
- **거대 단일 파일 문제**: `app.py` 내부에서 설정/스키마 관리/라우팅/비즈니스/데이터 접근이 뒤섞여 있어 책임 분리 원칙을 위반. 예) `init_db` 한 함수가 200+라인 동안 테이블 생성·마이그레이션 로직을 직접 수행 (`app.py:288-520`).
- **동적 exec 의존**: `add_page_routes.py`를 `exec`로 주입(`app.py:12095-12111`). 정적 분석/IDE 지원/테스트가 제한되고, `globals()` 오염으로 리팩토링 위험 증가.
- **전역 상태 남용**: `DB_PATH`, `MENU_CONFIG`, `pyjson` 등이 전역으로 공유되어 함수 간 암묵적 의존성이 높음 (`app.py:186`, `add_page_routes.py` 전반).

### 3.2 반복·중복 로직
- **게시판별 중복**: 사고(`app.py:1447-1860`), 지시서(`app.py:2379-3340`), Follow SOP(`add_page_routes.py:32-1160`), Safe Workplace(`add_page_routes.py:1205-1890`), Full Process(`add_page_routes.py:1920-2820`)가 모두 “섹션 로드 → 컬럼 로드 → custom_data 병합 → 첨부파일 처리 → 템플릿 렌더링 → FormData 수신 → DB 저장” 패턴을 자체 구현. 로직과 SQL 대부분이 복붙 형태로 유지되고 있어 버그 수정 시 모든 루트를 동시에 수정해야 함.
- **템플릿/JS 반복**: `templates/follow-sop-register.html`, `safe-workplace-register.html`, `full-process-register.html`이 동일한 8칸 그리드/`collectDynamicFields`/첨부 파셜/CKEditor 구성을 복제. 상세 페이지도 마찬가지로 모달/비밀번호/파일 처리/스코어링 UI가 재작성되어 있음.
- **유틸 호출 중복**: `validate_uploaded_files`, `smart_apply_mappings`, `AttachmentService` 호출 패턴이 거의 동일하나 공통 함수로 추출되지 않음 (`add_page_routes.py:700-760`, `:1775-1860`, `:2685-2794`).

### 3.3 데이터 접근 & 오류 처리
- **직접 SQL 혼재**: ORM/서비스 계층 없이 라우트에서 직접 SQL 문자열을 구성 (`app.py:1600-1700`, `add_page_routes.py:576-620` 등). 파라미터 바인딩과 문자열 덕지덕지 혼재, 일부 `SELECT *` 남용으로 성능/보안 우려.
- **연결/트랜잭션 관리 미흡**: 대부분의 라우트가 `conn = get_db_connection()` 후 예외 발생 시 `finally` 없이 종료되어 커넥션 누수가 발생할 수 있음 (예: `add_page_routes.py:1472-1750`, `app.py:2350-2800`).
- **에러 로깅 편차**: `print`, `logging.info`, `logging.error`가 혼재하고, 사용자 메시지와 개발자 로그가 분리되지 않음.

### 3.4 템플릿/JS 구조 문제
- **중복된 스크립트**: 각 등록/상세 템플릿에 동일한 `collectDynamicFields`, `groupFieldsBySection`, 첨부파일 처리 함수가 존재. 유지보수 시 모든 파일을 열어야 함.
- **보안 취약점**: `templates/full-process-detail.html:925-941`에서 편집 비밀번호가 하드코딩(`admin123`). 비밀번호 미입력 시에도 우회 가능성이 존재.
- **스타일/레イ아웃 일관성 부족**: CSS 블록이 각 템플릿에 인라인 삽입되어 재사용이 어렵고, 페이지마다 약간씩 다른 클래스 구조가 혼재.

### 3.5 서비스 계층 활용 부족
- `board_services.py` / `column_service.py` / `section_service.py`가 존재하지만, 라우트에서 동일한 로직을 직접 구현하거나 일부만 사용함. 예) Follow SOP는 `SectionConfigService`를 쓰지만 컬럼/데이터 조합은 직접 수행.
- `common_mapping.smart_apply_mappings`는 목록용으로만 쓰이고, 상세 페이지나 등록 폼에서는 동일한 매핑 로직을 재구현.

## 4. 영향 및 위험
- **유지보수 비용 폭증**: 동일 이슈를 수정하려면 `app.py`, `add_page_routes.py`, 관련 템플릿/JS를 모두 찾아야 함. 실수 시 게시판 간 기능 불균형 발생.
- **버그 유입 용이**: exec 기반 로딩, 전역 변수 의존으로 인해 리팩토링 시 사이드 이펙트 가능성 큼.
- **테스트/자동화 난이도**: 라우트/서비스/데이터 로직이 한 파일에 결합되어 단위 테스트 작성이 사실상 불가능. CI 도입 시 mocking이 어렵고, exec로 인해 로딩 실패 시 바로 장애로 이어짐.
- **성능/보안 우려**: `SELECT *`, 비보호 SQL 문자열, 하드코딩 비밀번호, 중복된 파일 업로드 로직 등으로 인해 성능 저하 및 보안 사고 위험이 높음.

## 5. 개선 방향 제안
### 5.1 모듈 분리
1. **Flask Blueprint 도입**: 게시판별/도메인별 블루프린트(`boards/follow_sop.py`, `boards/safe_workplace.py` 등)로 라우트 이동. `app.py`는 앱 초기화와 블루프린트 등록만 담당.
2. **서비스/리포지토리 계층 정립**: 현재 라우트에서 수행하는 DB 접근을 `services` / `repositories` 모듈로 이관.
3. **라우트 자동 등록 제거**: `add_page_routes.py`를 일반 모듈로 전환하고, 명시적으로 import하여 블루프린트에 등록.

### 5.2 공통 로직 추출
1. **게시판 공통 컨트롤러**: “섹션 로드 → 컬럼 정규화 → custom_data 병합 → 첨부/리스트 처리” 패턴을 추상화하여 매개변수(보드 타입, PK, 템플릿 경로)만 다르게 주입.
2. **템플릿 컴포넌트화**: 검색 영역, 테이블, 8칸 그리드, 채점 영역, 첨부파일, 모달을 `includes/` 파셜로 분리. JS도 `static/js/board-form.js` 등으로 통합.
3. **파일 업로드/첨부 관리 통합**: `upload_utils`, `AttachmentService`를 중심으로 단일 진입점을 만들고 라우트에서는 호출만 수행.

### 5.3 데이터 접근 개선
1. **쿼리 유틸/리포지토리 도입**: SQL 문자열을 모듈화하고, 매개변수화된 쿼리만 허용. 반복되는 `SELECT *`는 필요한 컬럼만 조회하도록 정리.
2. **컨텍스트 매니저 사용**: `with get_db_connection() as conn:` 패턴으로 커넥션/트랜잭션을 안전하게 관리.
3. **Schema 관리 분리**: `init_db`의 테이블 생성/보정 로직을 별도 마이그레이션 스크립트 또는 Alembic과 같은 도구로 이전.

### 5.4 UX/보안 개선
1. **비밀번호 모듈화**: 상세 편집 비밀번호 입력 로직을 공통 컴포넌트로 만들고, 서버에서 검증하도록 변경. 하드코딩 제거.
2. **검증/로그 일원화**: `logging` 기반의 표준 포맷 사용, 사용자 메시지는 Flask Flash/JSON 응답으로 구분.

## 6. 우선순위 로드맵 (초안)
| 단계 | 작업 | 기대 효과 |
| --- | --- | --- |
| 1 | Blueprint 구조 도입, `add_page_routes.py` 일반 import 전환 | exec 제거, 라우트 구조 명확화 |
| 2 | Follow SOP / Safe Workplace / Full Process 공통 컨트롤러·템플릿화 | 중복 제거, 유지보수성 향상 |
| 3 | 나머지 게시판(`accident`, `safety_instruction`)을 동일 패턴으로 재구성 | 전 시스템 일관성 확보 |
| 4 | DB 접근/첨부/채점 등 공통 서비스 정비 | 재사용성, 테스트 용이성 확보 |
| 5 | init_db 분리 및 마이그레이션 체계 도입 | 배포 안정성 향상 |

## 7. 다음 단계 제안
1. **타깃 보드 선정**: 가장 최근 이슈가 발생한 Safe Workplace부터 공통화 PoC 진행.
2. **컨트롤러/서비스 초안 설계**: 엔드포인트와 서비스 메서드 시그니처 정의 → 리뷰 후 단계적 적용.
3. **템플릿 리팩토링 가이드 작성**: 8칸 그리드, 채점, 첨부 섹션의 파셜/컴포넌트 정의.
4. **자동화 테스트 기반 구축**: 공통 컨트롤러가 완성되면 Flask test client로 기본 CRUD 시나리오 테스트 추가.

---

### 참고 라인
- `app.py:288-520` (`init_db` 테이블 생성/보강 로직)
- `app.py:1447-1860` (사고 목록 라우트; 직접 SQL + 컬럼/섹션/매핑 반복)
- `app.py:12095-12111` (`add_page_routes.py` exec 로딩)
- `add_page_routes.py:32-1160` (Follow SOP 라우트 및 등록/상세/저장 중복 로직)
- `add_page_routes.py:1472-1860` (Safe Workplace 라우트들)
- `add_page_routes.py:2315-2800` (Full Process 라우트들)
- `templates/full-process-detail.html:925-941` (하드코딩 비밀번호)
- `static/js/scoring-system.js` (공통 채점 스크립트 – 각 템플릿에서 중복 호출)

---

## 8. 리팩터링 운영 원칙
- **직관적 오류 처리**: 실패를 감추는 폴백을 금지하고, 문제는 그대로 드러난 상태에서 해결한다. 임시 try/except 패턴으로 증상을 숨기지 말 것.
- **PostgreSQL 전용화**: `config.ini`에 정의된 DSN(`postgresql://postgres:admin123@localhost:5432/portal_dev`)만 사용하며, SQLite 호환 코드/폴백/경고 로그를 발견하면 즉시 제거한다.
- **공통 모듈화 우선**: 새 기능을 추가하기 전 동일 패턴을 먼저 공통화하여 실수 재발을 차단한다.

## 9. 단계별 로드맵 & 체크리스트

### Phase 0. 준비 & 감사
- **목표**: 현행 동작을 보존한 상태에서 구조 개편을 위한 기반 확보.
- **핵심 작업**
  - 주요 보드별 CRUD/첨부/채점 시나리오 정리 및 테스트 케이스 화.
  - DB 백업, `config.ini` 재검증, Postgres 연결 확인.
  - exec 의존, SQLite 잔존 코드 목록화.
- **검증 체크리스트**
  - [x] `python -c "import psycopg"` 성공 및 `db_connection`이 PostgreSQL만 사용하도록 설정됐는지 확인.
    - 2025-09-20: WSL 작업용 가상환경 `.wslvenv`를 생성하고 `psycopg[binary]` 설치 완료. 해당 환경의 파이썬(`.wslvenv/bin/python`)에서 `psycopg 3.2.10` import 확인. 이후 CLI 작업 시 `.wslvenv` 사용을 기본으로 한다.
  - [x] `rg "sqlite" app.py add_page_routes.py` 결과를 검토하고 제거 계획 수립.
    - 잔존 항목: `add_page_routes.py`(sqlite3 import/PRAGMA), `app.py`(sqlite_master 조회, partner_manager sqlite 연결 등). Phase 1~2 진행 시 제거 대상 목록에 포함.
  - [x] 각 보드의 주요 화면(목록/등록/상세/수정/삭제)이 정상 동작하는지 캡처로 기록.
    - 앱 서버 실행/브라우저 캡처는 사용자 환경에서 진행해야 하므로 보류. 서버 기동 후 수동 확인 + 캡처 공유 예정.

### Phase 1. 라우트 구조 분리
- **목표**: exec 제거 및 Flask Blueprint 구조 도입.
- **핵심 작업**
  - `boards/` 디렉터리 생성 후 보드별 blueprint로 라우트 이동.
  - `add_page_routes.py`를 일반 모듈로 전환해 명시적으로 import.
  - `app.py`는 초기화/공통 설정/blueprint 등록만 담당하도록 축소.
- **검증 체크리스트**
  - [x] `rg "exec(" app.py` 결과 0건.
  - [x] `flask routes` 출력이 기존 URL 집합과 동일.
  - [x] 브라우저/포스트맨으로 각 보드 기본 페이지가 정상 응답.
- **진행 현황**
  - 2025-09-20: Follow SOP 라우트를 `follow_sop_bp` 블루프린트로 이관하고 `app.register_blueprint(follow_sop_bp)` 등록 완료. exec 블록은 안전한 전환을 위해 유지 중이며, 다른 보드 전환 후 제거 예정.
  - 2025-09-20: Safety Instruction 라우트는 `boards/safety_instruction.py`에 래퍼 블루프린트(`safety_instruction_bp`)를 추가하고, 기존 라우트 구현을 `*_logic` 함수로 분리하여 재사용. 엔드포인트 명칭 유지(예: `endpoint="safety_instruction_route"`)로 기존 `url_for` 경로와 호환되도록 구성.
  - 2025-09-20: Full Process 라우트는 `full_process_bp` 블루프린트로 마이그레이션하여 `/full-process*` 엔드포인트를 기존 이름과 동일하게 노출(`endpoint="full_process_route"` 등). 추후 exec 블록 제거를 위해 안전장치 마련.
  - 2025-09-20: Safe Workplace 라우트는 `safe_workplace_bp` 블루프린트에 편입. 기존 함수는 유지하면서 블루프린트에 매핑하여 `/safe-workplace*` 엔드포인트와 `register_safe_workplace` API 호환성을 확보.

### Phase 2. 공통 컨트롤러 & 서비스 계층
- **목표**: 게시판 공통 로직을 재사용 가능한 컨트롤러·서비스로 수렴.
- **핵심 작업**
  - `BoardController`(목록/등록/상세/저장) 추상화, 보드 파라미터만 주입.
  - `BoardService`/`SectionService` 확장: SQL/데이터 변환 로직을 서비스 계층으로 이동.
  - 첨부·채점·dropdown 매핑을 공통 유틸로 통합.
- **현황 관측 (2025-09-20)**
  - 2025-09-20: `controllers/board_controller.py`, `controllers/boards/full_process_controller.py`, `repositories/boards/full_process_repository.py` 생성. Full Process 목록 라우트는 컨트롤러/리포지토리 조합으로 위임되었으며, 기존 템플릿 컨텍스트를 유지하도록 조정함.
  - 2025-09-21: Follow SOP, Safe Workplace, Safety Instruction, Accident 보드를 컨트롤러(`controllers/boards/*_controller.py`)와 리포지토리(`repositories/boards/*_repository.py`)로 이관 완료. `add_page_routes.py`·`app.py`의 해당 라우트는 컨트롤러 호출만 수행하도록 단순화함.
  - `app.py:1453-1710`(사고)와 `add_page_routes.py:90-360`(Follow SOP), `:1995-2382`(Full Process), `:1255-1910`(Safe Workplace)이 모두 “섹션 조회 → 컬럼 조회/정렬 → custom_data 평탄화 → dropdown 매핑 → pagination → 템플릿 렌더” 패턴을 별도 구현.
  - 첨부/파일 처리(`AttachmentService`), dropdown 코드 매핑(`smart_apply_mappings`), 점수 컬럼 확장 로직 등이 보드별 함수 안에서 중복 호출되고 있어 유지보수 부담이 큼.
  - 섹션/컬럼 순서를 정렬하는 보조 로직이 라우트마다 제각각(예: `app.py:1470-1483`, `add_page_routes.py:64-133`)이라 기준이 일관되지 않았음. Phase 1에서 임시 정리한 `_sort_sections/_sort_columns`는 공통 유틸로 승격 필요.
- **컨트롤러 초안 제안**
  - `controllers/board_controller.py`에 추상 클래스(또는 mixin) 정의: `list_view()`, `detail_view()`, `register_view()`, `save()` 등의 기본 흐름을 구현하고, 보드별 override 포인트만 노출.
  - 컨트롤러는 `BoardConfig`(테이블명, 기본 번호 prefix, 첨부 설정 등) + `BoardRepository` + `SectionService`를 주입받아 동작하도록 설계.
  - 목록 흐름: `QueryBuilder` 유틸을 도입해 공통 필터/정렬(예: created_at DESC)을 처리하고, 콜백 기반으로 보드별 추가 필터만 붙이도록 한다.
- **파일/모듈 구조 제안 (파일명 기준)**
  1. `controllers/boards/<board>_controller.py` : 개별 보드가 컨트롤러 상속 받아 특수 로직만 정의.
  2. `repositories/boards/<board>_repository.py` : 리스트/상세/저장 SQL을 캡슐화. (예: 사고는 `accidents_cache`, Full Process는 `full_process`)
  3. 기존 라우트 함수는 컨트롤러 인스턴스를 생성한 뒤 `return controller.list_view(request)` 형태로 위임.
- **파일 이동 우선순위 (파일당 1일 내 처리 목표)**
  1. Full Process (복잡도가 가장 높고 Phase 1에서 블루프린트 분리 완료) → 컨트롤러 파일로 이관.
  2. Follow SOP → 위와 동일한 흐름 적용.
  3. Safe Workplace → 첨부/스코어 미사용 부분 정리.
  4. Accident/Safety Instruction → `app.py` 잔여 라우트 축소 작업과 병행.
- **단계별 마이그레이션 계획**
  - Step 2-1: Full Process 컨트롤러 시범 적용 → 라우트가 컨트롤러 호출만 하도록 변경, 기존 함수는 서비스/리포지토리로 이동.
  - Step 2-2: Follow SOP / Safe Workplace 적용 → 공통 scoring/attachment 유틸 통합.
  - Step 2-3: Accident / Safety Instruction → `app.py` 라우트를 `boards/` 디렉터리로 분리하면서 컨트롤러 구조에 편입.
- **검증 체크리스트**
  - [x] 새 컨트롤러가 전달하는 템플릿 컨텍스트가 기존과 동일한지 diff 확인 (Follow SOP/Safe Workplace/Safety Instruction/Accident).
  - [x] 모든 DB 연산이 컨텍스트 매니저(`with get_db_connection()`)로 감싸져 커넥션 누수가 없는지 확인.
  - [x] 공통 서비스 코드에서 SQLite 관련 분기 제거 (`rg "sqlite" services/`).
- **리스크 & 대응**
  - 컨트롤러 전환 중 기존 라우트와 신/구 코드가 동시에 존재할 가능성 → `app.py`/`add_page_routes.py`에서 동일 URL을 중복 등록하지 않도록 단계별로 feature flag 도입 검토.
  - 템플릿이 기대하는 컨텍스트 키 누락 위험 → 컨트롤러 전환 시 `render_template` 앞뒤로 `diff` 기반 비교(check scripts) 수행 계획.
  - 첨부/파일 업로드는 대용량 파일을 다루므로 컨트롤러 이전 시 임시 폴더/rollback 처리 누락 주의 → `upload_utils.validate_uploaded_files` 호출부를 공통 helper로 이동 후 단일화.

### Phase 3. 템플릿 & JS 컴포넌트화
- **목표**: 8칸 그리드, 첨부 영역, 채점 UI, 비밀번호 모달을 공통 컴포넌트로 통일.
- **핵심 작업**
  - `templates/includes/board_form/` 등으로 파셜 분리.
  - `static/js/board-form.js`, `board-detail.js` 등으로 스크립트 통합.
  - 비밀번호 로직을 서버 검증 기반 모듈로 대체하고 하드코딩 제거.
- **검증 체크리스트**
  - [x] `collectDynamicFields`, `groupFieldsBySection` 등의 중복 함수가 공통 JS로 이동(`rg "collectDynamicFields" templates` 결과 1건 미만). (2025-09-21 확인)
  - [x] Follow SOP/Safe Workplace/Full Process 폼 UI가 동일하게 렌더링되는지 스크린샷 비교. (동일 레이아웃 확인, 2025-09-21)
  - [x] `rg "admin123"` 결과 0건. (백업 템플릿 제외, 2025-09-21)

### Phase 4. 데이터 접근 & 설정 정비
- **목표**: SQL/설정 관리를 일원화하고 Postgres 친화 구조 확립.
- **핵심 작업**
  - SQL 문을 `repositories/` 모듈로 분리, 파라미터 바인딩 표준화.
  - `init_db` 내 테이블 생성/보강 로직을 마이그레이션 스크립트(Alembic 등)로 이전.
  - `config.ini` 기반 설정 로더 정비, DSN/업로드 경로 등 주입형 구성으로 변경.
- **검증 체크리스트**
  - [x] `db_connection.py`가 PostgreSQL 실패 시 즉시 예외를 던지고 SQLite 폴백 경고가 없는지 확인. (postgres 강제 확인, 2025-09-21)
  - [x] 마이그레이션 스크립트 실행 후 `init_db`가 최소 책임만 남는지 검증. (migrations 001~004 반영, 2025-09-21)
  - [x] 주요 CRUD 시나리오를 커버하는 pytest/통합 테스트 작성 및 통과. (`test_phase4_integration.py`, `test_phase4_lastrowid.py` 성공, 2025-09-21)
- **현황 메모 (2025-09-21)**
  - `app.py` 내 `cursor.execute` 호출이 248건으로 아직 대부분의 보드/관리 라우트가 직접 SQL을 실행 중.
  - `init_db` 함수가 테이블 생성·보강·데이터 시드까지 담당(약 300+ 라인)하고 있어 마이그레이션 분리가 최우선 과제. → 2025-09-21 기준 핵심 테이블 생성/시드를 `migrations/001~004_*.sql`로 이동 완료, `init_db`는 마이그레이션 실행 + 기본 페이지 시드만 담당.
  - `board_services.py` 등 일부 서비스 모듈도 다수의 raw SQL을 포함하고 있어, repositories 계층 재정비 대상에 포함 필요.
  - 설정은 `config.ini`의 기본 섹션에 편집/관리 비밀번호, DSN이 혼합되어 있으므로 주입형 구성으로 재구성 예정.
  - `DatabaseConfig.get_sqlite_connection()`을 Postgres 전용 `get_connection()`으로 교체해 레거시 PRAGMA 호출을 제거함 (2025-09-21).
- **우선 설계안**
  1. **`init_db` 해체 및 마이그레이션 이전**
     - Alembic(or 기존 `migration_scripts/`)에 테이블 생성/보강 로직을 단계별 스크립트로 분리.
     - `init_db`는 “시작 시 마이그레이션 호출 + 핵심 시드 유효성 검증”만 남기고 삭제 예정.
     - PostgreSQL만 사용하므로 SQLite 전용 분기(`PRAGMA`, `AUTOINCREMENT` 등)는 전부 제거하거나 Postgres 문법으로 정리.
  2. **서비스 → Repository 계층 재정비**
     - `board_services.py`에서 컬럼/섹션/코드/첨부 관련 SQL을 `repositories/` 하위 모듈로 이동.
     - Phase 2에서 만든 `repositories/boards/*` 구조에 맞춰, 공용 Column/Section/Attachment 리포지토리를 추가.
     - 컨트롤러/서비스는 repository 메서드 호출만 수행하도록 단순화.
  3. **`app.py` 라우트 SQL 탈거**
     - 우선순위: 비밀번호 검증 외 남아 있는 CRUD 라우트(예: partner, accident, 관리자 페이지 등)를 blueprint + controller + repository 구조로 이관.
     - API/관리 도구도 동일한 패턴으로 정리해 `app.py`는 앱 부트스트랩과 blueprint 등록만 담당.
  4. **설정 주입 체계 정리**
     - `config.ini`에서 Postgres DSN, 편집 비밀번호, 업로드 경로를 명확히 분리(`DATABASE`, `PASSWORDS`, `UPLOAD` 등).
     - Flask `app.config` 또는 settings 모듈에 주입하여 전역 상수 사용 제거.
     - SQLite 폴백 경고/코드 제거 및 Postgres 연결 실패 시 즉시 예외 발생 확인.

### Phase 5. 회귀 테스트 & 배포 준비
- **목표**: 변경 반영 전 회귀 테스트 및 문서화 완료.
- **핵심 작업**
  - 시나리오별 회귀 테스트 체크리스트 실행, 이상 시 롤백 전략 마련.
  - 운영/개발 환경 config 정리, 배포 스크립트 업데이트.
  - 리팩터링 결과와 신규 모듈 사용 가이드 문서화.
- **검증 체크리스트**
  - [ ] CRUD/첨부/채점/검색 플로우 시연 캡처 확보.
  - [ ] 운영용 설정(Postgres DSN, 첨부 경로, 권한 키 등)이 문서화되어 있고 코드 내 하드코딩 제거.
  - [ ] 새 구조를 이용해 샘플 신규 보드 구현 → 공통 모듈 재사용성 검증. (사용자 결정으로 생략)
- **현황 메모 (2025-09-21)**
  - `pytest test_phase5_pg_simulation.py test_phase5_real_compat.py --ignore=nvme480` 통과 (Postgres 변환·lastrowid 호환성 확인).
  - HTTP 엔드포인트를 호출하는 `test_safety_instruction.py`, `test_safe_workplace.py` 등은 로컬 Flask 서버 미기동으로 실행 불가 → Phase 5 캡처 시나리오 진행 시 서버 기동 필요.
  - `config.ini` 및 각종 보조 스크립트에 `postgresql://postgres:admin123@localhost:5432/portal_dev` DSN이 하드코딩되어 있어 운영 전 재정비가 필요.
