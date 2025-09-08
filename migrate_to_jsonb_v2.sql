-- Phase 6: TEXT → JSONB 마이그레이션 스크립트 v2
-- PostgreSQL Migration v7 (codex 검토 반영)
-- 실행 전 반드시 백업 필요!

BEGIN;

-- 필수 확장 모듈 설치
CREATE EXTENSION IF NOT EXISTS pg_trgm;

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

-- SERIAL 시퀀스 동기화 함수
CREATE OR REPLACE FUNCTION sync_serial_sequences()
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    rec RECORD;
    seq_name TEXT;
    max_id INTEGER;
BEGIN
    -- 모든 SERIAL 컬럼 찾기
    FOR rec IN 
        SELECT t.table_name, c.column_name
        FROM information_schema.tables t
        JOIN information_schema.columns c ON t.table_name = c.table_name
        WHERE t.table_schema = 'public' 
        AND c.column_default LIKE 'nextval%'
        AND c.data_type IN ('integer', 'bigint')
    LOOP
        -- 시퀀스 이름 가져오기
        seq_name := pg_get_serial_sequence(rec.table_name, rec.column_name);
        
        IF seq_name IS NOT NULL THEN
            -- 최대값 조회 및 시퀀스 동기화
            EXECUTE format('SELECT COALESCE(MAX(%I), 0) FROM %I', rec.column_name, rec.table_name) INTO max_id;
            EXECUTE format('SELECT setval(%L, %s, true)', seq_name, GREATEST(max_id, 1));
            
            RAISE NOTICE '시퀀스 동기화: %.% → %', rec.table_name, rec.column_name, max_id;
        END IF;
    END LOOP;
END $$;

-- 각 테이블별 마이그레이션 함수
CREATE OR REPLACE FUNCTION migrate_table_to_jsonb(p_table_name TEXT)
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 마이그레이션 로그 시작
    INSERT INTO migration_log (table_name, operation) 
    VALUES (p_table_name, 'TEXT_to_JSONB') 
    RETURNING id INTO migration_id;
    
    -- 테이블 존재 확인
    IF NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = p_table_name) THEN
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, 
            status = 'skipped', 
            error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE '% 테이블이 존재하지 않아 건너뜀', p_table_name;
        RETURN;
    END IF;
    
    -- 백업 컬럼 생성
    EXECUTE format('ALTER TABLE %I ADD COLUMN IF NOT EXISTS custom_data_backup TEXT', p_table_name);
    EXECUTE format('UPDATE %I SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL', p_table_name);
    
    -- JSONB 변환
    EXECUTE format('ALTER TABLE %I ALTER COLUMN custom_data DROP DEFAULT', p_table_name);
    EXECUTE format('ALTER TABLE %I ALTER COLUMN custom_data TYPE JSONB USING 
        CASE 
            WHEN custom_data IS NULL OR custom_data = '''' THEN ''''{}''''::JSONB
            ELSE custom_data::JSONB 
        END', p_table_name);
    EXECUTE format('ALTER TABLE %I ALTER COLUMN custom_data SET DEFAULT ''''{}''''::JSONB', p_table_name);
    
    GET DIAGNOSTICS row_count = ROW_COUNT;
    
    -- 성공 로그
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, 
        status = 'completed', 
        rows_affected = row_count
    WHERE id = migration_id;
    
    RAISE NOTICE '% 마이그레이션 완료: % rows', p_table_name, row_count;
    
EXCEPTION WHEN OTHERS THEN
    -- 실패 로그 (ROLLBACK 제거됨)
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, 
        status = 'failed', 
        error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE '% 마이그레이션 실패: %', p_table_name, SQLERRM;
    RAISE;
END $$;

-- 인덱스 생성 함수
CREATE OR REPLACE FUNCTION create_jsonb_indexes(p_table_name TEXT, p_keys TEXT[])
RETURNS void LANGUAGE plpgsql AS $$
DECLARE
    key_name TEXT;
    index_name TEXT;
BEGIN
    -- JSONB 전체 GIN 인덱스
    index_name := format('idx_%s_gin', p_table_name);
    EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN (custom_data)', 
                   index_name, p_table_name);
    RAISE NOTICE '생성: % (JSONB GIN)', index_name;
    
    -- 각 키별 인덱스
    FOREACH key_name IN ARRAY p_keys LOOP
        -- LIKE 검색용 trigram 인덱스
        index_name := format('idx_%s_%s_trgm', p_table_name, key_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I USING GIN ((custom_data->>%L) gin_trgm_ops)', 
                       index_name, p_table_name, key_name);
        
        -- 정확 매칭용 B-tree 인덱스  
        index_name := format('idx_%s_%s', p_table_name, key_name);
        EXECUTE format('CREATE INDEX IF NOT EXISTS %I ON %I ((custom_data->>%L))', 
                       index_name, p_table_name, key_name);
        
        RAISE NOTICE '생성: % 키 인덱스 (trigram + btree)', key_name;
    END LOOP;
END $$;

-- 실제 마이그레이션 실행
SELECT migrate_table_to_jsonb('accidents_cache');
SELECT create_jsonb_indexes('accidents_cache', ARRAY['workplace', 'accident_type', 'severity', 'department']);

SELECT migrate_table_to_jsonb('safety_instructions_cache');
SELECT create_jsonb_indexes('safety_instructions_cache', ARRAY['workplace', 'violation_type', 'severity', 'inspector']);

SELECT migrate_table_to_jsonb('follow_sop');
SELECT create_jsonb_indexes('follow_sop', ARRAY['workplace', 'process_type', 'status', 'department']);

SELECT migrate_table_to_jsonb('full_process');
SELECT create_jsonb_indexes('full_process', ARRAY['workplace', 'process_name', 'status', 'department']);

SELECT migrate_table_to_jsonb('followsop_cache');
SELECT create_jsonb_indexes('followsop_cache', ARRAY['workplace', 'process_type', 'status']);

SELECT migrate_table_to_jsonb('fullprocess_cache');
SELECT create_jsonb_indexes('fullprocess_cache', ARRAY['workplace', 'process_name', 'status']);

SELECT migrate_table_to_jsonb('partner_change_requests');
SELECT create_jsonb_indexes('partner_change_requests', ARRAY['requester_name', 'company_name', 'status', 'department']);

-- SERIAL 시퀀스 동기화 실행
SELECT sync_serial_sequences();

-- 임시 함수 정리
DROP FUNCTION IF EXISTS migrate_table_to_jsonb(TEXT);
DROP FUNCTION IF EXISTS create_jsonb_indexes(TEXT, TEXT[]);
DROP FUNCTION IF EXISTS sync_serial_sequences();

-- 마이그레이션 완료 검증
SELECT 
    table_name,
    operation,
    status,
    rows_affected,
    EXTRACT(EPOCH FROM (end_time - start_time))::INTEGER as duration_seconds,
    error_message
FROM migration_log 
WHERE operation = 'TEXT_to_JSONB'
ORDER BY start_time;

COMMIT;

-- 성공 메시지
SELECT 
    'Phase 6 JSONB 마이그레이션 v2 완료!' as message,
    'pg_trgm 확장 사용' as feature1,
    'DO 블록 ROLLBACK 제거' as feature2,
    'SERIAL 시퀀스 보정' as feature3;