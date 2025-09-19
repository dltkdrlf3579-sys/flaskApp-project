"""
권한 테이블 생성 및 초기화
"""
from db_connection import get_db_connection

def init_permission_tables():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 기존 테이블 삭제
        cursor.execute("DROP TABLE IF EXISTS user_menu_permissions CASCADE")
        cursor.execute("DROP TABLE IF EXISTS dept_menu_permissions CASCADE")
        cursor.execute("DROP TABLE IF EXISTS permission_access_log CASCADE")

        # user_menu_permissions 테이블 생성
        cursor.execute("""
            CREATE TABLE user_menu_permissions (
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
            )
        """)

        # dept_menu_permissions 테이블 생성
        cursor.execute("""
            CREATE TABLE dept_menu_permissions (
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
            )
        """)

        # permission_access_log 테이블 생성
        cursor.execute("""
            CREATE TABLE permission_access_log (
                id SERIAL PRIMARY KEY,
                login_id VARCHAR(100),
                menu_code VARCHAR(50),
                action VARCHAR(20),
                success BOOLEAN,
                reason TEXT,
                ip_address VARCHAR(45),
                user_agent TEXT,
                accessed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # 인덱스 생성
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_login_id ON user_menu_permissions(login_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_menu_code ON user_menu_permissions(menu_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_menu_permissions_dept_id ON dept_menu_permissions(dept_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_dept_menu_permissions_menu_code ON dept_menu_permissions(menu_code)")

        conn.commit()
        print("권한 테이블 생성 완료")

        # 테스트 데이터 추가
        test_users = [
            ('test_admin', [
                ('VENDOR_MGT', 3, 3),
                ('REFERENCE_CHANGE', 3, 3),
                ('ACCIDENT_MGT', 3, 3),
                ('SAFETY_INSTRUCTION', 3, 3),
                ('FOLLOW_SOP', 3, 3),
                ('FULL_PROCESS', 3, 3),
                ('CORRECTIVE_ACTION', 3, 3),
            ]),
            ('test_manager', [
                ('VENDOR_MGT', 2, 2),
                ('REFERENCE_CHANGE', 2, 1),
                ('ACCIDENT_MGT', 3, 2),
                ('SAFETY_INSTRUCTION', 2, 2),
                ('FOLLOW_SOP', 2, 1),
                ('CORRECTIVE_ACTION', 2, 2),
            ]),
            ('test_user', [
                ('VENDOR_MGT', 1, 0),
                ('REFERENCE_CHANGE', 1, 1),
                ('ACCIDENT_MGT', 2, 1),
                ('SAFETY_INSTRUCTION', 1, 0),
                ('CORRECTIVE_ACTION', 1, 1),
            ]),
            ('test_readonly', [
                ('VENDOR_MGT', 3, 0),
                ('REFERENCE_CHANGE', 3, 0),
                ('ACCIDENT_MGT', 3, 0),
                ('SAFETY_INSTRUCTION', 3, 0),
                ('FOLLOW_SOP', 3, 0),
                ('FULL_PROCESS', 3, 0),
                ('CORRECTIVE_ACTION', 3, 0),
            ])
        ]

        for login_id, permissions in test_users:
            for menu_code, read_level, write_level in permissions:
                cursor.execute("""
                    INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, is_active)
                    VALUES (%s, %s, %s, %s, true)
                """, (login_id, menu_code, read_level, write_level))

        conn.commit()
        print("테스트 데이터 추가 완료")

        # 결과 확인
        cursor.execute("""
            SELECT login_id, COUNT(*) as perm_count
            FROM user_menu_permissions
            WHERE is_active = true
            GROUP BY login_id
            ORDER BY login_id
        """)

        print("\n권한 설정 현황:")
        for row in cursor.fetchall():
            print(f"  - {row[0]}: {row[1]}개 메뉴 권한")

    except Exception as e:
        print(f"오류 발생: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    init_permission_tables()