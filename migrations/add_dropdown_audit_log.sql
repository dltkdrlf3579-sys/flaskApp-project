-- 드롭다운 코드 변경 이력 테이블
-- 모든 변경사항을 추적하여 감사(Audit) 로그 제공

CREATE TABLE IF NOT EXISTS dropdown_code_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    column_key TEXT NOT NULL,           -- 컬럼 식별자
    option_code TEXT NOT NULL,          -- 코드
    action_type TEXT NOT NULL,          -- 'CREATE', 'UPDATE', 'DELETE', 'ACTIVATE', 'DEACTIVATE'
    old_value TEXT,                     -- 이전 값
    new_value TEXT,                     -- 새 값
    old_order INTEGER,                  -- 이전 순서
    new_order INTEGER,                  -- 새 순서
    changed_by TEXT,                    -- 변경자 (현재는 NULL, 추후 SSO 연동 시 사번)
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ip_address TEXT,                    -- 접속 IP
    user_agent TEXT,                    -- 브라우저 정보
    notes TEXT                          -- 변경 사유 등 메모
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_audit_column_key ON dropdown_code_audit(column_key);
CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON dropdown_code_audit(changed_at);
CREATE INDEX IF NOT EXISTS idx_audit_action_type ON dropdown_code_audit(action_type);

-- 코드 변경 통계 뷰
CREATE VIEW IF NOT EXISTS dropdown_code_stats AS
SELECT 
    column_key,
    COUNT(CASE WHEN action_type = 'CREATE' THEN 1 END) as total_created,
    COUNT(CASE WHEN action_type = 'UPDATE' THEN 1 END) as total_updated,
    COUNT(CASE WHEN action_type = 'DELETE' THEN 1 END) as total_deleted,
    MAX(changed_at) as last_changed,
    COUNT(DISTINCT DATE(changed_at)) as active_days
FROM dropdown_code_audit
GROUP BY column_key;