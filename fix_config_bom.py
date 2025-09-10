"""
config.ini BOM 제거 스크립트
"""
import os

def remove_bom(filepath):
    """파일에서 BOM 제거"""
    try:
        with open(filepath, 'rb') as f:
            content = f.read()
        
        # BOM 확인 및 제거
        if content.startswith(b'\xef\xbb\xbf'):
            print(f"BOM 발견! 제거 중...")
            content = content[3:]
            
            # 백업 생성
            backup_path = filepath + '.backup'
            with open(backup_path, 'wb') as f:
                f.write(content[:100] if content.startswith(b'\xef\xbb\xbf') else content)
            print(f"백업 생성: {backup_path}")
            
            # BOM 없이 저장
            with open(filepath, 'wb') as f:
                f.write(content)
            print("BOM 제거 완료!")
            return True
        else:
            print("BOM이 없습니다.")
            return False
            
    except Exception as e:
        print(f"오류 발생: {e}")
        return False

if __name__ == "__main__":
    remove_bom('config.ini')
    print("\n완료! 이제 앱을 다시 실행하세요.")