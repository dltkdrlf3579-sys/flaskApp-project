#!/usr/bin/env python3
"""
종합적인 데이터베이스 및 코드 구조 수정 스크립트
1. 모든 테이블명 확인 및 수정
2. detailed_content를 custom_data로 이동
3. 불필요한 _details 테이블 제거
"""
import psycopg
import configparser
import re
import json

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        print(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
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
        print(f"PostgreSQL 연결 실패: {e}")
        return None

def check_current_structure(conn):
    """현재 테이블 구조 확인"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("현재 데이터베이스 구조 확인")
    print("="*60)
    
    # 1. 모든 테이블 목록 확인
    cursor.execute("""
        SELECT table_name 
        FROM information_schema.tables 
        WHERE table_schema = 'public' 
        ORDER BY table_name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    
    print("\n[전체 테이블 목록]")
    for table in tables:
        if 'cache' in table or 'details' in table:
            print(f"  - {table}")
    
    # 2. 잘못된 테이블명 확인
    wrong_names = {
        'followsop_cache': 'follow_sop_cache',
        'fullprocess_cache': 'full_process_cache',
        'accident_cache': 'accidents_cache',
        'safety_instruction_cache': 'safety_instructions_cache',
        'change_request_cache': 'change_requests_cache'
    }
    
    print("\n[테이블명 확인]")
    for wrong, correct in wrong_names.items():
        if wrong in tables:
            print(f"  [문제] {wrong} → {correct}로 변경 필요")
        elif correct in tables:
            print(f"  [OK] {correct} 사용 중")
        else:
            print(f"  [누락] {correct} 테이블이 없음")
    
    # 3. _details 테이블 확인
    details_tables = [
        'safety_instruction_details',
        'followsop_details',
        'accident_details',
        'full_process_details'
    ]
    
    print("\n[별도 상세내용 테이블]")
    for table in details_tables:
        if table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count}개 레코드")

def migrate_details_to_custom_data(conn):
    """_details 테이블의 데이터를 _cache 테이블의 custom_data로 이동"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("상세내용 데이터 마이그레이션")
    print("="*60)
    
    migrations = [
        ('safety_instruction_details', 'safety_instructions_cache', 'issue_number'),
        ('followsop_details', 'follow_sop_cache', 'work_req_no'),
        ('accident_details', 'accidents_cache', 'accident_number'),
        ('full_process_details', 'full_process_cache', 'fullprocess_number')
    ]
    
    for details_table, cache_table, id_column in migrations:
        try:
            # _details 테이블이 존재하는지 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (details_table,))
            
            if not cursor.fetchone()[0]:
                print(f"\n[스킵] {details_table} 테이블이 없음")
                continue
            
            print(f"\n[처리] {details_table} → {cache_table}")
            
            # 데이터 마이그레이션
            cursor.execute(f"""
                UPDATE {cache_table} c
                SET custom_data = 
                    CASE 
                        WHEN c.custom_data IS NULL THEN 
                            jsonb_build_object('detailed_content', d.detailed_content)
                        ELSE 
                            c.custom_data || jsonb_build_object('detailed_content', d.detailed_content)
                    END
                FROM {details_table} d
                WHERE c.{id_column} = d.{id_column}
                  AND d.detailed_content IS NOT NULL 
                  AND d.detailed_content != ''
            """)
            
            migrated = cursor.rowcount
            print(f"  → {migrated}개 레코드 마이그레이션 완료")
            
            # _details 테이블 백업 후 삭제
            backup_name = f"{details_table}_backup"
            cursor.execute(f"ALTER TABLE IF EXISTS {details_table} RENAME TO {backup_name}")
            print(f"  → {details_table} 테이블을 {backup_name}으로 백업")
            
        except Exception as e:
            print(f"  [오류] {details_table}: {e}")

def fix_table_names(conn):
    """잘못된 테이블명 수정"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("테이블명 수정")
    print("="*60)
    
    renames = [
        ('followsop_cache', 'follow_sop_cache'),
        ('fullprocess_cache', 'full_process_cache'),
        ('accident_cache', 'accidents_cache'),
        ('safety_instruction_cache', 'safety_instructions_cache'),
        ('change_request_cache', 'change_requests_cache')
    ]
    
    for old_name, new_name in renames:
        try:
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (old_name,))
            
            if cursor.fetchone()[0]:
                cursor.execute(f"ALTER TABLE {old_name} RENAME TO {new_name}")
                print(f"  [수정] {old_name} → {new_name}")
            else:
                print(f"  [확인] {old_name} 테이블 없음 (정상)")
                
        except Exception as e:
            if "already exists" in str(e):
                print(f"  [확인] {new_name} 이미 존재 (정상)")
            else:
                print(f"  [오류] {old_name}: {e}")

def create_summary_report(conn):
    """최종 상태 보고서 생성"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("최종 상태 보고서")
    print("="*60)
    
    cache_tables = [
        'safety_instructions_cache',
        'follow_sop_cache',
        'full_process_cache',
        'accidents_cache',
        'change_requests_cache'
    ]
    
    for table in cache_tables:
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if not cursor.fetchone()[0]:
                print(f"\n[누락] {table} 테이블이 없음!")
                continue
            
            # 레코드 수 및 detailed_content 포함 여부 확인
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN custom_data->>'detailed_content' IS NOT NULL THEN 1 END) as with_detail
                FROM {table}
            """)
            
            total, with_detail = cursor.fetchone()
            
            print(f"\n[{table}]")
            print(f"  - 전체 레코드: {total}개")
            print(f"  - detailed_content 포함: {with_detail}개")
            
        except Exception as e:
            print(f"\n[오류] {table}: {e}")

def main():
    conn = get_pg_connection()
    if not conn:
        return
    
    try:
        # 1. 현재 구조 확인
        check_current_structure(conn)
        
        # 2. 테이블명 수정
        fix_table_names(conn)
        
        # 3. 상세내용 마이그레이션
        migrate_details_to_custom_data(conn)
        
        # 4. 최종 보고서
        create_summary_report(conn)
        
        print("\n" + "="*60)
        print("[완료] 모든 처리가 완료되었습니다!")
        print("="*60)
        
    except Exception as e:
        print(f"\n[ERROR] 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()