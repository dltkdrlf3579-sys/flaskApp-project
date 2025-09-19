-- 권한 테이블 구조 확인 및 생성
-- 기존 테이블 삭제 (필요시)
-- DROP TABLE IF EXISTS user_menu_permissions CASCADE;
-- DROP TABLE IF EXISTS dept_menu_permissions CASCADE;

-- 사용자별 메뉴 권한 테이블
CREATE TABLE IF NOT EXISTS user_menu_permissions (
    id SERIAL PRIMARY KEY,
    login_id VARCHAR(100) NOT NULL,
    menu_code VARCHAR(50) NOT NULL,
    read_level INTEGER DEFAULT 0 CHECK (read_level >= 0 AND read_level <= 3),
    write_level INTEGER DEFAULT 0 CHECK (write_level >= 0 AND write_level <= 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    UNIQUE(login_id, menu_code)
);

-- 부서별 메뉴 권한 테이블
CREATE TABLE IF NOT EXISTS dept_menu_permissions (
    id SERIAL PRIMARY KEY,
    dept_id VARCHAR(100) NOT NULL,
    menu_code VARCHAR(50) NOT NULL,
    read_level INTEGER DEFAULT 0 CHECK (read_level >= 0 AND read_level <= 3),
    write_level INTEGER DEFAULT 0 CHECK (write_level >= 0 AND write_level <= 3),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(100),
    is_active BOOLEAN DEFAULT true,
    UNIQUE(dept_id, menu_code)
);

-- 권한 접근 로그 테이블
CREATE TABLE IF NOT EXISTS permission_access_log (
    id SERIAL PRIMARY KEY,
    login_id VARCHAR(100),
    menu_code VARCHAR(50),
    action VARCHAR(20),
    success BOOLEAN,
    reason TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 인덱스 생성
CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_login_id ON user_menu_permissions(login_id);
CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_menu_code ON user_menu_permissions(menu_code);
CREATE INDEX IF NOT EXISTS idx_dept_menu_permissions_dept_id ON dept_menu_permissions(dept_id);
CREATE INDEX IF NOT EXISTS idx_dept_menu_permissions_menu_code ON dept_menu_permissions(menu_code);
CREATE INDEX IF NOT EXISTS idx_permission_access_log_login_id ON permission_access_log(login_id);
CREATE INDEX IF NOT EXISTS idx_permission_access_log_accessed_at ON permission_access_log(accessed_at);

-- 테이블 구조 확인
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'user_menu_permissions'
ORDER BY ordinal_position;

SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'dept_menu_permissions'
ORDER BY ordinal_position;