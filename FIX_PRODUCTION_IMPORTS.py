#!/usr/bin/env python3
"""
운영 서버 database_config.py psycopg import 수정
운영 서버에서 실행하세요!
"""

def fix_database_config():
    """database_config.py에 psycopg fallback 추가"""
    
    # database_config.py 읽기
    with open('database_config.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # import 섹션 찾기
    import_end = 0
    for i, line in enumerate(lines):
        if line.startswith('from db_connection'):
            import_end = i
            break
    
    # psycopg import 추가
    psycopg_imports = '''
# PostgreSQL 드라이버 import (fallback 지원)
try:
    import psycopg
    PSYCOPG_AVAILABLE = True
    PSYCOPG_VERSION = 3
    print("[SUCCESS] psycopg (v3) loaded")
except ImportError:
    try:
        import psycopg2
        import psycopg2.extras
        PSYCOPG_AVAILABLE = True
        PSYCOPG_VERSION = 2
        psycopg = psycopg2  # alias for compatibility
        print("[SUCCESS] psycopg2 loaded")
    except ImportError:
        PSYCOPG_AVAILABLE = False
        PSYCOPG_VERSION = None
        print("[ERROR] No PostgreSQL driver available!")

'''
    
    # 이미 있는지 확인
    content = ''.join(lines)
    if 'PSYCOPG_AVAILABLE' not in content:
        lines.insert(import_end + 1, psycopg_imports)
        
        # 파일 쓰기
        with open('database_config.py', 'w', encoding='utf-8') as f:
            f.writelines(lines)
        
        print("✅ database_config.py 수정 완료")
    else:
        print("ℹ️ 이미 수정되어 있습니다")

def fix_db_connection():
    """db_connection.py psycopg import 수정"""
    
    content = '''import configparser
import os

# PostgreSQL 드라이버 자동 선택
try:
    import psycopg
    PSYCOPG_VERSION = 3
    print("Using psycopg (v3)")
except ImportError:
    try:
        import psycopg2
        import psycopg2.extras
        psycopg = psycopg2  # alias
        PSYCOPG_VERSION = 2
        print("Using psycopg2")
    except ImportError:
        PSYCOPG_VERSION = None
        print("WARNING: No PostgreSQL driver available!")

def get_db_connection():
    """PostgreSQL 연결 반환"""
    if PSYCOPG_VERSION is None:
        raise ImportError("PostgreSQL driver not available. Install psycopg or psycopg2-binary")
    
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    dsn = config.get('DATABASE', 'postgres_dsn', 
                     fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
    
    if PSYCOPG_VERSION == 3:
        return psycopg.connect(dsn)
    else:
        return psycopg2.connect(dsn)

def get_postgres_dsn():
    """DSN 문자열 반환"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn',
                     fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
'''
    
    with open('db_connection.py', 'w', encoding='utf-8') as f:
        f.write(content)
    
    print("✅ db_connection.py 수정 완료")

def main():
    print("=" * 60)
    print("운영 서버 Python 파일 수정")
    print("=" * 60)
    
    fix_database_config()
    fix_db_connection()
    
    print("\n완료! 이제 app.py를 재시작하세요.")

if __name__ == "__main__":
    main()