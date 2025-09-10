#!/usr/bin/env python3
"""
운영 서버 PostgreSQL 연결 테스트
이 스크립트를 운영 서버에서 실행하세요!
"""
import sys
import os

print("=" * 70)
print("운영 서버 PostgreSQL 연결 테스트")
print("=" * 70)

# 1. psycopg 모듈 확인
print("\n[1] PostgreSQL 드라이버 확인")
print("-" * 40)

psycopg_ok = False
try:
    import psycopg
    print(f"✅ psycopg (v3) 설치됨 - 버전: {psycopg.__version__}")
    psycopg_ok = True
    driver = 'psycopg3'
except ImportError:
    print("❌ psycopg (v3) 없음")
    
    try:
        import psycopg2
        print(f"✅ psycopg2 설치됨 - 버전: {psycopg2.__version__}")
        psycopg_ok = True
        driver = 'psycopg2'
    except ImportError:
        print("❌ psycopg2도 없음")
        driver = None

if not psycopg_ok:
    print("\n⚠️ PostgreSQL 드라이버가 없습니다!")
    print("다음 명령어로 설치하세요:")
    print("  pip install psycopg2-binary")
    sys.exit(1)

# 2. config.ini 확인
print("\n[2] config.ini 설정 확인")
print("-" * 40)

import configparser
config = configparser.ConfigParser()
config.read('config.ini', encoding='utf-8')

backend = config.get('DATABASE', 'db_backend', fallback='sqlite')
print(f"db_backend: {backend}")

if backend != 'postgres':
    print("⚠️ config.ini에서 db_backend가 'postgres'가 아닙니다!")
    print("config.ini 파일을 수정하세요:")
    print("[DATABASE]")
    print("db_backend = postgres")

dsn = config.get('DATABASE', 'postgres_dsn', fallback='없음')
print(f"postgres_dsn: {dsn}")

if dsn == '없음':
    print("⚠️ postgres_dsn이 설정되지 않았습니다!")
    print("config.ini에 추가하세요:")
    print("postgres_dsn = postgresql://사용자:비밀번호@호스트:포트/데이터베이스")
    sys.exit(1)

# 3. 직접 연결 테스트
print("\n[3] PostgreSQL 직접 연결 테스트")
print("-" * 40)

try:
    if driver == 'psycopg3':
        import psycopg
        conn = psycopg.connect(dsn)
        print("✅ psycopg3로 연결 성공!")
    else:
        import psycopg2
        conn = psycopg2.connect(dsn)
        print("✅ psycopg2로 연결 성공!")
    
    cursor = conn.cursor()
    cursor.execute("SELECT version()")
    version = cursor.fetchone()[0]
    print(f"PostgreSQL 버전: {version}")
    
    cursor.execute("SELECT current_database()")
    db_name = cursor.fetchone()[0]
    print(f"데이터베이스명: {db_name}")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 연결 실패: {e}")
    print("\n가능한 원인:")
    print("1. PostgreSQL 서버가 실행되지 않음")
    print("2. 방화벽이 포트를 차단함")
    print("3. 사용자명/비밀번호가 틀림")
    print("4. 데이터베이스가 존재하지 않음")
    sys.exit(1)

# 4. db_connection.py 테스트
print("\n[4] db_connection.py 모듈 테스트")
print("-" * 40)

try:
    from db_connection import get_db_connection
    conn = get_db_connection()
    print("✅ get_db_connection() 성공!")
    
    cursor = conn.cursor()
    cursor.execute("SELECT 1")
    result = cursor.fetchone()
    print(f"테스트 쿼리 결과: {result}")
    
    conn.close()
    
except Exception as e:
    print(f"❌ get_db_connection() 실패: {e}")
    print("\ndb/compat.py 파일이 수정되었는지 확인하세요")

# 5. 테이블 확인
print("\n[5] 테이블 존재 확인")
print("-" * 40)

try:
    if driver == 'psycopg3':
        import psycopg
        conn = psycopg.connect(dsn)
    else:
        import psycopg2
        conn = psycopg2.connect(dsn)
    
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_type = 'BASE TABLE'
    """)
    
    table_count = cursor.fetchone()[0]
    print(f"테이블 개수: {table_count}개")
    
    if table_count == 0:
        print("⚠️ 테이블이 없습니다. 마이그레이션이 필요합니다.")
    else:
        # 주요 테이블 확인
        important_tables = [
            'accidents', 'safety_instructions', 
            'follow_sop', 'full_process'
        ]
        
        for table in important_tables:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            exists = cursor.fetchone()[0]
            if exists:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} - 없음")
    
    cursor.close()
    conn.close()
    
except Exception as e:
    print(f"❌ 테이블 확인 실패: {e}")

print("\n" + "=" * 70)
print("테스트 완료!")
print("=" * 70)