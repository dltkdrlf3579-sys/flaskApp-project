"""
인코딩 설정 스크립트
Git Bash와 Windows 콘솔에서 출력/입력 한글 설정
"""
import sys
import os
import locale
import io

def setup_encoding():
    """인코딩 설정"""
    
    # 1. 환경 변수 설정
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    
    # 2. stdout/stderr를 UTF-8로 재설정
    if sys.platform == 'win32':
        # Windows에서 UTF-8 출력 설정
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        
        # Windows 콘솔 코드 페이지를 UTF-8로 설정
        import subprocess
        try:
            subprocess.run('chcp 65001', shell=True, capture_output=True)
        except:
            pass
    
    # 3. 로케일 설정
    try:
        locale.setlocale(locale.LC_ALL, 'ko_KR.UTF-8')
    except:
        try:
            locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
        except:
            pass
    
    print("✅ 인코딩 설정 완료")
    print("안녕하세요 세계!")
    print(f"Python 인코딩: {sys.getdefaultencoding()}")
    print(f"stdout 인코딩: {sys.stdout.encoding}")
    print(f"로케일: {locale.getlocale()}")

if __name__ == "__main__":
    setup_encoding()
