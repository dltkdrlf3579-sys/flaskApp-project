#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
리스트 필드 저장 문제 디버깅 및 수정
"""
import sqlite3
import json

def check_and_fix():
    conn = sqlite3.connect('portal.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 최신 사고 확인
    cursor.execute("""
        SELECT accident_number, accident_name, custom_data
        FROM accidents_cache 
        WHERE accident_number LIKE 'ACC%' 
        ORDER BY accident_number DESC 
        LIMIT 1
    """)
    
    accident = cursor.fetchone()
    
    if accident:
        print(f"사고번호: {accident['accident_number']}")
        print(f"사고명: {accident['accident_name']}")
        
        if accident['custom_data']:
            print(f"\n원본 custom_data:")
            print(accident['custom_data'])
            
            try:
                data = json.loads(accident['custom_data'])
                print(f"\n파싱된 custom_data:")
                print(json.dumps(data, indent=2, ensure_ascii=False))
                
                # tteesstt 필드 확인
                if 'tteesstt' in data:
                    tteesstt_value = data['tteesstt']
                    print(f"\ntteesstt 필드:")
                    print(f"  타입: {type(tteesstt_value)}")
                    
                    if isinstance(tteesstt_value, str):
                        print(f"  문제: 문자열로 저장됨")
                        print(f"  값: {tteesstt_value[:100]}")
                        
                        # 수정 시도
                        try:
                            parsed = json.loads(tteesstt_value)
                            data['tteesstt'] = parsed
                            
                            # DB 업데이트
                            new_custom_data = json.dumps(data, ensure_ascii=False)
                            cursor.execute("""
                                UPDATE accidents_cache 
                                SET custom_data = ? 
                                WHERE accident_number = ?
                            """, (new_custom_data, accident['accident_number']))
                            conn.commit()
                            
                            print(f"\n✅ 수정 완료! {len(parsed)}개 항목으로 변환")
                            print(f"수정된 데이터: {parsed}")
                            
                        except Exception as e:
                            print(f"\n수정 실패: {e}")
                    
                    elif isinstance(tteesstt_value, list):
                        print(f"  ✅ 이미 올바르게 저장됨: {len(tteesstt_value)}개 항목")
                        for item in tteesstt_value:
                            print(f"    - {item}")
                    
            except Exception as e:
                print(f"\nJSON 파싱 오류: {e}")
    
    conn.close()

if __name__ == "__main__":
    check_and_fix()