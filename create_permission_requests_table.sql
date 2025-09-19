-- 권한 신청 테이블 생성 (SSO 데이터 구조 그대로 사용)
CREATE TABLE IF NOT EXISTS permission_requests (
    id SERIAL PRIMARY KEY,
    login_id VARCHAR(100) NOT NULL,              -- SSO login_id
    user_name VARCHAR(100),                      -- SSO user_name
    deptid VARCHAR(100),                         -- SSO deptid
    dept_name VARCHAR(100),                      -- SSO dept_name
    menu_code VARCHAR(50) NOT NULL,              -- 메뉴 코드
    menu_name VARCHAR(100),                      -- 메뉴 이름 (표시용)
    permission_type VARCHAR(20) NOT NULL,        -- 'read' 또는 'read_write'
    reason TEXT NOT NULL,                        -- 신청 사유
    status VARCHAR(20) DEFAULT 'pending',        -- pending, approved, rejected
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    reviewed_by VARCHAR(100),                    -- 검토자 login_id
    reviewed_at TIMESTAMP,                       -- 검토 시간
    review_comment TEXT,                         -- 검토 의견
    is_active BOOLEAN DEFAULT true
);

-- 인덱스 추가
CREATE INDEX idx_permission_requests_status ON permission_requests(status);
CREATE INDEX idx_permission_requests_login ON permission_requests(login_id);
CREATE INDEX idx_permission_requests_created ON permission_requests(created_at DESC);

-- 메뉴 이름 매핑 (표시용)
CREATE TABLE IF NOT EXISTS menu_names (
    menu_code VARCHAR(50) PRIMARY KEY,
    menu_name VARCHAR(100) NOT NULL,
    description TEXT
);

-- 초기 메뉴 이름 데이터 (실제 메뉴와 동일하게)
INSERT INTO menu_names (menu_code, menu_name, description) VALUES
('VENDOR_MGT', '협력사 기준정보', '협력사 정보 관리'),
('REFERENCE_CHANGE', '기준정보 변경요청', '기준정보 변경 관리'),
('ACCIDENT_MGT', '협력사 사고', '사고 정보 관리'),
('SAFETY_INSTRUCTION', '환경안전 지시서', '안전지시 관리'),
('FOLLOW_SOP', 'Follow SOP', 'SOP 이행 관리'),
('FULL_PROCESS', 'FullProcess', '프로세스 전체 관리')
ON CONFLICT (menu_code) DO UPDATE SET
    menu_name = EXCLUDED.menu_name,
    description = EXCLUDED.description;