# 개발 가이드라인

**작성일**: 2025-08-21  
**목적**: 개발-운영 환경 분리와 장기 계획에 따른 개발 주의사항

---

## 🏢 개발/운영 환경 분리

### 현재 상황
- **개발용 컴퓨터 (사외)**: 현재 개발 진행 중인 환경
- **운영용 컴퓨터 (사내)**: 실제 서비스될 환경

### ⚠️ 주의사항
```
지금 개발은 철저하게 개발용 컴퓨터(사외), 운영용 컴퓨터(사내)로 분리되어 있음.
그래서 당장은 개발용 컴퓨터에서 잘 돌아가도록 개발하되, 
사내 상황은 다르다는 것을 염두해두고 코드를 짤 것.
```

**환경 차이점 고려사항:**
- 네트워크 접근 권한
- 보안 정책 (방화벽, 프록시)
- 파일 시스템 경로 구조
- 데이터베이스 연결 방식
- 라이브러리 설치 제한

---

## 📦 의존성 관리

### requirements.txt 관리 규칙
```
새로운 라이브러리를 설치하게 된다면 잊지말고 requirements.txt에 추가할 것
```

**현재 누락된 패키지:**
- pandas (현재 사용 중이지만 requirements.txt에 미기재)

### 패키지 추가 절차
1. 새 라이브러리 설치: `pip install 패키지명`
2. requirements.txt 업데이트: `pip freeze > requirements.txt`
3. 또는 수동으로 requirements.txt에 추가

**권장 방법:**
```bash
# 개발 중
pip install pandas

# requirements.txt 업데이트
echo "pandas>=1.5.0" >> requirements.txt
```

---

## 🔐 보안 및 인증 설계

### 장기 계획: SSO-SAML 도입
```
장기적으로 사내 보안 체계인 SSO-SAML 기능을 이용해야 하므로 
이 점에 맞춰서 설계 및 개발 진행할 것
```

### 현재 → 미래 마이그레이션 계획

**현재 (임시 방식):**
```python
# 단순 비밀번호 방식
PASSWORD = config.get('DEFAULT', 'EDIT_PASSWORD')
```

**미래 (SSO-SAML):**
```python
# 사용자 세션 기반
@login_required
def protected_route():
    user_info = session.get('user_info')  # 사번, 이름, 부서 등
```

### SSO 대비 설계 원칙

1. **세션 관리 준비**
   - Flask-Session 도입 고려
   - 사용자 정보 저장 구조 설계

2. **권한 체계 설계**
   - 역할 기반 접근 제어 (RBAC) 준비
   - 읽기/쓰기/관리자 권한 구분

3. **감사 로그**
   - 모든 수정 작업에 사용자 추적 준비
   - 로그 테이블 스키마 고려

4. **API 설계**
   - 사내 API 활용을 위한 확장 가능한 구조
   - 인증 토큰 관리 방식

---

## 🔌 사내 API 활용 계획

### API 통합 준비사항
- **인증**: SSO 토큰 기반 API 호출
- **설정**: config.ini에 API 엔드포인트 관리
- **에러 처리**: API 장애 시 fallback 방식
- **캐싱**: API 응답 로컬 캐시 전략

### 권장 설계 패턴
```python
# API 클라이언트 추상화
class InternalAPIClient:
    def __init__(self, base_url, auth_token):
        self.base_url = base_url
        self.auth_token = auth_token
    
    def get_partner_data(self):
        # SSO 토큰으로 사내 API 호출
        # 실패 시 로컬 캐시 사용
        pass
```

---

## 📝 개발 체크리스트

### 새 기능 개발 시
- [ ] 개발/운영 환경 차이 고려
- [ ] requirements.txt 업데이트
- [ ] SSO 마이그레이션 가능성 검토
- [ ] 사내 API 활용 가능성 검토
- [ ] config.ini 설정 추가 (하드코딩 금지)

### 코드 리뷰 시
- [ ] 환경별 설정 분리 확인
- [ ] 인증/권한 로직 SSO 대응 가능성
- [ ] 외부 의존성 문서화
- [ ] 에러 처리 및 fallback 로직

---

## 🚀 배포 프로세스

### 개발 → 운영 이관 시 주의사항
1. **config.ini 설정 변경**
   - IQADB 경로
   - 대시보드 URL
   - API 엔드포인트

2. **의존성 설치**
   ```bash
   pip install -r requirements.txt
   ```

3. **권한 확인**
   - 파일 시스템 접근 권한
   - 데이터베이스 연결 권한
   - 네트워크 접근 권한

4. **보안 검토**
   - 하드코딩된 비밀번호 제거
   - 로그 민감정보 마스킹
   - HTTPS 적용

---

## 🔒 보안 주의사항

### GitHub 푸시 제한
```
⚠️ 깃허브에 푸시할 때 .md 파일은 푸시하지 말 것 (사내 보안 문제)
```

**금지 파일 목록:**
- `*.md` (모든 마크다운 파일)
- `config.ini` (이미 .gitignore에 포함)
- `uploads/` 디렉토리
- 기타 민감한 사내 정보 포함 파일

