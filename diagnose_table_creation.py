#!/usr/bin/env python3
"""
테이블 생성 실패 원인을 진단하는 스크립트
CREATE TABLE이 성공으로 표시되지만 실제로 생성되지 않는 이유를 찾음
"""
import psycopg
import configparser
import traceback

def get_postgres_dsn():
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    return config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')

def diagnose_table_creation():
    dsn = get_postgres_dsn()
    
    print("=" * 70)
    print("테이블 생성 문제 진단")
    print("=" * 70)
    
    # 테스트용 테이블 이름
    test_table = 'safety_instruction_column_config'
    
    try:
        # 1. 연결 및 기본 정보
        conn = psycopg.connect(dsn)
        cursor = conn.cursor()
        
        print("\n1. 데이터베이스 연결 정보:")
        cursor.execute("SELECT current_database(), current_schema(), current_user")
        db, schema, user = cursor.fetchone()
        print(f"   Database: {db}")
        print(f"   Schema: {schema}") 
        print(f"   User: {user}")
        
        # 2. 권한 확인
        print("\n2. 사용자 권한 확인:")
        cursor.execute("""
            SELECT has_table_privilege(current_user, 'pg_catalog.pg_class', 'SELECT'),
                   has_schema_privilege(current_user, 'public', 'CREATE')
        """)
        select_priv, create_priv = cursor.fetchone()
        print(f"   SELECT 권한: {select_priv}")
        print(f"   CREATE 권한: {create_priv}")
        
        # 3. 테이블 삭제 시도 (자동 커밋 모드)
        print(f"\n3. {test_table} 테이블 삭제 시도:")
        try:
            cursor.execute(f"DROP TABLE IF EXISTS {test_table}")
            conn.commit()  # 명시적 커밋
            print("   삭제 성공 (있었다면)")
        except Exception as e:
            print(f"   삭제 실패: {e}")
            conn.rollback()
        
        # 4. 테이블 생성 시도 - 각 단계별로 확인
        print(f"\n4. {test_table} 테이블 생성 시도:")
        
        create_sql = f'''
            CREATE TABLE {test_table} (
                id SERIAL PRIMARY KEY,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        '''
        
        print("   SQL 실행 중...")
        cursor.execute(create_sql)
        print("   SQL 실행 완료")
        
        # 커밋 전 확인
        print("\n5. 커밋 전 테이블 존재 확인:")
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{test_table}'
            )
        """)
        exists_before = cursor.fetchone()[0]
        print(f"   커밋 전 존재 여부: {exists_before}")
        
        # 명시적 커밋
        print("\n6. 커밋 실행:")
        conn.commit()
        print("   커밋 완료")
        
        # 커밋 후 확인
        print("\n7. 커밋 후 테이블 존재 확인:")
        cursor.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{test_table}'
            )
        """)
        exists_after = cursor.fetchone()[0]
        print(f"   커밋 후 존재 여부: {exists_after}")
        
        if exists_after:
            # 테이블이 있으면 데이터 삽입 테스트
            print("\n8. 데이터 삽입 테스트:")
            try:
                cursor.execute(f"""
                    INSERT INTO {test_table} (column_key, column_name) 
                    VALUES ('test_key', 'test_name')
                """)
                conn.commit()
                print("   삽입 성공")
                
                cursor.execute(f"SELECT COUNT(*) FROM {test_table}")
                count = cursor.fetchone()[0]
                print(f"   현재 행 수: {count}")
            except Exception as e:
                print(f"   삽입 실패: {e}")
        
        # 9. 새 연결로 재확인
        print("\n9. 새 연결로 재확인:")
        cursor.close()
        conn.close()
        
        conn2 = psycopg.connect(dsn)
        cursor2 = conn2.cursor()
        
        cursor2.execute(f"""
            SELECT EXISTS (
                SELECT FROM information_schema.tables 
                WHERE table_name = '{test_table}'
            )
        """)
        exists_new_conn = cursor2.fetchone()[0]
        print(f"   새 연결에서 존재 여부: {exists_new_conn}")
        
        if exists_new_conn:
            cursor2.execute(f"SELECT COUNT(*) FROM {test_table}")
            count2 = cursor2.fetchone()[0]
            print(f"   새 연결에서 행 수: {count2}")
        
        # 10. pg_tables로도 확인
        print("\n10. pg_tables 시스템 뷰로 확인:")
        cursor2.execute(f"""
            SELECT tablename, schemaname 
            FROM pg_tables 
            WHERE tablename = '{test_table}'
        """)
        result = cursor2.fetchall()
        if result:
            for row in result:
                print(f"   찾음: {row}")
        else:
            print("   pg_tables에서 찾을 수 없음")
        
        cursor2.close()
        conn2.close()
        
        print("\n" + "=" * 70)
        if exists_new_conn:
            print("✅ 테이블 생성 성공!")
        else:
            print("❌ 테이블 생성 실패 - 원인 불명")
            print("\n가능한 원인:")
            print("1. 트랜잭션 격리 수준 문제")
            print("2. 다른 스키마에 생성됨")
            print("3. DDL 문 실행 권한 부족")
        
    except Exception as e:
        print(f"\n❌ 진단 중 오류 발생:")
        print(f"   {e}")
        print("\n상세 오류:")
        print(traceback.format_exc())

if __name__ == "__main__":
    diagnose_table_creation()