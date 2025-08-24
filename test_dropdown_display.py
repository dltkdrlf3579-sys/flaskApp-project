import requests
import json

# 등록 페이지 HTML 가져오기
url = "http://127.0.0.1:5000/accident-register"
response = requests.get(url)

if response.status_code == 200:
    html = response.text
    
    # column3 드롭다운 부분 찾기
    import re
    pattern = r'data-column-key="column3".*?</select>'
    match = re.search(pattern, html, re.DOTALL)
    
    if match:
        dropdown_html = match.group()
        print("=== column3 드롭다운 HTML ===")
        print(dropdown_html)
        
        # option 태그들 추출
        options = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', dropdown_html)
        print("\n=== 파싱된 옵션들 ===")
        for value, text in options:
            if value:  # 빈 value는 "선택하세요" 옵션
                print(f"  {value}: {text}")
    else:
        print("column3 드롭다운을 찾을 수 없습니다")
else:
    print(f"페이지 로드 실패: {response.status_code}")

# API 직접 호출 테스트
print("\n=== API 직접 호출 ===")
api_url = "http://127.0.0.1:5000/api/dropdown-codes/column3"
api_response = requests.get(api_url)
if api_response.status_code == 200:
    data = api_response.json()
    if data.get('success'):
        print("API 응답 코드들:")
        for code in data.get('codes', []):
            print(f"  {code['code']}: {code['value']}")
    else:
        print("API 실패:", data.get('message'))
else:
    print(f"API 호출 실패: {api_response.status_code}")