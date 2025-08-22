# 상생EHS Portal - 사이트 기능 정리서

**작성일**: 2025-08-21  
**현재 버전**: 대시보드 통합 버전  
**목적**: 프로젝트의 현재 상태와 구조를 명확히 정리하여 향후 개발/유지보수 지원  

## 🎯 프로젝트 개요

**Flask 기반 EHS(Environment, Health, Safety) 통합 관리 포털**
- 스팟파이어 대시보드 임베딩을 통한 실시간 데이터 시각화
- 협력사 정보 및 사고 정보 통합 관리
- IQADB_CONNECT310 모듈을 통한 실제 데이터 연동 지원
- 완전한 CRUD 기능과 첨부파일 관리

## 📁 파일 구조

```
flask-portal/
├── app.py                      # 메인 Flask 애플리케이션
├── database_config.py          # DB 설정 및 IQADB 연동
├── config.ini                  # 운영 설정 파일 (비공개)
├── config_template.ini         # 설정 템플릿
├── CONFIG_GUIDE.md            # 설정 가이드 문서
├── DROPDOWN_ISSUE.md          # 드롭다운 메뉴 이슈 정리
├── portal.db                   # SQLite 데이터베이스
├── requirements.txt            # Python 의존성
├── config/
│   ├── __init__.py
│   └── menu.py                 # 메뉴 구성 설정
├── templates/                  # HTML 템플릿
│   ├── base.html              # 기본 레이아웃 (네비게이션 포함)
│   ├── index.html             # 메인 대시보드 페이지
│   ├── index_backup_original.html # 원본 홈페이지 백업
│   ├── page.html              # 일반 페이지
│   ├── popup-base.html        # 팝업 베이스 템플릿
│   ├── partner-standards.html # 협력사 목록 페이지
│   ├── partner-detail.html    # 협력사 상세 팝업
│   ├── partner-accident.html  # 사고 목록 페이지
│   └── accident-detail.html   # 사고 상세 팝업
├── static/
│   └── images/                # 정적 이미지
│       └── main-safety.jpg    # 안전 관련 이미지
└── uploads/                   # 사용자 업로드 파일
```

## 🎨 현재 UI 구성

