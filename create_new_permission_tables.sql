-- 환경안전 특화 권한 시스템
-- 읽기 권한과 등록/수정 권한을 별도로 관리

-- 기존 테이블 백업 (이미 백업이 있으면 건너뜀)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_menu_permissions' AND table_schema = 'public')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'user_menu_permissions_old' AND table_schema = 'public')
    THEN
        ALTER TABLE user_menu_permissions RENAME TO user_menu_permissions_old;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dept_menu_roles' AND table_schema = 'public')
       AND NOT EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'dept_menu_roles_old' AND table_schema = 'public')
    THEN
        ALTER TABLE dept_menu_roles RENAME TO dept_menu_roles_old;
    END IF;
END$$;

-- 1. 새로운 사용자별 권한 테이블
CREATE TABLE IF NOT EXISTS user_menu_permissions (
    login_id VARCHAR(100) NOT NULL,
    menu_code VARCHAR(50) NOT NULL,

    -- 읽기 권한 레벨 (1: 본인, 2: 부서, 3: 전체)
    read_level INTEGER DEFAULT 0,  -- 0: 권한없음, 1-3: 레벨

    -- 등록/수정 권한 레벨 (1: 본인, 2: 부서, 3: 전체)
    write_level INTEGER DEFAULT 0,  -- 0: 권한없음, 1-3: 레벨

    -- 삭제 권한 (별도 관리 - 매우 제한적)
    can_delete BOOLEAN DEFAULT FALSE,

    granted_by VARCHAR(100),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    PRIMARY KEY (login_id, menu_code)
);

-- 2. 부서별 권한 테이블 (동일 구조)
CREATE TABLE IF NOT EXISTS dept_menu_roles (
    dept_id VARCHAR(50) NOT NULL,  -- SSO dept_id
    dept_code VARCHAR(100),
    dept_full_path TEXT,
    menu_code VARCHAR(50) NOT NULL,

    -- 읽기 권한 레벨
    read_level INTEGER DEFAULT 0,

    -- 등록/수정 권한 레벨
    write_level INTEGER DEFAULT 0,

    -- 삭제 권한
    can_delete BOOLEAN DEFAULT FALSE,

    granted_by VARCHAR(100),
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,

    PRIMARY KEY (dept_id, menu_code)
);

-- 3. 권한 레벨 정의 테이블 (참조용)
CREATE TABLE IF NOT EXISTS permission_levels (
    level_type VARCHAR(20) NOT NULL,  -- 'read' or 'write'
    level_value INTEGER NOT NULL,
    level_name VARCHAR(50),
    description TEXT,
    PRIMARY KEY (level_type, level_value)
);

INSERT INTO permission_levels (level_type, level_value, level_name, description) VALUES
('read', 0, '권한없음', '해당 메뉴 접근 불가'),
('read', 1, '본인 관련', '본인이 작성하거나 담당자로 지정된 글만 조회'),
('read', 2, '부서 관련', '본인 부서와 관련된 글 조회'),
('read', 3, '전체 조회', '게시판 내 모든 글 조회'),
('write', 0, '권한없음', '등록/수정 불가'),
('write', 1, '본인 글만', '등록 가능, 본인 작성 글만 수정'),
('write', 2, '부서 글', '등록 가능, 부서 관련 글 수정'),
('write', 3, '전체 수정', '등록 가능, 모든 글 수정')
ON CONFLICT (level_type, level_value) DO NOTHING;

-- 4. 통합 권한 체크 함수
CREATE OR REPLACE FUNCTION check_data_permission(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR,
    p_action VARCHAR,  -- 'read', 'write', 'delete'
    p_data_owner VARCHAR DEFAULT NULL,  -- 데이터 소유자 login_id
    p_data_dept VARCHAR DEFAULT NULL    -- 데이터 소속 부서
) RETURNS BOOLEAN AS $$
DECLARE
    user_level INTEGER := 0;
    dept_level INTEGER := 0;
    final_level INTEGER := 0;
    user_can_delete BOOLEAN := FALSE;
    dept_can_delete BOOLEAN := FALSE;
BEGIN
    -- 삭제 권한 체크
    IF p_action = 'delete' THEN
        SELECT can_delete INTO user_can_delete
        FROM user_menu_permissions
        WHERE login_id = p_login_id AND menu_code = p_menu_code AND is_active = TRUE;

        SELECT can_delete INTO dept_can_delete
        FROM dept_menu_roles
        WHERE dept_id = p_dept_id AND menu_code = p_menu_code AND is_active = TRUE;

        RETURN COALESCE(user_can_delete, FALSE) OR COALESCE(dept_can_delete, FALSE);
    END IF;

    -- 읽기/쓰기 레벨 체크
    IF p_action = 'read' THEN
        SELECT read_level INTO user_level
        FROM user_menu_permissions
        WHERE login_id = p_login_id AND menu_code = p_menu_code AND is_active = TRUE;

        SELECT read_level INTO dept_level
        FROM dept_menu_roles
        WHERE dept_id = p_dept_id AND menu_code = p_menu_code AND is_active = TRUE;
    ELSE  -- write
        SELECT write_level INTO user_level
        FROM user_menu_permissions
        WHERE login_id = p_login_id AND menu_code = p_menu_code AND is_active = TRUE;

        SELECT write_level INTO dept_level
        FROM dept_menu_roles
        WHERE dept_id = p_dept_id AND menu_code = p_menu_code AND is_active = TRUE;
    END IF;

    -- 더 높은 레벨 적용 (OR 연산)
    final_level := GREATEST(COALESCE(user_level, 0), COALESCE(dept_level, 0));

    -- 레벨에 따른 권한 체크
    IF final_level = 0 THEN
        RETURN FALSE;
    ELSIF final_level = 1 THEN
        -- 본인 관련 데이터만
        RETURN p_data_owner = p_login_id;
    ELSIF final_level = 2 THEN
        -- 부서 관련 데이터
        RETURN p_data_owner = p_login_id OR p_data_dept = p_dept_id;
    ELSIF final_level >= 3 THEN
        -- 전체 접근 가능
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END;
$$ LANGUAGE plpgsql;

-- 5. 간편 체크 함수들
CREATE OR REPLACE FUNCTION can_read_data(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR,
    p_data_owner VARCHAR,
    p_data_dept VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN check_data_permission(p_login_id, p_dept_id, p_menu_code, 'read', p_data_owner, p_data_dept);
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION can_write_data(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR,
    p_data_owner VARCHAR,
    p_data_dept VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN check_data_permission(p_login_id, p_dept_id, p_menu_code, 'write', p_data_owner, p_data_dept);
END;
$$ LANGUAGE plpgsql;

-- 인덱스 생성
CREATE INDEX idx_user_menu_permissions_lookup ON user_menu_permissions(login_id, menu_code) WHERE is_active = TRUE;
CREATE INDEX idx_dept_menu_roles_lookup ON dept_menu_roles(dept_id, menu_code) WHERE is_active = TRUE;

COMMENT ON TABLE user_menu_permissions IS '사용자별 메뉴 권한 (읽기/쓰기 레벨 분리)';
COMMENT ON TABLE dept_menu_roles IS '부서별 메뉴 권한 (읽기/쓰기 레벨 분리)';
COMMENT ON COLUMN user_menu_permissions.read_level IS '읽기 권한: 0-없음, 1-본인, 2-부서, 3-전체';
COMMENT ON COLUMN user_menu_permissions.write_level IS '쓰기 권한: 0-없음, 1-본인, 2-부서, 3-전체';
COMMENT ON COLUMN user_menu_permissions.can_delete IS '삭제 권한 (특별 관리)';