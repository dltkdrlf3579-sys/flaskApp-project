#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import json

# 데이터베이스 연결
conn = sqlite3.connect('portal.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== 최근 등록된 사고 데이터 확인 ===")

# 가장 최근에 등록된 ACC 사고 찾기
cursor.execute("""
    SELECT accident_number, accident_name, custom_data, accident_date 
    FROM accidents_cache 
    WHERE accident_number LIKE 'ACC%' 
    ORDER BY accident_number DESC 
    LIMIT 5
""")

accidents = cursor.fetchall()

if accidents:
    print(f"총 {len(accidents)}개의 ACC 사고를 찾았습니다:")
    for acc in accidents:
        print(f"\n사고번호: {acc['accident_number']}")
        print(f"사고명: {acc['accident_name']}")
        print(f"사고날짜: {acc['accident_date']}")
        print(f"custom_data: {acc['custom_data']}")
        
        if acc['custom_data']:
            try:
                parsed_data = json.loads(acc['custom_data'])
                print(f"파싱된 custom_data: {parsed_data}")
                
                # 리스트 필드가 있는지 확인
                list_fields = []
                for key, value in parsed_data.items():
                    if isinstance(value, str) and value.startswith('['):
                        list_fields.append(key)
                        try:
                            parsed_list = json.loads(value)
                            print(f"  리스트 필드 {key}: {len(parsed_list)}개 항목")
                            for idx, item in enumerate(parsed_list):
                                print(f"    {idx+1}: {item}")
                        except:
                            print(f"  리스트 필드 {key}: JSON 파싱 실패")
                
                if not list_fields:
                    print("  리스트 필드 없음")
                    
            except:
                print("  custom_data JSON 파싱 실패")
        else:
            print("  custom_data가 비어있음")
        print("-" * 50)
else:
    print("ACC로 시작하는 사고가 없습니다.")

conn.close()