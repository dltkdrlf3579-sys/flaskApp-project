#!/usr/bin/env python3
"""
모든 게시판의 컬럼 데이터 복구 스크립트
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

def add_is_list_display_column(conn):
    """모든 column_config 테이블에 is_list_display 컬럼 추가"""
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_column_config',
        'follow_sop_column_config',
        'full_process_column_config',
        'accident_column_config',
        'change_request_column_config'
    ]
    
    for table in tables:
        try:
            # is_list_display 컬럼 추가
            cursor.execute(f"""
                ALTER TABLE {table}
                ADD COLUMN IF NOT EXISTS is_list_display INTEGER DEFAULT 1
            """)
            logging.info(f"[OK] {table}: is_list_display 컬럼 추가")
        except Exception as e:
            logging.error(f"[ERROR] {table}: {e}")

def restore_safety_instruction_columns(conn):
    """환경안전 지시서 컬럼 복구"""
    cursor = conn.cursor()
    
    columns = [
        ('issue_number', '지시서번호', 'text', 'basic_info', 1, 1),
        ('company_name', '회사명', 'text', 'basic_info', 2, 1),
        ('business_number', '사업자번호', 'text', 'basic_info', 3, 1),
        ('issue_date', '발행일', 'date', 'basic_info', 4, 1),
        ('improvement_deadline', '개선기한', 'date', 'basic_info', 5, 1),
        ('status', '상태', 'dropdown', 'basic_info', 6, 1),
        ('issuer', '발행자', 'text', 'basic_info', 7, 0),
        ('recipient', '수신자', 'text', 'basic_info', 8, 0),
        ('created_at', '등록일', 'datetime', 'basic_info', 9, 1),
        
        ('violation_type', '위반유형', 'dropdown', 'violation_info', 10, 1),
        ('violation_details', '위반내용', 'textarea', 'violation_info', 11, 0),
        ('legal_basis', '법적근거', 'text', 'violation_info', 12, 0),
        ('penalty', '과태료', 'number', 'violation_info', 13, 1),
        ('violation_location', '위반장소', 'text', 'violation_info', 14, 1),
        ('violation_date', '위반일자', 'date', 'violation_info', 15, 1),
        ('violation_severity', '위반심각도', 'dropdown', 'violation_info', 16, 1),
        
        ('attachments', '첨부파일', 'file', 'additional', 17, 0),
        ('notes', '비고', 'textarea', 'additional', 18, 0),
        ('detailed_content', '상세내용', 'textarea', 'additional', 19, 0)
    ]
    
    # 먼저 테이블 비우기
    cursor.execute("DELETE FROM safety_instruction_column_config")
    
    # 데이터 삽입
    for col_key, col_name, col_type, tab, order, is_list in columns:
        cursor.execute("""
            INSERT INTO safety_instruction_column_config 
            (column_key, column_name, column_type, tab, column_order, is_active, is_list_display, is_deleted)
            VALUES (%s, %s, %s, %s, %s, 1, %s, 0)
        """, (col_key, col_name, col_type, tab, order, is_list))
    
    logging.info(f"[OK] safety_instruction_column_config: {len(columns)}개 컬럼 복구")

def restore_follow_sop_columns(conn):
    """Follow SOP 컬럼 복구"""
    cursor = conn.cursor()
    
    columns = [
        ('work_req_no', '작업요청번호', 'text', 'basic_info', 1, 1),
        ('company_name', '회사명', 'text', 'basic_info', 2, 1),
        ('business_number', '사업자번호', 'text', 'basic_info', 3, 1),
        ('request_date', '요청일', 'date', 'basic_info', 4, 1),
        ('department', '부서', 'text', 'basic_info', 5, 1),
        ('created_by', '작성자', 'text', 'basic_info', 6, 1),
        ('created_at', '등록일', 'datetime', 'basic_info', 7, 1),
        
        ('work_type', '작업유형', 'dropdown', 'work_info', 8, 1),
        ('work_location', '작업장소', 'text', 'work_info', 9, 1),
        ('work_content', '작업내용', 'textarea', 'work_info', 10, 0),
        ('work_status', '작업상태', 'dropdown', 'work_info', 11, 1),
        ('worker_count', '작업인원', 'number', 'work_info', 12, 1),
        ('work_duration', '작업기간', 'text', 'work_info', 13, 0),
        ('safety_measures', '안전조치', 'list', 'work_info', 14, 0),
        
        ('attachments', '첨부파일', 'file', 'additional', 15, 0),
        ('notes', '비고', 'textarea', 'additional', 16, 0),
        ('detailed_content', '상세내용', 'textarea', 'additional', 17, 0)
    ]
    
    cursor.execute("DELETE FROM follow_sop_column_config")
    
    for col_key, col_name, col_type, tab, order, is_list in columns:
        cursor.execute("""
            INSERT INTO follow_sop_column_config 
            (column_key, column_name, column_type, tab, column_order, is_active, is_list_display, is_deleted)
            VALUES (%s, %s, %s, %s, %s, 1, %s, 0)
        """, (col_key, col_name, col_type, tab, order, is_list))
    
    logging.info(f"[OK] follow_sop_column_config: {len(columns)}개 컬럼 복구")

def restore_full_process_columns(conn):
    """Full Process 컬럼 복구"""
    cursor = conn.cursor()
    
    columns = [
        ('fullprocess_number', '프로세스번호', 'text', 'basic_info', 1, 1),
        ('company_name', '회사명', 'text', 'basic_info', 2, 1),
        ('business_number', '사업자번호', 'text', 'basic_info', 3, 1),
        ('process_date', '프로세스일자', 'date', 'basic_info', 4, 1),
        ('department', '부서', 'text', 'basic_info', 5, 1),
        ('created_by', '작성자', 'text', 'basic_info', 6, 1),
        ('created_at', '등록일', 'datetime', 'basic_info', 7, 1),
        
        ('process_type', '프로세스유형', 'dropdown', 'process_info', 8, 1),
        ('process_name', '프로세스명', 'text', 'process_info', 9, 1),
        ('process_status', '프로세스상태', 'dropdown', 'process_info', 10, 1),
        ('process_owner', '프로세스담당자', 'text', 'process_info', 11, 1),
        ('process_steps', '프로세스단계', 'list', 'process_info', 12, 0),
        ('process_duration', '소요시간', 'text', 'process_info', 13, 1),
        ('process_output', '산출물', 'textarea', 'process_info', 14, 0),
        
        ('attachments', '첨부파일', 'file', 'additional', 15, 0),
        ('notes', '비고', 'textarea', 'additional', 16, 0),
        ('detailed_content', '상세내용', 'textarea', 'additional', 17, 0)
    ]
    
    cursor.execute("DELETE FROM full_process_column_config")
    
    for col_key, col_name, col_type, tab, order, is_list in columns:
        cursor.execute("""
            INSERT INTO full_process_column_config 
            (column_key, column_name, column_type, tab, column_order, is_active, is_list_display, is_deleted)
            VALUES (%s, %s, %s, %s, %s, 1, %s, 0)
        """, (col_key, col_name, col_type, tab, order, is_list))
    
    logging.info(f"[OK] full_process_column_config: {len(columns)}개 컬럼 복구")

def fix_change_request_boolean(conn):
    """change_request_column_config boolean 타입 수정"""
    cursor = conn.cursor()
    
    try:
        # boolean 컬럼을 INTEGER로 변환
        for col in ['is_active', 'is_deleted']:
            cursor.execute(f"""
                SELECT data_type 
                FROM information_schema.columns 
                WHERE table_name = 'change_request_column_config' AND column_name = '{col}'
            """)
            
            result = cursor.fetchone()
            if result and result[0] == 'boolean':
                # 임시 컬럼 생성
                cursor.execute(f"""
                    ALTER TABLE change_request_column_config 
                    ADD COLUMN IF NOT EXISTS {col}_temp INTEGER
                """)
                
                # 데이터 복사
                cursor.execute(f"""
                    UPDATE change_request_column_config 
                    SET {col}_temp = CASE WHEN {col} THEN 1 ELSE 0 END
                """)
                
                # 기존 컬럼 삭제
                cursor.execute(f"""
                    ALTER TABLE change_request_column_config DROP COLUMN {col}
                """)
                
                # 임시 컬럼 이름 변경
                cursor.execute(f"""
                    ALTER TABLE change_request_column_config 
                    RENAME COLUMN {col}_temp TO {col}
                """)
                
                # 기본값 설정
                default_val = 1 if col == 'is_active' else 0
                cursor.execute(f"""
                    ALTER TABLE change_request_column_config 
                    ALTER COLUMN {col} SET DEFAULT {default_val}
                """)
                
                logging.info(f"[OK] change_request_column_config.{col}: boolean → INTEGER 변환")
    except Exception as e:
        logging.error(f"[ERROR] change_request boolean 수정 실패: {e}")

def create_change_request_sections(conn):
    """change_request_sections 테이블 생성"""
    cursor = conn.cursor()
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS change_request_sections (
                id SERIAL PRIMARY KEY,
                section_key TEXT UNIQUE,
                section_name TEXT,
                section_order INTEGER DEFAULT 1,
                is_active INTEGER DEFAULT 1,
                is_deleted INTEGER DEFAULT 0
            )
        """)
        
        # 기본 섹션 추가
        sections = [
            ('basic_info', '기본정보', 1),
            ('change_info', '변경정보', 2),
            ('additional', '추가정보', 3)
        ]
        
        for key, name, order in sections:
            cursor.execute("""
                INSERT INTO change_request_sections (section_key, section_name, section_order, is_active, is_deleted)
                VALUES (%s, %s, %s, 1, 0)
                ON CONFLICT (section_key) DO NOTHING
            """, (key, name, order))
        
        logging.info("[OK] change_request_sections 테이블 생성 및 데이터 추가")
        
    except Exception as e:
        logging.error(f"[ERROR] change_request_sections 생성 실패: {e}")

