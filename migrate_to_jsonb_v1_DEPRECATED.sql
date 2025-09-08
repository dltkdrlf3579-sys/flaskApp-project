-- ⚠️  DEPRECATED - 이 스크립트는 사용하지 마세요!
-- 대신 migrate_to_jsonb_v2.sql을 사용하세요
-- 
-- Phase 6: TEXT → JSONB 마이그레이션 스크립트 v1 (DEPRECATED)
-- PostgreSQL Migration v7
-- 
-- 이슈: 일부 GIN 인덱스가 텍스트 표현식에 잘못 적용됨
-- 해결: v2 스크립트에서 pg_trgm 확장과 올바른 인덱스 전략 적용

BEGIN;

-- 필수 확장 모듈 설치 (LIKE 검색 최적화용)
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


-- 사고 캐시 테이블 (accidents_cache) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('accidents_cache', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'accidents_cache' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'accidents_cache') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE accidents_cache ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE accidents_cache SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE accidents_cache ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE accidents_cache ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'accidents_cache 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'accidents_cache 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'accidents_cache 마이그레이션 실패: %', SQLERRM;
END $$;

-- accidents_cache 성능 최적화 인덱스
-- LIKE 검색 최적화 (pg_trgm)
CREATE INDEX IF NOT EXISTS idx_accidents_cache_workplace_trgm ON accidents_cache USING GIN ((custom_data->>'workplace') gin_trgm_ops);
-- 정확 매칭 최적화 (B-tree)  
CREATE INDEX IF NOT EXISTS idx_accidents_cache_workplace ON accidents_cache ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_accidents_cache_accident_type ON accidents_cache USING GIN ((custom_data->>'accident_type'));
CREATE INDEX IF NOT EXISTS idx_accidents_cache_severity ON accidents_cache USING GIN ((custom_data->>'severity'));
CREATE INDEX IF NOT EXISTS idx_accidents_cache_department ON accidents_cache USING GIN ((custom_data->>'department'));
CREATE INDEX IF NOT EXISTS idx_accidents_cache_gin ON accidents_cache USING GIN (custom_data);


-- 안전지시 캐시 테이블 (safety_instructions_cache) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('safety_instructions_cache', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'safety_instructions_cache' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'safety_instructions_cache') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE safety_instructions_cache ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE safety_instructions_cache SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE safety_instructions_cache ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE safety_instructions_cache ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'safety_instructions_cache 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'safety_instructions_cache 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'safety_instructions_cache 마이그레이션 실패: %', SQLERRM;
END $$;

-- safety_instructions_cache 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_safety_instructions_cache_workplace ON safety_instructions_cache USING GIN ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_safety_instructions_cache_violation_type ON safety_instructions_cache USING GIN ((custom_data->>'violation_type'));
CREATE INDEX IF NOT EXISTS idx_safety_instructions_cache_severity ON safety_instructions_cache USING GIN ((custom_data->>'severity'));
CREATE INDEX IF NOT EXISTS idx_safety_instructions_cache_inspector ON safety_instructions_cache USING GIN ((custom_data->>'inspector'));
CREATE INDEX IF NOT EXISTS idx_safety_instructions_cache_gin ON safety_instructions_cache USING GIN (custom_data);


-- SOP 따르기 메인 테이블 (follow_sop) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('follow_sop', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'follow_sop' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'follow_sop') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE follow_sop ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE follow_sop SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE follow_sop ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE follow_sop ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'follow_sop 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'follow_sop 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'follow_sop 마이그레이션 실패: %', SQLERRM;
END $$;

-- follow_sop 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_follow_sop_workplace ON follow_sop USING GIN ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_follow_sop_process_type ON follow_sop USING GIN ((custom_data->>'process_type'));
CREATE INDEX IF NOT EXISTS idx_follow_sop_status ON follow_sop USING GIN ((custom_data->>'status'));
CREATE INDEX IF NOT EXISTS idx_follow_sop_department ON follow_sop USING GIN ((custom_data->>'department'));
CREATE INDEX IF NOT EXISTS idx_follow_sop_gin ON follow_sop USING GIN (custom_data);


-- 전체 프로세스 메인 테이블 (full_process) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('full_process', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'full_process' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'full_process') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE full_process ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE full_process SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE full_process ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE full_process ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'full_process 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'full_process 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'full_process 마이그레이션 실패: %', SQLERRM;
END $$;

-- full_process 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_full_process_workplace ON full_process USING GIN ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_full_process_process_name ON full_process USING GIN ((custom_data->>'process_name'));
CREATE INDEX IF NOT EXISTS idx_full_process_status ON full_process USING GIN ((custom_data->>'status'));
CREATE INDEX IF NOT EXISTS idx_full_process_department ON full_process USING GIN ((custom_data->>'department'));
CREATE INDEX IF NOT EXISTS idx_full_process_gin ON full_process USING GIN (custom_data);


