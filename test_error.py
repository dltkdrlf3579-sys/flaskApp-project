import sys
import traceback

# Flask app import 테스트
try:
    from app import app
    print("[OK] App imported successfully")
    
    # 테스트 요청 컨텍스트
    with app.test_request_context('/page/partner-accident'):
        from app import partner_accident
        print("[OK] Testing partner_accident function...")
        
        # 함수 실행
        result = partner_accident()
        print("[OK] Function executed successfully")
        
except Exception as e:
    print(f"[ERROR] {e}")
    traceback.print_exc()