#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Phase 6: JSONB 스키마 전환 및 성능 최적화
TEXT → JSONB 마이그레이션 및 인덱스 최적화
"""
import sys
import os
import psycopg
import configparser
import json
import time

# Windows에서 한글 출력을 위한 인코딩 설정
if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# 마이그레이션 대상 테이블 정의
MIGRATION_TABLES = [
    # 메인 테이블들
    {
        'name': 'accidents_cache',
        'description': '사고 캐시 테이블',
        'common_keys': ['workplace', 'accident_type', 'severity', 'department']
    },
    {
        'name': 'safety_instructions_cache', 
        'description': '안전지시 캐시 테이블',
        'common_keys': ['workplace', 'violation_type', 'severity', 'inspector']
    },
    {
        'name': 'follow_sop',
        'description': 'SOP 따르기 메인 테이블',
        'common_keys': ['workplace', 'process_type', 'status', 'department']
    },
    {
        'name': 'full_process',
        'description': '전체 프로세스 메인 테이블',
        'common_keys': ['workplace', 'process_name', 'status', 'department']
    },
    {
        'name': 'followsop_cache',
        'description': 'SOP 따르기 캐시 테이블',
        'common_keys': ['workplace', 'process_type', 'status']
    },
    {
        'name': 'fullprocess_cache',
        'description': '전체 프로세스 캐시 테이블', 
        'common_keys': ['workplace', 'process_name', 'status']
    },
    {
        'name': 'partner_change_requests',
        'description': '파트너 변경 요청 테이블',
        'common_keys': ['requester_name', 'company_name', 'status', 'department']
    }
]

def get_config():
    """config.ini에서 DB 설정 읽기"""
    config = configparser.ConfigParser()
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if os.path.exists(config_path):
        config.read(config_path, encoding='utf-8')
        
        # PostgreSQL 설정 읽기
        postgres_dsn = config.get('DATABASE', 'postgres_dsn', fallback='postgresql://postgres:admin123@localhost:5432/portal_dev')://{postgres}:{portal_password}@{host}:{port}/{database}'
        
        return admin_dsn, portal_dsn
    else:
        # 기본값 사용
        admin_dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
        portal_dsn = 'postgresql://postgres:admin123@localhost:5432/portal_dev'
        return admin_dsn, portal_dsn

def analyze_current_schema():
    """현재 스키마 상태 분석"""
    print("\n=== 현재 스키마 분석 ===")
    
    admin_dsn, _ = get_config()
    
    try:
        conn = psycopg.connect(admin_dsn)
        cur = conn.cursor()
        
        # 모든 custom_data 컬럼 찾기
        cur.execute("""
            SELECT table_name, column_name, data_type, is_nullable, column_default
            FROM information_schema.columns 
            WHERE column_name = 'custom_data' 
            AND table_schema = 'public'
            ORDER BY table_name
        """)
        
        columns = cur.fetchall()
        
        print(f"발견된 custom_data 컬럼: {len(columns)}개")
        existing_tables = set()
        
        for table_name, column_name, data_type, is_nullable, column_default in columns:
            print(f"  📊 {table_name}.{column_name}: {data_type} {'NULL' if is_nullable == 'YES' else 'NOT NULL'}")
            if column_default:
                print(f"      DEFAULT: {column_default}")
            existing_tables.add(table_name)
        
        # 데이터 샘플 분석
        print(f"\n--- 데이터 샘플 분석 ---")
        for table in MIGRATION_TABLES:
            table_name = table['name']
            
            if table_name not in existing_tables:
                print(f"⏭️  {table_name}: 테이블 존재하지 않음")
                continue
            
            try:
                # 레코드 수 확인
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cur.fetchone()[0]
                
                if count == 0:
                    print(f"📋 {table_name}: {count}개 레코드 (빈 테이블)")
                    continue
                
                # JSON 유효성 검사
                cur.execute(f"""
                    SELECT 
                        COUNT(*) as total_rows,
                        COUNT(CASE WHEN custom_data IS NULL OR custom_data = '' THEN 1 END) as empty_rows,
                        COUNT(CASE WHEN custom_data::jsonb IS NOT NULL THEN 1 END) as valid_json_rows
                    FROM {table_name}
                """)
                
                total, empty, valid = cur.fetchone()
                invalid = total - empty - valid
                
                print(f"📋 {table_name}: {total}개 레코드")
                print(f"   ✅ 유효 JSON: {valid}개 ({valid/total*100:.1f}%)")
                if empty > 0:
                    print(f"   🔘 빈 값: {empty}개 ({empty/total*100:.1f}%)")
                if invalid > 0:
                    print(f"   ❌ 무효 JSON: {invalid}개 ({invalid/total*100:.1f}%)")
                
                # 샘플 데이터 확인
                cur.execute(f"SELECT custom_data FROM {table_name} WHERE custom_data IS NOT NULL AND custom_data != '' LIMIT 1")
                sample = cur.fetchone()
                if sample and sample[0]:
                    try:
                        sample_json = json.loads(sample[0])
                        keys = list(sample_json.keys())[:5]  # 최대 5개 키만
                        print(f"   🔍 샘플 키: {keys}")
                    except json.JSONDecodeError:
                        print(f"   ⚠️  샘플 데이터 JSON 파싱 실패")
                        
            except Exception as e:
                print(f"❌ {table_name}: 분석 실패 - {e}")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ 스키마 분석 실패: {e}")
        return False

def create_migration_script():
    """마이그레이션 스크립트 생성"""
    print("\n=== 마이그레이션 스크립트 생성 ===")
    
    migration_sql = """-- Phase 6: TEXT → JSONB 마이그레이션 스크립트
