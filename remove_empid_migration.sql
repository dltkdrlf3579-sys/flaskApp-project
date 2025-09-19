-- Migration script to remove emp_id and use login_id as primary identifier
-- Knox ID will be used as the external identifier from SSO

-- 1. Update user_menu_permissions table
ALTER TABLE user_menu_permissions
DROP CONSTRAINT IF EXISTS user_menu_permissions_pkey CASCADE;

ALTER TABLE user_menu_permissions
DROP CONSTRAINT IF EXISTS user_menu_permissions_emp_id_menu_code_key CASCADE;

-- Remove emp_id column and make login_id the primary key
ALTER TABLE user_menu_permissions
DROP COLUMN IF EXISTS emp_id CASCADE;

ALTER TABLE user_menu_permissions
ADD CONSTRAINT user_menu_permissions_pkey PRIMARY KEY (login_id, menu_code);

-- 2. Update user_role_mapping table
ALTER TABLE user_role_mapping
DROP CONSTRAINT IF EXISTS user_role_mapping_pkey CASCADE;

ALTER TABLE user_role_mapping
DROP CONSTRAINT IF EXISTS user_role_mapping_emp_id_role_code_key CASCADE;

ALTER TABLE user_role_mapping
DROP COLUMN IF EXISTS emp_id CASCADE;

ALTER TABLE user_role_mapping
ADD CONSTRAINT user_role_mapping_pkey PRIMARY KEY (login_id, role_code);

-- 3. Update user_menu_roles table
ALTER TABLE user_menu_roles
DROP CONSTRAINT IF EXISTS user_menu_roles_pkey CASCADE;

ALTER TABLE user_menu_roles
DROP CONSTRAINT IF EXISTS user_menu_roles_emp_id_menu_code_key CASCADE;

ALTER TABLE user_menu_roles
DROP COLUMN IF EXISTS emp_id CASCADE;

ALTER TABLE user_menu_roles
ADD CONSTRAINT user_menu_roles_pkey PRIMARY KEY (login_id, menu_code);

-- 4. Update system_users table (keep emp_id for now but not as identifier)
ALTER TABLE system_users
DROP CONSTRAINT IF EXISTS system_users_pkey CASCADE;

ALTER TABLE system_users
ADD CONSTRAINT system_users_pkey PRIMARY KEY (login_id);

-- Add knox_id column for SSO integration
ALTER TABLE system_users
ADD COLUMN IF NOT EXISTS knox_id VARCHAR(100) UNIQUE;

-- Copy login_id to knox_id initially
UPDATE system_users SET knox_id = login_id WHERE knox_id IS NULL;

-- 5. Create index for performance
CREATE INDEX IF NOT EXISTS idx_system_users_knox_id ON system_users(knox_id);
CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_login_id ON user_menu_permissions(login_id);
CREATE INDEX IF NOT EXISTS idx_user_role_mapping_login_id ON user_role_mapping(login_id);
CREATE INDEX IF NOT EXISTS idx_user_menu_roles_login_id ON user_menu_roles(login_id);

-- 6. Update functions to use login_id
CREATE OR REPLACE FUNCTION check_user_permission(
    p_login_id VARCHAR,
    p_menu_code VARCHAR,
    p_action VARCHAR
) RETURNS BOOLEAN AS $$
DECLARE
    has_permission BOOLEAN := FALSE;
BEGIN
    SELECT
        CASE p_action
            WHEN 'view' THEN can_view
            WHEN 'create' THEN can_create
            WHEN 'edit' THEN can_edit
            WHEN 'delete' THEN can_delete
            ELSE FALSE
        END INTO has_permission
    FROM user_menu_permissions
    WHERE login_id = p_login_id
        AND menu_code = p_menu_code
        AND is_active = TRUE
    LIMIT 1;

    RETURN COALESCE(has_permission, FALSE);
END;
$$ LANGUAGE plpgsql;

-- 7. Function to get user by Knox ID
CREATE OR REPLACE FUNCTION get_user_by_knox_id(
    p_knox_id VARCHAR
) RETURNS TABLE(
    login_id VARCHAR,
    name VARCHAR,
    dept_code VARCHAR,
    position VARCHAR
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        u.login_id,
        u.name,
        u.dept_code,
        u.position
    FROM system_users u
    WHERE u.knox_id = p_knox_id
        AND u.is_active = TRUE
    LIMIT 1;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION check_user_permission IS 'Check user permission using login_id as primary identifier';
COMMENT ON FUNCTION get_user_by_knox_id IS 'Get user information by Knox ID (SSO identifier)';
COMMENT ON COLUMN system_users.knox_id IS 'Knox SSO system identifier';
COMMENT ON COLUMN system_users.login_id IS 'Primary identifier for internal system';