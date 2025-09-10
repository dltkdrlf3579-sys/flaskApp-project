#!/usr/bin/env python3
"""
모든 수정사항 검증 스크립트
"""
import requests
import json
import time

def test_page(url, name):
    """페이지 테스트"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            print(f"[OK] {name}: OK (200)")
            return True
        else:
            print(f"[ERROR] {name}: Error ({response.status_code})")
            return False
    except Exception as e:
        print(f"[ERROR] {name}: Exception ({e})")
        return False

def test_api(url, name):
    """API 테스트"""
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            if isinstance(data, list):
                count = len(data)
                print(f"[OK] {name}: {count}개 항목")
                return True
            else:
                print(f"[OK] {name}: OK")
                return True
        else:
            print(f"[ERROR] {name}: Error ({response.status_code})")
            return False
    except Exception as e:
        print(f"[ERROR] {name}: Exception ({e})")
        return False

def main():
    """메인 실행"""
    BASE_URL = "http://localhost:5000"
    
    print("="*60)
    print("Flask 포털 수정사항 검증")
    print("="*60)
    
    # 메인 페이지 테스트
    print("\n[메인 페이지 테스트]")
    pages = [
        ("/safety-instruction", "환경안전 지시서"),
        ("/follow-sop", "Follow SOP"),
        ("/full-process", "Full Process"),
        ("/partner-accident", "협력사 사고"),
    ]
    
    page_results = []
    for path, name in pages:
        result = test_page(f"{BASE_URL}{path}", name)
        page_results.append(result)
        time.sleep(0.1)
    
    # Admin 페이지 테스트
    print("\n[Admin 페이지 테스트]")
    admin_pages = [
        ("/admin/safety-instruction-columns", "환경안전 지시서 컬럼설정"),
        ("/admin/follow-sop-columns", "Follow SOP 컬럼설정"),
        ("/admin/full-process-columns", "Full Process 컬럼설정"),
        ("/admin/accident-columns-simplified", "협력사 사고 컬럼설정"),
        ("/admin/change-request-columns", "기준정보 변경요청 컬럼설정"),
    ]
    
    admin_results = []
    for path, name in admin_pages:
        result = test_page(f"{BASE_URL}{path}", name)
        admin_results.append(result)
        time.sleep(0.1)
    
    # API 테스트
    print("\n[API 테스트]")
    apis = [
        ("/api/safety-instruction-columns", "환경안전 지시서 API"),
        ("/api/follow-sop-columns", "Follow SOP API"),
        ("/api/full-process-columns", "Full Process API"),
        ("/api/accident-columns", "협력사 사고 API"),
        ("/api/change-request-columns", "기준정보 변경요청 API"),
    ]
    
    api_results = []
    for path, name in apis:
        result = test_api(f"{BASE_URL}{path}", name)
        api_results.append(result)
        time.sleep(0.1)
    
    # 결과 요약
    print("\n" + "="*60)
    print("[검증 결과 요약]")
    print("="*60)
    
    total_pages = len(page_results) + len(admin_results)
    success_pages = sum(page_results) + sum(admin_results)
    total_apis = len(api_results)
    success_apis = sum(api_results)
    
    print(f"- 페이지: {success_pages}/{total_pages} 성공")
    print(f"- API: {success_apis}/{total_apis} 성공")
    
    if success_pages == total_pages and success_apis == total_apis:
        print("\n[SUCCESS] 모든 테스트 통과! 시스템이 정상 작동합니다.")
    else:
        print("\n[WARNING] 일부 테스트 실패. 추가 수정이 필요합니다.")
    
    # 상세 문제 리스트
    if success_pages < total_pages or success_apis < total_apis:
        print("\n[실패 항목]")
        for i, (path, name) in enumerate(pages):
            if not page_results[i]:
                print(f"  - {name}: {path}")
        for i, (path, name) in enumerate(admin_pages):
            if not admin_results[i]:
                print(f"  - {name}: {path}")
        for i, (path, name) in enumerate(apis):
            if not api_results[i]:
                print(f"  - {name}: {path}")

if __name__ == "__main__":
    main()