# Flask Portal 전체 분석 체크리스트

작성일: 2026-06-13  
원칙: 코드 수정 금지, 단계별 분석, 단계별 산출물 작성, 완료 후 체크

## 운영 원칙

- [x] 분석 중에는 앱 코드 수정 금지
- [x] 각 단계 시작 전 범위 확정
- [x] 각 단계 종료 시 확인한 파일 목록 기록
- [x] 각 단계 종료 시 확인하지 못한 파일 목록 기록
- [x] 각 단계 종료 시 발견한 위험/질문 기록
- [x] 실행 검증 전에는 리팩터링 착수 금지
- [ ] 대규모 변경 제안 시 반드시 작은 단위로 쪼개기
- [x] 기존 사용자 변경분(`app.py`, `config.ini`) 덮어쓰기 금지

## 0. 기준선 정리

### 0.1 저장소 상태
- [x] `git status --short --untracked-files=all` 기록
- [x] 현재 수정 중인 파일 목록 기록
- [x] `.gitignore` 때문에 숨겨지는 분석 문서/메모 파일 확인
- [x] 루트 디렉터리의 정식 파일과 임시/백업 파일 구분
- [x] `backup`, `deletelist`, `needtodevelop`, `.serena` 역할 확인

### 0.2 실행 환경
- [x] Python 버전 확인
- [x] 사용 가상환경 후보 확인: `.venv`, `.wslvenv`, `venv`
- [x] `requirements.txt` 기반 주요 의존성 확인
- [x] Flask 실행 방식 확인: `python app.py`
- [x] WSGI 실행 방식 확인: `wsgi.py`
- [x] 로컬 포트/SSL 설정 확인
- [x] 로그 파일 위치 확인

### 0.3 설정 파일
- [x] `config.ini` 섹션별 역할 정리
- [x] `config.ini.production`과 차이 확인
- [x] DB 설정 확인
- [x] SSO 설정 확인
- [x] 권한 설정 확인
- [x] 업로드/보안 설정 확인
- [x] export 설정 확인
- [x] 민감값 분리 필요 항목 표시

## 1. 런타임 진입 분석

### 1.1 앱 초기화
- [x] `app.py` import 목록 분류
- [x] Flask app 생성 위치 확인
- [x] `app.secret_key` 설정 확인
- [x] static/template 설정 확인
- [x] logging 초기화 확인
- [x] 전역 상수/전역 객체 목록 작성

### 1.2 Blueprint 등록
- [x] 등록된 Blueprint 목록 작성
- [x] `add_page_routes.py`에서 생성되는 Blueprint 확인
- [x] `boards/safety_instruction.py` Blueprint 확인
- [x] `permission_api.register_permission_routes(app)` 분석
- [x] 미등록 Blueprint 후보 확인
- [x] 동일 URL 중복 등록 가능성 확인

### 1.3 요청 전후 훅
- [x] `@app.before_request` 전체 목록 작성
- [x] 첫 요청 DB sync 훅 확인
- [x] periodic sync 훅 확인
- [x] SSO 자동 리다이렉트 훅 확인
- [x] `@app.after_request` 전체 목록 작성
- [x] 캐시 헤더 훅 확인
- [x] 감사 로그 훅 확인

### 1.4 실행 진입점
- [x] `if __name__ == "__main__"` 흐름 확인
- [x] HTTP/HTTPS 포트 결정 로직 확인
- [x] SSL 인증서 사용 조건 확인
- [x] scheduler/thread 시작 조건 확인
- [x] `wsgi.py` production 진입점 확인
- [x] 개발 실행과 배포 실행 차이 정리

## 2. 라우트 전체 지도

### 2.1 라우트 목록
- [x] `app.py` 직접 라우트 전체 목록 추출
- [x] Blueprint 라우트 전체 목록 추출
- [x] `permission_api.py` 등록 라우트 목록 추출
- [x] 백업/테스트 파일의 라우트와 실제 런타임 라우트 구분
- [x] `/api` 라우트 그룹화
- [x] `/admin` 라우트 그룹화
- [x] 페이지 라우트 그룹화
- [x] SSO 라우트 그룹화
- [x] catch-all 라우트 분석

### 2.2 중복/레거시 라우트
- [x] 보드별 legacy API 확인
- [x] `/api/<board>/...` 공통 API 확인
- [x] 보드별 API와 공통 API의 기능 중복 확인
- [x] delete/restore/final-check/export/import API 분류
- [x] `change_request` 레거시 라우트 표시
- [x] `partner` 레거시 라우트 표시
- [x] 사고/안전지시서 레거시 라우트 표시

