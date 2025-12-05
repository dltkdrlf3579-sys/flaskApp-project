-- 통합 권한 체크 함수 (OR 연산)
-- 부서 권한과 개인 권한 중 더 높은 권한 반환

-- 1. 기본 권한 체크 함수
CREATE OR REPLACE FUNCTION check_combined_permission(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR,
    p_action VARCHAR
) RETURNS BOOLEAN AS $$
DECLARE
    personal_permission BOOLEAN := FALSE;
    dept_permission BOOLEAN := FALSE;
    has_higher_permission BOOLEAN := FALSE;
BEGIN
    -- 개인 권한 체크
    SELECT
        CASE p_action
            WHEN 'view' THEN can_view
            WHEN 'create' THEN can_create
            WHEN 'edit' THEN can_edit
            WHEN 'delete' THEN can_delete
            ELSE FALSE
        END INTO personal_permission
    FROM user_menu_permissions
    WHERE login_id = p_login_id
        AND menu_code = p_menu_code
        AND is_active = TRUE
    LIMIT 1;

    -- 부서 권한 체크
    SELECT
        CASE p_action
            WHEN 'view' THEN can_view
            WHEN 'create' THEN can_create
            WHEN 'edit' THEN can_edit
            WHEN 'delete' THEN can_delete
            ELSE FALSE
        END INTO dept_permission
    FROM dept_menu_roles
    WHERE dept_id = p_dept_id
        AND menu_code = p_menu_code
        AND is_active = TRUE
    LIMIT 1;

    -- view 권한 요청시 더 높은 권한이 있는지 체크
    IF p_action = 'view' AND NOT personal_permission AND NOT dept_permission THEN
        -- 개인 권한에서 더 높은 권한 체크
        SELECT (can_create OR can_edit OR can_delete) INTO has_higher_permission
        FROM user_menu_permissions
        WHERE login_id = p_login_id
            AND menu_code = p_menu_code
            AND is_active = TRUE
        LIMIT 1;

        IF has_higher_permission THEN
            RETURN TRUE;
        END IF;

        -- 부서 권한에서 더 높은 권한 체크
        SELECT (can_create OR can_edit OR can_delete) INTO has_higher_permission
        FROM dept_menu_roles
        WHERE dept_id = p_dept_id
            AND menu_code = p_menu_code
            AND is_active = TRUE
        LIMIT 1;

        IF has_higher_permission THEN
            RETURN TRUE;
        END IF;
    END IF;

    -- OR 연산으로 결과 반환
    RETURN COALESCE(personal_permission, FALSE) OR COALESCE(dept_permission, FALSE);
END;
$$ LANGUAGE plpgsql;

-- 2. 모든 권한 조회 함수
CREATE OR REPLACE FUNCTION get_combined_permissions(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR
) RETURNS TABLE(
    can_view BOOLEAN,
    can_create BOOLEAN,
    can_edit BOOLEAN,
    can_delete BOOLEAN,
    source TEXT
) AS $$
DECLARE
    personal_view BOOLEAN;
    personal_create BOOLEAN;
    personal_edit BOOLEAN;
    personal_delete BOOLEAN;
    dept_view BOOLEAN;
    dept_create BOOLEAN;
    dept_edit BOOLEAN;
    dept_delete BOOLEAN;
