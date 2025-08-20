# 📚 Flask Portal 개발 이력 및 이슈 정리

## 🎯 프로젝트 개요

**프로젝트명**: Flask 기반 협력사 관리 포털  
**개발 기간**: 2025년 8월  
**목적**: 보안사업장에서 협력사 정보 관리 및 업무 처리  
**핵심 요구사항**: PostgreSQL 연동, 파일 관리, 사업자번호 기반 식별  

## 📈 개발 진행 단계

### 🚀 1단계: 기본 포털 구조 완성 (초기)
- Flask 기반 웹 애플리케이션 구축
- SQLite 기반 협력사 데이터 관리
- 기본 CRUD 기능 구현
- 샘플 데이터 203개 생성

**주요 파일**: `app.py`, `templates/`, `portal.db`

### 🔧 2단계: 주요 기능 개발 및 버그 수정

#### **2-1. 검색 및 필터링 기능**
- 협력사명, 사업자번호 검색
- 업종별 필터링 (대분류/소분류)
- 상시근로자 수 범위 검색
- 페이징 처리

#### **2-2. 팝업 기반 상세 정보 관리**
- 협력사 목록에서 팝업으로 상세 정보 표시
- 3개 영역 구성: 기본정보 + 상세내용 + 첨부파일
- 실시간 편집 가능한 textarea
- 비밀번호 보호 저장 기능

#### **2-3. 파일 업로드/다운로드 시스템**
- 다중 파일 업로드
- 파일명 클릭으로 다운로드
- 실시간 설명 편집
- 파일 삭제 기능
- 자동 번호 정렬

### 🐛 3단계: 핵심 이슈 해결

#### **이슈 #1: 새로고침 시 데이터 변경 문제**
**문제**: 페이지 새로고침할 때마다 협력사 정보가 바뀜  
**원인**: `@app.before_request`에서 매 요청마다 `DROP TABLE` 실행  
**해결**: 
- `DROP TABLE IF EXISTS` → `CREATE TABLE IF NOT EXISTS` 변경
- `random.seed(42)` 추가로 고정된 샘플 데이터 생성

```python
# 수정 전 (문제)
cursor.execute('DROP TABLE IF EXISTS partners')

# 수정 후 (해결)
cursor.execute('CREATE TABLE IF NOT EXISTS partners')
random.seed(42)  # 고정된 시드
```

#### **이슈 #2: 사업자번호 하이픈 문제**
**문제**: 하이픈 있는 사업자번호로 인한 URL/DB 불일치  
**원인**: 샘플 데이터는 하이픈 포함, URL은 하이픈 제거  
**해결**:
- 모든 사업자번호를 하이픈 없는 형태로 통일
- URL 파라미터와 DB 데이터 일치시킴

```sql
-- 기존 데이터 변경
UPDATE partners SET business_number = REPLACE(business_number, '-', '');
```

#### **이슈 #3: 파트너 ID vs 사업자번호 식별 문제**
**문제**: `partner.id` 사용으로 인한 데이터 불일치  
**원인**: 기본정보 변경 시 ID가 변경되어 첨부파일/상세내용과 연결 끊어짐  
**해결**: 모든 식별을 사업자번호 기반으로 변경

```python
# 수정 전
partner_id = request.form.get('partner_id')

# 수정 후  
business_number = request.form.get('business_number')
```

#### **이슈 #4: 첨부파일/상세내용 저장 실패**
**문제**: 팝업에서 수정해도 저장되지 않음  
**원인**: `partner.id` 기반 식별로 인한 연결 문제  
**해결**: 사업자번호 기반 식별로 변경 + `INSERT OR REPLACE` 사용

### 🏗️ 4단계: 아키텍처 재설계 (핵심 업데이트)

#### **4-1. 데이터베이스 이원화 구조**
**배경**: 실제 운영환경에서 PostgreSQL 연동 필요  
**설계**:

```
외부 PostgreSQL (읽기 전용)    로컬 SQLite (읽기/쓰기)
├── partners_master            ├── partners_cache (동기화된 마스터 데이터)
│   ├── business_number        ├── partner_details (업무 상세내용)  
│   ├── company_name           └── partner_attachments (첨부파일)
│   └── ... (기본정보)             
```

**주요 파일**: `database_config.py`, `config.ini`

#### **4-2. 설정 기반 관리 시스템**
**목적**: GitHub 업데이트 시에도 사용자 설정 보존  
**구현**:
- `config.ini`: 운영환경별 설정
- `config_template.ini`: 배포용 템플릿
- `.gitignore`: 사용자 설정 보호

