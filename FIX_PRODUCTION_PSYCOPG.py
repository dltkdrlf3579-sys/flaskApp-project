#!/usr/bin/env python3
"""
운영 서버 psycopg 설치 및 확인 스크립트
운영 서버에서 실행하세요!
"""

import sys
import subprocess

def check_psycopg():
    """psycopg 설치 확인"""
    print("=" * 60)
    print("PostgreSQL 드라이버 확인")
    print("=" * 60)
    
    # psycopg 확인
    try:
        import psycopg
        print("✅ psycopg 설치됨 - 버전:", psycopg.__version__)
        return True
    except ImportError:
        print("❌ psycopg 없음")
    
    # psycopg2 확인
    try:
        import psycopg2
        print("✅ psycopg2 설치됨 - 버전:", psycopg2.__version__)
        return True
    except ImportError:
        print("❌ psycopg2 없음")
    
    return False

def install_psycopg():
    """psycopg 자동 설치"""
    print("\n" + "=" * 60)
    print("psycopg 자동 설치 시작")
    print("=" * 60)
    
    commands = [
        # pip 업그레이드
        [sys.executable, "-m", "pip", "install", "--upgrade", "pip"],
        # psycopg[binary] 설치
        [sys.executable, "-m", "pip", "install", "psycopg[binary]"],
    ]
    
    for cmd in commands:
        print(f"\n실행: {' '.join(cmd)}")
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode == 0:
                print("✅ 성공")
            else:
                print(f"⚠️ 경고: {result.stderr}")
                # psycopg[binary] 실패시 psycopg2-binary 시도
                if "psycopg[binary]" in ' '.join(cmd):
                    print("\npsycopg2-binary 설치 시도...")
                    alt_cmd = [sys.executable, "-m", "pip", "install", "psycopg2-binary"]
                    subprocess.run(alt_cmd)
        except Exception as e:
            print(f"❌ 에러: {e}")

def test_connection():
    """PostgreSQL 연결 테스트"""
    print("\n" + "=" * 60)
    print("PostgreSQL 연결 테스트")
    print("=" * 60)
    
    # config.ini 읽기
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    dsn = config.get('DATABASE', 'postgres_dsn', 
                     fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
    
    print(f"연결 문자열: {dsn}")
    
    try:
        # psycopg 시도
        try:
            import psycopg
            conn = psycopg.connect(dsn)
            print("✅ psycopg으로 연결 성공!")
            conn.close()
            return True
        except ImportError:
            pass
        
        # psycopg2 시도
        try:
            import psycopg2
            conn = psycopg2.connect(dsn)
            print("✅ psycopg2로 연결 성공!")
            conn.close()
            return True
        except ImportError:
            pass
            
        print("❌ PostgreSQL 드라이버를 찾을 수 없습니다")
        return False
        
    except Exception as e:
        print(f"❌ 연결 실패: {e}")
        return False

def main():
    print("운영 서버 PostgreSQL 드라이버 설치 도구")
    print("=" * 60)
    
    # 1. 현재 상태 확인
    if not check_psycopg():
        # 2. 자동 설치
        response = input("\npsycopg을 설치하시겠습니까? (yes/no): ")
        if response.lower() == 'yes':
            install_psycopg()
            
            # 3. 재확인
            print("\n설치 후 확인...")
            if check_psycopg():
                print("✅ 설치 완료!")
            else:
                print("❌ 설치 실패. 수동 설치가 필요합니다.")
                print("\n수동 설치 명령어:")
                print("1. pip install psycopg[binary]")
                print("2. 또는 pip install psycopg2-binary")
    
    # 4. 연결 테스트
    print("\n연결 테스트를 하시겠습니까? (yes/no): ", end="")
    if input().lower() == 'yes':
        test_connection()
    
    print("\n" + "=" * 60)
    print("완료!")

if __name__ == "__main__":
    main()