## 3. 게시판별 흐름 분석

각 게시판은 같은 체크리스트로 반복한다.

### 3.1 공통 체크 항목
- [x] 메뉴 URL 확인
- [x] 권한 코드 확인
- [x] 목록 라우트 확인
- [x] 등록 화면 라우트 확인
- [x] 상세 화면 라우트 확인
- [x] 저장 API 확인
- [x] 수정 API 확인
- [x] 삭제 API 확인
- [x] 복구 API 확인
- [x] 최종검토/상태 변경 API 확인
- [x] export API 확인
- [x] import API 확인
- [x] 첨부 다운로드 API 확인
- [x] 템플릿 3종 확인
- [x] 연결 JS 확인
- [x] Controller 사용 여부 확인
- [x] Repository 사용 여부 확인
- [x] Service 사용 여부 확인
- [x] 사용하는 DB 테이블 목록 작성
- [x] `custom_data` 사용 방식 정리
- [x] 권한 체크 위치 확인
- [x] 감사 로그 기록 여부 확인
- [x] 대표 위험 3개 기록

### 3.2 보드 목록
- [x] `partner`
- [x] `change_request`
- [x] `accident`
- [x] `safety_instruction`
- [x] `follow_sop`
- [x] `full_process`
- [x] `safe_workplace`
- [x] `subcontract_approval`
- [x] `subcontract_report`

## 3.5 실행 전 안전 계획

### 3.5.1 문서 재확인
- [x] `BASELINE_REPORT.md` 재확인
- [x] `RUNTIME_ENTRY_REPORT.md` 재확인
- [x] `ROUTE_MAP_REPORT.md` 재확인
- [x] `BOARD_FLOW_REPORT.md` 재확인
- [x] 다음 단계 전 `.md` 재확인 규칙 작성

### 3.5.2 안전 실행 설계
- [x] 직접 `python app.py` 실행 위험 정리
- [x] WSGI import 방식 우선 실행안 작성
- [x] PostgreSQL 서비스/포트 상태 확인
- [x] 백업 대상 목록 작성
- [x] `pg_dump` 백업 계획 작성
- [x] 읽기 전용 브라우저 검증 범위 작성
- [x] 쓰기 테스트 별도 승인 원칙 작성
- [x] URL drift 후보 검증 순서 작성
- [x] 중단 조건 작성

### 3.5.3 Phase 0/1 사전 실행 점검
- [x] `venv\Scripts\python.exe -m py_compile app.py wsgi.py` 성공
- [x] PostgreSQL 서비스 실행 상태 확인
- [x] `from wsgi import app` import-only 성공
- [x] 실제 `app.url_map` route 수 확인
- [x] URL drift 후보 route matching 확인
- [x] `login` endpoint 부재 확인
- [x] import-only 중 DB 구조 확인성 동작 발생 기록
- [x] `PREFLIGHT_EXECUTION_REPORT.md` 작성
- [x] `SAFE_EXECUTION_PLAN.md` 보정

## 4. 프론트엔드 연결 분석

### 4.1 템플릿 구조
- [x] `templates/base.html` 확인
- [x] `templates/index.html` 확인
- [x] 보드별 목록 템플릿 확인
- [x] 보드별 등록 템플릿 확인
- [x] 보드별 상세 템플릿 확인
- [x] 관리자 컬럼 설정 템플릿 확인
- [x] 권한 관리 템플릿 확인
- [x] 공통 include 템플릿 목록 작성
- [x] 백업 템플릿과 실제 사용 템플릿 구분

### 4.2 JavaScript 연결
- [x] `static/js/board-form.js` 역할 분석
- [x] `static/js/board-detail.js` 역할 분석
- [x] `static/js/admin-columns-common.js` 역할 분석
- [x] `static/js/list-child-support.js` 역할 분석
- [x] `static/js/popup-handler.js` 역할 분석
- [x] `static/js/universal-popup-handler.js` 역할 분석
- [x] `static/js/scoring-system.js` 역할 분석
- [x] 템플릿별 script include 매핑 작성

### 4.3 UI 기능별 흐름
- [x] 동적 필드 수집 흐름
- [x] 첨부파일 추가/삭제 흐름
- [x] 상세 내용 CKEditor 흐름
- [x] 팝업 검색 흐름
- [x] 리스트 필드/child schema 흐름
- [x] 채점 필드 흐름
- [x] 비밀번호 모달 흐름
- [x] 권한 기반 버튼 노출 흐름

