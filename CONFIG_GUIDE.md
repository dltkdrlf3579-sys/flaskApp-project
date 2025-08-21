# 설정 가이드 (Config Guide)

## config.ini 설정 방법

### 1. 기본 설정
```ini
[DEFAULT]
DEBUG = True  # 개발 모드
SECRET_KEY = your-secret-key-here
UPLOAD_FOLDER = uploads
EDIT_PASSWORD = admin123  # 기본 수정 비밀번호
```

### 2. 데이터베이스 설정
```ini
[DATABASE]
# 로컬 SQLite (업무 데이터)
LOCAL_DB_PATH = portal.db

# IQADB 모듈 경로 (본인의 환경에 맞게 수정)
IQADB_MODULE_PATH = C:/Users/user/AppData/Local/aipforge/pkgs/dist/obf/PY310

# 외부 DB 연동 설정
# True: IQADB를 통해 실제 데이터 조회
# False: 샘플 데이터 사용
EXTERNAL_DB_ENABLED = False
```

### 3. 주요 설정 항목 설명

#### EXTERNAL_DB_ENABLED
- **True**: IQADB_CONNECT310을 통해 실제 데이터베이스에서 데이터 조회
- **False**: 샘플 데이터 사용 (개발/테스트용)

#### IQADB_MODULE_PATH
- IQADB_CONNECT310 모듈이 설치된 경로
- Git Bash 사용 시 경로가 변경되는 문제를 해결하기 위해 설정 가능하도록 함
- 기본값: `C:/Users/user/AppData/Local/aipforge/pkgs/dist/obf/PY310`

### 4. SQL 쿼리 설정
```ini
[SQL_QUERIES]
# 협력사 정보 조회 쿼리 (12개 컬럼 필수)
PARTNERS_QUERY = SELECT 
    business_number,      -- 사업자번호
    company_name,         -- 협력사명
    partner_class,        -- Class
    business_type_major,  -- 업종(대분류)
    business_type_minor,  -- 업종(소분류)
    hazard_work_flag,     -- 위험작업여부
    representative,       -- 대표자
    address,             -- 주소
    average_age,         -- 평균연령
    annual_revenue,      -- 매출액
    transaction_count,   -- 거래차수 (TEXT)
    permanent_workers    -- 상시근로자 (INTEGER)
FROM your_table

# 사고 정보 조회 쿼리
ACCIDENTS_QUERY = SELECT ...
```

### 5. 데이터 타입 요구사항

| 컬럼명 | 데이터 타입 | 설명 |
|--------|------------|------|
| business_number | TEXT | 사업자번호 (PRIMARY KEY) |
| company_name | TEXT | 협력사명 (NOT NULL) |
| partner_class | TEXT | 협력사 등급 |
| business_type_major | TEXT | 업종 대분류 |
| business_type_minor | TEXT | 업종 소분류 |
| hazard_work_flag | TEXT | 위험작업여부 (O/X) |
| representative | TEXT | 대표자명 |
| address | TEXT | 주소 |
| average_age | INTEGER | 평균연령 |
| annual_revenue | BIGINT | 연매출액 |
| transaction_count | TEXT | 거래차수 |
| permanent_workers | INTEGER | 상시근로자수 |

### 6. 제거된 설정 (더 이상 사용하지 않음)
- PostgreSQL 관련 설정들 (EXTERNAL_DB_HOST, PORT, NAME 등)
- ACCIDENTS_DB_ENABLED, ACCIDENTS_DB_TABLE
- 기타 불필요한 DB 연결 설정

### 7. 실제 데이터 연동 시 체크리스트
1. ✅ IQADB_MODULE_PATH가 올바른지 확인
2. ✅ EXTERNAL_DB_ENABLED를 True로 설정
3. ✅ SQL_QUERIES의 PARTNERS_QUERY가 실제 테이블 구조와 일치하는지 확인
4. ✅ 모든 12개 컬럼이 쿼리 결과에 포함되는지 확인
5. ✅ 데이터 타입이 요구사항과 일치하는지 확인