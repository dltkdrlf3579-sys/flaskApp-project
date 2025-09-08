#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import json

# 데이터베이스 연결
conn = sqlite3.connect('portal.db')
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# 가장 최근 사고 1개만 조회
cursor.execute("""
    SELECT accident_number, accident_name, custom_data
    FROM accidents_cache 
    WHERE accident_number LIKE 'ACC%' 
    ORDER BY accident_number DESC 
    LIMIT 1
""")

accident = cursor.fetchone()

if accident:
    print("="*60)
    print(f"사고번호: {accident['accident_number']}")
    print(f"사고명: {accident['accident_name']}")
    print("="*60)
    
    print(f"\ncustom_data 원본값:")
    print(f"  타입: {type(accident['custom_data'])}")
    print(f"  내용: {accident['custom_data']}")
    
    if accident['custom_data']:
        try:
            data = json.loads(accident['custom_data'])
            print(f"\n파싱된 custom_data:")
            print(f"  타입: {type(data)}")
            print(f"  키들: {list(data.keys())}")
            
            for key, value in data.items():
                print(f"\n  필드: {key}")
                print(f"    타입: {type(value)}")
                print(f"    값: {value}")
                
                if isinstance(value, list):
                    print(f"    ✅ 리스트 정상 저장됨! 항목 수: {len(value)}")
                elif isinstance(value, str) and value.startswith('['):
                    print(f"    ❌ 문자열로 저장됨 (이중 인코딩)")
                    
        except Exception as e:
            print(f"\nJSON 파싱 오류: {e}")
    else:
        print("\ncustom_data가 비어있음")
else:
    print("사고 데이터 없음")

conn.close()