-- partner_change_requests 테이블 재생성 스크립트

-- 1. 기존 테이블 백업 (데이터 있으면)
ALTER TABLE IF EXISTS partner_change_requests
RENAME TO partner_change_requests_backup;

-- 2. 새 테이블 생성 (올바른 구조로)
CREATE TABLE partner_change_requests (
    id SERIAL PRIMARY KEY,
    request_number TEXT UNIQUE,
    requester_name TEXT,
    requester_department TEXT,
    company_name TEXT,
    business_number TEXT,
    change_type TEXT,
    current_value TEXT,
    new_value TEXT,
    change_reason TEXT,
    status TEXT DEFAULT 'pending',
    custom_data JSONB DEFAULT '{}',
    other_info TEXT,
    final_check_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);

-- 3. 백업 데이터 복원 (있으면)
-- INSERT INTO partner_change_requests
-- SELECT * FROM partner_change_requests_backup;

-- 4. 백업 테이블 삭제
-- DROP TABLE IF EXISTS partner_change_requests_backup;