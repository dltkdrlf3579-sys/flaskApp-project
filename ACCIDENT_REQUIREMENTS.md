# 사고 페이지 개선 요구사항 및 기술 검토

**작성일**: 2025-08-21  
**프로젝트**: 상생EHS Portal - 협력사 사고 관리 시스템 고도화

---

## 📋 요구사항 분석

### 1. 현재 상태 vs 목표 상태

| 구분 | 현재 (협력사 정보) | 현재 (사고 페이지) | 목표 (사고 페이지) |
|------|-------------------|-------------------|-------------------|
| **데이터 연동** | 간단한 상세내용 + 첨부파일 | 정적 컬럼1~10 | 일부 연동 + 담당자 입력 |
| **컬럼 관리** | 고정 구조 | 하드코딩된 컬럼1~10 | 동적 컬럼 추가/삭제/수정 |
| **입력 방식** | 단순 텍스트 | 단순 텍스트 | 다양한 입력 타입 |
| **데이터 표준화** | X | X | 업체명/사업자번호 표준화 |
| **대량 처리** | X | X | Excel Import/Export |

### 2. 핵심 요구사항

#### A. 유연한 컬럼 관리 시스템
```
업무담당자가 직접 컬럼을 추가/삭제/수정할 수 있어야 함
- 컬럼명 변경
- 컬럼 순서 조정  
- 컬럼 타입 설정 (텍스트/드롭다운/날짜/팝업선택)
- 실시간 적용 (개발자 개입 없이)
```

#### B. 다양한 입력 컨트롤
1. **드롭다운**: 사전 정의된 선택 옵션
2. **날짜 선택기**: 정확한 날짜 입력
3. **표준화 팝업**: 
   - 업체명 선택 → 표준 업체명 + 사업자번호 자동 입력
   - 담당자 선택 → 표준 이름 + 부서/직책 자동 입력

#### C. Excel 연동
- **Import**: 대량 데이터 업로드
- **Export**: 현재 목록 추출

---

## 🔧 기술적 검토 사항

### 1. 동적 컬럼 관리 구조

#### 데이터베이스 설계
```sql
-- 컬럼 정의 테이블
CREATE TABLE accident_column_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key VARCHAR(50) UNIQUE,          -- 내부 키 (column1, column2...)
    column_name VARCHAR(100),               -- 화면 표시명
    column_type VARCHAR(20),                -- text, dropdown, date, popup_company, popup_person
    column_order INTEGER,                   -- 표시 순서
    is_active BOOLEAN DEFAULT TRUE,         -- 활성 여부
    dropdown_options TEXT,                  -- JSON: ["옵션1", "옵션2"]
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 사고 상세 데이터 (기존 구조 확장)
ALTER TABLE accidents_cache ADD COLUMN custom_data TEXT;  -- JSON으로 동적 데이터 저장
```

#### JSON 구조 예시
```json
{
  "custom_field_1": "값1",
  "custom_field_2": "2025-01-15",
  "company_standard": {
    "name": "삼성전자㈜",
    "business_number": "124-81-00998"
  }
}
```

### 2. 컬럼 관리 인터페이스

#### A. 관리자 페이지 필요
```
/admin/accident-columns  
- 컬럼 목록 조회
- 드래그&드롭 순서 변경
- 컬럼 추가/편집/삭제
- 실시간 미리보기
```

#### B. 컬럼 타입별 설정
```javascript
columnTypes = {
    'text': { hasOptions: false },
    'dropdown': { hasOptions: true, optionsFormat: 'array' },
    'date': { hasOptions: false },
    'popup_company': { hasOptions: false, popupType: 'company' },
    'popup_person': { hasOptions: false, popupType: 'person' }
}
```

### 3. 표준화 팝업 시스템

#### A. 업체 선택 팝업
```sql
-- 표준 업체 목록 (기존 partners_cache 활용)
SELECT company_name, business_number 
FROM partners_cache 
WHERE company_name LIKE '%검색어%'
ORDER BY company_name;
```

#### B. 담당자 선택 팝업
```sql
-- 담당자 마스터 테이블 (신규 생성 필요)
CREATE TABLE person_master (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50),
    department VARCHAR(100),
    position VARCHAR(50),
    company_name VARCHAR(100),
    phone VARCHAR(20),
    email VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE
);
```

### 4. Excel Import/Export

#### A. Import 처리 흐름
```python
# pandas 활용
def import_accidents_excel(file_path):
    df = pd.read_excel(file_path)
    # 1. 컬럼 매핑 확인
    # 2. 데이터 검증
    # 3. 표준화 처리 (업체명 등)
    # 4. DB 저장
    # 5. 오류 리포트 생성
```

#### B. Export 기능
```python
# 현재 검색 조건 + 동적 컬럼 반영
def export_accidents_excel(search_params, column_config):
    # 1. 검색 조건으로 데이터 조회
    # 2. 동적 컬럼 설정 적용
    # 3. Excel 파일 생성
    # 4. 다운로드 제공
```

---

## 📊 복잡도 분석

### 난이도별 분류

#### 🟢 **쉬움** (1주 이내)
- 정적 컬럼을 동적 컬럼으로 변환
- 기본 드롭다운, 날짜 선택기
- Excel Export 기본 기능

#### 🟡 **보통** (2-3주)
- 컬럼 관리 인터페이스 구축
- 표준화 팝업 (업체/담당자 선택)
- Excel Import + 검증 로직

