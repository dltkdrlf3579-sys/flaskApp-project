# 🚀 Flask Portal 보안사업장 배포 가이드

## 📋 배포 전 준비사항

### 1. 필수 파일 복사
```bash
# 전체 프로젝트 폴더를 배포 서버로 복사
scp -r flask-portal/ user@server:/path/to/deployment/
```

### 2. Python 환경 설정
```bash
# Python 3.8+ 필요
python --version

# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 또는
venv\Scripts\activate     # Windows

# 필수 패키지 설치
pip install flask psycopg2-binary
```

## ⚙️ 설정 파일 구성

### 1. 기본 설정 파일 생성
```bash
# 템플릿 복사
cp config_template.ini config.ini
```

### 2. config.ini 수정 (중요!)
```ini
[DEFAULT]
DEBUG = False
SECRET_KEY = your-unique-secret-key-here-128-chars-recommended
EDIT_PASSWORD = your-secure-password

[DATABASE]
EXTERNAL_DB_ENABLED = True
EXTERNAL_DB_HOST = your-postgresql-server
EXTERNAL_DB_PORT = 5432
EXTERNAL_DB_NAME = company_database
EXTERNAL_DB_USER = portal_user
EXTERNAL_DB_PASSWORD = secure_password
EXTERNAL_DB_SCHEMA = public
EXTERNAL_DB_TABLE = partners_master

[SECURITY]
ALLOWED_HOSTS = 127.0.0.1,localhost,your-server-ip
```

## 🗄️ 데이터베이스 설정

### PostgreSQL 테이블 스키마
협력사 마스터 데이터 테이블이 다음 구조를 가져야 합니다:

```sql
CREATE TABLE public.partners_master (
    business_number VARCHAR(12) NOT NULL,    -- 사업자번호 (하이픈 없이)
    company_name VARCHAR(200) NOT NULL,      -- 회사명
    representative VARCHAR(100),             -- 대표자명
    regular_workers INTEGER,                 -- 상시근로자 수
    business_type VARCHAR(200),              -- 전체 업종 정보
    business_type_major VARCHAR(50),         -- 업종 대분류
    business_type_minor VARCHAR(200),        -- 업종 소분류
    establishment_date VARCHAR(10),          -- 설립일 (YYYY-MM-DD)
    capital_amount BIGINT,                   -- 자본금
    annual_revenue BIGINT,                   -- 연매출
    main_products VARCHAR(200),              -- 주요제품
    certification VARCHAR(100),              -- 인증현황
    safety_rating VARCHAR(20),               -- 안전등급
    contact_person VARCHAR(100),             -- 담당자
    phone_number VARCHAR(20),                -- 연락처
    email VARCHAR(100),                      -- 이메일
    PRIMARY KEY (business_number)
);
```

### 데이터베이스 권한 설정
```sql
-- 읽기 전용 사용자 생성 (권장)
CREATE USER portal_user WITH PASSWORD 'secure_password';
GRANT SELECT ON public.partners_master TO portal_user;
```

## 🔒 보안 설정

### 1. 파일 권한 설정
```bash
# 설정 파일 보호
chmod 600 config.ini

# 업로드 폴더 생성
mkdir uploads
chmod 755 uploads

# 로그 파일 권한
touch app.log
chmod 644 app.log
```

### 2. 방화벽 설정
```bash
# Flask 기본 포트 5000 열기 (또는 운영 포트)
sudo ufw allow 5000/tcp
```

## 🚀 애플리케이션 실행

### 1. 개발 모드 (테스트용)
```bash
python app.py
```

### 2. 운영 모드 (권장)
```bash
# Gunicorn 설치
pip install gunicorn

# Gunicorn으로 실행
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 3. 서비스 등록 (Linux)
```bash
# systemd 서비스 파일 생성
sudo nano /etc/systemd/system/flask-portal.service
```

```ini
[Unit]
Description=Flask Portal
After=network.target

[Service]
User=your-user
WorkingDirectory=/path/to/flask-portal
Environment=PATH=/path/to/flask-portal/venv/bin
ExecStart=/path/to/flask-portal/venv/bin/gunicorn -w 4 -b 0.0.0.0:5000 app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

```bash
# 서비스 시작
sudo systemctl enable flask-portal
sudo systemctl start flask-portal
sudo systemctl status flask-portal
```

## 📊 동기화 확인

### 1. 로그 확인
```bash
tail -f app.log
```

### 2. 수동 동기화 테스트
```python
# Python 콘솔에서
from database_config import partner_manager
result = partner_manager.sync_partners_from_postgresql()
print(f"동기화 결과: {result}")
```

## 🔧 문제 해결

### 1. PostgreSQL 연결 오류
- 네트워크 연결 확인
- 방화벽 설정 확인  
- 사용자 권한 확인
- 호스트, 포트, 데이터베이스명 확인

### 2. 동기화 실패
- 테이블 스키마 확인
- 컬럼명 일치 확인
- 데이터 타입 확인

### 3. 파일 업로드 실패
- uploads 폴더 권한 확인
- 디스크 용량 확인
- MAX_UPLOAD_SIZE_MB 설정 확인

## 📝 운영 체크리스트

- [ ] config.ini 파일 보안 설정 완료
- [ ] PostgreSQL 연결 테스트 완료
- [ ] 첫 데이터 동기화 성공 확인
- [ ] 파일 업로드/다운로드 테스트 완료
- [ ] 로그 모니터링 설정 완료
- [ ] 백업 계획 수립 완료
- [ ] 사용자 교육 완료

## 📞 지원

설정 관련 문의나 문제 발생 시:
1. app.log 파일 확인
2. 설정 파일 검토  
3. 네트워크 연결 상태 확인
4. 개발팀에 로그와 함께 문의