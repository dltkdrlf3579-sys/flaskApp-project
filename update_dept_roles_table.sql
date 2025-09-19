-- 부서 권한 테이블에 deptid와 dept_full_path 컬럼 추가
-- deptid: SSO 인증에서 받는 부서 ID
-- dept_full_path: 부서 계층 구조를 파이프(|)로 구분한 경로

-- 1. dept_menu_roles 테이블에 컬럼 추가 (없으면 생성)
CREATE TABLE IF NOT EXISTS dept_menu_roles (
    id SERIAL PRIMARY KEY,
    dept_id VARCHAR(50) NOT NULL,           -- SSO에서 받는 deptid
    dept_code VARCHAR(100) NOT NULL,        -- 부서 코드
    dept_full_path TEXT,                    -- 전체 부서 경로 (예: D001|D001-1|D001-1-1)
    menu_code VARCHAR(100) NOT NULL,
    role_for_menu VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_by VARCHAR(50),
    updated_by VARCHAR(50),
    UNIQUE(dept_id, menu_code)
);

-- 2. 인덱스 생성 (검색 성능 최적화)
CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_dept_id ON dept_menu_roles(dept_id);
CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_dept_code ON dept_menu_roles(dept_code);
CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_menu_code ON dept_menu_roles(menu_code);
CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_full_path ON dept_menu_roles(dept_full_path);

-- 3. departments 테이블 (외부 연동용)
CREATE TABLE IF NOT EXISTS departments_external (
    dept_id VARCHAR(50) PRIMARY KEY,        -- SSO deptid
    dept_code VARCHAR(100) NOT NULL UNIQUE, -- 부서 코드
    dept_name VARCHAR(200) NOT NULL,        -- 부서명
    parent_dept_code VARCHAR(100),          -- 상위 부서 코드
    dept_full_path TEXT,                    -- 전체 경로
    dept_level INTEGER,                     -- 부서 레벨 (1: 부문, 2: 사업부, 3: 센터, 4: 팀, 5: 그룹)
    is_active BOOLEAN DEFAULT true,
    last_sync_at TIMESTAMP                  -- 외부 시스템과 마지막 동기화 시간
);

-- 4. deptid와 dept_code 매핑 뷰
CREATE OR REPLACE VIEW v_dept_mapping AS
SELECT
    d.dept_id,
    d.dept_code,
    d.dept_name,
    d.dept_full_path,
    d.dept_level,
    CASE
        WHEN d.dept_full_path IS NOT NULL THEN
            string_to_array(d.dept_full_path, '|')
    END as path_array,
    CASE
        WHEN d.dept_full_path IS NOT NULL THEN
            split_part(d.dept_full_path, '|', -1)  -- 마지막 요소 = 현재 부서 코드
    END as current_dept_code
FROM departments_external d
WHERE d.is_active = true;

