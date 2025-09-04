#!/usr/bin/env python3
"""
협력사 HTML 생성 및 업로드 API 테스트 스크립트
"""

from pathlib import Path
from datetime import datetime
import requests
import tempfile

# API 엔드포인트
BASE_URL = "http://localhost:5000"
AUTO_UPLOAD_API = f"{BASE_URL}/api/auto-upload-partner-files"
GENERATE_HTML_API = f"{BASE_URL}/api/generate-partner-html"

def ensure_full_html(html: str) -> str:
    """HTML을 완전한 문서로 변환"""
    u = html.lower()
    if "<html" in u and "<body" in u:
        return html  # 이미 완성된 문서
    # 스켈레톤 입혀주기(UTF-8 메타 포함)
    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>자동 리포트</title>
</head>
<body>
{html}
</body>
</html>"""

def save_html(content: str, biz_no: str, out_dir: str | Path) -> Path:
    """HTML 내용을 파일로 저장"""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    fn = f"{biz_no}_{ts}_report.html"
    path = out_dir / fn
    html = ensure_full_html(content)
    path.write_text(html, encoding="utf-8", newline="\n")
    return path

def upload_via_api(biz_no: str, local_paths: list[str | Path]):
    """API를 통해 파일 업로드"""
    files = [str(Path(p).resolve()) for p in local_paths]
    r = requests.post(AUTO_UPLOAD_API, json={"business_number": biz_no, "file_paths": files}, timeout=30)
    r.raise_for_status()
    return r.json() if r.headers.get("content-type","").startswith("application/json") else r.text

def generate_partner_html_via_api(biz_no: str):
    """API를 통해 협력사 HTML 생성"""
    r = requests.post(f"{GENERATE_HTML_API}/{biz_no}", timeout=30)
    r.raise_for_status()
    return r.json() if r.headers.get("content-type","").startswith("application/json") else r.text

def test_sample_usage():
    """샘플 사용 예제"""
    # 테스트용 사업자번호 (실제 DB에 있는 번호로 변경 필요)
    biz_no = "2618117455"
    
    try:
        print(f"=== 협력사 {biz_no} HTML 생성 테스트 ===")
        
        # 1. 직접 HTML 생성하여 업로드하는 방법
        sample_content = f"""
        <div style="padding: 20px; font-family: Arial, sans-serif;">
            <h1>협력사 상세 정보</h1>
            <h2>사업자번호: {biz_no}</h2>
            <p>생성일시: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
            <p>이 파일은 API 테스트를 위해 자동 생성된 샘플 리포트입니다.</p>
        </div>
        """
        
        # 임시 디렉토리에 HTML 저장
        temp_dir = tempfile.mkdtemp()
        html_path = save_html(sample_content, biz_no, temp_dir)
        print(f"HTML 파일 생성: {html_path}")
        
        # API를 통해 업로드
        result = upload_via_api(biz_no, [html_path])
        print("업로드 결과:", result)
        
        # 2. 서버에서 HTML 생성하는 방법 (협력사 정보가 DB에 있는 경우)
        print(f"\n=== 서버에서 HTML 자동 생성 테스트 ===")
        result = generate_partner_html_via_api(biz_no)
        print("생성 결과:", result)
        
    except Exception as e:
        print(f"테스트 실패: {str(e)}")

if __name__ == "__main__":
    test_sample_usage()