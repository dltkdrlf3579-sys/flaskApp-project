#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
최종 테스트: 리스트 필드가 저장되고 표시되는지 확인
"""
import sqlite3
import json
import sys

# UTF-8 출력 설정
sys.stdout.reconfigure(encoding='utf-8')

def test_list_field():
    conn = sqlite3.connect('portal.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("=" * 70)
    print("리스트 필드 최종 테스트")
    print("=" * 70)
    
    # 최신 ACC 사고 조회
    cursor.execute("""
        SELECT accident_number, accident_name, custom_data
        FROM accidents_cache 
        WHERE accident_number LIKE 'ACC%' 
        ORDER BY accident_number DESC 
        LIMIT 1
    """)
    
    accident = cursor.fetchone()
    
    if accident:
        print(f"\n📋 사고번호: {accident['accident_number']}")
        print(f"📝 사고명: {accident['accident_name']}")
        
        if accident['custom_data']:
            try:
                custom_data = json.loads(accident['custom_data'])
                
                # tteesstt 필드 확인
                if 'tteesstt' in custom_data:
                    tteesstt = custom_data['tteesstt']
                    
                    print(f"\n🔍 tteesstt 필드 확인:")
                    print(f"   타입: {type(tteesstt)}")
                    
                    if isinstance(tteesstt, list):
                        print(f"   ✅ 저장 상태: 정상 (배열)")
                        print(f"   📊 데이터 ({len(tteesstt)}개 항목):")
                        for idx, item in enumerate(tteesstt, 1):
                            print(f"      {idx}. 이름: {item.get('name', 'N/A')}")
                            print(f"         ID: {item.get('id', 'N/A')}")
                            print(f"         회사: {item.get('company', 'N/A')}")
                            print(f"         사업자번호: {item.get('bizno', 'N/A')}")
                        
                        print("\n✅ 결론: 데이터가 올바르게 저장되었습니다!")
                        print("   → 이제 상세보기 페이지에서 표시되어야 합니다.")
                        
                    elif isinstance(tteesstt, str):
                        print(f"   ❌ 저장 상태: 문제 (문자열)")
                        print(f"   원본: {tteesstt[:100]}...")
                        
                else:
                    print("\n⚠️ tteesstt 필드가 없습니다.")
                    print(f"   custom_data 키: {list(custom_data.keys())}")
                    
            except json.JSONDecodeError as e:
                print(f"\n❌ JSON 파싱 오류: {e}")
        else:
            print("\n⚠️ custom_data가 비어있습니다.")
    else:
        print("\n❌ ACC 사고가 없습니다.")
    
    conn.close()
    
    print("\n" + "=" * 70)
    print("💡 상세보기 페이지 확인 방법:")
    print("   1. 브라우저에서 사고 상세보기 페이지 열기")
    print("   2. 'test' 섹션의 'tteesstt' 필드 확인")
    print("   3. 표에 협력사 근로자 목록이 표시되는지 확인")
    print("=" * 70)

if __name__ == "__main__":
    test_list_field()