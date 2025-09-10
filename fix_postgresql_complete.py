#!/usr/bin/env python3
"""
PostgreSQL 완전 수정 스크립트
모든 테이블 스키마와 데이터를 완벽하게 복구
"""
import psycopg
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(message)s')

def get_pg_connection():
    """PostgreSQL 연결"""
    import configparser
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    
    postgres_dsn = config.get('DATABASE', 'postgres_dsn')
    # postgresql://postgres:admin123@localhost:5432/portal_dev 파싱
    import re
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
        conn.autocommit = True  # 자동 커밋으로 트랜잭션 문제 방지
        return conn
    except Exception as e:
        logging.error(f"PostgreSQL 연결 실패: {e}")
        sys.exit(1)

def create_section_tables(conn):
    """모든 섹션 테이블 생성 및 스키마 수정"""
    cursor = conn.cursor()
    
    tables = [
        'safety_instruction_sections',
        'accident_sections', 
        'follow_sop_sections',
        'full_process_sections'
    ]
    
    for table in tables:
        try:
            # 테이블 생성 (없으면)
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
            
            # 누락된 컬럼 추가
            columns = ['section_order', 'is_active', 'is_deleted']
            for col in columns:
                try:
                    if col == 'section_order':
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT 1")
                    else:
                        cursor.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {col} INTEGER DEFAULT {1 if col == 'is_active' else 0}")
                except Exception as e:
                    pass  # 이미 있으면 무시
                    
        except Exception as e:
            logging.error(f"❌ {table} 처리 실패: {e}")

def migrate_section_data(conn):
    """섹션 데이터 마이그레이션"""
    cursor = conn.cursor()
    
    # section_config 테이블이 있는지 확인
    cursor.execute("""
        SELECT EXISTS (
            SELECT FROM information_schema.tables 
            WHERE table_name = 'section_config'
        )
    """)
    
    if not cursor.fetchone()[0]:
        logging.info("section_config 테이블이 없음 - 기본 데이터 직접 삽입")
        insert_default_sections(conn)
        return
    
    # section_config에서 데이터 마이그레이션
    migrations = [
        ('safety_instruction_sections', 'safety_instruction'),
        ('accident_sections', 'accident'),
        ('follow_sop_sections', 'follow_sop'),
        ('full_process_sections', 'full_process')
    ]
    
    for target_table, board_type in migrations:
        try:
            cursor.execute(f"""
                INSERT INTO {target_table} (section_key, section_name, section_order, is_active, is_deleted)
                SELECT section_key, section_name, section_order, is_active, COALESCE(is_deleted, 0)
                FROM section_config
                WHERE board_type = %s
                ON CONFLICT (section_key) DO UPDATE SET
                    section_name = EXCLUDED.section_name,
                    section_order = EXCLUDED.section_order,
                    is_active = EXCLUDED.is_active,
                    is_deleted = EXCLUDED.is_deleted
            """, (board_type,))
            
            count = cursor.rowcount
            logging.info(f"  ➜ {target_table}: {count}개 섹션 마이그레이션")
            
        except Exception as e:
            logging.error(f"  ❌ {target_table} 마이그레이션 실패: {e}")

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
        for section_key, section_name, section_order in sections:
            try:
                cursor.execute(f"""
                    INSERT INTO {table} (section_key, section_name, section_order, is_active, is_deleted)
                    VALUES (%s, %s, %s, 1, 0)
                    ON CONFLICT (section_key) DO UPDATE SET
                        section_name = EXCLUDED.section_name,
                        section_order = EXCLUDED.section_order,
                        is_active = EXCLUDED.is_active
                """, (section_key, section_name, section_order))
            except Exception as e:
                logging.error(f"섹션 삽입 실패 {table}.{section_key}: {e}")
        
        # 삽입된 데이터 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE is_active = 1")
        count = cursor.fetchone()[0]
        logging.info(f"✅ {table}: {count}개 섹션")

