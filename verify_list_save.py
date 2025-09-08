#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
리스트 필드 저장 검증 스크립트
이중 JSON 인코딩 문제 확인용
"""
import sqlite3
import json
import sys

def check_latest_accident():
    """최신 사고의 리스트 필드 저장 상태 확인"""
    
    # UTF-8 출력 설정
    sys.stdout.reconfigure(encoding='utf-8')
    
    conn = sqlite3.connect('portal.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 최신 사고 조회
    cursor.execute("""
        SELECT accident_number, accident_name, custom_data
        FROM accidents_cache 
        WHERE accident_number LIKE 'ACC%' 
        ORDER BY accident_number DESC 
        LIMIT 1
    """)
    
    accident = cursor.fetchone()
    
    if not accident:
        print("❌ 등록된 사고가 없습니다.")
        return False
        
    print("="*70)
    print(f"📋 사고번호: {accident['accident_number']}")
    print(f"📝 사고명: {accident['accident_name']}")
    print("="*70)
    
    if not accident['custom_data']:
        print("❌ custom_data가 비어있습니다.")
        return False
        
    try:
        # 첫 번째 파싱
        custom_data = json.loads(accident['custom_data'])
        print(f"\n1️⃣ 첫 번째 JSON 파싱 성공")
        print(f"   타입: {type(custom_data)}")
        print(f"   키: {list(custom_data.keys())}")
        
        success = True
        
        for key, value in custom_data.items():
            print(f"\n📌 필드: {key}")
            print(f"   원본 타입: {type(value)}")
            
            if isinstance(value, list):
                print(f"   ✅ 정상: 배열로 저장됨 ({len(value)}개 항목)")
                for idx, item in enumerate(value, 1):
                    print(f"      {idx}. {item}")
                    
            elif isinstance(value, str) and value.startswith('['):
                print(f"   ❌ 문제: 문자열로 저장됨 (이중 인코딩)")
                print(f"   원본 값: {value[:100]}...")
                
                try:
                    # 두 번째 파싱 시도
                    parsed = json.loads(value)
                    print(f"\n   2️⃣ 두 번째 JSON 파싱 시도")
                    print(f"      파싱 후 타입: {type(parsed)}")
                    if isinstance(parsed, list):
                        print(f"      파싱 후 배열 ({len(parsed)}개 항목):")
                        for idx, item in enumerate(parsed, 1):
                            print(f"         {idx}. {item}")
                    success = False
                except:
                    print(f"   두 번째 파싱 실패")
                    success = False
                    
            else:
                print(f"   값: {value}")
        
        print("\n" + "="*70)
        if success:
            print("✅ 결과: 리스트 필드가 정상적으로 저장되었습니다!")
        else:
            print("❌ 결과: 이중 JSON 인코딩 문제가 있습니다.")
            print("\n💡 해결 방법:")
            print("   1. collectDynamicFields에서 JSON.parse 확인")
            print("   2. custom_data 구성 시 배열 유지 확인")
            print("   3. 서버에서 추가 파싱 로직 확인")
        
        return success
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON 파싱 오류: {e}")
        print(f"   원본: {accident['custom_data']}")
        return False
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    print("\n[LIST FIELD VERIFICATION]")
    print("="*70)
    
    result = check_latest_accident()
    
    print("\n" + "="*70)
    if result:
        print("[SUCCESS] Test passed!")
    else:
        print("[NEED FIX] Modification required.")
    print("="*70)