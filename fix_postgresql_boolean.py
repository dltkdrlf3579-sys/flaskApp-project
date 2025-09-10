#!/usr/bin/env python3
"""
PostgreSQL boolean 타입 완전 수정 스크립트
boolean을 INTEGER로 변환하고 모든 데이터 수정
"""
import psycopg
import logging
import sys
import configparser
import re

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_pg_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    match = re.match(r'postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)', postgres_dsn)
    if not match:
        logging.error(f"잘못된 PostgreSQL DSN: {postgres_dsn}")
        sys.exit(1)
    
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
        sys.exit(1)

def fix_boolean_columns(conn):
    """모든 테이블의 boolean 컬럼을 INTEGER로 변환"""
    cursor = conn.cursor()
    
    # 섹션 테이블들
    section_tables = [
        'safety_instruction_sections',
        'accident_sections',
        'follow_sop_sections',
        'full_process_sections'
    ]
    
    # 컬럼 설정 테이블들
    column_tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config'
    ]
    
    # section_config 테이블
    all_tables = section_tables + column_tables + ['section_config']
    
    for table in all_tables:
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if not cursor.fetchone()[0]:
                logging.info(f"⏭️  {table} 테이블 없음 - 건너뜀")
                continue
            
            # is_active, is_deleted 컬럼 타입 확인 및 변환
            for col in ['is_active', 'is_deleted']:
                cursor.execute("""
                    SELECT data_type 
                    FROM information_schema.columns 
                    WHERE table_name = %s AND column_name = %s
                """, (table, col))
                
                result = cursor.fetchone()
                if result and result[0] == 'boolean':
                    logging.info(f"🔄 {table}.{col} boolean → INTEGER 변환")
                    
                    # 임시 컬럼 생성
                    temp_col = f"{col}_temp"
                    cursor.execute(f"""
                        ALTER TABLE {table} 
                        ADD COLUMN IF NOT EXISTS {temp_col} INTEGER
                    """)
                    
                    # 데이터 복사 (true->1, false->0)
                    cursor.execute(f"""
                        UPDATE {table} 
                        SET {temp_col} = CASE WHEN {col} THEN 1 ELSE 0 END
                    """)
                    
                    # 기존 컬럼 삭제
                    cursor.execute(f"""
                        ALTER TABLE {table} DROP COLUMN {col}
                    """)
                    
                    # 임시 컬럼을 원래 이름으로 변경
                    cursor.execute(f"""
                        ALTER TABLE {table} 
                        RENAME COLUMN {temp_col} TO {col}
                    """)
                    
                    # 기본값 설정
                    default_val = 1 if col == 'is_active' else 0
                    cursor.execute(f"""
                        ALTER TABLE {table} 
                        ALTER COLUMN {col} SET DEFAULT {default_val}
                    """)
                    
                    logging.info(f"  ✅ 완료")
                    
        except Exception as e:
            logging.error(f"❌ {table} 처리 실패: {e}")

