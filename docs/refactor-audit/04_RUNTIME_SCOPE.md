# 현재 런타임 분석 범위

작성일: 2026-07-10

## 목적

이 문서는 과거 테스트, 진단, 마이그레이션, 권한 프로토타입을 현재 Flask 런타임으로 오인하지 않기 위한 기준이다.

현재 작업공간은 사외 개발 노트북의 모델링/기본 동작 검증 환경이다. 실제 데이터, IQADB, SSO, 권한 마스터, 네트워크 제약은 사내 개발 PC와 가상서버에서 최종 검증한다.

## 기본 진입점

- `app.py`
- `wsgi.py`

일반 코드 분석은 위 진입점의 import 그래프에서 시작한다.

## 활성 런타임 영역

- 루트 핵심 모듈: 앱, DB 설정, 권한, 컬럼/섹션, 검색, 첨부, 알림, 출입정보, AI 도우미
- `boards/`
- `config/`
- `controllers/`
- `db/`
- `repositories/`
- `utils/`
- 활성 라우트가 렌더링하는 `templates/`
- 활성 템플릿이 로딩하는 `static/`
- `migrations/run_migrations.py`와 현재 numbered migration

`ai_internal_client.py`는 정적 import 그래프에는 없지만 사내 환경에서 설정으로 동적 import하는 공식 어댑터이므로 활성 파일로 취급한다.

## 수동 운영 스크립트

다음은 Flask 요청 런타임이 아니라 사람이 명시적으로 실행하는 운영 도구다.

- `scripts/sync_permission_master_data.py`
- `scripts/operations/force_sync.py`
- `scripts/operations/run_daily_sync.py`

일반 분석에서는 읽지 않고, 동기화 작업을 다룰 때만 확인한다.

## 기본 분석 제외 영역

- `legacy/`
- `.tmp/`
- `backup/`
- `deletelist/`
- `migration_scripts/`
- `needtodevelop/`
- `scripts/operations/`
- 로그, 업로드, 스크린샷, 로컬 DB 파일

위 영역은 `.rgignore`에 등록되어 있다. 역사적 원인 분석이나 복구 작업을 사용자가 명시적으로 요청한 경우에만 검색 제외를 해제한다.

## 2026-07-10 정리 결과

- 브라우저 임시 프로필 585개와 명백한 생성 파일을 삭제했다.
- Git에 추적되던 루트 비런타임 Python 107개를 `legacy/one-off-scripts/`로 격리했다.
- Git에서 무시되던 로컬 테스트/진단/수리 더미 Python 147개도 같은 폴더로 이동하고 새로 추적하지 않도록 했다.
- 강제/일일 동기화 CLI 2개를 `scripts/operations/`로 이동했다.
- 참조되지 않는 과거 관리자 권한 템플릿 10개를 `legacy/templates-admin-old/`로 격리했다.
- 루트 Python 파일은 활성/공식 어댑터 27개만 남겼다. 여기에는 Git 추적에서 빠져 있던 `wsgi.py`를 복구한 결과도 포함된다.

## 판단 규칙

1. 파일명이 검색된 것만으로 현재 동작이라고 판단하지 않는다.
2. Flask 동적 라우트 `/api/<board>/...`를 확인한 뒤 API 누락 여부를 판단한다.
3. 템플릿이 실제 활성 라우트에서 렌더링되는지 확인한다.
4. 개발 PC의 샘플 데이터 불일치는 운영 결함으로 단정하지 않는다.
5. 사내 데이터 파이프라인과 포털 사이 문제는 입력 뷰/컬럼 계약을 먼저 확인한다.
