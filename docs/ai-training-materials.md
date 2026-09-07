# AI 학습자료 업로드

## 범위와 저장 구조

- 협력사 정보 → **AI 학습자료 업로드** (`/ai-training-materials`).
- 목록: 제목, 첨부파일명, 등록자, 등록일, 수정일, 등록부서. 최근 수정순 정렬.
- 기존 게시판처럼 등록·상세는 팝업. 요청번호·등록일·작성자·작성부서와 제목·수정일, 첨부파일만 표시.
- 웹 등록은 제목을 지정하고 파일 여러 개를 한 게시글에 첨부할 수 있다.
- 폴더 일괄 등록은 **파일 1개당 게시글 1개**, 제목은 **확장자를 포함한 원래 파일명**이다.
- 제목 수정, 파일 추가·삭제·교체를 저장하면 수정일만 갱신된다. 변경 없이 저장하면 수정일도 유지된다.
- 작성자·작성부서는 최초 등록 시 SSO 세션에서 기록하며 수정 시 덮어쓰지 않는다.
- DB는 `[DATABASE] postgres_dsn`의 팀 전용 PostgreSQL이다. IQADB를 사용하지 않는다.
- 신규 테이블 `ai_training_materials`(게시글), `ai_training_material_files`(파일명·저장경로·크기·해시).
- 파일은 `[AI_TRAINING_MATERIALS] upload_folder/<요청번호>/<고유값>_<파일명>`에 저장된다. 기본 위치 `uploads/ai_training_materials`.
- 챗봇 학습용으로 수집할 때 **요청번호 하위 폴더까지 재귀적으로** 읽는다. 카카오톡/LLM 전송이나 자동 학습은 하지 않는다.
- 파일당 기본 제한 50MB, 확장자는 기존 `[SECURITY] allowed_extensions`를 따른다. 이 게시판의 제한은 다른 게시판에 영향을 주지 않는다.
- DB와 업로드 폴더를 함께 백업한다. 저장된 파일을 탐색기에서 직접 바꾸지 말고 게시판에서 교체해야 수정일과 파일 정보가 맞는다.
- 첨부 삭제 후 저장하면 이전 파일도 저장 폴더에서 제거한다. Windows 파일 잠금·권한 문제로 제거에 실패하면 경고가 표시된다. 이때는 AI 학습 전에 서버 로그에 표시된 이전 파일을 확인한다.

## 운영 PC 이관

이 문서는 사외 노트북이 아닌 **사내 운영 PC에서 사용자 본인이 실행할 절차**도 포함한다. 개발 PC의 샘플 DB 설정을 운영 PC에 덮어쓰지 않는다.

필요한 신규 파일:

- `ai_training_materials.py`
- `migrations/008_create_ai_training_materials.sql`
- `scripts/import_ai_training_materials.py`
- `templates/ai-training-materials.html`
- `templates/ai-training-material-detail.html`
- `static/css/ai-training-materials.css`
- `static/js/ai-training-materials.js`

기존 파일의 해당 부분만 반영:

- `app.py`: 신규 Blueprint import·등록 및 page_view 라우트 매핑.
- `config/menu.py`: 협력사 정보 하위 메뉴.
- `permission_helpers.py`: `AI_TRAINING_MATERIALS` 메뉴·게시판 코드 및 아이콘.
- `config.ini`: 아래 섹션만 추가. 기존 운영 DB/SSO/쿼리 설정은 유지.

```ini
[AI_TRAINING_MATERIALS]
upload_folder = uploads/ai_training_materials
max_upload_size_mb = 50
```

다른 디스크에 저장하려면 `upload_folder = D:/AI_training_uploads`처럼 절대경로를 지정한다. 웹서버 계정과 일괄 등록 실행 계정 모두 이 경로에 쓰기 권한이 있어야 한다. 파일 등록 후 경로를 바꿀 경우 기존 폴더의 내용도 같은 하위 구조로 복사해야 한다.

서버 시작 시 기존 마이그레이션으로 테이블이 생성된다. 이 메뉴 테이블만 먼저 준비하려면 **포털 가상환경의 Python**으로 다음을 실행한다. 아래 `D:\flask-portal`은 실제 운영 폴더로 바꾼다.

```cmd
D:\flask-portal\venv\Scripts\python.exe D:\flask-portal\scripts\import_ai_training_materials.py --init-only
```

