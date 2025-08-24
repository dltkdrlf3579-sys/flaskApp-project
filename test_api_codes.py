import requests
import json

# API로 column3 코드 조회
response = requests.get("http://127.0.0.1:5000/api/dropdown-codes/column3")
data = response.json()

print("=== API 응답 ===")
print(f"Success: {data.get('success')}")
print(f"Codes 개수: {len(data.get('codes', []))}")
print("\n코드 목록:")
for code in data.get('codes', []):
    print(f"  {code['code']}: {repr(code['value'])} (type: {type(code['value']).__name__})")
    
    # JSON 배열인지 확인
    value = code['value']
    if isinstance(value, str) and value.startswith('[') and value.endswith(']'):
        print(f"    -> JSON 배열로 보임! 파싱 시도...")
        try:
            parsed = json.loads(value)
            print(f"    -> 파싱 성공: {parsed}")
        except:
            print(f"    -> 파싱 실패")

# 테스트: 올바른 개별 값으로 다시 저장
print("\n=== 올바른 값으로 재저장 시도 ===")
correct_data = {
    "column_key": "column3",
    "codes": [
        {"code": "COLUMN3_001", "value": "진행중", "order": 1},
        {"code": "COLUMN3_002", "value": "완료", "order": 2},
        {"code": "COLUMN3_003", "value": "보류", "order": 3},
        {"code": "COLUMN3_004", "value": "ㅇㅇ", "order": 4},
        {"code": "COLUMN3_005", "value": "보류2", "order": 5}
    ]
}

save_response = requests.post(
    "http://127.0.0.1:5000/api/dropdown-codes",
    json=correct_data,
    headers={"Content-Type": "application/json"}
)

print(f"저장 응답: {save_response.json()}")

# 다시 조회
response2 = requests.get("http://127.0.0.1:5000/api/dropdown-codes/column3")
data2 = response2.json()
print("\n=== 저장 후 재조회 ===")
for code in data2.get('codes', []):
    print(f"  {code['code']}: {repr(code['value'])}")