-- PostgreSQL Migration v7
-- 실행 전 반드시 백업 필요!

BEGIN;

-- 마이그레이션 로그 테이블 생성
CREATE TABLE IF NOT EXISTS migration_log (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT DEFAULT 'running',
    rows_affected INTEGER DEFAULT 0,
    error_message TEXT
);

"""
    
    # 각 테이블별 마이그레이션 SQL 생성
    for table in MIGRATION_TABLES:
        table_name = table['name']
        description = table['description']
        common_keys = table['common_keys']
        
        migration_sql += f"""
-- {description} ({table_name}) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('{table_name}', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = '{table_name}' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE {table_name} ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE {table_name} SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE {table_name} ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{{}}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE {table_name} ALTER COLUMN custom_data SET DEFAULT '{{}}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE '{table_name} 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE '{table_name} 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE '{table_name} 마이그레이션 실패: %', SQLERRM;
    ROLLBACK;
END $$;
"""

        # 자주 사용되는 키에 대한 인덱스 생성
        migration_sql += f"""
-- {table_name} 성능 최적화 인덱스
"""
        for key in common_keys:
            migration_sql += f"CREATE INDEX IF NOT EXISTS idx_{table_name}_{key} ON {table_name} USING GIN ((custom_data->>'{key}'));\n"
        
        migration_sql += f"CREATE INDEX IF NOT EXISTS idx_{table_name}_gin ON {table_name} USING GIN (custom_data);\n\n"

    migration_sql += """
-- 마이그레이션 완료 검증
SELECT 
    table_name,
    operation,
    status,
    rows_affected,
    end_time - start_time as duration,
    error_message
FROM migration_log 
WHERE operation = 'TEXT_to_JSONB'
ORDER BY id;

COMMIT;

-- 성공 메시지
SELECT 'Phase 6 JSONB 마이그레이션 완료!' as message;
"""
    
    # 파일 저장
    script_path = os.path.join(os.path.dirname(__file__), 'migrate_to_jsonb.sql')
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(migration_sql)
    
    print(f"✅ 마이그레이션 스크립트 생성: {script_path}")
    print("📋 스크립트 내용:")
    print(f"   - {len(MIGRATION_TABLES)}개 테이블 처리")
    print("   - 백업 컬럼 자동 생성")
    print("   - 성능 최적화 인덱스 포함")
    print("   - 상세한 로깅 시스템")
    
    return script_path

def create_rollback_script():
    """롤백 스크립트 생성"""
    print("\n=== 롤백 스크립트 생성 ===")
    
    rollback_sql = """-- Phase 6 JSONB 마이그레이션 롤백 스크립트
-- PostgreSQL Migration v7 
-- JSONB → TEXT 되돌리기 (긴급 시에만 사용)

BEGIN;

-- 롤백 로그 테이블
CREATE TABLE IF NOT EXISTS rollback_log (
    id SERIAL PRIMARY KEY,
    table_name TEXT NOT NULL,
    operation TEXT NOT NULL,
    start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_time TIMESTAMP,
    status TEXT DEFAULT 'running',
    rows_affected INTEGER DEFAULT 0,
    error_message TEXT
);

"""
    
    # 각 테이블별 롤백 SQL
    for table in MIGRATION_TABLES:
        table_name = table['name']
        
        rollback_sql += f"""
-- {table_name} 롤백
INSERT INTO rollback_log (table_name, operation) VALUES ('{table_name}', 'JSONB_to_TEXT');

DO $$
DECLARE
    rollback_id INTEGER;
    row_count INTEGER;
BEGIN
    SELECT id INTO rollback_id FROM rollback_log 
    WHERE table_name = '{table_name}' AND operation = 'JSONB_to_TEXT' 
    ORDER BY id DESC LIMIT 1;
    
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = '{table_name}') THEN
        -- 백업에서 복원
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = 'custom_data_backup') THEN
            UPDATE {table_name} SET custom_data = custom_data_backup::TEXT WHERE custom_data_backup IS NOT NULL;
        END IF;
        
        -- JSONB → TEXT 변환
        ALTER TABLE {table_name} ALTER COLUMN custom_data TYPE TEXT;
        ALTER TABLE {table_name} ALTER COLUMN custom_data SET DEFAULT '{{}}';
        
        -- 인덱스 제거
        DROP INDEX IF EXISTS idx_{table_name}_gin;
