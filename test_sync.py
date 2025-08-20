#!/usr/bin/env python3
"""
간단한 DB 동기화 테스트 스크립트
"""

import sys
import os

# 현재 디렉토리를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database_config import partner_manager

def test_simple_sync():
    """간단한 DB 동기화 테스트"""
    print("🧪 DB 동기화 테스트 시작")
    print("=" * 50)
    
    try:
        # 협력사 동기화 실행
        print("📥 협력사 데이터 동기화 실행 중...")
        success = partner_manager.sync_partners_from_external_db()
        
        if success:
            print("✅ 동기화 성공!")
            
            # 결과 확인
            partners, total = partner_manager.get_all_partners(page=1, per_page=3)
            print(f"📊 총 {total}건의 데이터가 동기화되었습니다.")
            
            if partners:
                print("\n📋 샘플 데이터 (상위 3건):")
                for i, partner in enumerate(partners, 1):
                    print(f"  {i}. {partner['company_name']} ({partner['business_number']})")
                    print(f"     Class: {partner['partner_class'] or '-'}")
                    print(f"     업종: {partner['business_type_major'] or '-'}")
                    print(f"     위험작업: {'예' if partner['hazard_work_flag'] == 'O' else '아니오' if partner['hazard_work_flag'] == 'X' else '-'}")
                    print(f"     거래차수: {partner['transaction_count'] or '-'}")
                    print()
            else:
                print("⚠️ 동기화된 데이터가 없습니다.")
                
        else:
            print("❌ 협력사 동기화 실패!")
        
        # 사고 데이터 동기화 실행
        print("\n📥 사고 데이터 동기화 실행 중...")
        accidents_success = partner_manager.sync_accidents_from_external_db()
        
        if accidents_success:
            print("✅ 사고 동기화 성공!")
        else:
            print("❌ 사고 동기화 실패!")
            
    except Exception as e:
        print(f"🚨 테스트 중 오류 발생: {e}")
        import traceback
        traceback.print_exc()
    
    print("=" * 50)
    print("🏁 테스트 완료")

if __name__ == "__main__":
    test_simple_sync()