def create_missing_section_tables(conn):
    """누락된 섹션 테이블 생성"""
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_sections',
        'accident_sections',
        'follow_sop_sections',
        'full_process_sections'
    ]
    
    for table in tables:
        try:
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    id SERIAL PRIMARY KEY,
                    section_key TEXT UNIQUE,
                    section_name TEXT,
                    section_order INTEGER DEFAULT 1,
                    is_active INTEGER DEFAULT 1,
                    is_deleted INTEGER DEFAULT 0
                )
            """)
            logging.info(f"✅ {table} 테이블 생성/확인")
            
            # 컬럼 추가 (없으면)
            for col, default in [('section_order', 1), ('is_active', 1), ('is_deleted', 0)]:
                cursor.execute(f"""
                    ALTER TABLE {table} 
                    ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT {default}
                """)
                
        except Exception as e:
            logging.error(f"❌ {table} 생성 실패: {e}")

def migrate_section_data(conn):
    """섹션 데이터 마이그레이션"""
    cursor = conn.cursor()
    
    # section_config 테이블 확인
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'section_config'
        )
    """)
    
    if cursor.fetchone()[0]:
        migrations = [
            ('safety_instruction_sections', 'safety_instruction'),
            ('accident_sections', 'accident'),
            ('follow_sop_sections', 'follow_sop'),
            ('full_process_sections', 'full_process')
        ]
        
        for target_table, board_type in migrations:
            try:
                # section_config의 is_active, is_deleted도 INTEGER로 처리
                cursor.execute(f"""
                    INSERT INTO {target_table} (section_key, section_name, section_order, is_active, is_deleted)
                    SELECT 
                        section_key, 
                        section_name, 
                        section_order,
                        CASE WHEN is_active::text IN ('true', 't', '1') THEN 1 ELSE 0 END,
                        CASE WHEN is_deleted::text IN ('true', 't', '1') THEN 1 ELSE 0 END
                    FROM section_config
                    WHERE board_type = %s
                    ON CONFLICT (section_key) DO UPDATE SET
                        section_name = EXCLUDED.section_name,
                        section_order = EXCLUDED.section_order,
                        is_active = EXCLUDED.is_active,
                        is_deleted = EXCLUDED.is_deleted
                """, (board_type,))
                
                logging.info(f"✅ {target_table}: {cursor.rowcount}개 섹션 마이그레이션")
                
            except Exception as e:
                logging.error(f"❌ {target_table} 마이그레이션 실패: {e}")

def insert_default_sections(conn):
    """기본 섹션 데이터 삽입"""
    cursor = conn.cursor()
    
    default_sections = {
        'safety_instruction_sections': [
            ('basic_info', '기본정보', 1),
            ('violation_info', '위반정보', 2),
            ('additional', '추가정보', 3)
        ],
        'accident_sections': [
            ('basic_info', '기본정보', 1),
            ('accident_info', '사고정보', 2),
            ('location_info', '장소정보', 3),
            ('additional', '추가정보', 4)
        ],
        'follow_sop_sections': [
            ('basic_info', '기본정보', 1),
            ('work_info', '작업정보', 2),
            ('additional', '추가정보', 3)
        ],
        'full_process_sections': [
            ('basic_info', '기본정보', 1),
            ('process_info', '프로세스정보', 2),
            ('additional', '추가정보', 3)
        ]
    }
    
    for table, sections in default_sections.items():
        # 현재 섹션 수 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        current_count = cursor.fetchone()[0]
        
        if current_count == 0:
            for section_key, section_name, section_order in sections:
                try:
                    cursor.execute(f"""
                        INSERT INTO {table} (section_key, section_name, section_order, is_active, is_deleted)
                        VALUES (%s, %s, %s, 1, 0)
                        ON CONFLICT (section_key) DO NOTHING
                    """, (section_key, section_name, section_order))
                except Exception as e:
                    logging.error(f"섹션 삽입 실패 {table}.{section_key}: {e}")
            
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            new_count = cursor.fetchone()[0]
            logging.info(f"✅ {table}: {new_count}개 섹션 추가")

