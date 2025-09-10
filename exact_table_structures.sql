-- 개발 환경 테이블 구조 덤프
-- 운영 환경에서 이 SQL을 그대로 실행하세요


-- safety_instructions
CREATE TABLE IF NOT EXISTS safety_instructions (
    id SERIAL PRIMARY KEY,
    issue_number TEXT NOT NULL,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    disciplined_person TEXT,
    disciplined_person_id TEXT,
    violation_content TEXT,
    detailed_content TEXT,
    custom_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    is_deleted INTEGER DEFAULT 0
);
-- UNIQUE: issue_number

-- accidents
CREATE TABLE IF NOT EXISTS accidents (
    id SERIAL PRIMARY KEY,
    accident_number TEXT NOT NULL,
    accident_name TEXT,
    workplace TEXT,
    accident_grade TEXT,
    accident_date DATE,
    custom_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    is_deleted INTEGER DEFAULT 0
);
-- UNIQUE: accident_number

-- follow_sop
CREATE TABLE IF NOT EXISTS follow_sop (
    id SERIAL PRIMARY KEY,
    work_req_no TEXT,
    custom_data JSONB DEFAULT '{}',
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- full_process
CREATE TABLE IF NOT EXISTS full_process (
    id SERIAL PRIMARY KEY,
    fullprocess_number TEXT,
    custom_data JSONB DEFAULT '{}',
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- partners
CREATE TABLE IF NOT EXISTS partners (
    id SERIAL PRIMARY KEY,
    business_number TEXT NOT NULL,
    company_name TEXT,
    partner_class TEXT,
    business_type_major TEXT,
    business_type_minor TEXT,
    hazard_work_flag TEXT,
    representative TEXT,
    address TEXT,
    average_age DOUBLE PRECISION,
    annual_revenue DOUBLE PRECISION,
    transaction_count INTEGER,
    permanent_workers INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- UNIQUE: business_number

-- change_requests
CREATE TABLE IF NOT EXISTS change_requests (
    id SERIAL PRIMARY KEY,
    request_number TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    custom_data TEXT
);
-- UNIQUE: request_number

-- partner_change_requests
CREATE TABLE IF NOT EXISTS partner_change_requests (
    id SERIAL PRIMARY KEY,
    request_number TEXT,
    business_number TEXT,
    company_name TEXT,
    change_type TEXT,
    change_details TEXT,
    status TEXT,
    requested_by TEXT,
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_by TEXT,
    approved_at TIMESTAMP,
    is_deleted BOOLEAN,
    requester_name TEXT,
    requester_department TEXT,
    current_value TEXT,
    new_value TEXT,
    change_reason TEXT,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    custom_data TEXT
);
-- UNIQUE: request_number

-- safety_instructions_cache
CREATE TABLE IF NOT EXISTS safety_instructions_cache (
    id SERIAL PRIMARY KEY,
    issue_number TEXT,
    issue_title TEXT,
    issue_date DATE,
    instruction_type TEXT,
    department TEXT,
    target_audience TEXT,
    related_regulation TEXT,
    custom_data JSONB,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    status TEXT,
    request_date DATE,
    process_date DATE,
    work_type TEXT,
    process_type TEXT
);
-- UNIQUE: issue_number

-- accidents_cache
CREATE TABLE IF NOT EXISTS accidents_cache (
    id SERIAL PRIMARY KEY,
    accident_number TEXT,
    accident_name TEXT,
    accident_time TEXT,
    workplace TEXT,
    accident_grade TEXT,
    major_category TEXT,
    injury_form TEXT,
    injury_type TEXT,
    accident_date DATE,
    day_of_week TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    building TEXT,
    floor TEXT,
    location_category TEXT,
    location_detail TEXT,
    is_deleted INTEGER DEFAULT 0,
    synced_at TIMESTAMP,
    custom_data JSONB,
    accident_datetime TIMESTAMP,
    accident_type TEXT,
    responsible_company1 TEXT,
    responsible_company1_no TEXT,
    responsible_company2 TEXT,
    responsible_company2_no TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    department TEXT,
    status TEXT,
    request_date DATE,
    process_date DATE,
    work_type TEXT,
    process_type TEXT
);
-- UNIQUE: accident_number

-- followsop_cache
CREATE TABLE IF NOT EXISTS followsop_cache (
    id SERIAL PRIMARY KEY,
    work_req_no TEXT,
    custom_data JSONB DEFAULT '{}',
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);
-- UNIQUE: work_req_no

-- fullprocess_cache
CREATE TABLE IF NOT EXISTS fullprocess_cache (
    id SERIAL PRIMARY KEY,
    fullprocess_number TEXT,
    custom_data JSONB DEFAULT '{}',
    sync_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);
-- UNIQUE: fullprocess_number

-- partners_cache
CREATE TABLE IF NOT EXISTS partners_cache (
    business_number TEXT NOT NULL,
    company_name TEXT NOT NULL,
    partner_class TEXT,
    business_type_major TEXT,
    business_type_minor TEXT,
    hazard_work_flag TEXT,
    representative TEXT,
    address TEXT,
    average_age INTEGER,
    annual_revenue BIGINT,
    transaction_count TEXT,
    permanent_workers INTEGER,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

-- change_requests_cache
CREATE TABLE IF NOT EXISTS change_requests_cache (
    id SERIAL PRIMARY KEY,
    request_number TEXT,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    custom_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    created_by TEXT,
    updated_by TEXT,
    department TEXT,
    status TEXT,
    request_date DATE,
    process_date DATE,
    work_type TEXT,
    process_type TEXT
);
-- UNIQUE: request_number
-- UNIQUE: request_number

-- partner_standards_cache
CREATE TABLE IF NOT EXISTS partner_standards_cache (
    id SERIAL PRIMARY KEY,
    standard_number TEXT,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    custom_data JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    created_by TEXT,
    updated_by TEXT,
    department TEXT,
    status TEXT,
    request_date DATE,
    process_date DATE,
    work_type TEXT,
    process_type TEXT
);
-- UNIQUE: standard_number

-- safety_instruction_column_config
CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
-- UNIQUE: column_key

-- accident_column_config
CREATE TABLE IF NOT EXISTS accident_column_config (
    id SERIAL PRIMARY KEY,
    column_key VARCHAR(50) NOT NULL,
    column_name VARCHAR(100) NOT NULL,
    column_type VARCHAR(20),
    column_order INTEGER DEFAULT 0,
    is_active INTEGER,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    table_name TEXT,
    table_type TEXT,
    is_required BOOLEAN,
    dropdown_values TEXT,
    is_deleted INTEGER DEFAULT 0,
    is_readonly BOOLEAN,
    is_list_display INTEGER,
    is_system INTEGER DEFAULT 0,
    input_type TEXT,
    table_group TEXT
);
-- UNIQUE: column_key

-- follow_sop_column_config
CREATE TABLE IF NOT EXISTS follow_sop_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT,
    column_order INTEGER DEFAULT 0,
    is_active INTEGER,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    is_list_display INTEGER,
    is_system INTEGER DEFAULT 0,
    is_required INTEGER DEFAULT 0,
    input_type TEXT,
    table_group TEXT,
    table_type TEXT,
    table_name TEXT
);
-- UNIQUE: column_key

-- full_process_column_config
CREATE TABLE IF NOT EXISTS full_process_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT,
    column_order INTEGER DEFAULT 0,
    is_active INTEGER,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    is_list_display INTEGER,
    is_system INTEGER DEFAULT 0,
    is_required INTEGER DEFAULT 0,
    input_type TEXT,
    table_group TEXT,
    table_type TEXT,
    table_name TEXT,
    scoring_config TEXT
);
-- UNIQUE: column_key

-- change_request_column_config
CREATE TABLE IF NOT EXISTS change_request_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT,
    column_order INTEGER DEFAULT 0,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_list_display INTEGER,
    is_active INTEGER,
    is_deleted INTEGER DEFAULT 0,
    is_system INTEGER DEFAULT 0,
    is_required INTEGER DEFAULT 0,
    input_type TEXT
);
-- UNIQUE: column_key

-- partner_change_column_config
CREATE TABLE IF NOT EXISTS partner_change_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT,
    column_order INTEGER DEFAULT 0,
    is_active INTEGER,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0,
    is_list_display INTEGER DEFAULT 0,
    is_system INTEGER DEFAULT 0,
    is_required INTEGER DEFAULT 0,
    input_type TEXT,
    table_group TEXT,
    table_type TEXT,
    table_name TEXT,
    scoring_config TEXT
);
-- UNIQUE: column_key
