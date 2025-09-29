
-- access_audit_log 기본 스키마 및 인덱스/보강 스크립트

-- 1. 테이블 생성 (없을 때만)
CREATE TABLE IF NOT EXISTS access_audit_log (
    id SERIAL PRIMARY KEY,
    emp_id VARCHAR(50),
    login_id VARCHAR(100),
    action VARCHAR(50),
    menu_code VARCHAR(50),
    resource_id VARCHAR(100),
    ip_address VARCHAR(45),
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 추가 컬럼 보강 (schema_migration_day4.py 기준)
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS action_scope VARCHAR(50);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS action_type VARCHAR(50);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS request_path TEXT;
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS permission_result VARCHAR(50);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS user_agent TEXT;
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS object_type VARCHAR(50);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS object_id VARCHAR(100);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS object_name VARCHAR(255);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS details JSONB;
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS action TEXT;
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS login_id VARCHAR(100);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS resource_id VARCHAR(100);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS error_message TEXT;
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS ip_address VARCHAR(45);
ALTER TABLE access_audit_log ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT TRUE;

-- 3. 인덱스
CREATE INDEX IF NOT EXISTS idx_audit_uid_created ON access_audit_log(emp_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_action_created ON access_audit_log(action, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_scope_created ON access_audit_log(action_scope, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_menu_created  ON access_audit_log(menu_code, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_log_compound ON access_audit_log(emp_id, created_at DESC);

-- 4. 성공 여부 보정
UPDATE access_audit_log
SET success = CASE
    WHEN permission_result = 'SUCCESS' THEN TRUE
    WHEN permission_result = 'DENIED' OR permission_result = 'REJECTED' THEN FALSE
    ELSE success
END
WHERE success IS NULL;