def fix_column_tabs(conn):
    """컬럼 tab 매핑 수정"""
    cursor = conn.cursor()
    
    tab_fixes = {
        'safety_instruction_column_config': {
            'basic_info': ['issue_number', 'company_name', 'business_number', 'created_at', 
                          'issue_date', 'improvement_deadline', 'status', 'issuer', 'recipient'],
            'violation_info': ['violation_type', 'violation_details', 'legal_basis', 'penalty',
                              'violation_location', 'violation_date', 'violation_severity']
        },
        'accident_column_config': {
            'basic_info': ['accident_number', 'company_name', 'business_number', 'created_at',
                          'accident_date', 'reporter', 'department'],
            'accident_info': ['accident_type', 'accident_cause', 'injury_type', 'injury_severity',
                             'accident_description', 'victim_name', 'victim_age'],
            'location_info': ['accident_location', 'location_detail', 'building', 'floor']
        },
        'follow_sop_column_config': {
            'basic_info': ['work_req_no', 'company_name', 'business_number', 'created_at',
                          'created_by', 'request_date', 'department'],
            'work_info': ['work_type', 'work_location', 'work_content', 'work_status',
                         'worker_count', 'work_duration', 'safety_measures']
        },
        'full_process_column_config': {
            'basic_info': ['fullprocess_number', 'company_name', 'business_number', 'created_at',
                          'created_by', 'process_date', 'department'],
            'process_info': ['process_type', 'process_name', 'process_status', 'process_owner',
                            'process_steps', 'process_duration', 'process_output']
        }
    }
    
    for table, mappings in tab_fixes.items():
        try:
            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = %s
                )
            """, (table,))
            
            if not cursor.fetchone()[0]:
                continue
            
            # 먼저 모든 NULL을 기본값으로
            cursor.execute(f"""
                UPDATE {table}
                SET tab = 'basic_info'
                WHERE (tab IS NULL OR tab = '')
            """)
            
            # 특정 컬럼들을 올바른 섹션으로
            for section, columns in mappings.items():
                if columns:
                    cursor.execute(f"""
                        UPDATE {table}
                        SET tab = %s
                        WHERE column_key = ANY(%s)
                    """, (section, columns))
            
            # 매핑되지 않은 나머지는 additional로
            all_mapped = sum(mappings.values(), [])
            cursor.execute(f"""
                UPDATE {table}
                SET tab = 'additional'
                WHERE column_key NOT IN %s
                  AND tab = 'basic_info'
            """, (tuple(all_mapped) if all_mapped else ('',),))
            
            logging.info(f"✅ {table} tab 매핑 완료")
            
        except Exception as e:
            logging.error(f"❌ {table} tab 수정 실패: {e}")

def verify_final_state(conn):
    """최종 상태 검증"""
    cursor = conn.cursor()
    
    logging.info("\n=== 최종 검증 ===")
    
    # 섹션 테이블 확인
    section_tables = [
        'safety_instruction_sections',
        'accident_sections',
        'follow_sop_sections',
        'full_process_sections'
    ]
    
    for table in section_tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE is_active = 1")
            count = cursor.fetchone()[0]
            logging.info(f"✅ {table}: {count}개 활성 섹션")
        except Exception as e:
            logging.error(f"❌ {table}: {e}")
    
    # 컬럼 tab 매핑 확인
    column_tables = [
        'safety_instruction_column_config',
        'accident_column_config',
        'follow_sop_column_config',
        'full_process_column_config'
    ]
    
    for table in column_tables:
        try:
            cursor.execute(f"""
                SELECT 
                    COUNT(*) as total,
                    COUNT(CASE WHEN tab IS NOT NULL AND tab != '' THEN 1 END) as mapped
                FROM {table}
                WHERE is_active = 1
            """)
            total, mapped = cursor.fetchone()
            if total > 0:
                ratio = (mapped / total) * 100
                logging.info(f"✅ {table}: {mapped}/{total} 매핑 ({ratio:.0f}%)")
        except Exception as e:
            logging.error(f"❌ {table}: {e}")

def main():
    """메인 실행"""
    logging.info("=== PostgreSQL Boolean 타입 완전 수정 ===\n")
    
    conn = get_pg_connection()
    
    try:
        # 1. Boolean 컬럼을 INTEGER로 변환
        logging.info("1️⃣  Boolean → INTEGER 변환")
        fix_boolean_columns(conn)
        
        # 2. 누락된 섹션 테이블 생성
        logging.info("\n2️⃣  섹션 테이블 생성")
        create_missing_section_tables(conn)
        
        # 3. 섹션 데이터 마이그레이션
        logging.info("\n3️⃣  섹션 데이터 마이그레이션")
        migrate_section_data(conn)
        
        # 4. 기본 섹션 데이터 삽입
        logging.info("\n4️⃣  기본 섹션 데이터")
        insert_default_sections(conn)
        
        # 5. 컬럼 tab 매핑 수정
        logging.info("\n5️⃣  컬럼 tab 매핑")
        fix_column_tabs(conn)
        
        # 6. 최종 검증
        verify_final_state(conn)
        
        logging.info("\n✅ 모든 수정 완료!")
        
    except Exception as e:
        logging.error(f"\n❌ 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()