-- Safe Workplace core schema (PostgreSQL)
-- Ensure this script runs on portal_dev database
-- Provides main, detail, configuration, and attachment tables aligned with Follow SOP feature set

BEGIN;

CREATE TABLE IF NOT EXISTS safe_workplace (
    safeplace_no VARCHAR(20) PRIMARY KEY,
    custom_data JSONB DEFAULT '{}'::jsonb,
    is_deleted SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(64),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64)
);

CREATE TABLE IF NOT EXISTS safe_workplace_details (
    safeplace_no VARCHAR(20) PRIMARY KEY REFERENCES safe_workplace(safeplace_no) ON DELETE CASCADE,
    detailed_content TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safe_workplace_sections (
    id SERIAL PRIMARY KEY,
    section_key VARCHAR(64) UNIQUE NOT NULL,
    section_name VARCHAR(128) NOT NULL,
    section_order INTEGER DEFAULT 1,
    is_active SMALLINT DEFAULT 1,
    is_deleted SMALLINT DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safe_workplace_column_config (
    id SERIAL PRIMARY KEY,
    column_key VARCHAR(128) UNIQUE NOT NULL,
    column_name VARCHAR(255) NOT NULL,
    column_type VARCHAR(64) DEFAULT 'text',
    input_type VARCHAR(64),
    column_order INTEGER DEFAULT 0,
    column_span INTEGER DEFAULT 1,
    tab VARCHAR(64),
    is_active SMALLINT DEFAULT 1,
    is_deleted SMALLINT DEFAULT 0,
    is_system SMALLINT DEFAULT 0,
    is_required SMALLINT DEFAULT 0,
    dropdown_options TEXT,
    scoring_config TEXT,
    linked_columns TEXT,
    validation_rules TEXT,
    default_value TEXT,
    placeholder TEXT,
    table_group VARCHAR(64),
    table_type VARCHAR(64),
    code_group VARCHAR(64),
    code_category VARCHAR(64),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS safe_workplace_attachments (
    id SERIAL PRIMARY KEY,
    safeplace_no VARCHAR(20) REFERENCES safe_workplace(safeplace_no) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    file_size BIGINT,
    description TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(64),
    is_deleted SMALLINT DEFAULT 0
);

-- Seed baseline sections (idempotent)
INSERT INTO safe_workplace_sections (section_key, section_name, section_order, is_active, is_deleted)
VALUES
    ('basic_info', '기본정보', 1, 1, 0),
    ('workplace_info', '작업장정보', 2, 1, 0),
    ('safety_info', '안전정보', 3, 1, 0)
ON CONFLICT (section_key) DO UPDATE
SET section_name = EXCLUDED.section_name,
    section_order = EXCLUDED.section_order,
    is_active = EXCLUDED.is_active,
    is_deleted = 0;

-- Helpful indexes for board operations
CREATE INDEX IF NOT EXISTS idx_safe_workplace_created_at ON safe_workplace (created_at DESC);
CREATE INDEX IF NOT EXISTS idx_safe_workplace_is_deleted ON safe_workplace (is_deleted);
CREATE INDEX IF NOT EXISTS idx_safe_workplace_sections_order ON safe_workplace_sections (section_order);
CREATE INDEX IF NOT EXISTS idx_safe_workplace_column_tab_order ON safe_workplace_column_config (tab, column_order);

COMMIT;
