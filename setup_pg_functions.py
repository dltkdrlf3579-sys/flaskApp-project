#!/usr/bin/env python3
"""
PostgreSQL SQLite 호환 함수 설치 스크립트 - v7
"""
import psycopg
import configparser
import os

def get_config():
    """config.ini에서 DB 설정 읽기"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        
        # DATABASE 섹션에서 postgres_dsn 직접 읽기
        postgres_dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')
        
        return postgres_dsn, postgres_dsn  # admin과 portal 동일하게 사용
    else:
        # 기본값 사용
        print('WARN - config.ini not found, using defaults')
        postgres_dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
        return postgres_dsn, postgres_dsn

def setup_compatibility_functions():
    """SQLite 호환 함수들을 PostgreSQL에 설치"""
    
    postgres_dsn, _ = get_config()
    print(f'INFO - Connecting with DSN: {postgres_dsn.replace(":admin123@", ":***@")}')
    
    # postgres 계정으로 연결
    conn = psycopg.connect(postgres_dsn)
    conn.autocommit = True
    cur = conn.cursor()
    
    try:
        # SQLite json_extract 호환 함수 (JSONB 버전)
        json_extract_jsonb_sql = """
        CREATE OR REPLACE FUNCTION json_extract(data jsonb, path text)
        RETURNS text IMMUTABLE LANGUAGE sql AS $$
          SELECT data #>> string_to_array(regexp_replace(path, '^\\$\\.?',''), '.')
        $$;
        """
        cur.execute(json_extract_jsonb_sql)
        print('OK - json_extract(jsonb, text) function created')
        
        # TEXT 오버로드 함수 추가 (호환성용)
        json_extract_text_sql = """
        CREATE OR REPLACE FUNCTION json_extract(data text, path text)
        RETURNS text IMMUTABLE LANGUAGE sql AS $$
          SELECT (data::jsonb) #>> string_to_array(regexp_replace(path, '^\\$\\.?',''), '.')
        $$;
        """
        cur.execute(json_extract_text_sql)
        print('OK - json_extract(text, text) function created')
        
        # SQLite datetime('now') 호환 함수
        datetime_sql = """
        CREATE OR REPLACE FUNCTION datetime(val text)
        RETURNS timestamp LANGUAGE sql AS $$
          SELECT CASE WHEN val = 'now' THEN CURRENT_TIMESTAMP ELSE val::timestamp END
        $$;
        """
        cur.execute(datetime_sql)
        print('OK - datetime function created')
        
        # portal_user에게 함수 실행 권한 부여
        cur.execute('GRANT EXECUTE ON FUNCTION json_extract(jsonb, text) TO portal_user')
        cur.execute('GRANT EXECUTE ON FUNCTION json_extract(text, text) TO portal_user')
        cur.execute('GRANT EXECUTE ON FUNCTION datetime(text) TO portal_user')
        print('OK - Function permissions granted to portal_user')
        
        # 테스트
        test_json = """{"test": "value", "nested": {"key": "nested_value"}}"""
        cur.execute("SELECT json_extract(%s::jsonb, '$.test')", (test_json,))
        result1 = cur.fetchone()[0]
        print(f'OK - json_extract test: {result1}')
        
        cur.execute("SELECT json_extract(%s::jsonb, '$.nested.key')", (test_json,))
        result2 = cur.fetchone()[0]
        print(f'OK - json_extract nested test: {result2}')
        
        # TEXT 오버로드 테스트
        cur.execute("SELECT json_extract(%s, '$.test')", (test_json,))
        result3 = cur.fetchone()[0]
        print(f'OK - json_extract(text) test: {result3}')
        
        cur.execute("SELECT datetime('now')")
        result4 = cur.fetchone()[0]
        print(f'OK - datetime test: {result4}')
        
        # 기본 데이터베이스 정보 확인
        cur.execute("SELECT current_database(), current_user, version()")
        db_info = cur.fetchone()
        print(f'OK - Database: {db_info[0]}, User: {db_info[1]}')
        print(f'OK - Version: {db_info[2][:50]}...')
        
    except Exception as e:
        print(f'ERROR - {e}')
        return False
    
    finally:
        conn.close()
    
    print('\nSUCCESS - PostgreSQL compatibility functions installed successfully!')
    return True

def test_portal_user_access():
    """portal_user 계정으로 함수 접근 테스트"""
    
    try:
        _, portal_dsn = get_config()
        print(f'INFO - Testing portal_user access: {portal_dsn.replace(":admin123@", ":***@")}')
        
        conn = psycopg.connect(portal_dsn)
        cur = conn.cursor()
        
        # 함수 접근 테스트
        test_json = """{"workplace": "공장A", "level": 1}"""
        cur.execute("SELECT json_extract(%s::jsonb, '$.workplace')", (test_json,))
        result = cur.fetchone()[0]
        print(f'OK - portal_user json_extract(jsonb) test: {result}')
        
        # TEXT 오버로드 테스트 
        cur.execute("SELECT json_extract(%s, '$.workplace')", (test_json,))
        result = cur.fetchone()[0]
        print(f'OK - portal_user json_extract(text) test: {result}')
        
        cur.execute("SELECT datetime('now')")
        result = cur.fetchone()[0]
        print(f'OK - portal_user datetime test: {result}')
        
        conn.close()
        print('OK - portal_user function access: SUCCESS')
        return True
        
    except Exception as e:
        print(f'ERROR - portal_user function access failed: {e}')
        return False

if __name__ == '__main__':
    print('SETUP - Setting up PostgreSQL compatibility functions...\n')
    
    if setup_compatibility_functions():
        print('\nTEST - Testing portal_user access...\n')
        test_portal_user_access()
        print('\nCOMPLETE - Setup completed successfully!')
    else:
        print('\nFAILED - Setup failed!')