#### **4-3. 자동 쿼리 생성 시스템**
**문제**: 회사마다 다른 DB 스키마로 인한 수동 쿼리 작성 부담  
**해결**: 컬럼 매핑 기반 자동 쿼리 생성

```ini
[COLUMN_MAPPING]
business_number = biz_reg_no    # 실제 컬럼명
company_name = corp_name        # 실제 컬럼명
representative = ceo_name       # 실제 컬럼명
```

```python
# 자동 생성되는 쿼리
SELECT biz_reg_no AS business_number, 
       corp_name AS company_name,
       ceo_name AS representative
FROM schema.table
```

## 🛠️ 기술적 해결책 요약

### **핵심 설계 원칙**
1. **데이터 분리**: 마스터 데이터(외부) + 업무 데이터(로컬)
2. **설정 기반**: 코드 변경 없이 환경별 배포
3. **표준화**: HTML은 표준 인터페이스, DB는 매핑으로 해결
4. **점진적 확장**: 필요한 만큼만 자동화

### **보안 고려사항**
- 읽기 전용 PostgreSQL 계정 사용
- SECRET_KEY 기반 세션 보호
- 비밀번호 기반 수정 권한 관리
- 파일 업로드 확장자 제한

## 🚨 현재 알려진 제한사항

### **1. HTML 레이아웃 수동 업데이트**
**현상**: 새로운 필드 추가 시 HTML 템플릿 수동 수정 필요  
**이유**: 과도한 자동화 방지 (유지보수성 고려)  
**대응**: 표준 필드는 고정, 변경 빈도 낮음

### **2. 파일 저장 방식**
**현재**: `uploads/` 폴더에 파일 저장  
**장점**: 빠른 접근, 쉬운 백업  
**제한**: 파일시스템 의존성

### **3. 동기화 간격**
**현재**: 30분마다 자동 동기화  
**제한**: 실시간 반영 불가  
**대응**: 수동 동기화 기능 제공

## 📁 최종 파일 구조

```
flask-portal/
├── app.py                      # 메인 Flask 애플리케이션
├── database_config.py          # 데이터베이스 설정 및 매니저
├── config.ini                  # 운영 설정 (Git 제외)
├── config_template.ini         # 배포용 설정 템플릿
├── sync_test.py               # 연결 테스트 스크립트
├── deploy_guide.md            # 배포 가이드
├── requirements.txt           # Python 의존성
├── .gitignore                 # Git 제외 파일
├── templates/
│   ├── base.html              # 기본 레이아웃
│   ├── popup-base.html        # 팝업용 레이아웃
│   ├── partner-standards.html # 협력사 목록
│   └── partner-detail.html    # 협력사 상세 팝업
├── config/
│   └── menu.py               # 메뉴 설정
├── uploads/                  # 업로드 파일 저장소
└── portal.db                # SQLite 데이터베이스
```

## 🎯 운영 가이드

### **배포 프로세스**
1. 프로젝트 복사
2. `config_template.ini` → `config.ini` 복사 후 수정
3. `python sync_test.py` 실행하여 연결 테스트
4. `python app.py` 실행

### **업데이트 프로세스**
1. `git pull origin main` (새 버전 다운로드)
2. `config.ini` 자동 보존됨
3. 새 필드 추가된 경우에만 HTML 수정
4. 재시작

### **트러블슈팅**
- 연결 실패: `sync_test.py` 실행
- 파일 업로드 실패: `uploads/` 폴더 권한 확인
- 세션 문제: SECRET_KEY 확인

## 🔮 향후 개발 방향

### **단기 계획**
- 사고 정보 관리 기능 완성
- 평가/교육 정보 추가
- UI/UX 개선

### **장기 계획**
- API 기반 실시간 동기화
- 대시보드 기능
- 모바일 지원

## 💡 핵심 학습 사항

1. **과도한 자동화는 오히려 복잡성을 증가시킴**
2. **표준화된 인터페이스 + 유연한 데이터 매핑이 최적**
3. **설정과 코드의 적절한 분리가 중요**
4. **사용자 경험과 개발 효율성의 균형 필요**
5. **보안사업장 특성상 단순하고 안정적인 구조가 우선**

## 📞 미래 개발자를 위한 메모

- `config.ini`의 COLUMN_MAPPING만 수정하면 대부분 해결됨
- 새로운 기능 추가 시 기존 패턴 따라 점진적 확장
- 복잡한 요구사항은 별도 모듈로 분리 고려
- 보안사업장 특성상 외부 의존성 최소화 유지

---

**최종 업데이트**: 2025-08-19  
**개발자**: Claude & 사용자 협업  
**상태**: 운영 준비 완료 ✅