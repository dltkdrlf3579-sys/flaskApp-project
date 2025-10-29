-- 005_create_subcontract_tables.sql
-- 적격성평가 보드(산안법 도급승인 / 화관법 도급신고) 기본 테이블 생성

-- 산안법 도급승인 메인 테이블
CREATE TABLE IF NOT EXISTS subcontract_approval (
    approval_number TEXT PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- 산안법 도급승인 섹션 테이블
CREATE TABLE IF NOT EXISTS subcontract_approval_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

-- 산안법 도급승인 상세 테이블
CREATE TABLE IF NOT EXISTS subcontract_approval_details (
    approval_number TEXT PRIMARY KEY,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 산안법 도급승인 컬럼 설정 테이블
CREATE TABLE IF NOT EXISTS subcontract_approval_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER DEFAULT 1,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 산안법 도급승인 캐시 테이블
CREATE TABLE IF NOT EXISTS subcontract_approval_cache (
    id SERIAL PRIMARY KEY,
    approval_number TEXT UNIQUE,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    custom_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

-- 화관법 도급신고 메인 테이블
CREATE TABLE IF NOT EXISTS subcontract_report (
    report_number TEXT PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

-- 화관법 도급신고 섹션 테이블
CREATE TABLE IF NOT EXISTS subcontract_report_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

-- 화관법 도급신고 상세 테이블
CREATE TABLE IF NOT EXISTS subcontract_report_details (
    report_number TEXT PRIMARY KEY,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 화관법 도급신고 컬럼 설정 테이블
CREATE TABLE IF NOT EXISTS subcontract_report_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER DEFAULT 1,
    linked_columns TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 화관법 도급신고 캐시 테이블
CREATE TABLE IF NOT EXISTS subcontract_report_cache (
    id SERIAL PRIMARY KEY,
    report_number TEXT UNIQUE,
    primary_company TEXT,
    primary_business_number TEXT,
    subcontractor TEXT,
    subcontractor_business_number TEXT,
    custom_data JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);