## 5. DB와 데이터 흐름

### 5.1 DB 연결 계층
- [x] `db_connection.py` 분석
- [x] `db/compat.py` 분석
- [x] `db/upsert.py` 분석
- [x] `database_config.py` 분석
- [x] PostgreSQL 전용 경로 확인
- [x] SQLite 호환층 잔존 위치 기록
- [x] 커넥션 close/commit/rollback 패턴 확인

### 5.2 마이그레이션
- [x] `migrations/run_migrations.py` 분석
- [x] `001_create_core_tables.sql` 분석
- [x] `002_create_board_tables.sql` 분석
- [x] `003_seed_sections.sql` 분석
- [x] `004_create_attachments.sql` 분석
- [x] `005_create_subcontract_tables.sql` 분석
- [x] 기타 `migrations/*.sql` 역할 확인
- [x] `migration_scripts/`와 `migrations/` 차이 정리
- [x] 루트의 `FINAL_*`, `COMPLETE_*` 스크립트 사용 여부 분류

### 5.3 테이블 사용표
- [x] 게시판별 메인 테이블 정리
- [x] 게시판별 cache 테이블 정리
- [x] 게시판별 detail 테이블 정리
- [x] 게시판별 section 테이블 정리
- [x] 게시판별 column_config 테이블 정리
- [x] 첨부 테이블 구조 정리
- [x] 권한 테이블 구조 정리
- [x] 감사 로그 테이블 구조 정리
- [x] sync 상태 테이블 구조 정리
- [x] 삭제/복구 플래그 정책 정리

### 5.4 JSONB/custom_data
- [x] `custom_data` 저장 위치 정리
- [x] list 타입 필드 저장 방식 정리
- [x] popup linked field 저장 방식 정리
- [x] scoring 저장 방식 정리
- [x] `[]` 문자열/배열 이슈 재확인
- [x] 빈 문자열 삭제 정책 확인
- [x] schema 기반 검증 적용 범위 확인

## 6. 권한/SSO/보안 분석

### 6.1 권한 구조
- [x] `permission_helpers.py` 분석
- [x] `permission_api.py` 분석
- [x] `permission_utils.py` 분석
- [x] `scoped_permission_check.py` 분석
- [x] `login_id_permission_utils.py` 분석
- [x] `menu_permission_mapper.py` 분석
- [x] 최종 표준 권한 엔진 후보 표시
- [x] 권한 캐시 무효화 흐름 확인

### 6.2 라우트/API 권한 체크
- [x] 페이지 라우트별 view 권한 체크 여부
- [x] 등록/수정 API별 write 권한 체크 여부
- [x] 삭제 API별 delete 권한 체크 여부
- [x] 관리자 API 권한 체크 여부
- [x] export/import API 권한 체크 여부
- [x] debug/diagnostics 라우트 보호 여부
- [x] SSO 우회/dev-login 보호 여부

### 6.3 SSO
- [x] `/sso/dev-login` 흐름 확인
- [x] `/SSO` 흐름 확인
- [x] `/acs` 흐름 확인
- [x] `/slo` 흐름 확인
- [x] 인증서 로딩 흐름 확인
- [x] session key 표준 확인
- [x] dev/prod 설정 차이 확인

### 6.4 보안/업로드
- [x] `upload_utils.py` 분석
- [x] 허용 확장자 확인
- [x] 파일 크기 제한 확인
- [x] 파일명 sanitize 확인
- [x] 다운로드 경로 검증 확인
- [x] inline image 업로드 확인
- [x] HTML 업로드 허용 위험 검토
- [x] 평문 비밀번호/DSN 목록 작성


- [x] `AUTH_SECURITY_REPORT.md` 작성
## 7. 서비스/공통 모듈 분석

### 7.1 동적 게시판 엔진
- [x] `controllers/board_controller.py` 분석
- [x] `controllers/dynamic_board_controller.py` 분석
- [x] `repositories/boards/follow_sop_repository.py` 분석
- [x] `repositories/boards/full_process_repository.py` 분석
- [x] `repositories/boards/safe_workplace_repository.py` 분석
- [x] `repositories/boards/accident_repository.py` 분석
- [x] `repositories/boards/safety_instruction_repository.py` 분석
- [x] `repositories/boards/subcontract_repository.py` 분석
- [x] 공통화 성공/실패 지점 정리