-- SOP 따르기 캐시 테이블 (followsop_cache) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('followsop_cache', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'followsop_cache' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'followsop_cache') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE followsop_cache ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE followsop_cache SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE followsop_cache ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE followsop_cache ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'followsop_cache 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'followsop_cache 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'followsop_cache 마이그레이션 실패: %', SQLERRM;
END $$;

-- followsop_cache 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_followsop_cache_workplace ON followsop_cache USING GIN ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_followsop_cache_process_type ON followsop_cache USING GIN ((custom_data->>'process_type'));
CREATE INDEX IF NOT EXISTS idx_followsop_cache_status ON followsop_cache USING GIN ((custom_data->>'status'));
CREATE INDEX IF NOT EXISTS idx_followsop_cache_gin ON followsop_cache USING GIN (custom_data);


-- 전체 프로세스 캐시 테이블 (fullprocess_cache) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('fullprocess_cache', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'fullprocess_cache' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'fullprocess_cache') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE fullprocess_cache ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE fullprocess_cache SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE fullprocess_cache ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE fullprocess_cache ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'fullprocess_cache 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'fullprocess_cache 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'fullprocess_cache 마이그레이션 실패: %', SQLERRM;
END $$;

-- fullprocess_cache 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_fullprocess_cache_workplace ON fullprocess_cache USING GIN ((custom_data->>'workplace'));
CREATE INDEX IF NOT EXISTS idx_fullprocess_cache_process_name ON fullprocess_cache USING GIN ((custom_data->>'process_name'));
CREATE INDEX IF NOT EXISTS idx_fullprocess_cache_status ON fullprocess_cache USING GIN ((custom_data->>'status'));
CREATE INDEX IF NOT EXISTS idx_fullprocess_cache_gin ON fullprocess_cache USING GIN (custom_data);


-- 파트너 변경 요청 테이블 (partner_change_requests) 마이그레이션
INSERT INTO migration_log (table_name, operation) VALUES ('partner_change_requests', 'TEXT_to_JSONB');

DO $$
DECLARE
    migration_id INTEGER;
    row_count INTEGER;
BEGIN
    -- 현재 마이그레이션 ID 가져오기
    SELECT id INTO migration_id FROM migration_log 
    WHERE table_name = 'partner_change_requests' AND operation = 'TEXT_to_JSONB' 
    ORDER BY id DESC LIMIT 1;
    
    -- 테이블 존재 확인
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'partner_change_requests') THEN
        -- 백업 컬럼 생성 (안전장치)
        ALTER TABLE partner_change_requests ADD COLUMN IF NOT EXISTS custom_data_backup TEXT;
        UPDATE partner_change_requests SET custom_data_backup = custom_data WHERE custom_data_backup IS NULL;
        
        -- JSONB 컬럼으로 변경
        ALTER TABLE partner_change_requests ALTER COLUMN custom_data TYPE JSONB USING 
            CASE 
                WHEN custom_data IS NULL OR custom_data = '' THEN '{}'::JSONB
                ELSE custom_data::JSONB 
            END;
        
        -- 기본값 설정
        ALTER TABLE partner_change_requests ALTER COLUMN custom_data SET DEFAULT '{}'::JSONB;
        
        GET DIAGNOSTICS row_count = ROW_COUNT;
        
        -- 성공 로그 업데이트
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'completed', rows_affected = row_count
        WHERE id = migration_id;
        
        RAISE NOTICE 'partner_change_requests 마이그레이션 완료: % rows', row_count;
    ELSE
        -- 테이블 없음 로그
        UPDATE migration_log 
        SET end_time = CURRENT_TIMESTAMP, status = 'skipped', error_message = 'Table does not exist'
        WHERE id = migration_id;
        
        RAISE NOTICE 'partner_change_requests 테이블이 존재하지 않아 건너뜀';
    END IF;
    
EXCEPTION WHEN OTHERS THEN
    -- 오류 로그 업데이트
    UPDATE migration_log 
    SET end_time = CURRENT_TIMESTAMP, status = 'failed', error_message = SQLERRM
    WHERE id = migration_id;
    
    RAISE NOTICE 'partner_change_requests 마이그레이션 실패: %', SQLERRM;
END $$;

-- partner_change_requests 성능 최적화 인덱스
CREATE INDEX IF NOT EXISTS idx_partner_change_requests_requester_name ON partner_change_requests USING GIN ((custom_data->>'requester_name'));
CREATE INDEX IF NOT EXISTS idx_partner_change_requests_company_name ON partner_change_requests USING GIN ((custom_data->>'company_name'));
CREATE INDEX IF NOT EXISTS idx_partner_change_requests_status ON partner_change_requests USING GIN ((custom_data->>'status'));
CREATE INDEX IF NOT EXISTS idx_partner_change_requests_department ON partner_change_requests USING GIN ((custom_data->>'department'));
CREATE INDEX IF NOT EXISTS idx_partner_change_requests_gin ON partner_change_requests USING GIN (custom_data);


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
