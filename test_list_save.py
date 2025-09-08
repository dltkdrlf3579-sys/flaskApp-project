#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sqlite3
import json
from datetime import datetime

def test_list_field_save():
    """리스트 필드 저장 테스트"""
    
    # 데이터베이스 연결
    conn = sqlite3.connect('portal.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    print("="*60)
    print("리스트 필드 저장 테스트")
    print("="*60)
    
    # 가장 최근 ACC 사고 조회
    cursor.execute("""
        SELECT accident_number, accident_name, custom_data, accident_date
        FROM accidents_cache 
        WHERE accident_number LIKE 'ACC%' 
        ORDER BY accident_number DESC 
        LIMIT 3
    """)
    
    accidents = cursor.fetchall()
    
    if accidents:
        print(f"\n최근 {len(accidents)}개 ACC 사고:")
        print("-" * 60)
        
        for acc in accidents:
            print(f"\n사고번호: {acc['accident_number']}")
            print(f"사고명: {acc['accident_name']}")
            print(f"사고날짜: {acc['accident_date']}")
            
            if acc['custom_data']:
                try:
                    custom_data = json.loads(acc['custom_data'])
                    print(f"custom_data 타입: {type(custom_data)}")
                    
                    # 리스트 필드 찾기
                    list_fields = []
                    for key, value in custom_data.items():
                        if isinstance(value, list):
                            list_fields.append(key)
                            print(f"\n  ✅ 리스트 필드 '{key}': {len(value)}개 항목")
                            for idx, item in enumerate(value, 1):
                                print(f"    {idx}. {item}")
                        elif isinstance(value, str):
                            # 문자열이지만 JSON 배열처럼 생긴 경우
                            if value.startswith('['):
                                print(f"\n  ❌ 문자열로 저장된 필드 '{key}': {value[:100]}...")
                                try:
                                    parsed = json.loads(value)
                                    if isinstance(parsed, list):
                                        print(f"     -> 파싱하면 {len(parsed)}개 항목의 리스트")
                                        for idx, item in enumerate(parsed, 1):
                                            print(f"        {idx}. {item}")
                                except:
                                    print(f"     -> JSON 파싱 실패")
                    
                    if not list_fields:
                        # tteesstt 필드 특별 체크
                        if 'tteesstt' in custom_data:
                            tteesstt_value = custom_data['tteesstt']
                            print(f"\n  ⚠️ tteesstt 필드 발견:")
                            print(f"    타입: {type(tteesstt_value)}")
                            print(f"    값: {tteesstt_value}")
                            if tteesstt_value == "[]":
                                print(f"    -> 빈 배열 문자열로 저장됨 (이중 인코딩 문제!)")
                        else:
                            print("\n  리스트 필드 없음")
                    
                except Exception as e:
                    print(f"  custom_data 파싱 오류: {e}")
            else:
                print("  custom_data 없음")
            
            print("-" * 60)
    else:
        print("ACC 사고가 없습니다.")
    
    # 컬럼 설정 확인
    print("\n\n컬럼 설정 확인:")
    print("-" * 60)
    
    cursor.execute("""
        SELECT cc.column_key, cc.column_name, cc.column_type, sc.section_name
        FROM columns_config cc
        LEFT JOIN sections_config sc ON cc.tab = sc.section_key
        WHERE cc.column_type = 'list'
        AND cc.board_type = 'accident'
    """)
    
    list_columns = cursor.fetchall()
    
    if list_columns:
        print(f"{len(list_columns)}개의 리스트 타입 컬럼:")
        for col in list_columns:
            print(f"  - {col['column_key']} ({col['column_name']}) in {col['section_name']}")
    else:
        print("리스트 타입 컬럼이 설정되지 않음")
    
    conn.close()
    
    print("\n" + "="*60)
    print("테스트 완료")
    print("="*60)
    print("\n💡 이중 인코딩 문제 해결 확인:")
    print("  1. 리스트 필드가 배열로 저장되면 ✅")
    print("  2. 리스트 필드가 문자열 '[]'로 저장되면 ❌")
    print("  3. collectDynamicFields에서 JSON.parse가 제대로 동작하는지 확인 필요")

if __name__ == "__main__":
    test_list_field_save()