웹서버 재시작 후 접속한다. `[PERMISSION] enabled = true`라면 권한 관리 화면의 **AI 학습자료 업로드**에서 읽기 `전체(3)`, 업로드·교체 담당자에게 쓰기 `전체(3)`를 부여한다. 조회/다운로드와 등록/수정은 서버에서도 각각 읽기/쓰기 권한을 확인한다. 이 게시판은 공유자료용이며 작성자별 비공개 게시판이 아니다. 개발 환경에서 권한을 끄고 SSO 세션도 없으면 `개발 사용자`로 기록된다.

계약평가 시범 코드와 독립적이므로 이 기능 때문에 계약평가 관련 파일을 추가 이관할 필요는 없다.

## 폴더 일괄 등록

1. 예: `D:\AI_upload_inbox`에 등록할 파일을 넣는다. 실제 저장 폴더와 겹치지 않는 별도 입력 폴더를 쓴다.
2. 다음 명령으로 미리 검사한다. 이 단계는 DB/실제 저장 폴더를 변경하지 않는다.

```cmd
D:\flask-portal\venv\Scripts\python.exe D:\flask-portal\scripts\import_ai_training_materials.py --folder "D:\AI_upload_inbox"
```

3. 정상 파일을 확인한 뒤 실제 등록한다. 등록자 ID·이름·부서는 실제 값으로 바꾼다. 스크립트는 브라우저 SSO 세션을 갖지 않으므로 명시적으로 받는다.

```cmd
D:\flask-portal\venv\Scripts\python.exe D:\flask-portal\scripts\import_ai_training_materials.py --folder "D:\AI_upload_inbox" --author-id "my_sso_id" --author-name "홍길동" --department "상생EHS기획그룹" --apply
```

- `--recursive`: 입력 폴더 하위 폴더까지 등록하려는 경우에만 추가.
- `--department-id "부서코드"`: 부서코드도 저장하려는 경우 추가.
- 원본은 복사하며 이동·삭제하지 않는다. 파일별로 게시글과 첨부파일을 함께 저장한다.
- 동일한 **파일명 + 파일내용(SHA-256)**으로 이 스크립트에서 이미 등록한 자료는 재실행 시 건너뛴다. 일부 실패 후 같은 명령을 다시 실행해도 성공한 자료를 중복 생성하지 않는다.
- 같은 이름이어도 파일 내용이 달라지면 **새 게시글**이 된다. 기존 게시글을 교체하려면 웹 팝업에서 기존 첨부 삭제 → 새 첨부 추가 → 수정완료를 사용한다.
- 웹에서 이미 수정한 게시글을 스크립트 재실행으로 되돌리지 않는다. 웹으로 직접 등록했던 자료까지 중복 판별하지는 않는다.
- `[FAILED]`가 있으면 해당 파일과 이유를 확인한다. 성공한 게시글은 유지되며 프로세스 종료코드는 1이다.
- 이 스크립트는 팀 DB에 직접 쓰는 운영자 도구이므로 웹 권한 검사를 거치지 않는다. 운영자가 관리하는 PC에서만 실행한다.

## 구현·검증 체크리스트

- [x] 메뉴·권한 관리 연결, 기존 목록/팝업 스타일 재사용.
- [x] PostgreSQL 스키마, 전용 저장 폴더, 한글 파일명 다운로드.
- [x] 제목·다중 첨부 등록 및 파일 교체, 수정일 갱신.
- [x] 폴더 일괄 등록·사전 검사·원본 보존·재실행 중복 방지.
- [x] 실제 PostgreSQL 격리 검증: 등록·조회·교체·롤백·중복 방지.
- [x] 읽기/쓰기 권한 차단 및 브라우저 화면 확인.
- [ ] 운영 PC 검증: 실제 SSO·팀 DB·저장 폴더 권한·서버 재시작 후 메뉴 확인(사용자 수행).

개발 PC 검증(2026-09-07): 별도 PostgreSQL 스키마에서 30개 항목 확인. 실제 브라우저에서 24개 파일을 두 번 나누어 선택·등록, 첨부 교체, 목록 자동 새로고침, 한글 다운로드, 팝업 레이아웃과 JavaScript 오류 없음 확인. 실제 `app.py`의 라우트·템플릿·메뉴·권한 관리 연동도 확인했다. 테스트 게시글·파일·별도 DB 스키마는 삭제했으며, 개발 DB에는 새 메뉴의 빈 테이블만 준비했다. 사내 SSO나 운영 DB를 검증했다는 의미는 아니다.
