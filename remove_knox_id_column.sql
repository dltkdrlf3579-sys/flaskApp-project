-- Knox ID 컬럼 제거 (login_id = knox_id이므로 중복 불필요)

-- system_users 테이블에서 knox_id 컬럼 제거
ALTER TABLE system_users DROP COLUMN IF EXISTS knox_id CASCADE;

-- 불필요한 인덱스 제거
DROP INDEX IF EXISTS idx_system_users_knox_id;

-- emp_id 컬럼도 있다면 제거
ALTER TABLE system_users DROP COLUMN IF EXISTS emp_id CASCADE;

-- login_id가 primary key인지 확인
ALTER TABLE system_users
DROP CONSTRAINT IF EXISTS system_users_pkey CASCADE;

ALTER TABLE system_users
ADD CONSTRAINT system_users_pkey PRIMARY KEY (login_id);

COMMENT ON COLUMN system_users.login_id IS 'Knox ID (SSO identifier and primary key)';