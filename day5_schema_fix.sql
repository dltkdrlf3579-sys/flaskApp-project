-- Day 5 Schema Fix Script
-- 실행: psql -U postgres -d portal_db -f day5_schema_fix.sql

-- 1. menu_departments 테이블 생성 (누락됨)
CREATE TABLE IF NOT EXISTS menu_departments (
    id SERIAL PRIMARY KEY,
    menu_code VARCHAR(100),
    dept_id VARCHAR(50),
    access_level VARCHAR(20) DEFAULT 'view',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(menu_code, dept_id)
);

-- 2. department_hierarchy 컬럼 수정
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'department_hierarchy'
        AND column_name = 'level'
    ) THEN
        ALTER TABLE department_hierarchy RENAME COLUMN level TO dept_level;
    END IF;
END $$;

-- 3. system_roles 테이블 확인 및 생성
CREATE TABLE IF NOT EXISTS system_roles (
    role_id VARCHAR(50) PRIMARY KEY,
    role_name VARCHAR(100) NOT NULL,
    role_code VARCHAR(50) UNIQUE,
    description TEXT,
    priority INTEGER DEFAULT 100,
    is_system BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 누락된 컬럼 추가
ALTER TABLE system_users
ADD COLUMN IF NOT EXISTS sso_role VARCHAR(50),
ADD COLUMN IF NOT EXISTS last_sync TIMESTAMP,
ADD COLUMN IF NOT EXISTS position VARCHAR(100);

ALTER TABLE user_role_mapping
ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS assigned_by VARCHAR(50);

-- 5. partner_change_requests 테이블
CREATE TABLE IF NOT EXISTS partner_change_requests (
    id SERIAL PRIMARY KEY,
    partner_id VARCHAR(50),
    request_type VARCHAR(50),
    status VARCHAR(20) DEFAULT 'pending',
    request_data JSONB,
    requested_by VARCHAR(50),
    approved_by VARCHAR(50),
    requested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    approved_at TIMESTAMP,
    violation_content TEXT
);

-- 6. 기본 역할 데이터 삽입
INSERT INTO system_roles (role_id, role_name, role_code, description, priority, is_system)
VALUES
    ('super_admin', 'Super Administrator', 'super_admin', 'Full system access', 1, TRUE),
    ('admin', 'Administrator', 'admin', 'Administrative access', 10, TRUE),
    ('manager', 'Manager', 'manager', 'Management access', 20, TRUE),
    ('user', 'User', 'user', 'Standard user access', 30, FALSE),
    ('viewer', 'Viewer', 'viewer', 'Read-only access', 40, FALSE),
    ('partner', 'Partner', 'partner', 'Partner access', 50, FALSE)
ON CONFLICT (role_id) DO NOTHING;