"""권한 관련 테이블과 인덱스를 안전하게 생성/보정하는 스크립트.

- 이미 존재하는 경우 DROP 하지 않고 필요한 컬럼만 추가합니다.
- user_menu_permissions / dept_menu_roles / permission_requests / menu_names /
  permission_access_log / permission_levels 테이블을 다룹니다.
- menu_names 에는 필수 메뉴명만 기본으로 채워 줍니다.

사용법: venv 활성화 후 `python scripts/setup_permission_schema.py`
"""
from __future__ import annotations

import logging
from typing import Iterable, Tuple

from db_connection import get_db_connection

CORE_MENU_NAMES = {
    "VENDOR_MGT": "협력사 기준정보",
    "REFERENCE_CHANGE": "기준정보 변경요청",
    "ACCIDENT_MGT": "협력사 사고",
    "SAFETY_INSTRUCTION": "환경안전 지시서",
    "FOLLOW_SOP": "Follow SOP",
    "SAFE_WORKPLACE": "안전한 일터",
    "FULL_PROCESS": "FullProcess",
    "SAFETY_COUNCIL": "안전보건 협의체",
}


def column_exists(cursor, table: str, column: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        """,
        (table, column),
    )
    return cursor.fetchone() is not None


def ensure_columns(cursor, table: str, columns: Iterable[Tuple[str, str]]) -> None:
    """Add columns that do not yet exist."""
    for column, definition in columns:
        if not column_exists(cursor, table, column):
            cursor.execute(f"ALTER TABLE {table} ADD COLUMN {definition}")


def ensure_table_user_permissions(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_menu_permissions (
            login_id VARCHAR(100) NOT NULL,
            menu_code VARCHAR(50) NOT NULL,
            read_level INTEGER DEFAULT 0,
            write_level INTEGER DEFAULT 0,
            can_delete BOOLEAN DEFAULT FALSE,
            granted_by VARCHAR(100),
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (login_id, menu_code)
        )
        """
    )

    ensure_columns(
        cursor,
        "user_menu_permissions",
        [
            ("can_delete", "BOOLEAN DEFAULT FALSE"),
            ("granted_by", "VARCHAR(100)"),
            ("granted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
        ],
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_lookup
        ON user_menu_permissions(login_id, menu_code)
        WHERE is_active = TRUE
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_menu_permissions_menu
        ON user_menu_permissions(menu_code)
        WHERE is_active = TRUE
        """
    )


def ensure_table_dept_roles(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS dept_menu_roles (
            dept_id VARCHAR(100) NOT NULL,
            dept_code VARCHAR(100),
            dept_full_path TEXT,
            menu_code VARCHAR(50) NOT NULL,
            read_level INTEGER DEFAULT 0,
            write_level INTEGER DEFAULT 0,
            can_delete BOOLEAN DEFAULT FALSE,
            granted_by VARCHAR(100),
            granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            PRIMARY KEY (dept_id, menu_code)
        )
        """
    )

    ensure_columns(
        cursor,
        "dept_menu_roles",
        [
            ("dept_code", "VARCHAR(100)"),
            ("dept_full_path", "TEXT"),
            ("can_delete", "BOOLEAN DEFAULT FALSE"),
            ("granted_by", "VARCHAR(100)"),
            ("granted_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("updated_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
        ],
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_lookup
        ON dept_menu_roles(dept_id, menu_code)
        WHERE is_active = TRUE
        """
    )

    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_dept_menu_roles_path
        ON dept_menu_roles(dept_full_path)
        """
    )


def ensure_table_permission_requests(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS permission_requests (
            id SERIAL PRIMARY KEY,
            login_id VARCHAR(100) NOT NULL,
            user_name VARCHAR(100),
            deptid VARCHAR(100),
            dept_name VARCHAR(100),
            menu_code VARCHAR(50) NOT NULL,
            menu_name VARCHAR(100),
            permission_type VARCHAR(20) NOT NULL,
            reason TEXT NOT NULL,
            status VARCHAR(20) DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_by VARCHAR(100),
            reviewed_at TIMESTAMP,
            review_comment TEXT,
            is_active BOOLEAN DEFAULT TRUE
        )
        """
    )

    ensure_columns(
        cursor,
        "permission_requests",
        [
            ("menu_name", "VARCHAR(100)"),
            ("review_comment", "TEXT"),
            ("is_active", "BOOLEAN DEFAULT TRUE"),
        ],
    )

    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_permission_requests_status ON permission_requests(status)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_permission_requests_login ON permission_requests(login_id)"
    )
    cursor.execute(
        "CREATE INDEX IF NOT EXISTS idx_permission_requests_created ON permission_requests(created_at DESC)"
    )


def ensure_table_menu_names(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS menu_names (
            menu_code VARCHAR(50) PRIMARY KEY,
            menu_name VARCHAR(100) NOT NULL,
            description TEXT
        )
        """
    )

    for code, name in CORE_MENU_NAMES.items():
        cursor.execute(
            """
            INSERT INTO menu_names (menu_code, menu_name)
            VALUES (%s, %s)
            ON CONFLICT (menu_code) DO UPDATE SET menu_name = EXCLUDED.menu_name
            """,
            (code, name),
        )


def ensure_table_permission_levels(cursor) -> None:
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS permission_levels (
            level_type VARCHAR(20) NOT NULL,
            level_value INTEGER NOT NULL,
            level_name VARCHAR(50),
            description TEXT,
            PRIMARY KEY (level_type, level_value)
        )
        """
    )

    rows = [
        ("read", 0, "권한없음", "해당 메뉴 접근 불가"),
        ("read", 1, "본인", "본인 관련 데이터 조회"),
        ("read", 2, "부서", "부서 관련 데이터 조회"),
        ("read", 3, "전체", "모든 데이터 조회"),
        ("write", 0, "권한없음", "등록/수정 불가"),
        ("write", 1, "본인", "본인 데이터만 수정"),
        ("write", 2, "부서", "부서 데이터 수정"),
        ("write", 3, "전체", "전체 데이터 수정"),
    ]
    cursor.executemany(
        """
        INSERT INTO permission_levels (level_type, level_value, level_name, description)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (level_type, level_value) DO UPDATE
        SET level_name = EXCLUDED.level_name,
            description = EXCLUDED.description
        """,
        rows,
    )


def ensure_table_access_log(cursor) -> None:
    cursor.execute(
        """
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
        )
        """
    )


def main() -> None:
    conn = get_db_connection()
    conn.autocommit = False
    cursor = conn.cursor()

    try:
        ensure_table_user_permissions(cursor)
        ensure_table_dept_roles(cursor)
        ensure_table_permission_requests(cursor)
        ensure_table_menu_names(cursor)
        ensure_table_permission_levels(cursor)
        ensure_table_access_log(cursor)

        conn.commit()
        print("✅ 권한 관련 테이블 점검 및 보정이 완료되었습니다.")
    except Exception as exc:
        conn.rollback()
        print(f"❌ 오류 발생: {exc}")
        raise
    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    main()