#### 🔴 **어려움** (4주 이상)
- 드래그&드롭 컬럼 순서 변경
- 실시간 컬럼 구조 변경
- 복잡한 데이터 검증 + 오류 처리
- 대량 데이터 처리 최적화

---

## 🚀 단계별 개발 계획 및 진행 현황

### ✅ Phase 1: 기반 구조 구축 (완료 - 2025-08-21)
1. **DB 스키마 설계** ✅
   - `accident_column_config` 테이블 생성 완료
   - `accidents_cache` 테이블에 `custom_data` JSON 컬럼 추가 완료
   - 기본 10개 컬럼 설정 데이터 입력 완료 (조치사항, 재발방지대책, 처리상태 등)
   - `person_master` 테이블 생성 및 샘플 데이터 5명 입력 완료

2. **백엔드 API 개발** ✅
   - GET `/api/accident-columns`: 동적 컬럼 설정 조회 API 구현
   - POST `/api/accident-columns`: 컬럼 추가 API 구현
   - PUT `/api/accident-columns/<id>`: 컬럼 수정 API 구현
   - GET `/api/person-master`: 담당자 검색 API 구현
   - 사고 목록 페이지에서 동적 컬럼 렌더링 로직 구현

### ✅ Phase 2: 사고 상세 페이지 동적 입력 폼 (완료 - 2025-08-22)
1. **추가 기입정보 섹션 구현** ✅
   - 기본정보와 동일한 4열 레이아웃 구성
   - 동적 컬럼별 입력 폼 자동 생성
   - 섹션 접기/펼치기 기능

2. **다양한 입력 컨트롤 구현** ✅
   - 텍스트 입력 (`text` 타입)
   - 드롭다운 선택 (`dropdown` 타입) - 처리상태 등
   - 날짜 선택기 (`date` 타입) - 완료예정일 등
   - 담당자 선택 팝업 UI (`popup_person` 타입)
   - 업체 선택 팝업 UI (`popup_company` 타입)

3. **데이터 저장 기능** ✅
   - JavaScript로 동적 컬럼 데이터 수집
   - `/update-accident` API에서 `custom_data` JSON 처리
   - `accidents_cache` 테이블에 저장 로직 구현
   - 기존 상세내용/첨부파일 저장과 통합

### ⏳ Phase 3: 컬럼 관리 인터페이스 (예정)
1. **관리자 페이지**
   - `/admin/accident-columns` 라우트
   - 컬럼 추가/편집/삭제/순서변경 UI
   - 컬럼 타입별 옵션 설정
   - 실시간 미리보기

2. **권한 관리**
   - 컬럼 설정 변경 권한
   - 변경 이력 추적

### ⏳ Phase 4: Excel 연동 (예정)
1. **Export 기능**
   - 현재 검색 조건 반영
   - 동적 컬럼 포함
   - 한글 인코딩 처리

2. **Import 기능**
   - 템플릿 다운로드
   - 대량 데이터 업로드
   - 데이터 검증 및 오류 리포트

### ⏳ Phase 5: 고도화 (선택사항)
1. **표준화 팝업 완성**
   - 담당자 선택 팝업 실제 구현
   - 업체 선택 팝업 실제 구현
   - 검색 및 페이징 기능

2. **UX 개선**
   - 드래그&드롭 컬럼 순서 변경
   - 자동 저장 기능
   - 변경사항 표시

3. **성능 최적화**
   - 대량 데이터 처리
   - 캐싱 전략

---

## ⚠️ 주의사항 및 리스크

### 1. 데이터 정합성
- 컬럼 구조 변경 시 기존 데이터 보존
- JSON 필드 검증 로직 필수

### 2. 사용자 인터페이스
- 너무 복잡하면 사용자 혼란
- 단계적 도입 권장

### 3. 성능
- JSON 컬럼 검색 성능 한계
- 인덱싱 전략 필요

### 4. 보안
- 컬럼 설정 변경 권한 관리
- 파일 업로드 보안 검증

---

## 📊 현재 구현 상태 요약 (2025-08-22)

### 완료된 기능
1. **동적 컬럼 시스템** ✅
   - DB 구조 완성 (3개 테이블)
   - 10개 기본 컬럼 설정
   - API 4개 구현

2. **사고 상세 페이지 개선** ✅
   - "추가 기입정보" 섹션 추가
   - 다양한 입력 타입 지원
   - 저장 기능 완성

### 현재 사용 가능한 기능
- 사고 목록에서 동적 컬럼 표시
- 사고 상세 페이지에서 추가 정보 입력/수정
- 텍스트, 드롭다운, 날짜, 담당자, 업체 입력

### 다음 단계 권장사항
1. **Phase 3 (컬럼 관리)**: 업무담당자가 직접 컬럼 추가/수정
2. **Phase 4 (Excel)**: 대량 데이터 처리
3. **Phase 5 (고도화)**: 팝업 실제 구현, UX 개선

## 🤝 의사결정 필요 사항

1. **컬럼 관리 권한**
   - 모든 사용자 vs 관리자만?
   - 변경 이력 추적 필요 여부?

2. **Excel 템플릿**
   - 동적 컬럼 반영 방식
   - 필수/선택 필드 구분

3. **표준화 팝업**
   - 담당자/업체 마스터 데이터 관리 주체
   - 실시간 연동 vs 주기적 동기화

---

**현재 Phase 2까지 완료되어 기본적인 동적 컬럼 입력/저장이 가능합니다.**
**업무 활용을 시작하면서 추가 요구사항을 파악하는 것을 권장합니다.**