# 3단계 게시판별 흐름 분석 보고서

작성일: 2026-06-13

## 3단계의 의미

3단계는 2단계의 URL 지도를 업무 게시판 단위로 다시 묶는 단계다.

이번 단계에서는 다음을 확인했다.

- 메뉴 URL
- 권한 코드
- 목록/등록/상세/저장/수정 라우트
- 삭제/복구/최종검토/export/import 라우트
- 템플릿 3종
- 연결 JS와 공통 include
- Controller/Repository/Service 사용 여부
- DB 테이블과 `custom_data` 사용 방식
- 감사 로그 기록 위치
- 프론트 URL과 백엔드 라우트의 정적 불일치 후보

이번 단계에서도 앱 실행, DB 접속, 브라우저 테스트, 코드 수정은 하지 않았다.

## 분석 대상 게시판

메뉴 설정과 라우트 기준으로 다음 9개 보드를 분석 대상으로 확정했다.

| 보드 | 메뉴 URL | 표시명 |
| --- | --- | --- |
| `partner` | `/partner-standards` | 협력사 기준정보 |
| `change_request` | `/partner-change-request` | 기준정보 변경요청 |
| `accident` | `/accident` | 협력사 사고 |
| `safety_instruction` | `/safety-instruction` | 환경안전 지시서 |
| `follow_sop` | `/follow-sop` | Follow SOP |
| `full_process` | `/full-process` | Full Process |
| `safe_workplace` | `/safe-workplace` | 안전한 일터 |
| `subcontract_approval` | `/subcontract-approval` | 산안법 도급승인 |
| `subcontract_report` | `/subcontract-report` | 화관법 도급신고 |

## 전체 구조 요약

현재 게시판 구조는 세 그룹으로 나뉜다.

| 그룹 | 보드 | 구조 |
| --- | --- | --- |
| 레거시 중심 | `partner`, `change_request` | `app.py` 직접 라우트와 직접 SQL 중심 |
| 부분 분리 | `accident`, `safety_instruction` | Controller/Repository가 있지만 컬럼/삭제/export는 `app.py`에 잔존 |
| 신형 동적 보드 | `follow_sop`, `full_process`, `safe_workplace`, `subcontract_approval`, `subcontract_report` | Blueprint + Controller + Repository 중심, 단 일부 보조 API는 `app.py` |

## 보드별 흐름

### `partner`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/partner-standards` |
| 권한 코드 | `VENDOR_MGT` |
| 목록 | `GET /partner-standards` |
| 상세 | `GET /partner/<business_number>`, `GET /partner-detail/<business_number>` |
| 등록 | 명확한 신규 등록 페이지 없음 |
| 수정 | `POST /update-partner` |
| 삭제 | `POST /api/partners/delete` |
| 복구 | `POST /api/partners/restore` |
| export | `GET /api/partners/export` |
| import | 별도 import 라우트 없음 |
| 첨부 | `GET /partner-attachments/<business_number>`, `GET /download/<int:attachment_id>` |
| 템플릿 | `partner-standards.html`, `partner-detail.html` |
| Controller/Repository | 전용 Controller/Repository 없음 |
| 주요 테이블 | `partners_cache`, `partner_details`, `partner_attachments` |
| `custom_data` | 핵심 흐름은 아님 |
| 감사 로그 | 전용 `record_board_action` 호출은 확인되지 않음. 공통 after_request 감사 로그 대상 |

`partner`는 가장 오래된 방식에 가깝다. 협력사 기준정보는 외부/마스터 데이터 성격이 강하고, 등록보다 조회/수정/삭제/복구/export 중심이다.