"""
        
        for key in table['common_keys']:
            rollback_sql += f"        DROP INDEX IF EXISTS idx_{table_name}_{key};\n"
        
        rollback_sql += f"""
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        UPDATE rollback_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = rollback_id;
        
        RAISE NOTICE '{table_name} 롤백 완료';
    ELSE
        UPDATE rollback_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = rollback_id;
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    UPDATE rollback_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = rollback_id;
    RAISE;
END $$;
"""

    rollback_sql += """
-- 롤백 결과 확인
SELECT 
    table_name,
    operation,
    status,
    rows_affected,
    end_time - start_time as duration,
    error_message
FROM rollback_log 
WHERE operation = 'JSONB_to_TEXT'
ORDER BY id;

COMMIT;

SELECT 'JSONB → TEXT 롤백 완료' as message;
"""
    
    # 파일 저장
    rollback_path = os.path.join(os.path.dirname(__file__), 'rollback_jsonb_migration.sql')
    with open(rollback_path, 'w', encoding='utf-8') as f:
        f.write(rollback_sql)
    
    print(f"✅ 롤백 스크립트 생성: {rollback_path}")
    
    return rollback_path

def main():
    print("SETUP - Phase 6: JSONB 스키마 전환 및 성능 최적화")
    
    steps = [
        ("스키마 분석", analyze_current_schema),
        ("마이그레이션 스크립트 생성", create_migration_script),
        ("롤백 스크립트 생성", create_rollback_script)
    ]
    
    results = []
    for step_name, step_func in steps:
        try:
            print(f"\n🔄 {step_name} 시작...")
            result = step_func()
            results.append(result)
            if result:
                print(f"✅ {step_name} 완료")
            else:
                print(f"⚠️  {step_name} 부분 완료")
        except Exception as e:
            print(f"❌ {step_name} 실패: {e}")
            results.append(False)
    
    # 결과
    passed = sum(1 for r in results if r)
    total = len(results)
    
    print(f"\n=== Phase 6 준비 결과 ===")
    print(f"완료: {passed}/{total}")
    
    if all(results):
        print("🎉 SUCCESS - Phase 6 JSONB 마이그레이션 준비 완료!")
        print("📋 생성된 파일:")
        print("   - migrate_to_jsonb.sql: 메인 마이그레이션")
        print("   - rollback_jsonb_migration.sql: 안전 롤백")
        print("\n🚀 다음 단계:")
        print("   1. 데이터베이스 백업")
        print("   2. migrate_to_jsonb.sql 실행")
        print("   3. 성능 테스트 및 검증")
        return True
    else:
        print("⚠️  일부 준비 과정에 이슈가 있습니다")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)