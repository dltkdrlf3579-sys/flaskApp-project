-- PostgreSQL 섹션 테이블 스키마 보정 스크립트
-- 모든 섹션 테이블에 필수 컬럼 추가

-- Follow SOP sections 테이블 스키마 보정
ALTER TABLE follow_sop_sections ADD COLUMN IF NOT EXISTS section_order INTEGER DEFAULT 1;
ALTER TABLE follow_sop_sections ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;
ALTER TABLE follow_sop_sections ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;

-- Full Process sections 테이블 스키마 보정  
ALTER TABLE full_process_sections ADD COLUMN IF NOT EXISTS section_order INTEGER DEFAULT 1;
ALTER TABLE full_process_sections ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;
ALTER TABLE full_process_sections ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;

-- Safety Instruction sections 테이블 생성 (없는 경우)
CREATE TABLE IF NOT EXISTS safety_instruction_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

-- Safety Instruction sections 테이블 스키마 보정
ALTER TABLE safety_instruction_sections ADD COLUMN IF NOT EXISTS section_order INTEGER DEFAULT 1;
ALTER TABLE safety_instruction_sections ADD COLUMN IF NOT EXISTS is_active INTEGER DEFAULT 1;
ALTER TABLE safety_instruction_sections ADD COLUMN IF NOT EXISTS is_deleted INTEGER DEFAULT 0;

-- 섹션 초기 데이터 시드 (없는 경우에만)
-- Safety Instruction 섹션
INSERT INTO safety_instruction_sections (section_key, section_name, section_order, is_active, is_deleted)
VALUES 
    ('basic_info', '기본정보', 1, 1, 0),
    ('violation_info', '위반정보', 2, 1, 0),
    ('additional', '추가정보', 3, 1, 0)
ON CONFLICT (section_key) DO NOTHING;

-- Follow SOP 섹션
INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active, is_deleted)
VALUES 
    ('basic_info', '기본정보', 1, 1, 0),
    ('work_info', '작업정보', 2, 1, 0),
    ('additional', '추가정보', 3, 1, 0)
ON CONFLICT (section_key) DO NOTHING;

-- Full Process 섹션
INSERT INTO full_process_sections (section_key, section_name, section_order, is_active, is_deleted)
VALUES 
    ('basic_info', '기본정보', 1, 1, 0),
    ('process_info', '프로세스정보', 2, 1, 0),
    ('additional', '추가정보', 3, 1, 0)
ON CONFLICT (section_key) DO NOTHING;

-- 컬럼 tab 매핑 수정 (NULL인 경우 적절한 섹션으로 설정)
UPDATE safety_instruction_column_config 
SET tab = 'basic_info' 
WHERE tab IS NULL AND column_key IN (
    'issue_number', 'company_name', 'business_number', 'created_at', 
    'issue_date', 'improvement_deadline', 'status'
);

UPDATE safety_instruction_column_config 
SET tab = 'violation_info' 
WHERE tab IS NULL AND column_key IN (
    'violation_type', 'violation_details', 'legal_basis', 'penalty'
);

UPDATE follow_sop_column_config 
SET tab = 'basic_info' 
WHERE tab IS NULL AND column_key IN (
    'work_req_no', 'company_name', 'business_number', 'created_at'
);

UPDATE full_process_column_config 
SET tab = 'basic_info' 
WHERE tab IS NULL AND column_key IN (
    'fullprocess_number', 'company_name', 'business_number', 'created_at'
);

-- 확인 쿼리
SELECT 'follow_sop_sections' as table_name, COUNT(*) as count FROM follow_sop_sections WHERE is_active = 1
UNION ALL
SELECT 'full_process_sections', COUNT(*) FROM full_process_sections WHERE is_active = 1
UNION ALL
SELECT 'safety_instruction_sections', COUNT(*) FROM safety_instruction_sections WHERE is_active = 1;

-- 컬럼-섹션 매핑 확인
SELECT 'safety_instruction' as board, COUNT(DISTINCT tab) as section_count, COUNT(*) as column_count 
FROM safety_instruction_column_config WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
UNION ALL
SELECT 'follow_sop', COUNT(DISTINCT tab), COUNT(*) 
FROM follow_sop_column_config WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL)
UNION ALL
SELECT 'full_process', COUNT(DISTINCT tab), COUNT(*) 
FROM full_process_column_config WHERE is_active = 1 AND (is_deleted = 0 OR is_deleted IS NULL);