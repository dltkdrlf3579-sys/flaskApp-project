# PostgreSQL 마이그레이션 스크립트

## 운영 서버에서 실행 방법

### 간단한 방법 (권장)
```bash
cd migration_scripts
python FINAL_MIGRATION_TO_PRODUCTION.py
```

### 수동 실행 (문제 발생시)
순서대로 실행:

1. **PostgreSQL 함수 설치**
```bash
python setup_pg_functions.py
```

2. **메인 테이블 생성**
```bash
python create_all_postgresql_tables.py
```

3. **캐시/config 테이블 생성**
```bash
python fix_missing_tables_properly.py
```

4. **sync_date 컬럼 추가**
```bash
python add_sync_date_columns.py
```

5. **COALESCE 타입 에러 수정**
```bash
python fix_coalesce_type_error.py
```

6. **상태 확인**
```bash
python check_postgres.py
```

## 파일 설명

| 파일명 | 설명 | 필수 여부 |
|--------|------|----------|
| FINAL_MIGRATION_TO_PRODUCTION.py | 통합 실행 스크립트 | ⭐ 이것만 실행 |
| setup_pg_functions.py | json_extract, datetime 함수 설치 | 필수 |
| create_all_postgresql_tables.py | 30개 메인 테이블 생성 | 필수 |
| fix_missing_tables_properly.py | 캐시/config 테이블 생성 | 필수 |
| add_sync_date_columns.py | sync_date 컬럼 추가 | 필수 |
| fix_coalesce_type_error.py | database_config.py 수정 | 필수 |
| check_postgres.py | 데이터베이스 상태 확인 | 검증용 |

## 주의사항

1. **운영 서버에서만 실행** - 개발 환경에서는 실행하지 마세요
2. **config.ini 확인** - postgres_dsn이 올바른지 확인
3. **백업 필수** - 실행 전 데이터베이스 백업

## 문제 해결

### "테이블이 생성되지 않음"
- `fix_missing_tables_properly.py` 실행 후 `check_postgres.py`로 확인

### "COALESCE type mismatch" 에러
- `fix_coalesce_type_error.py` 실행 후 Flask 재시작

### "json_extract function does not exist" 에러
- `setup_pg_functions.py` 다시 실행

## 성공 확인

모든 마이그레이션이 성공하면:
- `check_postgres.py` 실행시 모든 테이블이 "OK"로 표시
- Flask 앱이 정상 작동
- 웹사이트에서 데이터 조회/등록 가능