def verify_results(conn):
    """복구 결과 검증"""
    cursor = conn.cursor()
    
    print("\n" + "="*60)
    print("복구 결과 검증")
    print("="*60)
    
    tables = [
        ('safety_instruction_column_config', '환경안전 지시서'),
        ('follow_sop_column_config', 'Follow SOP'),
        ('full_process_column_config', 'Full Process'),
        ('accident_column_config', '협력사 사고'),
        ('change_request_column_config', '기준정보 변경요청')
    ]
    
    for table, name in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE is_active = 1")
            count = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT COUNT(DISTINCT tab) FROM {table} 
                WHERE is_active = 1 AND tab IS NOT NULL
            """)
            sections = cursor.fetchone()[0]
            
            status = "[OK]" if count > 0 else "[FAIL]"
            print(f"{status} {name}: {count}개 컬럼, {sections}개 섹션")
            
        except Exception as e:
            print(f"[ERROR] {name}: {e}")

def main():
    """메인 실행"""
    print("="*60)
    print("모든 게시판 컬럼 데이터 복구")
    print("="*60)
    
    conn = get_pg_connection()
    if not conn:
        return
    
    try:
        # 1. is_list_display 컬럼 추가
        print("\n1. is_list_display 컬럼 추가")
        add_is_list_display_column(conn)
        
        # 2. 각 게시판 컬럼 데이터 복구
        print("\n2. 컬럼 데이터 복구")
        restore_safety_instruction_columns(conn)
        restore_follow_sop_columns(conn)
        restore_full_process_columns(conn)
        
        # 3. change_request 처리
        print("\n3. change_request 처리")
        fix_change_request_boolean(conn)
        create_change_request_sections(conn)
        
        # 4. 결과 검증
        verify_results(conn)
        
        print("\n[완료] 모든 복구 작업이 완료되었습니다!")
        
    except Exception as e:
        print(f"\n[ERROR] 복구 실패: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()