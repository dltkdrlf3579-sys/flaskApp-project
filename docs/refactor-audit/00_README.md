# 리팩토링 감사 문서 보관소

작성일: 2026-06-14  
목적: 나중에 리팩토링이나 안정화 작업을 다시 시작할 때, 어디서부터 읽어야 하는지 잊지 않기 위한 문서 모음.

## 1. 결론부터 읽기

가장 먼저 아래 3개만 읽으면 된다.

1. `02_STABILIZATION_PLAN.md`
   - 실제로 무엇부터 해야 하는지 정리한 운영 안정화 계획.
2. `03_TECH_DEBT_ROADMAP.md`
   - 어떤 기술부채가 있고, 무엇을 나중으로 미뤄도 되는지 정리한 로드맵.
3. `01_ANALYSIS_CHECKLIST.md`
   - 0~10단계 분석이 어디까지 끝났는지 확인하는 체크리스트.

## 2. 세부 보고서 읽는 순서

세부 확인이 필요하면 `reports` 폴더를 아래 순서로 읽는다.

1. `reports/PROJECT_AUDIT_REPORT_2026.md`
2. `reports/BASELINE_REPORT.md`
3. `reports/RUNTIME_ENTRY_REPORT.md`
4. `reports/ROUTE_MAP_REPORT.md`
5. `reports/BOARD_FLOW_REPORT.md`
6. `reports/FRONTEND_CONNECTION_REPORT.md`
7. `reports/DB_USAGE_MAP.md`
8. `reports/SERVICE_COMMON_REPORT.md`
9. `reports/TEST_ASSET_REPORT.md`
10. `reports/RISK_CLASSIFICATION_REPORT.md`

## 3. 리팩토링 재개 원칙

리팩토링은 대공사로 시작하지 않는다.

- 먼저 백업과 안전 검증 루틴을 확정한다.
- 프론트/API 불일치처럼 작고 확실한 문제부터 고친다.
- DB 마이그레이션 누락은 새 환경 구축 안정성 관점에서 정리한다.
- `app.py` 전체 분해는 가장 나중에 한다.
- 보안 대공사는 하지 않는다. 내부망 운영 사고 방지 수준만 본다.
- 새 기능을 넣을 때, 그 주변 코드만 작게 정리한다.

## 4. 주의할 점

- 원본 문서는 프로젝트 루트에도 남아 있다.
- 이 폴더는 보관용 복사본이다.
- 나중에 원본 문서가 바뀌면 이 폴더의 복사본은 자동으로 갱신되지 않는다.
- Windows PowerShell 5.1 한글 인코딩 문제 때문에 Markdown 편집은 UTF-8을 명시해야 한다.

## 5. 다음에 다시 시작한다면

다음 문장으로 시작하면 된다.

> `docs/refactor-audit/00_README.md`를 읽고, `STABILIZATION_PLAN.md` 기준으로 첫 번째 국소수술 작업을 골라줘.