### `change_request`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/partner-change-request` |
| 권한 코드 | `REFERENCE_CHANGE` |
| 목록 | `GET /partner-change-request` |
| 등록 화면 | `GET /change-request-register` |
| 상세 | `GET /change-request-detail/<int:request_id>` |
| 저장 | `POST /register-change-request`, `POST /api/partner-change-request` |
| 수정 | `POST /update-change-request` |
| 삭제 | `POST /api/change-requests/delete` |
| 복구 | 별도 복구 라우트 없음 |
| 최종검토/상태 | 별도 최종검토 라우트 없음. status는 저장/수정 데이터에 포함되는 구조 |
| export | `GET /api/change-requests/export` |
| import | 별도 import 라우트 없음 |
| 첨부 | `change_request_attachments`를 `AttachmentService`로 사용 |
| 템플릿 | `partner-change-request.html`, `change-request-register.html`, `change-request-detail.html` |
| Controller/Repository | 전용 Controller/Repository 없음 |
| Service | `ColumnConfigService`, `AttachmentService` 사용 |
| 주요 테이블 | `partner_change_requests`, `change_requests`, `change_requests_cache`, `change_request_details`, `change_request_column_config`, `change_request_attachments` |
| `custom_data` | 강하게 사용. `change_reason`, `detailed_content`, 동적 필드 저장에 사용 |
| 감사 로그 | 전용 `record_board_action` 호출은 확인되지 않음. 공통 after_request 감사 로그 대상 |

`change_request`는 레거시성이 가장 강하다. `partner_change_requests`, `change_requests`, `change_requests_cache`가 함께 보이고, 공통 `/api/<board>/...` 체계와도 URL 형태가 겹친다.

### `accident`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/accident` |
| 권한 코드 | `ACCIDENT_MGT` |
| 목록 | `GET /accident` |
| 등록 화면 | `GET /accident-register` |
| 상세 | `GET /accident-detail/<accident_id>` |
| 저장 | `POST /register-accident` |
| 수정 | `POST /update-accident` |
| 삭제 | `POST /api/accidents/delete` |
| 복구 | `POST /api/accidents/restore` |
| 영구삭제 | `POST /api/accidents/permanent-delete` |
| 최종검토 | 별도 final-check 라우트 없음 |
| export | `GET /api/accident-export` |
| import | `POST /api/accident-import` |
| 첨부 | `accident_attachments`, `GET /download/<board_type>/<int:attachment_id>` |
| 템플릿 | `partner-accident.html`, `accident-register.html`, `accident-detail.html` |
| Controller/Repository | `AccidentController`, `AccidentRepository` 사용 |
| Service | 컬럼/섹션/첨부/업로드 관련 서비스 혼재 |
| 주요 테이블 | `accidents_cache`, `accident_column_config`, `accident_sections`, `accident_attachments` |
| `custom_data` | 매우 강하게 사용. K사고 원본 필드 보존과 동적 필드 병합 로직 존재 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

`accident`는 Controller/Repository로 옮겨가는 중이지만, `app.py`에 레거시 로직이 많이 남아 있다. 특히 수정 로직과 `custom_data` 병합 로직은 복잡하다.

