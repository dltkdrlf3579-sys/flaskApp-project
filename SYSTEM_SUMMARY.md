# Flask Portal 시스템 요약 (리셋 후 참조용)

## 📋 시스템 개요
- **Flask 기반 협력사 정보 관리 포털**
- **DCInside 스타일 호버 네비게이션**
- **고급 검색 기능 (Excel 필터 스타일)**
- **203개 샘플 데이터 자동 생성**

## 🏗️ 파일 구조
```
flask-portal/
├── app.py (메인 Flask 앱)
├── requirements.txt
├── config/menu.py (메뉴 설정)
├── templates/
│   ├── base.html (공통 레이아웃)
│   ├── index.html
│   ├── page.html
│   ├── edit.html
│   ├── unlock.html
│   ├── partner-standards.html (협력사 검색 페이지)
│   └── partner-detail.html (협력사 상세 페이지)
└── portal.db (SQLite 자동 생성)
```

## 🎯 핵심 기능

### 1. 상단 네비게이션 (DCInside 스타일)
- **데스크톱**: 마우스 호버로 드롭다운 열림
- **모바일**: 클릭/탭으로 토글
- **색상**: 파란색 배경 (#2f5fd3) + 흰 글자
- **브랜드**: "상생EHS 업무 포탈"

### 2. 메뉴 구조 (config/menu.py)
```python
MENU_CONFIG = [
    {
        "title": "협력사 정보",
        "submenu": [
            {"title": "협력사 기준정보", "url": "partner-standards"},
            {"title": "공지사항", "url": "safety-notice"},
            {"title": "사고사례", "url": "safety-case"},
        ],
    },
    {"title": "협력사", "submenu": [...]},
    {"title": "자료실", "submenu": [...]}
]
```

### 3. 데이터베이스 스키마 (partners 테이블)
```sql
CREATE TABLE partners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_name TEXT NOT NULL,
    business_number TEXT,
    representative TEXT,
    regular_workers INTEGER,
    business_type TEXT,
    business_type_major TEXT,      -- 대분류
    business_type_minor TEXT,      -- 소분류 (콤마 구분)
    establishment_date TEXT,
    capital_amount BIGINT,
    annual_revenue BIGINT,
    main_products TEXT,
    certification TEXT,
    safety_rating TEXT,
    contact_person TEXT,
    phone_number TEXT,
    email TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4. 업종 분류 체계
- **8개 대분류**: 제조업, 건설업, IT업, 서비스업, 운수업, 유통업, 금융업, 에너지업
- **각 대분류당 8-10개 소분류**
- **소분류는 콤마로 구분**: "전자제품, 기계, 화학"

### 5. 고급 검색 기능
**검색 필드 (5개, 2줄 자동 배치):**
1. **협력사명**: 일반 텍스트 입력
2. **사업자번호**: 일반 텍스트 입력  
3. **업종(대분류)**: Excel 필터 스타일 드롭다운
4. **업종(소분류)**: Excel 필터 스타일 드롭다운 (독립적)
5. **상시근로자**: 범위 검색 (최소~최대명)

**검색 로직:**
- 협력사명, 사업자번호: `LIKE %값%`
- 업종(대분류): `= 값`
- 업종(소분류): `LIKE %값%` (콤마 구분 값 포함 검색)
- 상시근로자: `>= 최소 AND <= 최대`

### 6. 페이지네이션 (슬라이딩 윈도우)
- **기본**: 10개씩 표시
- **선택 가능**: 10개, 25개, 50개
- **윈도우 방식**: 항상 10페이지씩 표시
  - 1~10페이지 → 다음 → 11~20페이지
- **총 203개 데이터** (21페이지)

### 7. 테이블 기능
- **15개 컬럼** (협력사명 고정, 나머지 가로 스크롤)
- **협력사명 클릭** → 상세 페이지 이동
- **반응형 지원**

## 💻 핵심 코드

### Flask 라우트 (app.py)
```python
@app.route("/<path:url>")
def page_view(url):
    if url == 'partner-standards':
        return partner_standards()
    # 일반 페이지 처리

def partner_standards():
    # 검색 조건 처리
    # 페이지네이션 처리
    # 데이터베이스 쿼리
    # 템플릿 렌더링
```

### CSS 핵심 스타일
```css
/* 검색 필드 정렬 */
.search-group label { width: 80px; }
.search-group input, .filter-select { width: 200px; height: 40px; }

/* 호버 드롭다운 */
@media (min-width: 992px) {
    .nav-item:hover > .submenu { display: block; }
}
```

## 🚀 실행 방법
1. `python app.py` 실행
2. `http://localhost:5000` 접속
3. 협력사 정보 > 협력사 기준정보 클릭

## 🔧 주요 특징
- **자동 데이터 생성**: 첫 실행 시 203개 샘플 데이터 생성
- **완전 반응형**: 데스크톱/모바일 최적화
- **Excel 수준 검색**: 필터 드롭다운 + 범위 검색
- **직관적 UI**: DCInside 스타일 네비게이션
- **확장 가능**: 메뉴/컬럼 쉽게 추가 가능

## ⚠️ 리셋 후 복원 시 주의사항
1. `portal.db` 파일 삭제하여 새 데이터 생성
2. 모든 템플릿 파일 그대로 유지
3. `config/menu.py` 메뉴 설정 확인
4. Flask 앱 재시작으로 자동 초기화

---
**생성일**: 2025-08-19
**상태**: 완전 구현 완료