BEGIN
    -- 개인 권한 조회
    SELECT
        ump.can_view, ump.can_create, ump.can_edit, ump.can_delete
    INTO
        personal_view, personal_create, personal_edit, personal_delete
    FROM user_menu_permissions ump
    WHERE ump.login_id = p_login_id
        AND ump.menu_code = p_menu_code
        AND ump.is_active = TRUE
    LIMIT 1;

    -- 부서 권한 조회
    SELECT
        dmr.can_view, dmr.can_create, dmr.can_edit, dmr.can_delete
    INTO
        dept_view, dept_create, dept_edit, dept_delete
    FROM dept_menu_roles dmr
    WHERE dmr.dept_id = p_dept_id
        AND dmr.menu_code = p_menu_code
        AND dmr.is_active = TRUE
    LIMIT 1;

    -- OR 연산으로 통합 권한 반환
    RETURN QUERY
    SELECT
        COALESCE(personal_view, FALSE) OR COALESCE(dept_view, FALSE) AS can_view,
        COALESCE(personal_create, FALSE) OR COALESCE(dept_create, FALSE) AS can_create,
        COALESCE(personal_edit, FALSE) OR COALESCE(dept_edit, FALSE) AS can_edit,
        COALESCE(personal_delete, FALSE) OR COALESCE(dept_delete, FALSE) AS can_delete,
        CASE
            WHEN personal_view IS NOT NULL AND dept_view IS NOT NULL THEN 'both'
            WHEN personal_view IS NOT NULL THEN 'personal'
            WHEN dept_view IS NOT NULL THEN 'dept'
            ELSE 'none'
        END AS source;
END;
$$ LANGUAGE plpgsql;

-- 3. 사용자의 모든 메뉴 권한 조회
CREATE OR REPLACE FUNCTION get_user_all_menu_permissions(
    p_login_id VARCHAR,
    p_dept_id VARCHAR
) RETURNS TABLE(
    menu_code VARCHAR,
    can_view BOOLEAN,
    can_create BOOLEAN,
    can_edit BOOLEAN,
    can_delete BOOLEAN
) AS $$
BEGIN
    RETURN QUERY
    WITH all_menus AS (
        SELECT DISTINCT mc.menu_code
        FROM (
            SELECT menu_code FROM user_menu_permissions WHERE login_id = p_login_id AND is_active = TRUE
            UNION
            SELECT menu_code FROM dept_menu_roles WHERE dept_id = p_dept_id AND is_active = TRUE
        ) mc
    ),
    personal_perms AS (
        SELECT
            menu_code,
            can_view,
            can_create,
            can_edit,
            can_delete
        FROM user_menu_permissions
        WHERE login_id = p_login_id
            AND is_active = TRUE
    ),
    dept_perms AS (
        SELECT
            menu_code,
            can_view,
            can_create,
            can_edit,
            can_delete
        FROM dept_menu_roles
        WHERE dept_id = p_dept_id
            AND is_active = TRUE
    )
    SELECT
        am.menu_code,
        COALESCE(pp.can_view, FALSE) OR COALESCE(dp.can_view, FALSE) AS can_view,
        COALESCE(pp.can_create, FALSE) OR COALESCE(dp.can_create, FALSE) AS can_create,
        COALESCE(pp.can_edit, FALSE) OR COALESCE(dp.can_edit, FALSE) AS can_edit,
        COALESCE(pp.can_delete, FALSE) OR COALESCE(dp.can_delete, FALSE) AS can_delete
    FROM all_menus am
    LEFT JOIN personal_perms pp ON am.menu_code = pp.menu_code
    LEFT JOIN dept_perms dp ON am.menu_code = dp.menu_code;
END;
$$ LANGUAGE plpgsql;

-- 4. 삭제 권한 체크 (가장 많이 사용)
CREATE OR REPLACE FUNCTION can_user_delete(
    p_login_id VARCHAR,
    p_dept_id VARCHAR,
    p_menu_code VARCHAR
) RETURNS BOOLEAN AS $$
BEGIN
    RETURN check_combined_permission(p_login_id, p_dept_id, p_menu_code, 'delete');
END;
$$ LANGUAGE plpgsql;

-- 함수 설명 추가
COMMENT ON FUNCTION check_combined_permission IS 'Check permission using OR logic between personal and department permissions';
COMMENT ON FUNCTION get_combined_permissions IS 'Get all permissions for a menu with source information';
COMMENT ON FUNCTION get_user_all_menu_permissions IS 'Get all menu permissions for a user (personal OR department)';
COMMENT ON FUNCTION can_user_delete IS 'Quick check for delete permission';