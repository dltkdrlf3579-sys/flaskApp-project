# Flask Portal 트러블슈팅 가이드

## 1. ACCIDENTS_QUERY 데이터 표시 문제 (2025-08-29)

### 증상
- `/partner-accident` 페이지에서 사고 데이터가 None 또는 "-"로 표시
- 재해날짜(accident_date)만 정상 표시되고 나머지 필드는 모두 빈 값
- 개발 환경에서는 정상 동작하나 운영 환경에서만 발생

### 원인
**테이블 스키마 불일치** - `database_config.py`의 CREATE TABLE 구조와 실제 사용하는 컬럼이 완전히 다름

#### 잘못된 테이블 구조 (기존)
```sql
CREATE TABLE IF NOT EXISTS accidents_cache (
    business_number TEXT NOT NULL,
    accident_type TEXT,
    accident_location TEXT,
    ...
)
```

#### 올바른 테이블 구조 (수정 후)
```sql
CREATE TABLE IF NOT EXISTS accidents_cache (
    accident_number TEXT,
    accident_name TEXT,
    accident_time TEXT,
    workplace TEXT,
    accident_grade TEXT,
    ...
)
```

### 해결 방법
1. `database_config.py`의 CREATE TABLE 문 수정
2. 기존 테이블 DROP 후 재생성
3. `sync_accidents_from_external_db()` 실행하여 데이터 재동기화

### 디버깅 팁
```python
# DataFrame 컬럼명 확인 (database_config.py)
print(f"[DEBUG] DataFrame 컬럼명: {list(df.columns)}")

# 실제 데이터 확인
for col in df.columns:
    print(f"  - {col}: {first_row[col]}")
```

### 주의사항
- config.ini의 ACCIDENTS_QUERY는 **외부 DB 조회용**
- INSERT 매핑 시 DataFrame 컬럼명과 정확히 일치해야 함
- AS 별칭 사용 시 DataFrame에는 별칭으로 컬럼명이 들어옴

---

## 2. 캐시 테이블 동기화 구조

### 전체 흐름
1. **외부 DB** → (IQADB_CONNECT310) → **DataFrame**
2. **DataFrame** → (INSERT 매핑) → **로컬 캐시 테이블**
3. **로컬 캐시** → (SELECT) → **웹 페이지 표시**

### 체크 포인트
- [ ] config.ini의 쿼리에 AS 별칭이 제대로 설정되어 있는가?
- [ ] CREATE TABLE 구조가 INSERT 컬럼과 일치하는가?
- [ ] DataFrame의 컬럼명이 예상과 일치하는가?
- [ ] 템플릿에서 사용하는 필드명이 테이블 컬럼과 일치하는가?

### 동기화 스케줄
- 서버 시작 시 자동 실행
- 매일 오전 7시 자동 실행 (Python scheduler)
- 수동 실행: `sync_all_master_data()`

---

## 3. 자주 발생하는 실수

### 테이블 구조 변경 시
**절대 하지 말 것:**
- CREATE TABLE만 수정하고 기존 테이블 유지 ❌
- INSERT 매핑 수정 없이 테이블 구조만 변경 ❌

**반드시 해야 할 것:**
1. CREATE TABLE 수정
2. DROP TABLE 실행
3. INSERT 매핑 확인 및 수정
4. 데이터 재동기화

### 디버깅 시
**비효율적인 방법:**
- 대소문자 문제로 추측 ❌
- 무작정 컬럼명 변경 ❌

**효율적인 방법:**
1. DataFrame 컬럼명 출력
2. 테이블 스키마 확인
3. INSERT 매핑 검증

---

## 4. 관련 파일 위치

- 테이블 생성: `database_config.py` → `__init__()` → CREATE TABLE
- 동기화 함수: `database_config.py` → `sync_*_from_external_db()`
- 쿼리 설정: `config.ini` → `[SQL_QUERIES]` 섹션
- 웹 라우트: `app.py` → `partner_accident()` 등
- 템플릿: `templates/partner-accident.html`

---

## 5. 긴급 복구 방법

문제 발생 시:
```bash
# 1. 테이블 구조 확인
sqlite3 portal.db ".schema accidents_cache"

# 2. 데이터 확인
sqlite3 portal.db "SELECT * FROM accidents_cache LIMIT 1"

# 3. 테이블 재생성
python -c "
import sqlite3
conn = sqlite3.connect('portal.db')
conn.execute('DROP TABLE IF EXISTS accidents_cache')
conn.close()
"

# 4. 서버 재시작 (자동으로 테이블 생성 및 동기화)
python app.py
```