-- 5. 하위 부서 조회 함수
CREATE OR REPLACE FUNCTION get_child_departments(p_dept_code VARCHAR)
RETURNS TABLE (
    dept_id VARCHAR,
    dept_code VARCHAR,
    dept_name VARCHAR,
    dept_level INTEGER
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        d.dept_id,
        d.dept_code,
        d.dept_name,
        d.dept_level
    FROM departments_external d
    WHERE d.dept_full_path LIKE '%' || p_dept_code || '%'
      AND d.is_active = true;
END;
$$ LANGUAGE plpgsql;

-- 6. SSO deptid로 권한 조회 함수
CREATE OR REPLACE FUNCTION get_user_permissions_by_sso(p_sso_dept_id VARCHAR, p_emp_id VARCHAR)
RETURNS TABLE (
    menu_code VARCHAR,
    role_for_menu VARCHAR,
    permission_source VARCHAR  -- 'personal', 'dept_direct', 'dept_inherited'
) AS $$
BEGIN
    RETURN QUERY
    WITH user_dept AS (
        -- SSO deptid로 부서 정보 조회
        SELECT dept_code, dept_full_path
        FROM departments_external
        WHERE dept_id = p_sso_dept_id
        LIMIT 1
    ),
    dept_hierarchy AS (
        -- dept_full_path에서 모든 상위 부서 코드 추출
        SELECT unnest(string_to_array(dept_full_path, '|')) as dept_code
        FROM user_dept
    )
    SELECT
        COALESCE(u.menu_code, d.menu_code) as menu_code,
        COALESCE(u.role_for_menu, d.role_for_menu) as role_for_menu,
        CASE
            WHEN u.menu_code IS NOT NULL THEN 'personal'
            WHEN d.dept_code = (SELECT dept_code FROM user_dept) THEN 'dept_direct'
            ELSE 'dept_inherited'
        END as permission_source
    FROM (
        -- 부서 권한 (상위 부서 포함)
        SELECT DISTINCT ON (menu_code)
            menu_code,
            role_for_menu,
            dept_code,
            CASE
                WHEN dept_code = (SELECT dept_code FROM user_dept) THEN 1
                ELSE 2
            END as priority
        FROM dept_menu_roles
        WHERE dept_code IN (SELECT dept_code FROM dept_hierarchy)
          AND is_active = true
        ORDER BY menu_code, priority, updated_at DESC
    ) d
    FULL OUTER JOIN (
        -- 개인 권한
        SELECT menu_code, role_for_menu
        FROM user_menu_roles
        WHERE emp_id = p_emp_id
          AND is_active = true
    ) u ON d.menu_code = u.menu_code;
END;
$$ LANGUAGE plpgsql;

-- 7. 하위 부서에 권한 전파 함수
CREATE OR REPLACE FUNCTION propagate_dept_permissions(p_dept_code VARCHAR)
RETURNS INTEGER AS $$
DECLARE
    affected_count INTEGER := 0;
    parent_permissions RECORD;
    child_dept RECORD;
BEGIN
    -- 부모 부서의 권한 조회
    FOR parent_permissions IN
        SELECT menu_code, role_for_menu
        FROM dept_menu_roles
        WHERE dept_code = p_dept_code
          AND is_active = true
    LOOP
        -- 모든 하위 부서에 권한 적용
        FOR child_dept IN
            SELECT dept_id, dept_code
            FROM departments_external
            WHERE dept_full_path LIKE '%' || p_dept_code || '|%'
              AND is_active = true
        LOOP
            -- UPSERT: 있으면 업데이트, 없으면 삽입
            INSERT INTO dept_menu_roles (dept_id, dept_code, menu_code, role_for_menu)
            VALUES (child_dept.dept_id, child_dept.dept_code, parent_permissions.menu_code, parent_permissions.role_for_menu)
            ON CONFLICT (dept_id, menu_code)
            DO UPDATE SET
                role_for_menu = EXCLUDED.role_for_menu,
                updated_at = CURRENT_TIMESTAMP;

            affected_count := affected_count + 1;
        END LOOP;
    END LOOP;

    RETURN affected_count;
END;
$$ LANGUAGE plpgsql;

-- 8. 샘플 데이터 (테스트용)
INSERT INTO departments_external (dept_id, dept_code, dept_name, parent_dept_code, dept_full_path, dept_level)
VALUES
    ('DID001', 'D001', '제조본부', NULL, 'D001', 1),
    ('DID001-1', 'D001-1', '제1공장', 'D001', 'D001|D001-1', 2),
    ('DID001-1-1', 'D001-1-1', '생산1팀', 'D001-1', 'D001|D001-1|D001-1-1', 3),
    ('DID001-1-2', 'D001-1-2', '생산2팀', 'D001-1', 'D001|D001-1|D001-1-2', 3),
    ('DID002', 'D002', '경영지원본부', NULL, 'D002', 1),
    ('DID002-1', 'D002-1', '안전환경실', 'D002', 'D002|D002-1', 2),
    ('DID002-1-1', 'D002-1-1', '환경안전팀', 'D002-1', 'D002|D002-1|D002-1-1', 3)
ON CONFLICT (dept_id) DO NOTHING;