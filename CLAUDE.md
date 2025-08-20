# 🚀 Flask Portal - 보안사업장용 협력사 관리 시스템

## 📋 최종 완성 현황 (2025-08-19)

### ✅ **모든 핵심 기능 완료**
- 협력사 정보 관리 (검색, 필터링, 상세 정보)
- 파일 업로드/다운로드 시스템
- PostgreSQL 연동 아키텍처
- 설정 기반 배포 시스템
- 자동 쿼리 생성 시스템

### ✅ **주요 이슈 해결 완료**
- 새로고침 시 데이터 변경 문제 → 해결 ✅
- 사업자번호 하이픈 문제 → 해결 ✅  
- 첨부파일/상세내용 저장 문제 → 해결 ✅
- GitHub 업데이트 시 설정 보존 → 해결 ✅

## ⚠️ **중요 개발 규칙 (절대 위반 금지)**

### **📌 사업자번호 처리 규칙**
- **사업자번호는 10자리 숫자 문자열**
- 로우 데이터 자체가 하이픈 없는 10글자 숫자
- 예: `1234567890` (10자리 문자열)
- 별도 정규화 로직 불필요, 문자열 그대로 사용

### **🎯 UI/UX 핵심 원칙**
- 텍스트 입력은 반드시 동작해야 함
- 첨부파일 업로드는 즉시 반영되어야 함  
- 저장 기능은 절대 실패하면 안됨
- 리치 텍스트 에디터는 기존 기능을 대체하되 호환성 유지

### **🔧 데이터 정합성 규칙**
- business_number는 시스템 전체의 Primary Key
- 모든 테이블 간 JOIN은 business_number 기준
- 외부 DB 동기화 시에도 business_number 일관성 유지

## 🏗️ 최종 아키텍처

### **데이터베이스 이원화 구조**
```
외부 PostgreSQL (읽기 전용)    로컬 SQLite (읽기/쓰기)
├── partners_master            ├── partners_cache (동기화)
│   └── 협력사 기본정보            ├── partner_details (업무내용)
                               └── partner_attachments (파일)
```

### **설정 기반 관리 시스템**
```
config.ini (사용자 설정)       GitHub (코드 업데이트)  
├── DB 연결정보                ├── app.py
├── 컬럼 매핑                  ├── database_config.py
├── SQL 쿼리                   └── templates/
└── 보안 설정                  
```

## 📁 최종 파일 구조
```
flask-portal/
├── app.py                      # 메인 애플리케이션
├── database_config.py          # DB 매니저 & 자동 쿼리 생성
├── config.ini                  # 운영 설정 (Git 제외)
├── config_template.ini         # 배포용 템플릿
├── sync_test.py               # 연결 테스트 스크립트
├── deploy_guide.md            # 상세 배포 가이드
├── DEVELOPMENT_HISTORY.md     # 개발 이력 및 이슈 정리
├── requirements.txt           # Python 의존성
├── .gitignore                 # 설정 보호
├── templates/                 # HTML 템플릿
├── config/menu.py            # 메뉴 설정
├── uploads/                  # 파일 저장소
└── portal.db                # SQLite DB
```

## ⚙️ 핵심 혁신 기능

### **1. 자동 쿼리 생성 시스템**
```ini
# config.ini에서 컬럼만 매핑
[COLUMN_MAPPING]
business_number = biz_reg_no
company_name = corp_name
representative = ceo_name

# 자동으로 이런 쿼리 생성됨:
# SELECT biz_reg_no AS business_number, 
#        corp_name AS company_name,
#        ceo_name AS representative
# FROM schema.table
```

### **2. GitHub 업데이트 안전성**
- `config.ini` 는 `.gitignore`로 보호
- 코드 업데이트 시에도 사용자 설정 보존
- 템플릿 파일로 새 환경 배포 지원

### **3. 이중 쿼리 방식 지원**
1. **자동 생성**: 컬럼 매핑으로 쿼리 자동 생성
2. **수동 작성**: 복잡한 쿼리는 직접 작성 가능

## 🚀 배포 방법

### **신규 배포**
```bash
# 1. 프로젝트 복사
git clone [repository]

# 2. 설정 파일 생성
cp config_template.ini config.ini

# 3. 설정 수정 (DB 정보, 컬럼 매핑)
nano config.ini

# 4. 연결 테스트
python sync_test.py

# 5. 실행
python app.py
```

### **업데이트**
```bash
# 1. 새 버전 다운로드
git pull origin main

# 2. config.ini 자동 보존됨 ✅
# 3. 바로 실행 가능
python app.py
```

## 🔧 운영 가이드

### **기본 사용법**
1. **협력사 정보**: PostgreSQL에서 자동 동기화 (30분마다)
2. **업무 내용**: 포털에서 직접 작성/수정
3. **파일 관리**: 드래그앤드롭으로 업로드/다운로드
4. **검색/필터**: 다양한 조건으로 협력사 검색

### **보안 설정**
- 편집 시 비밀번호 인증 (기본: `admin123`)
- 파일 업로드 확장자 제한
- 세션 기반 권한 관리

### **모니터링**
- `app.log`: 시스템 로그
- `sync_test.py`: 연결 상태 확인
- 동기화 상태: 자동 기록

## 🎯 운영 시 체크포인트

### **일일 점검**
- [ ] 서비스 정상 접속 확인
- [ ] 파일 업로드/다운로드 테스트

### **주간 점검**  
- [ ] `app.log` 로그 확인
- [ ] `uploads/` 폴더 용량 확인
- [ ] 데이터 동기화 상태 확인

### **월간 점검**
- [ ] 데이터베이스 백업
- [ ] SECRET_KEY 보안 점검
- [ ] 시스템 업데이트 검토

## 🚨 트러블슈팅

### **자주 발생하는 문제**

**1. 연결 실패**
```bash
# 진단
python sync_test.py

# 해결
config.ini의 DB 설정 확인
```

**2. 파일 업로드 실패**
```bash
# 진단  
ls -la uploads/

# 해결
chmod 755 uploads/
```

**3. 세션 문제**
```ini
# config.ini 확인
SECRET_KEY = [올바른 키 확인]
```

## 📞 추가 개발 시 가이드

### **새 필드 추가**
1. `config.ini`의 `COLUMN_MAPPING`에 추가
2. HTML 템플릿에 표시 코드 추가
3. 테스트 후 배포

### **새 기능 개발**
1. 기존 패턴 참고
2. `database_config.py`에 매니저 함수 추가
3. `app.py`에 라우트 추가
4. 설정 필요 시 `config.ini`에 추가

### **성능 최적화**
- 동기화 간격 조정: `SYNC_INTERVAL_MINUTES`
- 파일 크기 제한: `MAX_UPLOAD_SIZE_MB`
- 로그 레벨 조정: `LOG_LEVEL`

---

## 📈 개발 성과

✅ **완전 자동화된 배포 시스템**  
✅ **GitHub 업데이트 안전성 보장**  
✅ **유연한 DB 연동 아키텍처**  
✅ **직관적인 사용자 인터페이스**  
✅ **강력한 파일 관리 시스템**  

**최종 상태**: 운영 준비 완료 🚀  
**마지막 업데이트**: 2025-08-19  
**다음 단계**: 실제 PostgreSQL 연결 및 운영 시작