### 7.2 컬럼/섹션/코드
- [x] `column_service.py` 분석
- [x] `board_services.py` 분석
- [x] `section_service.py` 분석
- [x] `repositories/common/board_config.py` 분석
- [x] `repositories/common/column_config_repository.py` 분석
- [x] `column_utils.py` 분석
- [x] `list_schema_utils.py` 분석
- [x] 보호 컬럼 정책 확인
- [x] child schema 정책 확인

### 7.3 검색/팝업/매핑
- [x] `search_popup_service.py` 분석
- [x] `common_search.py` 분석
- [x] `common_mapping.py` 분석
- [x] `table_mappings.py` 분석
- [x] `utils/sql_filters.py` 분석
- [x] popup 유형별 데이터 소스 확인

### 7.4 기타 공통 기능
- [x] `audit_logger.py` 분석
- [x] `notification_service.py` 분석
- [x] `access_log_helper.py` 분석
- [x] `id_generator.py` 분석
- [x] `scoring_service.py` 분석
- [x] `scoring_external_service*.py` 분석


- [x] `SERVICE_COMMON_REPORT.md` 작성
## 8. 테스트/검증 자산 분류

### 8.1 테스트 파일 분류
- [x] 실제 회귀 테스트로 사용할 파일 분류
- [x] 단발성 디버그 테스트 분류
- [x] DB 연결이 필요한 테스트 분류
- [x] 외부 서비스가 필요한 테스트 분류
- [x] 실행하면 데이터 변경 가능성이 있는 테스트 분류
- [x] 폐기 후보 테스트 분류

### 8.2 검증 명령 후보
- [x] 문법 검사 명령 정리
- [x] 특정 모듈 단위 테스트 명령 정리
- [x] Flask route 확인 명령 정리
- [x] DB schema 확인 명령 정리
- [x] 브라우저 smoke test URL 목록 작성


- [x] `TEST_ASSET_REPORT.md` 작성
## 9. 위험도 분류
작성 결과: `RISK_CLASSIFICATION_REPORT.md`

### 9.1 즉시 위험
- [x] 비밀값/DSN 하드코딩
- [x] 권한 누락 가능 API
- [x] 삭제/복구/permanent-delete API
- [x] 업로드/다운로드 경로
- [x] SSO debug/diagnostics 노출
- [x] 실행 시 조용히 묻히는 broad exception

### 9.2 중기 위험
- [x] SQLite 호환층 잔존
- [x] 보드별 구현 불일치
- [x] dynamic column schema 불일치
- [x] custom_data 타입 오염
- [x] migration 체계 이원화
- [x] 루트 스크립트 난립

### 9.3 리팩터링 후보
- [x] `change_request` Controller/Repository 분리
- [x] `partner` 계열 분리
- [x] export/import 공통화
- [x] 권한 엔진 단일화
- [x] 설정 로더 정리
- [x] SQLite 호환층 축소
- [x] 템플릿/JS 공통화

## 10. 최종 산출물

- [x] `PROJECT_AUDIT_REPORT_2026.md` 1차 보고서 확인
- [x] `RUNTIME_ENTRY_REPORT.md` 작성
- [x] `ROUTE_MAP_REPORT.md` 작성
- [x] `BOARD_FLOW_REPORT.md` 작성
- [x] `FRONTEND_CONNECTION_REPORT.md` 작성
- [x] `DB_USAGE_MAP.md` 작성
- [x] `AUTH_SECURITY_REPORT.md` 작성
- [x] `TECH_DEBT_ROADMAP.md` 작성
- [x] `STABILIZATION_PLAN.md` 작성

- [x] `SERVICE_COMMON_REPORT.md` 작성
- [x] `TEST_ASSET_REPORT.md` 작성
- [x] `RISK_CLASSIFICATION_REPORT.md` 작성
## 현재 완료 상태

- [x] 0차 감사 보고서 작성: `PROJECT_AUDIT_REPORT_2026.md`
- [x] 숨김 메모리 위치 확인: `.serena/memories/project_overview.md`
- [x] 기존 리팩터링 문서 확인: `APP_ROUTE_REFACTOR_ANALYSIS.md`
- [x] 전체 파일 수/라우트 수/민감 문자열 수 1차 계량
- [x] 주요 Python 파일 일부 문법 검사
- [ ] 실제 서버 실행 검증
- [ ] DB 연결 검증
- [ ] 브라우저 화면 검증
