# 드롭다운 코드 시스템 현재 상황 (2025-08-23)

## 🚀 프로젝트 개요
Flask 포털 시스템의 드롭다운 옵션을 단순 JSON 배열에서 코드-값 매핑 방식으로 전환하는 프로젝트

### 왜 코드-값 매핑인가?
- **기존 방식**: `["진행중", "완료", "취소"]` 
- **새 방식**: `[{code: "COLUMN3_001", value: "진행중"}, ...]`
- **장점**: 표시 값 변경해도 기존 데이터 유지, 다국어 지원 가능

## ✅ 완료된 작업 (Phase 1-3)

### Phase 1: 기초 구축
- ✅ `dropdown_option_codes` 테이블 생성
- ✅ 기본 API 엔드포인트 구현
- ✅ 관리자 UI 개발 (v2, v3, enhanced, simplified 버전)

### Phase 2: 핵심 기능
- ✅ 드롭다운 코드 CRUD 완성
- ✅ 엑셀형 편집기 UI (드래그앤드롭, 자동저장)
- ✅ 감사 로그 시스템 (`dropdown_code_audit` 테이블)
- ✅ 코드 자동 생성 (COLUMN_XXX 형식)

### Phase 3: 시스템 통합
- ✅ 사고 등록/조회 페이지 연동
- ✅ 협력사 기준정보 페이지 연동
- ✅ 기존 데이터 마이그레이션 (13건)
- ✅ DictAsAttr 객체 처리 버그 수정

### Phase 4: 통합 개선 (진행중)
- ✅ 기존 admin-accident-columns.html과 simplified 버전 통합
- ✅ 드롭다운 생성 시 자동 코드 생성
- ✅ 컬럼 삭제 시 관련 코드 비활성화
- ✅ 타입 변경 시 코드 처리

## 🔧 주요 파일 구조

### 백엔드 (app.py)
```python
# 주요 함수들
- get_dropdown_options_for_display(column_key)  # 코드 매핑 형식으로 옵션 반환
- convert_code_to_value(column_key, code)       # 코드를 값으로 변환
- convert_accident_codes_to_values()            # 일괄 변환

# API 엔드포인트
- GET  /api/dropdown-codes/<column_key>         # 코드 조회
- POST /api/dropdown-codes                      # 코드 저장
- GET  /api/dropdown-codes/<column_key>/history # 변경 이력
```

### 프론트엔드
- `admin-accident-columns.html` - 메인 컬럼 관리 페이지
- `admin-accident-columns-simplified.html` - 코드 편집기 (embedded 모드 지원)
- `accident-register.html` - 사고 등록 (코드로 저장)
- `partner-accident.html` - 협력사 사고 조회 (값으로 표시)

### 데이터베이스
```sql
-- dropdown_option_codes 테이블
CREATE TABLE dropdown_option_codes (
    id INTEGER PRIMARY KEY,
    column_key TEXT,
    option_code TEXT,       -- COLUMN3_001
    option_value TEXT,      -- "진행중"
    display_order INTEGER,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- dropdown_code_audit 테이블 (변경 이력)
CREATE TABLE dropdown_code_audit (
    id INTEGER PRIMARY KEY,
    column_key TEXT,
    action TEXT,            -- CREATE/UPDATE/DELETE
    old_value TEXT,
    new_value TEXT,
    ip_address TEXT,
    user_agent TEXT,
    created_at TIMESTAMP
);
```

## 🐛 현재 이슈

### 1. Embedded 모드 UI 문제
- **문제**: Top Bar가 여전히 표시됨
- **시도한 해결책**: CSS !important로 강제 숨김 처리
- **상태**: 부분적 해결, 완전하지 않음

### 2. 저장 후 창 닫기
- **문제**: 저장 후 창이 자동으로 닫히지 않음
- **시도한 해결책**: setTimeout으로 2초 후 window.close()
- **상태**: 작동하지 않음

### 3. 데이터 지속성
- **문제**: 저장 후 다시 열면 데이터가 초기화됨
- **원인**: API 응답 형식 불일치
- **해결**: 응답 형식 통일 (`{success: true, codes: [...]}`)

### 4. 드롭다운 옵션 표시
- **문제**: 처리상태 드롭다운에 1개 옵션만 표시
- **원인**: 데이터 로드 또는 변환 로직 문제
- **상태**: 디버깅 필요

## 📝 다음 작업 필요 사항

1. **Embedded 모드 완전 분리**
   - 별도 템플릿 파일 생성 고려
   - 또는 iframe 대신 모달 사용

2. **저장 로직 개선**
   - 저장 후 부모 창과의 통신 개선
   - postMessage 대신 직접 callback

3. **데이터 일관성**
   - 모든 페이지에서 동일한 데이터 형식 사용
   - 마이그레이션 스크립트 재실행

4. **UI/UX 개선**
   - 코드 자동 생성 로직 안정화
   - 에러 처리 강화

## 🚀 실행 방법

```bash
# 1. 서버 실행
python app.py

# 2. 관리자 페이지 접속
http://127.0.0.1:5000/admin/accident-columns

# 3. 코드 편집기 (simplified)
http://127.0.0.1:5000/admin/accident-columns-simplified

# 4. 마이그레이션 실행 (필요시)
python migrate_all_accident_data.py
```

## 📌 중요 결정사항

1. **코드 형식**: `{COLUMN_KEY}_{번호}` (예: COLUMN3_001)
2. **Soft Delete**: is_active 플래그 사용
3. **변경 이력**: 모든 CRUD 작업 audit 테이블에 기록
4. **하위 호환성**: 기존 JSON 형식도 지원

## 🔗 참고 링크

- GitHub: https://github.com/dltkdrlf3579-sys/flaskApp-project
- 프로젝트 문서: DROPDOWN_CODE_MAPPING_PROJECT.md
- 개발 가이드: DEVELOPMENT_GUIDELINES.md

---

**마지막 업데이트**: 2025-08-23 오후
**작업자**: Claude Code Assistant
**상태**: Phase 4 진행중, 일부 버그 수정 필요