### 1. 상단 네비게이션 (전체 페이지 공통)
```
[로고] [상생EHS Portal] --- [협력사 정보▼] [사고예방▼]
                           │               │
                           ├─ 협력사 기준정보  └─ 협력사 사고
                           └─ (추가 가능)
```
- **색상**: 흰색 배경, 파란색 강조 (#2f5fd3)
- **로고**: 좌측에 위치 (40px 높이)
- **드롭다운**: 클릭 시 하위 메뉴 표시 (▼ 화살표 회전)
- **반응형**: 모든 기기에서 동일한 클릭 방식

### 2. 메인 페이지 (/)
```
┌────────────── 네비게이션 바 ──────────────┐
├────────────────────────────────────────┤
│              여백 (34px)                │
├────────────────────────────────────────┤
│                                        │
│     스팟파이어 대시보드 (iframe)          │
│     - 전체 화면 사용                    │
│     - 실시간 데이터 시각화               │
│                                        │
└────────────────────────────────────────┘
```

### 3. 협력사 기준정보 (/partner-standards)
- 검색 필터: 협력사명, 사업자번호, 업종(대/소분류), 상시근로자 수
- 테이블 컬럼 (12개):
  1. 협력사명 (클릭 시 상세 팝업)
  2. 사업자번호
  3. Class
  4. 업종(대분류)
  5. 업종(소분류)
  6. 위험작업여부
  7. 대표자성명
  8. 주소
  9. 평균연령
  10. 매출액
  11. 거래차수
  12. 상시근로자
- 페이지네이션: 10개씩, 10페이지 단위 네비게이션

### 4. 협력사 사고 (/partner-accident)
- 검색 필터: 협력사명, 사고기간
- 더미 데이터 50건 표시 (실제 연동 준비됨)
- 사고 상세 정보 팝업

## 💾 데이터베이스 구조

### SQLite 테이블
1. **partners_cache**: 협력사 마스터 정보 (12개 컬럼)
2. **partner_details**: 협력사 상세 내용
3. **partner_attachments**: 협력사 첨부파일
4. **accidents_cache**: 사고 정보
5. **accident_attachments**: 사고 첨부파일
6. **pages**: 일반 페이지 콘텐츠

### 데이터 소스
- **EXTERNAL_DB_ENABLED = True**: IQADB_CONNECT310을 통한 실제 데이터
- **EXTERNAL_DB_ENABLED = False**: 샘플 데이터 (개발/테스트용)

## ⚙️ 주요 설정 (config.ini)

```ini
[DEFAULT]
DEBUG = True/False
SECRET_KEY = [보안키]
EDIT_PASSWORD = [수정 비밀번호]

[DASHBOARD]
DASHBOARD_URL = [스팟파이어 대시보드 URL]
DASHBOARD_ENABLED = True/False

[DATABASE]
LOCAL_DB_PATH = portal.db
IQADB_MODULE_PATH = [IQADB 모듈 경로]
EXTERNAL_DB_ENABLED = True/False

[SQL_QUERIES]
PARTNERS_QUERY = [협력사 조회 쿼리]
ACCIDENTS_QUERY = [사고 조회 쿼리]
```

## 🔧 주요 기능

### 1. 대시보드 통합
- 스팟파이어 대시보드를 iframe으로 임베딩
- 전체 화면 활용으로 최대 가시성 확보
- 로딩 상태 표시 및 에러 처리

### 2. 협력사 관리
- 실시간 검색 및 필터링
- 상세 정보 팝업 (편집 가능)
- 첨부파일 업로드/다운로드
- 리치 텍스트 편집기 (이미지, 표 지원)

### 3. 사고 정보 관리
- 사고 이력 조회 및 관리
- 상세 정보 입력 (15개 이상 필드)
- 첨부파일 관리
- 비밀번호 보호 편집

### 4. 데이터 동기화
- IQADB_CONNECT310을 통한 실제 데이터 연동
- 선택적 쿼리 실행 (PARTNERS_QUERY, ACCIDENTS_QUERY)
- 동기화 실패 시 샘플 데이터 폴백

## ✅ 최근 해결된 이슈

### 드롭다운 메뉴 개선 (2025-08-21)
- **호버 방식 복원**: 마우스 호버로 자연스럽게 메뉴 표시, 0.75초 지연으로 실수로 벗어나도 유지
- **Spotfire 높이 최적화**: iframe 높이를 전체 화면으로 복구하여 대시보드 가시성 극대화

## 📝 향후 개선 사항

1. **대시보드 통합**: API 직접 연동 검토
2. **모바일 최적화**: 반응형 대시보드 개선
3. **보안 강화**: 역할 기반 접근 제어 추가
4. **성능 최적화**: 대용량 데이터 페이징 개선
5. **드롭다운 애니메이션**: 부드러운 전환 효과 추가

## 🚀 실행 방법

```bash
# 가상환경 활성화
python -m venv venv
venv\Scripts\activate  # Windows

# 의존성 설치
pip install -r requirements.txt

# 설정 파일 생성
copy config_template.ini config.ini
# config.ini 편집 (DB 경로, 대시보드 URL 등)

# 실행
python app.py
```

## 📌 중요 참고사항

1. **config.ini는 git에서 제외됨** (보안상 이유)
2. **IQADB_MODULE_PATH**: 환경에 따라 경로 수정 필요
3. **대시보드 URL**: 실제 스팟파이어 서버 주소로 변경 필요
4. **샘플 데이터**: 203개 협력사, 50개 사고 자동 생성

---

*이 문서는 2025-08-21 기준으로 작성되었으며, 코드 변경 시 업데이트가 필요합니다.*