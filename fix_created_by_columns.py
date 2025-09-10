#!/usr/bin/env python3
"""
모든 _cache 테이블에 created_by 컬럼 추가
"""
import psycopg
import configparser
import re
import logging

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        logging.error(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
        return None
    
    user, password, host, port, database = match.groups()
    
    try:
        conn = psycopg.connect(
            host=host,
            port=int(port),
            dbname=database,
            user=user,
            password=password
        )
        conn.autocommit = True
        return conn
    except Exception as e:
        logging.error(f"PostgreSQL 연결 실패: {e}")
        return None

def check_and_add_columns(conn):
    """모든 _cache 테이블에 필요한 컬럼 확인 및 추가"""
    cursor = conn.cursor()
    
    # 확인할 테이블 목록
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache', 
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache',
        'partner_standards_cache'
    ]
    
    # 각 테이블에 필요한 컬럼들
    required_columns = {
        'created_by': 'TEXT',
        'updated_by': 'TEXT',
        'department': 'TEXT',
        'status': 'TEXT',
        'request_date': 'DATE',
        'process_date': 'DATE',
        'work_type': 'TEXT',
        'process_type': 'TEXT'
    }
    
    for table in tables:
        print(f"\n{'='*60}")
        print(f"[{table}] 테이블 점검")
        print('='*60)
        
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if not cursor.fetchone()[0]:
                print(f"[WARNING] {table} 테이블이 존재하지 않습니다.")
                continue
            
            # 현재 컬럼 확인
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
            """, (table,))
            
            existing_columns = {row[0] for row in cursor.fetchall()}
            print(f"기존 컬럼: {', '.join(existing_columns)}")
            
            # 필요한 컬럼 추가
            added = []
            for col_name, col_type in required_columns.items():
                if col_name not in existing_columns:
                    try:
                        cursor.execute(f"""
                            ALTER TABLE {table}
                            ADD COLUMN IF NOT EXISTS {col_name} {col_type}
                        """)
                        added.append(col_name)
                        print(f"  [추가] {col_name} ({col_type})")
                    except Exception as e:
                        print(f"  [ERROR] {col_name} 추가 실패: {e}")
            
            if added:
                print(f"[OK] {len(added)}개 컬럼 추가됨: {', '.join(added)}")
            else:
                print(f"[OK] 모든 필수 컬럼이 이미 존재합니다.")
                
        except Exception as e:
            print(f"[ERROR] {table} 처리 중 오류: {e}")

def verify_columns(conn):
    """컬럼 추가 확인"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("컬럼 추가 검증")
    print("="*60)
    
    tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache',
        'partner_standards_cache'
    ]
    
    for table in tables:
        try:
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table,))
            
            columns = [row[0] for row in cursor.fetchall()]
            
            # created_by와 updated_by 확인
            has_created_by = 'created_by' in columns
            has_updated_by = 'updated_by' in columns
            
            status = "[OK]" if has_created_by else "[MISSING]"
            print(f"{status} {table}: created_by={has_created_by}, updated_by={has_updated_by}")
            print(f"     전체 컬럼 수: {len(columns)}")
            
        except Exception as e:
            print(f"[ERROR] {table}: {e}")

def main():
    """메인 실행"""
    print("="*60)
    print("_cache 테이블 created_by 컬럼 추가")
    print("="*60)
    
    conn = get_pg_connection()
    if not conn:
        return
    
    try:
        # 1. 컬럼 확인 및 추가
        check_and_add_columns(conn)
        
        # 2. 검증
        verify_columns(conn)
        
        print("\n[완료] 모든 테이블에 필요한 컬럼이 추가되었습니다!")
        
    except Exception as e:
        print(f"\n[ERROR] 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()