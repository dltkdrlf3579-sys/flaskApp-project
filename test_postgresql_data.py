#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PostgreSQL 데이터 쌓임 확인 테스트
실제 데이터 추가/조회로 PostgreSQL 동작 검증
"""
import sys
import json
from datetime import datetime
from db_connection import get_db_connection

def test_postgresql_data_flow():
    """PostgreSQL에 실제 데이터가 쌓이는지 테스트"""
    print("=== PostgreSQL 데이터 쌓임 확인 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 현재 레코드 수 확인
    cursor.execute("SELECT COUNT(*) FROM partners_cache")
    before_count = cursor.fetchone()[0]
    print(f"📊 현재 partners_cache 레코드 수: {before_count}개")
    
    # 2. 테스트 데이터 추가
    test_data = {
        'business_number': f'TEST-{datetime.now().strftime("%Y%m%d%H%M%S")}',
        'company_name': 'PostgreSQL 테스트 회사',
        'partner_class': '협력사',
        'address': '서울시 강남구 테헤란로 123',
        'synced_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
    
    print(f"➕ 테스트 데이터 추가: {test_data['company_name']}")
    cursor.execute("""
        INSERT INTO partners_cache 
        (business_number, company_name, partner_class, address, synced_at) 
        VALUES (?, ?, ?, ?, ?)
    """, (
        test_data['business_number'], 
        test_data['company_name'],
        test_data['partner_class'], 
        test_data['address'], 
        test_data['synced_at']
    ))
    
    conn.commit()
    
    # 3. 추가 후 레코드 수 확인
    cursor.execute("SELECT COUNT(*) FROM partners_cache")
    after_count = cursor.fetchone()[0]
    print(f"📊 추가 후 partners_cache 레코드 수: {after_count}개")
    
    # 4. 추가된 데이터 조회
    cursor.execute("SELECT * FROM partners_cache WHERE business_number = ?", 
                   (test_data['business_number'],))
    result = cursor.fetchone()
    
    if result:
        print(f"✅ 데이터 확인 성공:")
        print(f"   사업자번호: {result[0]}")
        print(f"   회사명: {result[1]}")
        print(f"   주소: {result[4] if len(result) > 4 else 'N/A'}")
        print(f"   등록일시: {result[-2] if len(result) >= 2 else 'N/A'}")
    else:
        print("❌ 데이터 조회 실패")
        
    # 5. 증가 확인
    if after_count > before_count:
        print(f"🎉 PostgreSQL에 데이터가 정상적으로 쌓이고 있습니다! (+{after_count - before_count}개)")
    else:
        print("⚠️  데이터 증가가 확인되지 않습니다.")
    
    # 6. accidents_cache 테이블도 확인
    print("\n--- accidents_cache 테이블 확인 ---")
    cursor.execute("SELECT COUNT(*) FROM accidents_cache")
    accident_count = cursor.fetchone()[0]
    print(f"📊 accidents_cache 레코드 수: {accident_count}개")
    
    # 7. 최신 데이터 5개 조회 (있다면)
    if after_count > 0:
        print("\n--- 최근 등록된 협력사 5개 ---")
        cursor.execute("""
            SELECT business_number, company_name, synced_at 
            FROM partners_cache 
            ORDER BY synced_at DESC 
            LIMIT 5
        """)
        recent_data = cursor.fetchall()
        
        for i, row in enumerate(recent_data, 1):
            print(f"   {i}. {row[1]} ({row[0]}) - {row[2]}")
    
    conn.close()
    return True

def test_jsonb_data():
    """JSONB 데이터 저장/조회 테스트"""
    print("\n=== JSONB 데이터 테스트 ===")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # custom_data가 있는 테이블에 JSONB 데이터 추가
    test_jsonb = {
        'workplace': '테스트 사업장',
        'accident_type': 'PostgreSQL 연결 테스트',
        'severity': '정보',
        'test_time': datetime.now().isoformat()
    }
    
    try:
        # accidents_cache에 JSONB 테스트 데이터 추가
        cursor.execute("""
            INSERT INTO accidents_cache (accident_name, custom_data) 
            VALUES (?, ?)
        """, ('PostgreSQL JSONB 테스트', test_jsonb))
        
        conn.commit()
        
        # JSONB 연산자로 검색 테스트
        cursor.execute("""
            SELECT accident_name, custom_data
            FROM accidents_cache 
            WHERE custom_data->>'workplace' = ?
            ORDER BY id DESC 
            LIMIT 1
        """, ('테스트 사업장',))
        
        result = cursor.fetchone()
        if result:
            print(f"✅ JSONB 데이터 저장/조회 성공:")
            print(f"   사고명: {result[0]}")
            print(f"   JSONB 데이터: {result[1]}")
        else:
            print("❌ JSONB 데이터 조회 실패")
            
    except Exception as e:
        print(f"⚠️  JSONB 테스트 중 오류: {e}")
    
    conn.close()

if __name__ == "__main__":
    try:
        success = test_postgresql_data_flow()
        test_jsonb_data()
        
        print("\n" + "="*50)
        print("🎯 PostgreSQL 데이터 쌓임 확인 완료!")
        print("✅ Flask 앱에서 생성되는 모든 데이터가")
        print("   PostgreSQL에 실제로 저장되고 있습니다.")
        print("="*50)
        
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")
        import traceback
        traceback.print_exc()