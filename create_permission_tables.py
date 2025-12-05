"""
권한 시스템 Day 1 - PostgreSQL 테이블 생성 및 기본 데이터 설정
"""
import psycopg2
from psycopg2 import sql
import configparser
import logging
from datetime import datetime

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_connection():
    """PostgreSQL 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    dsn = config.get('DATABASE', 'postgres_dsn')
    return psycopg2.connect(dsn)

def create_permission_tables():
    """권한 관련 테이블 생성"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        logger.info("권한 시스템 테이블 생성 시작...")

        # 1. system_users 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_users (
                emp_id VARCHAR(50) PRIMARY KEY,
                login_id VARCHAR(100) NOT NULL,
                user_name VARCHAR(100),
                dept_id VARCHAR(50),
                dept_name VARCHAR(200),
                company_id VARCHAR(50),
                email VARCHAR(200),
                is_active BOOLEAN DEFAULT TRUE,
                last_login_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_users_login_id ON system_users(login_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_users_dept_id ON system_users(dept_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_system_users_company_id ON system_users(company_id)")

        logger.info("✓ system_users 테이블 생성 완료")

        # 2. system_roles 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_roles (
                role_code VARCHAR(20) PRIMARY KEY,
                role_name VARCHAR(100) NOT NULL,
                role_level INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        logger.info("✓ system_roles 테이블 생성 완료")

        # 3. user_role_mapping 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_role_mapping (
                id SERIAL PRIMARY KEY,
                emp_id VARCHAR(50) NOT NULL,
                role_code VARCHAR(20) NOT NULL,
                assigned_by VARCHAR(50),
                assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                UNIQUE(emp_id, role_code),
                FOREIGN KEY (emp_id) REFERENCES system_users(emp_id) ON DELETE CASCADE,
                FOREIGN KEY (role_code) REFERENCES system_roles(role_code) ON DELETE CASCADE
            )
        """)
        logger.info("✓ user_role_mapping 테이블 생성 완료")

        # 4. menu_registry 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS menu_registry (
                menu_code VARCHAR(50) PRIMARY KEY,
                menu_name VARCHAR(100) NOT NULL,
                menu_path VARCHAR(200),
                display_order INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        """)
        logger.info("✓ menu_registry 테이블 생성 완료")

        # 5. role_menu_permissions 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS role_menu_permissions (
                id SERIAL PRIMARY KEY,
                role_code VARCHAR(20) NOT NULL,
                menu_code VARCHAR(50) NOT NULL,
                can_view BOOLEAN DEFAULT FALSE,
                can_create BOOLEAN DEFAULT FALSE,
                can_edit BOOLEAN DEFAULT FALSE,
                can_delete BOOLEAN DEFAULT FALSE,
                data_scope VARCHAR(20) DEFAULT 'own',
                UNIQUE(role_code, menu_code),
                FOREIGN KEY (role_code) REFERENCES system_roles(role_code) ON DELETE CASCADE,
                FOREIGN KEY (menu_code) REFERENCES menu_registry(menu_code) ON DELETE CASCADE
            )
        """)
        logger.info("✓ role_menu_permissions 테이블 생성 완료")

        # 추가 테이블: 부서 계층 (대기업용)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS department_hierarchy (
                dept_id VARCHAR(50) PRIMARY KEY,
                dept_name VARCHAR(200) NOT NULL,
                parent_dept_id VARCHAR(50),
                dept_level INTEGER NOT NULL,
                dept_path VARCHAR(500),
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (parent_dept_id) REFERENCES department_hierarchy(dept_id)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_parent ON department_hierarchy(parent_dept_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_path ON department_hierarchy(dept_path)")
        logger.info("✓ department_hierarchy 테이블 생성 완료")

        # 권한 캐시 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_cache (
                emp_id VARCHAR(50),
                menu_code VARCHAR(50),
                permissions_json JSONB,
                cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP,
                PRIMARY KEY (emp_id, menu_code)
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_cache_expires ON permission_cache(expires_at)")
        logger.info("✓ permission_cache 테이블 생성 완료")

        # 접근 로그 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS access_audit_log (
                id SERIAL PRIMARY KEY,
                emp_id VARCHAR(50),
                login_id VARCHAR(100),
                action VARCHAR(50),
                menu_code VARCHAR(50),
                resource_id VARCHAR(100),
                ip_address VARCHAR(45),
                success BOOLEAN DEFAULT TRUE,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_uid_created ON access_audit_log(emp_id, created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action_created ON access_audit_log(action, created_at)")
        logger.info("✓ access_audit_log 테이블 생성 완료")

        conn.commit()
        logger.info("모든 테이블 생성 완료!")

    except Exception as e:
        conn.rollback()
        logger.error(f"테이블 생성 중 오류: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def insert_base_data():
    """기본 역할 및 메뉴 데이터 입력"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        logger.info("기본 데이터 입력 시작...")

        # 기본 역할 입력
        cursor.execute("""
            INSERT INTO system_roles (role_code, role_name, role_level)
            VALUES
                ('super_admin', '슈퍼 관리자', 1000),
                ('admin', '관리자', 100),
                ('manager', '팀장', 70),
                ('user', '일반 사용자', 50),
                ('partner', '협력사', 30),
                ('viewer', '조회 전용', 10)
            ON CONFLICT (role_code) DO UPDATE
            SET role_name = EXCLUDED.role_name,
                role_level = EXCLUDED.role_level
        """)
        logger.info("✓ 기본 역할 데이터 입력 완료")

        # 메뉴 등록
        cursor.execute("""
            INSERT INTO menu_registry (menu_code, menu_name, menu_path, display_order)
            VALUES
                ('accident', '사고 관리', '/accidents', 10),
                ('safety_instruction', '안전지시서', '/safety-instructions', 20),
                ('follow_sop', 'Follow SOP', '/follow-sop', 30),
                ('full_process', 'Full Process', '/full-process', 40),
                ('partners', '협력사 관리', '/partners', 50),
                ('permission_admin', '권한 관리', '/admin/permissions', 100)
            ON CONFLICT (menu_code) DO UPDATE
            SET menu_name = EXCLUDED.menu_name,
                menu_path = EXCLUDED.menu_path,
                display_order = EXCLUDED.display_order
        """)
        logger.info("✓ 메뉴 등록 완료")

        # Super Admin - 모든 권한
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            SELECT 'super_admin', menu_code, TRUE, TRUE, TRUE, TRUE, 'all'
            FROM menu_registry
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = TRUE, can_create = TRUE, can_edit = TRUE, can_delete = TRUE, data_scope = 'all'
        """)

        # Admin - 권한 관리 제외한 모든 권한
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            SELECT 'admin', menu_code, TRUE, TRUE, TRUE, TRUE, 'all'
            FROM menu_registry
            WHERE menu_code != 'permission_admin'
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = TRUE, can_create = TRUE, can_edit = TRUE, can_delete = TRUE, data_scope = 'all'
        """)

        # Manager - 부서 데이터 권한
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            VALUES
                ('manager', 'accident', TRUE, TRUE, TRUE, TRUE, 'dept'),
                ('manager', 'safety_instruction', TRUE, TRUE, TRUE, FALSE, 'dept'),
                ('manager', 'follow_sop', TRUE, TRUE, TRUE, FALSE, 'dept'),
                ('manager', 'full_process', TRUE, TRUE, TRUE, FALSE, 'dept'),
                ('manager', 'partners', TRUE, FALSE, FALSE, FALSE, 'all')
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                data_scope = EXCLUDED.data_scope
        """)

        # User - 제한적 권한
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            VALUES
                ('user', 'accident', TRUE, TRUE, TRUE, FALSE, 'own'),
                ('user', 'safety_instruction', TRUE, TRUE, TRUE, FALSE, 'own'),
                ('user', 'follow_sop', TRUE, TRUE, TRUE, FALSE, 'own'),
                ('user', 'full_process', TRUE, TRUE, TRUE, FALSE, 'own'),
                ('user', 'partners', TRUE, FALSE, FALSE, FALSE, 'all')
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                data_scope = EXCLUDED.data_scope
        """)

        # Partner - 협력사 권한
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            VALUES
                ('partner', 'accident', TRUE, FALSE, FALSE, FALSE, 'company'),
                ('partner', 'safety_instruction', TRUE, FALSE, FALSE, FALSE, 'company'),
                ('partner', 'partners', TRUE, FALSE, TRUE, FALSE, 'own')
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                data_scope = EXCLUDED.data_scope
        """)

        # Viewer - 읽기 전용
        cursor.execute("""
            INSERT INTO role_menu_permissions
            (role_code, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            SELECT 'viewer', menu_code, TRUE, FALSE, FALSE, FALSE, 'all'
            FROM menu_registry
            WHERE menu_code != 'permission_admin'
            ON CONFLICT (role_code, menu_code) DO UPDATE
            SET can_view = TRUE, can_create = FALSE, can_edit = FALSE, can_delete = FALSE
        """)

        logger.info("✓ 역할별 권한 설정 완료")

        conn.commit()
        logger.info("기본 데이터 입력 완료!")

    except Exception as e:
        conn.rollback()
        logger.error(f"데이터 입력 중 오류: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def migrate_existing_users():
    """기존 사용자 데이터 마이그레이션"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        logger.info("기존 사용자 마이그레이션 시작...")

        # 모든 테이블에서 created_by/modified_by 사용자 추출
        cursor.execute("""
            INSERT INTO system_users (emp_id, login_id, user_name, is_active)
            SELECT DISTINCT
                COALESCE(created_by, modified_by) as emp_id,
                COALESCE(created_by, modified_by) as login_id,
                COALESCE(created_by, modified_by) as user_name,
                TRUE
            FROM (
                SELECT created_by FROM accidents_cache WHERE created_by IS NOT NULL
                UNION
                SELECT modified_by FROM accidents_cache WHERE modified_by IS NOT NULL
                UNION
                SELECT created_by FROM safety_instructions WHERE created_by IS NOT NULL
                UNION
                SELECT updated_by FROM safety_instructions WHERE updated_by IS NOT NULL
                UNION
                SELECT created_by FROM change_requests WHERE created_by IS NOT NULL
                UNION
                SELECT modified_by FROM change_requests WHERE modified_by IS NOT NULL
            ) users
            WHERE COALESCE(created_by, modified_by) IS NOT NULL
            AND COALESCE(created_by, modified_by) != ''
            ON CONFLICT (emp_id) DO NOTHING
        """)

        migrated = cursor.rowcount
        logger.info(f"✓ {migrated}명의 기존 사용자 마이그레이션 완료")

        # 기본 역할(user) 할당
        cursor.execute("""
            INSERT INTO user_role_mapping (emp_id, role_code)
            SELECT emp_id, 'user'
            FROM system_users
            WHERE emp_id NOT IN (
                SELECT emp_id FROM user_role_mapping
            )
        """)

        assigned = cursor.rowcount
        logger.info(f"✓ {assigned}명에게 기본 역할(user) 할당 완료")

        # 테스트용 관리자 계정 생성
        cursor.execute("""
            INSERT INTO system_users (emp_id, login_id, user_name, email, is_active)
            VALUES
                ('admin', 'admin', '시스템 관리자', 'admin@company.com', TRUE),
                ('test_user', 'test_user', '테스트 사용자', 'test@company.com', TRUE),
                ('test_partner', 'test_partner', '테스트 협력사', 'partner@company.com', TRUE)
            ON CONFLICT (emp_id) DO UPDATE
            SET user_name = EXCLUDED.user_name,
                email = EXCLUDED.email
        """)

        # 테스트 계정 역할 할당
        cursor.execute("""
            INSERT INTO user_role_mapping (emp_id, role_code)
            VALUES
                ('admin', 'super_admin'),
                ('test_user', 'user'),
                ('test_partner', 'partner')
            ON CONFLICT (emp_id, role_code) DO NOTHING
        """)

        logger.info("✓ 테스트 계정 생성 완료")

        conn.commit()
        logger.info("사용자 마이그레이션 완료!")

    except Exception as e:
        conn.rollback()
        logger.error(f"마이그레이션 중 오류: {e}")
        raise
    finally:
        cursor.close()
        conn.close()

def verify_installation():
    """설치 검증"""
    conn = get_connection()
    cursor = conn.cursor()

    try:
        logger.info("\n=== 설치 검증 시작 ===")

        # 테이블 확인
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN (
                'system_users', 'system_roles', 'user_role_mapping',
                'menu_registry', 'role_menu_permissions',
                'department_hierarchy', 'permission_cache', 'access_audit_log'
            )
            ORDER BY table_name
        """)

        tables = cursor.fetchall()
        logger.info(f"생성된 테이블 ({len(tables)}/8):")
        for table in tables:
            logger.info(f"  - {table[0]}")

        # 데이터 확인
        cursor.execute("SELECT COUNT(*) FROM system_roles")
        role_count = cursor.fetchone()[0]
        logger.info(f"역할: {role_count}개")

        cursor.execute("SELECT COUNT(*) FROM menu_registry")
        menu_count = cursor.fetchone()[0]
        logger.info(f"메뉴: {menu_count}개")

        cursor.execute("SELECT COUNT(*) FROM system_users")
        user_count = cursor.fetchone()[0]
        logger.info(f"사용자: {user_count}명")

        cursor.execute("SELECT COUNT(*) FROM role_menu_permissions")
        perm_count = cursor.fetchone()[0]
        logger.info(f"권한 설정: {perm_count}개")

        # 샘플 권한 조회
        cursor.execute("""
            SELECT r.role_name, m.menu_name, p.can_view, p.can_create, p.can_edit, p.can_delete, p.data_scope
            FROM role_menu_permissions p
            JOIN system_roles r ON p.role_code = r.role_code
            JOIN menu_registry m ON p.menu_code = m.menu_code
            WHERE r.role_code IN ('admin', 'user')
            AND m.menu_code = 'accident'
            ORDER BY r.role_level DESC
        """)

        logger.info("\n사고 관리 메뉴 권한 샘플:")
        for row in cursor.fetchall():
            logger.info(f"  {row[0]}: 조회={row[2]}, 생성={row[3]}, 수정={row[4]}, 삭제={row[5]}, 범위={row[6]}")

        logger.info("\n✅ 권한 시스템 Day 1 설치 완료!")

    except Exception as e:
        logger.error(f"검증 중 오류: {e}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    try:
        # 1. 테이블 생성
        create_permission_tables()

        # 2. 기본 데이터 입력
        insert_base_data()

        # 3. 기존 사용자 마이그레이션
        migrate_existing_users()

        # 4. 설치 검증
        verify_installation()

    except Exception as e:
        logger.error(f"설치 실패: {e}")
        exit(1)