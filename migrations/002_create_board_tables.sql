-- 002_create_board_tables.sql
-- Phase 4: init_db 해체 작업 2/4
-- 주요 본문 테이블 (Follow SOP, Safety Instruction, Safe Workplace, Full Process 등)

-- Safety Instruction main/detail/section tables
CREATE TABLE IF NOT EXISTS safety_instructions (
    issue_number TEXT PRIMARY KEY,
    issuer TEXT,
    issuer_department TEXT,
    classification TEXT,
    employment_type TEXT,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    disciplined_person TEXT,
    gbm TEXT,
    business_division TEXT,
    team TEXT,
    department TEXT,
    violation_date DATE,
    discipline_date DATE,
    discipline_department TEXT,
    discipline_type TEXT,
    accident_type TEXT,
    accident_grade TEXT,
    safety_violation_grade TEXT,
    violation_type TEXT,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS safety_instruction_details (
    issue_number TEXT PRIMARY KEY,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safety_instruction_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

-- Follow SOP main/detail tables
CREATE TABLE IF NOT EXISTS follow_sop (
    work_req_no TEXT PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS follow_sop_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS follow_sop_details (
    work_req_no TEXT PRIMARY KEY,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Full Process main/detail tables
CREATE TABLE IF NOT EXISTS full_process (
    fullprocess_number TEXT PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS full_process_details (
    fullprocess_number TEXT PRIMARY KEY,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS full_process_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