### `safety_instruction`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/safety-instruction` |
| 권한 코드 | `SAFETY_INSTRUCTION` |
| 목록 | `GET /safety-instruction` |
| 등록 화면 | `GET /safety-instruction-register` |
| 상세 | `GET /safety-instruction-detail/<issue_number>` |
| 저장 | `POST /register-safety-instruction` |
| 수정 | `POST /update-safety-instruction` |
| 삭제 | `POST /api/safety-instructions/delete` |
| 복구 | `POST /api/safety-instruction/restore` |
| 최종검토 | 별도 final-check 라우트 없음 |
| export | `GET /api/safety-instruction-export` |
| import | 백엔드 전용 import 라우트 없음 |
| 첨부 | `safety_instruction_attachments` |
| 템플릿 | `safety-instruction.html`, `safety-instruction-register.html`, `safety-instruction-detail.html` |
| Controller/Repository | `SafetyInstructionController`, `SafetyInstructionRepository` 사용 |
| Service | 컬럼/섹션/첨부/점수계산 관련 서비스 |
| 주요 테이블 | `safety_instructions`, `safety_instruction_column_config`, `safety_instruction_sections`, `safety_instruction_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

정적 분석상 `safety-instruction.html`에 `POST /api/accident-import` 호출이 있다. 안전지시서 전용 import 라우트는 확인되지 않았다. 복사/붙여넣기 잔재 또는 미완성 기능 후보로 보인다.

### `follow_sop`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/follow-sop` |
| 권한 코드 | `FOLLOW_SOP` |
| 목록 | `GET /follow-sop` |
| 등록 화면 | `GET /follow-sop-register` |
| 상세 | `GET /follow-sop-detail/<work_req_no>` |
| 저장 | `POST /register-follow-sop` |
| 수정 | `POST /update-follow-sop` |
| 삭제 | `POST /api/follow-sop/delete` |
| 복구 | `POST /api/follow-sop/restore` |
| 최종검토 | `POST /api/follow-sop/final-check` |
| export | 백엔드 `GET /api/follow-sop-export` |
| import | 별도 import 라우트 없음 |
| 첨부 | `follow_sop_attachments` |
| 템플릿 | `follow-sop.html`, `follow-sop-register.html`, `follow-sop-detail.html` |
| Controller/Repository | `FollowSopController`, `FollowSopRepository` 사용 |
| Service | 동적 보드 컨트롤러, 컬럼/섹션/첨부 서비스 |
| 주요 테이블 | `follow_sop`, 후보 `follow_sop_cache`, `followsop_cache`, `follow_sop_column_config`, `follow_sop_sections`, `follow_sop_details`, `follow_sop_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

정적 분석상 `follow-sop.html`의 export JS는 `/api/${boardPageConfig.slug}/export`를 호출한다. 하지만 백엔드 라우트는 `/api/follow-sop-export`다. 실행 시 export 버튼이 실패할 가능성이 있다.

### `full_process`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/full-process` |
| 권한 코드 | `FULL_PROCESS` |
| 목록 | `GET /full-process` |
| 등록 화면 | `GET /full-process-register` |
| 상세 | `GET /full-process-detail/<fullprocess_number>` |
| 저장 | `POST /register-full-process` |
| 수정 | `POST /update-full-process` |
| 삭제 | `POST /api/full-process/delete` |
| 복구 | `POST /api/full-process/restore` |
| 최종검토 | `POST /api/full-process/final-check` |
| export | `GET /api/full-process-export` |
| import | 별도 full-process import 라우트 없음 |
| 첨부 | `full_process_attachments` |
| 템플릿 | `full-process.html`, `full-process-register.html`, `full-process-detail.html` |
| Controller/Repository | `FullProcessController`, `FullProcessRepository` 사용 |
| Service | 동적 보드 컨트롤러, 컬럼/섹션/첨부/점수계산 |
| 주요 테이블 | `full_process`, 후보 `full_process_cache`, `fullprocess_cache`, `full_process_column_config`, `full_process_sections`, `full_process_details`, `full_process_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

정적 분석상 `full-process.html`에도 `POST /api/accident-import` 호출이 있다. Full Process 전용 import 라우트는 확인되지 않았다.

### `safe_workplace`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/safe-workplace` |
| 권한 코드 | `SAFE_WORKPLACE` |
| 목록 | `GET /safe-workplace` |
| 등록 화면 | `GET /safe-workplace-register` |
| 상세 | `GET /safe-workplace-detail/<safeplace_no>` |
| 저장 | `POST /register-safe-workplace` |
| 수정 | `POST /update-safe-workplace` |
| 삭제 | `POST /api/safe-workplace/delete` |
| 복구 | `POST /api/safe-workplace/restore` |
| 최종검토 | `POST /api/safe-workplace/final-check` |
| export | `GET /api/safe-workplace-export` |
| import | 별도 import 라우트 없음 |
| 첨부 | `safe_workplace_attachments` |
| 템플릿 | `safe-workplace.html`, `safe-workplace-register.html`, `safe-workplace-detail.html` |
| Controller/Repository | `SafeWorkplaceController`, `SafeWorkplaceRepository` 사용 |
| Service | 동적 보드 컨트롤러, 컬럼/섹션/첨부 |
| 주요 테이블 | `safe_workplace`, 후보 `safe_workplace_cache`, `safe_workplace_column_config`, `safe_workplace_sections`, `safe_workplace_details`, `safe_workplace_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

주의점은 `repositories/common/board_config.py`의 `safe_workplace` 설정에는 `section_table`, `detail_table`, `table_candidates`가 명시되어 있지 않지만, `SafeWorkplaceRepository`는 자체적으로 `safe_workplace_sections`, `safe_workplace_details`, `safe_workplace_cache`를 사용한다는 점이다. 설정과 구현이 분산되어 있다.

### `subcontract_approval`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/subcontract-approval` |
| 권한 코드 | `SUBCONTRACT_APPROVAL` |
| 목록 | `GET /subcontract-approval` |
| 등록 화면 | `GET /subcontract-approval-register` |
| 상세 | `GET /subcontract-approval-detail/<approval_number>` |
| 저장 | `POST /register-subcontract-approval` |
| 수정 | `POST /update-subcontract-approval` |
| 삭제 | 전용 라우트 없음. `POST /api/<board_type>/delete`가 `/api/subcontract-approval/delete`를 처리할 가능성 |
| 복구 | 별도 복구 라우트 없음 |
| 최종검토 | 백엔드 라우트 없음 |
| export | 백엔드 라우트 없음 |
| import | 별도 import 라우트 없음 |
| 첨부 | `subcontract_approval_attachments` |
| 템플릿 | `subcontract-approval.html`, `subcontract-approval-register.html`, `subcontract-approval-detail.html` |
| Controller/Repository | `SubcontractApprovalController`, `SubcontractApprovalRepository` 사용 |
| Service | 동적 보드 컨트롤러, 컬럼/섹션/첨부 |
| 주요 테이블 | `subcontract_approval`, `subcontract_approval_column_config`, `subcontract_approval_sections`, `subcontract_approval_details`, `subcontract_approval_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

정적 분석상 템플릿은 `/api/${boardPageConfig.slug}/final-check`와 `/api/${boardPageConfig.slug}/export`를 호출하는 공통 JS를 가진다. 하지만 `subcontract-approval` 전용 final-check/export 백엔드 라우트는 확인되지 않았다.

### `subcontract_report`

| 항목 | 내용 |
| --- | --- |
| 메뉴 URL | `/subcontract-report` |
| 권한 코드 | `SUBCONTRACT_REPORT` |
| 목록 | `GET /subcontract-report` |
| 등록 화면 | `GET /subcontract-report-register` |
| 상세 | `GET /subcontract-report-detail/<report_number>` |
| 저장 | `POST /register-subcontract-report` |
| 수정 | `POST /update-subcontract-report` |
| 삭제 | 전용 라우트 없음. `POST /api/<board_type>/delete`가 `/api/subcontract-report/delete`를 처리할 가능성 |
| 복구 | 별도 복구 라우트 없음 |
| 최종검토 | 백엔드 라우트 없음 |
| export | 백엔드 라우트 없음 |
| import | 별도 import 라우트 없음 |
| 첨부 | `subcontract_report_attachments` |
| 템플릿 | `subcontract-report.html`, `subcontract-report-register.html`, `subcontract-report-detail.html` |
| Controller/Repository | `SubcontractReportController`, `SubcontractReportRepository` 사용 |
| Service | 동적 보드 컨트롤러, 컬럼/섹션/첨부 |
| 주요 테이블 | `subcontract_report`, `subcontract_report_column_config`, `subcontract_report_sections`, `subcontract_report_details`, `subcontract_report_attachments` |
| `custom_data` | 강하게 사용 |
| 감사 로그 | 목록/등록/상세/저장/수정에 `record_menu_view`, `record_board_action` 사용 |

`subcontract_report`도 `subcontract_approval`과 동일하게 final-check/export 프론트 호출과 백엔드 라우트 불일치 후보가 있다.

## 공통 프론트 구조

등록/상세 화면은 대체로 다음 include를 사용한다.

- `templates/includes/board_form_scripts.html`
- `static/js/board-form.js`
- `static/js/board-detail.js`
- 일부 화면에서 `static/js/ckeditor-simple.js`

`board-detail.js`는 템플릿에서 전달한 endpoint를 받아 `FormData`를 구성한다.

공통으로 수집하는 데이터는 다음과 같다.

- 동적 섹션 필드
- `custom_data`
- 첨부 파일 메타데이터
- 삭제 예정 첨부 ID
- 작성자/수정자 정보

즉 신형 보드의 핵심 저장 구조는 "템플릿에서 endpoint 지정 → `BoardDetail.createUpdater` → Repository 저장" 흐름이다.

## 정적 불일치 후보

실행 전 정적 분석으로 발견한 불일치 후보는 다음과 같다.

| 후보 | 프론트 호출 | 백엔드 확인 결과 |
| --- | --- | --- |
| Follow SOP export | `/api/follow-sop/export` | 실제 라우트는 `/api/follow-sop-export` |
| Subcontract Approval export | `/api/subcontract-approval/export` | 백엔드 라우트 없음 |
| Subcontract Report export | `/api/subcontract-report/export` | 백엔드 라우트 없음 |
| Subcontract Approval final-check | `/api/subcontract-approval/final-check` | 백엔드 라우트 없음 |
| Subcontract Report final-check | `/api/subcontract-report/final-check` | 백엔드 라우트 없음 |
| Safety Instruction import | `/api/accident-import` 호출 | 안전지시서 전용 import 라우트 없음 |
| Full Process import | `/api/accident-import` 호출 | Full Process 전용 import 라우트 없음 |

삭제의 경우 `/api/subcontract-approval/delete`, `/api/subcontract-report/delete`는 전용 라우트가 없지만 `POST /api/<board_type>/delete` 동적 라우트가 받을 가능성이 있다. 이 부분은 실행 검증에서 확인해야 한다.

## 대표 위험 3개

### 1. 프론트/백엔드 URL drift

템플릿이 호출하는 URL과 실제 Flask 라우트가 서로 다른 후보가 있다. 특히 export/final-check/import 쪽이 위험하다.

### 2. 보드 구조의 세대 차이

`partner`, `change_request`, `accident`, `safety_instruction`, 신형 동적 보드의 구현 방식이 서로 다르다.

한 번에 공통화하려고 하면 기존 동작을 깨뜨릴 가능성이 높다.

### 3. `custom_data` 의존도

대부분의 동적 보드가 `custom_data`에 많은 필드를 저장한다.

DB 컬럼으로 존재하는 값과 `custom_data`에만 존재하는 값이 섞일 수 있으므로, 리팩터링 전에는 보드별 저장 규칙을 더 확인해야 한다.

## 3단계 결론

현재 프로젝트는 "게시판이 많다"보다 "게시판마다 세대와 저장 방식이 다르다"가 핵심 문제다.

안전한 다음 순서는 다음이다.

1. 바로 리팩터링하지 않는다.
2. 먼저 실행 전 검증 계획을 만든다.
3. export/final-check/import URL 불일치 후보를 브라우저로 실제 확인한다.
4. 수정이 필요하면 보드 하나, 기능 하나씩만 고친다.

다음 단계는 4단계 프론트엔드 연결 분석이다. 다만 3단계에서 이미 URL drift 후보가 나왔으므로, 4단계 전에 "안전 실행 계획"을 별도 단계로 끼워 넣는 것도 가능하다.
