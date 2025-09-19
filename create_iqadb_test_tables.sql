-- 가상 iqadb 스키마 및 테스트 테이블 생성
-- 권한 테스트를 위한 외부 쿼리 테이블

-- iqadb 스키마 생성 (이미 있으면 무시)
CREATE SCHEMA IF NOT EXISTS iqadb;

-- 1. followsop 테이블 (SOP 이행)
CREATE TABLE IF NOT EXISTS iqadb."외부_followsop_테이블" (
    id SERIAL PRIMARY KEY,
    sop_number VARCHAR(50),
    sop_title VARCHAR(200),
    implementation_date DATE,
    assigned_user_id VARCHAR(100),      -- 담당자 (owner)
    assigned_dept_code VARCHAR(50),     -- 담당 부서 (dept)
    status VARCHAR(50),
    compliance_rate INTEGER,
    notes TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. fullprocess 테이블 (Full Process)
CREATE TABLE IF NOT EXISTS iqadb."외부_fullprocess_테이블" (
    id SERIAL PRIMARY KEY,
    process_id VARCHAR(50),
    process_name VARCHAR(200),
    process_date DATE,
    responsible_user_id VARCHAR(100),   -- 책임자 (owner)
    responsible_dept_code VARCHAR(50),  -- 책임 부서 (dept)
    stage VARCHAR(50),
    completion_rate INTEGER,
    description TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. partner_change_requests 테이블 (협력사 변경 요청)
CREATE TABLE IF NOT EXISTS iqadb."외부_partner_change_requests_테이블" (
    id SERIAL PRIMARY KEY,
    request_number VARCHAR(50),
    partner_name VARCHAR(200),
    business_number VARCHAR(20),
    change_type VARCHAR(50),
    requester_id VARCHAR(100),          -- 요청자 (owner)
    requester_dept_code VARCHAR(50),    -- 요청 부서 (dept)
    request_date DATE,
    status VARCHAR(50),
    reason TEXT,
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 테스트 데이터 삽입

-- followsop 테스트 데이터
INSERT INTO iqadb."외부_followsop_테이블"
    (sop_number, sop_title, implementation_date, assigned_user_id, assigned_dept_code, status, compliance_rate, notes, created_by)
VALUES
    ('SOP-001', '안전모 착용 절차', '2025-09-15', 'kim_john', 'SAFETY_001', '진행중', 85, '전체 작업자 교육 완료', 'admin'),
    ('SOP-002', '고소작업 안전절차', '2025-09-16', 'lee_jane', 'SAFETY_001', '완료', 95, '재교육 실시 완료', 'admin'),
    ('SOP-003', '화학물질 취급 절차', '2025-09-17', 'park_mike', 'ENV_002', '진행중', 70, '보호구 지급 진행', 'manager'),
    ('SOP-004', '비상대피 절차', '2025-09-18', 'kim_john', 'SAFETY_001', '계획', 0, '다음주 교육 예정', 'kim_john'),
    ('SOP-005', '전기작업 안전절차', '2025-09-19', 'choi_sara', 'ELEC_003', '진행중', 60, '절연장비 점검 중', 'manager');

-- fullprocess 테스트 데이터
INSERT INTO iqadb."외부_fullprocess_테이블"
    (process_id, process_name, process_date, responsible_user_id, responsible_dept_code, stage, completion_rate, description, created_by)
VALUES
    ('PROC-001', '신규 안전관리 프로세스', '2025-09-10', 'admin', 'SAFETY_001', '실행', 75, '3단계 중 2단계 완료', 'admin'),
    ('PROC-002', '환경영향평가 프로세스', '2025-09-11', 'lee_jane', 'ENV_002', '계획', 25, '초기 평가 진행', 'manager'),
    ('PROC-003', '품질관리 프로세스', '2025-09-12', 'park_mike', 'QA_004', '실행', 50, '샘플링 검사 진행', 'admin'),
    ('PROC-004', '협력사 평가 프로세스', '2025-09-13', 'kim_john', 'SAFETY_001', '검토', 90, '최종 검토 단계', 'kim_john'),
    ('PROC-005', '교육훈련 프로세스', '2025-09-14', 'choi_sara', 'HR_005', '완료', 100, '전체 교육 완료', 'admin');

-- partner_change_requests 테스트 데이터
INSERT INTO iqadb."외부_partner_change_requests_테이블"
    (request_number, partner_name, business_number, change_type, requester_id, requester_dept_code, request_date, status, reason, created_by)
VALUES
    ('REQ-001', '안전건설(주)', '123-45-67890', '정보변경', 'kim_john', 'SAFETY_001', '2025-09-10', '승인', '대표자 변경', 'admin'),
    ('REQ-002', '환경기술(주)', '234-56-78901', '신규등록', 'lee_jane', 'ENV_002', '2025-09-11', '검토중', '신규 협력사 등록', 'manager'),
    ('REQ-003', '품질엔지니어링', '345-67-89012', '정보변경', 'park_mike', 'QA_004', '2025-09-12', '승인', '주소 변경', 'admin'),
    ('REQ-004', '전기공사(주)', '456-78-90123', '계약해지', 'choi_sara', 'ELEC_003', '2025-09-13', '반려', '서류 미비', 'manager'),
    ('REQ-005', '시설관리(주)', '567-89-01234', '신규등록', 'kim_john', 'SAFETY_001', '2025-09-14', '검토중', '시설관리 협력사', 'kim_john');

-- 권한 테스트를 위한 추가 사용자 데이터
-- 다양한 부서와 사용자 조합
INSERT INTO iqadb."외부_followsop_테이블"
    (sop_number, sop_title, implementation_date, assigned_user_id, assigned_dept_code, status, compliance_rate, notes, created_by)
VALUES
    ('SOP-006', '타부서 SOP', '2025-09-20', 'other_user', 'OTHER_999', '진행중', 40, '타부서 데이터', 'other_user'),
    ('SOP-007', '관리자 전용', '2025-09-21', 'admin', 'ADMIN_000', '완료', 100, '관리자만 볼 수 있음', 'admin');

-- 결과 확인
SELECT 'followsop' as table_name, COUNT(*) as row_count FROM iqadb."외부_followsop_테이블"
UNION ALL
SELECT 'fullprocess', COUNT(*) FROM iqadb."외부_fullprocess_테이블"
UNION ALL
SELECT 'partner_change_requests', COUNT(*) FROM iqadb."외부_partner_change_requests_테이블";

-- 권한 체크 예시 확인
SELECT
    'followsop 담당자별' as check_type,
    assigned_user_id,
    COUNT(*) as count
FROM iqadb."외부_followsop_테이블"
GROUP BY assigned_user_id
ORDER BY count DESC;