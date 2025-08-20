# 🤔 현재 고민사항 및 해결 과제

**작성일**: 2025-08-20  
**현재 상태**: IQADB_CONNECT310 통합 완료, 실제 DB 연결 준비됨

---

## 📋 **주요 고민사항들**

### 1. **DB 연결 방식 최종 결정** ✅ 해결됨
- **문제**: psycopg2 vs IQADB_CONNECT310 중 어떤 방식을 사용할지?
- **해결**: 기존 성공 방식인 IQADB_CONNECT310으로 결정
- **이유**: 
  - 이미 성공적으로 사용 중인 방식
  - 방화벽 이슈 없음
  - 복잡한 DB 연결 설정 불필요

### 2. **컬럼 구조 확정** ✅ 해결됨
- **최종 결정**: 11개 컬럼 구조
  1. 협력사명 (company_name)
  2. 사업자번호 (business_number) 
  3. Class (partner_class)
  4. 업종(대분류) (business_type_major)
  5. 업종(소분류) (business_type_minor)
  6. 위험작업여부 (hazard_work_flag) - O/X → 예/아니오
  7. 대표자성명 (representative)
  8. 주소 (address)
  9. 평균연령 (average_age) - 숫자형
  10. 매출액 (annual_revenue)
  11. **거래차수 (transaction_count)** - 추가됨

### 3. **코드 복잡성 해결** ✅ 해결됨
- **문제**: DB_HOST, DB_PORT 등 불필요한 설정들로 인한 복잡성
- **해결**: 완전 간단화
  - execute_SQL(query) 한 줄로 데이터 조회
  - config.ini에서 PARTNERS_QUERY, ACCIDENTS_QUERY만 설정
  - 복잡한 DB 연결 정보 완전 제거

---

## 🚧 **아직 남은 과제들**

### 1. **실제 DB 연결 테스트** ✅ 준비완료
- **현재 상태**: 코드와 쿼리 구조 수정 완료
- **완료된 작업**:
  - ✅ config.ini에 11개 컬럼 PARTNERS_QUERY 작성
  - ✅ config.ini에 ACCIDENTS_QUERY 작성  
  - ⚠️ `test_sync.py` 실행 확인 (IQADB_CONNECT310 모듈 필요)
- **다음 단계**: 실제 DB 컬럼명으로 쿼리 수정 후 테스트

### 2. **실제 데이터 검증**
- **확인 사항**:
  - 11개 컬럼이 정확히 매핑되는지
  - O/X 위험작업여부가 제대로 표시되는지
  - 평균연령이 숫자로 나오는지
  - 거래차수 데이터가 있는지

### 3. **Flask 앱 연동**
- **app.py에서 동기화 호출 방식**:
  ```python
  # 협력사 데이터 동기화
  success = partner_manager.sync_partners_from_external_db()
  
  # 사고 데이터 동기화  
  accidents_success = partner_manager.sync_accidents_from_external_db()
  ```

### 4. **성능 최적화 고민**
- **대용량 데이터 처리**: 만약 데이터가 많다면 배치 처리 필요할 수도
- **동기화 주기**: 언제, 얼마나 자주 동기화할지?
- **메모리 사용량**: 판다스 DataFrame 메모리 사용량 모니터링

---

## 🎯 **다음 단계 우선순위**

### **1순위 (즉시 해야 할 것)**
1. ✅ config.ini에 11개 컬럼 쿼리 구조 작성 완료
2. 🔧 쿼리의 실제 DB 컬럼명 수정 (your_schema.your_table → 실제명)
3. 🔧 IQADB_CONNECT310 환경에서 test_sync.py 실행 및 결과 확인

### **2순위 (테스트 후 해야 할 것)**
1. Flask 앱에서 실제 데이터 확인
2. 11개 컬럼이 화면에 정확히 표시되는지 확인
3. 협력사 상세보기에서 데이터 확인

### **3순위 (안정화 후 고려할 것)**
1. 동기화 자동화 (크론잡 등)
2. 성능 모니터링 및 최적화
3. 에러 알림 시스템 구축

---

## 🛠️ **현재 파일 구조**

```
flask-portal/
├── database_config.py     # ✅ IQADB 통합 완료
├── config_template.ini    # ✅ 11개 컬럼 쿼리 템플릿
├── config.ini            # 🚧 실제 쿼리 작성 필요
├── test_sync.py          # ✅ 테스트 스크립트 준비됨
├── templates/
│   ├── partner-standards.html  # ✅ 11개 컬럼 대응
│   └── partner-detail.html     # ✅ 11개 컬럼 대응
└── CURRENT_ISSUES.md     # 📝 이 파일
```

---

## 💡 **기술적 결정사항 기록**

### **성공한 접근법**
- ✅ 기존 성공 방식(IQADB_CONNECT310) 재사용
- ✅ 복잡한 설정 제거하고 단순화
- ✅ 판다스 DataFrame 기반 데이터 처리
- ✅ SQLite 캐시 시스템 유지

### **실패한 접근법들**
- ❌ CKEditor 통합 (기존 시스템과 충돌)
- ❌ psycopg2 직접 연결 (방화벽 이슈)
- ❌ 복잡한 DB 연결 설정 (불필요한 복잡성)

---

## 📞 **다음 개발자를 위한 메모**

1. **IQADB_CONNECT310 의존성**: 이 프로젝트는 특정 내부 모듈에 의존하므로, 해당 모듈 없이는 실제 DB 연결 불가

2. **간단함 유지**: 복잡한 설정보다는 execute_SQL() 한 줄로 해결하는 방식 선호

3. **11개 컬럼 고정**: UI와 DB 모두 이 구조에 맞춰져 있으므로 함부로 변경 금지

4. **테스트 우선**: 새로운 기능 추가 전에 반드시 test_sync.py로 검증

---

**마지막 업데이트**: 2025-08-20  
**상태**: 11개 컬럼 쿼리 구조 준비 완료 ✅ → 실제 DB 컬럼명 수정 필요 🔧