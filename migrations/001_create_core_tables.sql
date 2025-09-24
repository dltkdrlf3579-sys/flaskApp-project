-- 001_create_core_tables.sql
-- Phase 4: init_db 해체 작업 1/4
-- Postgres 전용 스키마 정의 (IF NOT EXISTS / CREATE TABLE) 모음

-- page table (UI page 관리)
CREATE TABLE IF NOT EXISTS pages (
    id SERIAL PRIMARY KEY,
    url TEXT UNIQUE,
    title TEXT,
    content TEXT
);

-- dropdown_option_codes_v2: 보드 별 코드 옵션 관리
CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
    id SERIAL PRIMARY KEY,
    board_type TEXT NOT NULL,
    column_key TEXT NOT NULL,
    option_code TEXT NOT NULL,
    option_value TEXT NOT NULL,
    display_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_by TEXT,
    UNIQUE(board_type, column_key, option_code)
);
CREATE INDEX IF NOT EXISTS idx_doc_v2_board_col ON dropdown_option_codes_v2(board_type, column_key, is_active);

-- 공통 section_config: 게시판별 섹션 정의
CREATE TABLE IF NOT EXISTS section_config (
    id SERIAL PRIMARY KEY,
    board_type TEXT NOT NULL,
    section_key TEXT NOT NULL,
    section_name TEXT NOT NULL,
    section_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(board_type, section_key)
);

-- 각 게시판 컬럼 설정 테이블
CREATE TABLE IF NOT EXISTS accident_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    dropdown_options TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    dropdown_options TEXT,
    tab TEXT,
    column_span INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS follow_sop_column_config (
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

CREATE TABLE IF NOT EXISTS full_process_column_config (
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

CREATE TABLE IF NOT EXISTS partner_standards_column_config (
    id SERIAL PRIMARY KEY,
    column_key TEXT UNIQUE NOT NULL,
    column_name TEXT NOT NULL,
    column_type TEXT DEFAULT 'text',
    column_order INTEGER DEFAULT 0,
    is_active INTEGER DEFAULT 1,
    dropdown_options TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Safe Workplace: main + details + sections
CREATE TABLE IF NOT EXISTS safe_workplace (
    safeplace_no TEXT PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by TEXT
);

CREATE TABLE IF NOT EXISTS safe_workplace_sections (
    id SERIAL PRIMARY KEY,
    section_key TEXT UNIQUE,
    section_name TEXT,
    section_order INTEGER DEFAULT 1,
    is_active INTEGER DEFAULT 1,
    is_deleted INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS safe_workplace_details (
    id SERIAL PRIMARY KEY,
    safeplace_no TEXT UNIQUE NOT NULL,
    detailed_content TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