**안전한 푸시 방법:**
```bash
# 1단계: 현재 상태 확인
git status

# 2단계: 필요한 파일만 개별 확인 후 추가
git add app.py                    # Flask 메인 앱
git add database_config.py        # DB 설정 (민감정보 없는지 확인!)
git add config/                   # 메뉴 설정만
git add templates/                # HTML 템플릿
git add static/                   # CSS, JS, 이미지
git add requirements.txt          # 의존성 목록

# 3단계: 추가된 파일 재확인 (중요!)
git status
git diff --cached                 # 추가된 변경사항 확인

# 4단계: 민감정보 포함 여부 최종 점검
# - 하드코딩된 비밀번호, API 키
# - 사내 DB 연결 정보
# - 실제 서버 주소나 경로

# 5단계: 안전하면 커밋
git commit -m "기능 개선"
git push
```

**절대 푸시하면 안 되는 것들:**
- `*.md` 파일 (사내 정보 포함)
- `config.ini` (비밀번호, DB 정보)
- `uploads/` (사용자 업로드 파일)
- `portal.db` (실제 데이터)
- `app.log` (로그 파일)
- `.env` 파일들

---

## 🎨 CSS 레이아웃 통일 가이드라인

### ⚠️ 페이지 간 스타일 불일치 문제와 해결법

**문제 상황:**
- 코드상으로는 동일한 CSS가 적용된 것처럼 보이지만, 실제 브라우저에서는 페이지마다 다른 스타일이 적용되는 경우
- 특히 `.page-header` 같은 공통 요소에서 자주 발생

**원인 분석:**
1. **중복 CSS 정의**: 같은 파일 내에서 동일한 클래스가 여러 번 정의
2. **CSS 적용 순서**: 나중에 정의된 스타일이 앞서 정의된 스타일을 덮어씀 (Cascade 규칙)
3. **스타일 위치**: `<style>` 태그가 HTML 중간에 있으면 이미 렌더링된 요소에 적용되지 않음

**실제 사례 (협력사 사고 vs 협력사 기준정보):**
```css
/* 문제: 같은 파일에 두 개의 .page-header 정의 */

/* 첫 번째 정의 (상단) - 무시됨 */
.page-header {
    padding: 24px 0;
    font-size: 28px;
    border-bottom: 1px solid #e5e7eb;
}

/* ... 중간에 다른 CSS들 ... */

/* 두 번째 정의 (하단) - 실제 적용됨 */
.page-header {
    padding-bottom: 10px;  /* 상단 패딩 없음 */
    font-size: 20px;
    border-bottom: 2px solid #2f5fd3;
}
```

### 🔧 해결 방법

#### 1. 빠른 해결 (현 상태 유지)
문제가 되는 페이지의 스타일을 통일하려는 기준에 맞춤:

```css
/* 기준이 되는 최종 스타일로 통일 */
.page-header {
    background: #fff;
    margin-bottom: 20px;
    padding-bottom: 10px;           /* 상단 패딩 제거 */
    border-bottom: 2px solid #2f5fd3; /* 파란색 보더 */
}
.page-title {
    color: #333;
    font-size: 20px;               /* 폰트 크기 통일 */
    font-weight: 700;
    margin: 0;
}
```

#### 2. 근본 해결 (권장)
공통 스타일을 `base.html`로 이동:

**base.html에 추가:**
```html
<style>
/* Global Page Header */
.page-header {
  background: #fff;
  margin-bottom: 20px;
  padding-bottom: 10px;
  border-bottom: 2px solid #2f5fd3;
}
.page-title {
  font-size: 20px;
  font-weight: 700;
  color: #333;
  margin: 0;
}
</style>
```

**개별 페이지에서:**
```html
<!-- 중복 .page-header, .page-title 정의 제거 -->
<!-- 페이지별 고유 스타일만 유지 -->
```

### 📋 CSS 통일 체크리스트

**새 페이지 개발 시:**
- [ ] 공통 요소(헤더, 버튼 등)는 base.html의 전역 스타일 사용
- [ ] 페이지별 CSS는 해당 페이지만의 고유 요소에만 적용
- [ ] `<style>` 태그는 HTML 상단에 배치

**기존 페이지 수정 시:**
- [ ] 동일한 클래스의 중복 정의 확인
- [ ] DevTools로 실제 적용된 CSS 확인 (`Computed` 탭 활용)
- [ ] 여러 페이지에 영향을 주는 변경사항은 base.html에서 처리

**디버깅 방법:**
1. **브라우저 개발자도구 (F12) 사용**
   - `Elements` 탭에서 해당 요소 선택
   - `Computed` 탭에서 최종 적용된 스타일 확인
   - `Styles` 탭에서 어떤 CSS가 덮어써졌는지 확인

2. **강력 새로고침**
   - `Ctrl + F5` 또는 `Ctrl + Shift + R`
   - 캐시된 CSS로 인한 문제 해결

3. **CSS 우선순위 강제 적용 (임시방편)**
   ```css
   .page-header {
       padding: 10px !important;  /* 다른 스타일보다 강제 우선 */
   }
   ```

### ⚡ 성능 최적화 팁

**CSS 구조화:**
```
base.html
├── 전역 스타일 (모든 페이지 공통)
├── 컴포넌트 스타일 (버튼, 폼 등)
└── 페이지별 스타일 블록

개별 페이지.html  
└── 해당 페이지만의 고유 스타일
```

**권장 사항:**
- 공통 스타일은 한 번만 정의
- 페이지별 스타일은 최소한으로 유지  
- 중복 코드 제거로 유지보수성 향상

---

**이 가이드라인은 지속적으로 업데이트되며, 모든 개발자가 숙지하고 따라야 합니다.**