def fix_null_tabs(conn):
    """NULL tab 값 수정"""
    cursor = conn.cursor()
    
    tab_mappings = {
        'safety_instruction_column_config': {
            'basic_info': ['issue_number', 'company_name', 'business_number', 'created_at', 
                          'issue_date', 'improvement_deadline', 'status', 'issuer', 'recipient'],
            'violation_info': ['violation_type', 'violation_details', 'legal_basis', 'penalty',
                              'violation_location', 'violation_date', 'violation_severity'],
            'additional': []  # 나머지는 additional로
        },
        'accident_column_config': {
            'basic_info': ['accident_number', 'company_name', 'business_number', 'created_at',
                          'accident_date', 'reporter', 'department'],
            'accident_info': ['accident_type', 'accident_cause', 'injury_type', 'injury_severity',
                             'accident_description', 'victim_name', 'victim_age'],
            'location_info': ['accident_location', 'location_detail', 'building', 'floor'],
            'additional': []
        },
        'follow_sop_column_config': {
            'basic_info': ['work_req_no', 'company_name', 'business_number', 'created_at',
                          'created_by', 'request_date', 'department'],
            'work_info': ['work_type', 'work_location', 'work_content', 'work_status',
                         'worker_count', 'work_duration', 'safety_measures'],
            'additional': []
        },
        'full_process_column_config': {
            'basic_info': ['fullprocess_number', 'company_name', 'business_number', 'created_at',
                          'created_by', 'process_date', 'department'],
            'process_info': ['process_type', 'process_name', 'process_status', 'process_owner',
                            'process_steps', 'process_duration', 'process_output'],
            'additional': []
        }
    }
    
    for table, mappings in tab_mappings.items():
        try:
            # 먼저 모든 NULL을 기본값으로
            cursor.execute(f"""
                UPDATE {table}
                SET tab = 'basic_info'
                WHERE (tab IS NULL OR tab = '') 
                  AND is_active = 1 
                  AND (is_deleted = 0 OR is_deleted IS NULL)
            """)
            null_count = cursor.rowcount
            
            # 특정 컬럼들을 올바른 섹션으로 매핑
            for section, columns in mappings.items():
                if columns:
                    placeholders = ','.join(['%s'] * len(columns))
                    cursor.execute(f"""
                        UPDATE {table}
                        SET tab = %s
                        WHERE column_key IN ({placeholders})
                          AND is_active = 1
                    """, [section] + columns)
            
            # 매핑되지 않은 나머지는 additional로
            cursor.execute(f"""
                UPDATE {table}
                SET tab = 'additional'
                WHERE tab = 'basic_info'
                  AND column_key NOT IN (
                    SELECT column_key FROM {table}
                    WHERE column_key IN %s
                  )
                  AND is_active = 1
            """, (tuple(sum(mappings.values(), [])),))
            
            logging.info(f"✅ {table}: {null_count}개 NULL tab 수정")
            
        except Exception as e:
            logging.error(f"❌ {table} tab 수정 실패: {e}")

def verify_setup(conn):
    """설정 검증"""
    cursor = conn.cursor()
    
    logging.info("\n=== 최종 검증 ===")
    
    # 섹션 테이블 확인
    tables = [
        'safety_instruction_sections',
        'accident_sections',
        'follow_sop_sections', 
        'full_process_sections'
    ]
    
    all_good = True
    for table in tables:
        try:
            cursor.execute(f"""
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN is_active = 1 THEN 1 END) as active
                FROM {table}
            """)
            result = cursor.fetchone()
            if result[1] > 0:
                logging.info(f"✅ {table}: {result[1]}개 활성 섹션")
            else:
                logging.error(f"❌ {table}: 활성 섹션 없음")
                all_good = False
        except Exception as e:
            logging.error(f"❌ {table}: 테이블 없음 - {e}")
            all_good = False
    
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
                SELECT COUNT(*) as total,
                       COUNT(CASE WHEN tab IS NOT NULL AND tab != '' THEN 1 END) as mapped
                FROM {table}
                WHERE is_active = 1
            """)
            result = cursor.fetchone()
            if result[0] > 0:
                ratio = (result[1] / result[0]) * 100
                if ratio == 100:
                    logging.info(f"✅ {table}: {result[1]}/{result[0]} 매핑됨")
                else:
                    logging.warning(f"⚠️  {table}: {result[1]}/{result[0]} 매핑됨 ({ratio:.0f}%)")
            else:
                logging.warning(f"⚠️  {table}: 활성 컬럼 없음")
                
        except Exception as e:
            logging.error(f"❌ {table}: 확인 실패 - {e}")
            all_good = False
    
    return all_good

def main():
    """메인 실행"""
    logging.info("=== PostgreSQL 완전 수정 시작 ===\n")
    
    conn = get_pg_connection()
    
    try:
        # 1. 섹션 테이블 생성 및 스키마 수정
        logging.info("1️⃣  섹션 테이블 생성 및 스키마 수정")
        create_section_tables(conn)
        
        # 2. 섹션 데이터 마이그레이션
        logging.info("\n2️⃣  섹션 데이터 마이그레이션")
        migrate_section_data(conn)
        
        # 3. 기본 섹션 데이터 확인/삽입
        logging.info("\n3️⃣  기본 섹션 데이터 확인")
        insert_default_sections(conn)
        
        # 4. NULL tab 수정
        logging.info("\n4️⃣  NULL tab 값 수정")
        fix_null_tabs(conn)
        
        # 5. 최종 검증
        if verify_setup(conn):
            logging.info("\n✅ 모든 수정 완료! 서버를 재시작하세요.")
        else:
            logging.warning("\n⚠️  일부 문제가 남아있습니다. 로그를 확인하세요.")
            
    except Exception as e:
        logging.error(f"\n❌ 치명적 오류: {e}")
        import traceback
        traceback.print_exc()
    finally:
        conn.close()

if __name__ == "__main__":
    main()