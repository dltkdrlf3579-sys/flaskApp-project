#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
부서 계층 권한 상속 구현
Recursive CTE를 활용한 계층적 권한 관리
"""

import psycopg2
import configparser
import logging
import json
from datetime import datetime

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_connection():
    """데이터베이스 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    if config.has_option('DATABASE', 'postgres_dsn'):
        dsn = config.get('DATABASE', 'postgres_dsn')
        return psycopg2.connect(dsn)
    else:
        logger.error("PostgreSQL DSN이 설정되지 않았습니다.")
        raise Exception("PostgreSQL DSN not configured")

def setup_dept_hierarchy():
    """부서 계층 구조 설정"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        logger.info("부서 계층 구조 설정 시작...")

        # 샘플 부서 계층 구조
        dept_hierarchy = [
            ('COMP01', None, '본사', 1),
            ('DEPT_CEO', 'COMP01', '경영진', 2),
            ('DEPT_IT', 'COMP01', 'IT부서', 2),
            ('DEPT_IT_DEV', 'DEPT_IT', '개발팀', 3),
            ('DEPT_IT_OPS', 'DEPT_IT', '운영팀', 3),
            ('DEPT_HR', 'COMP01', '인사부서', 2),
            ('DEPT_QA', 'COMP01', '품질관리부서', 2),
            ('DEPT_EXT', 'COMP01', '외부협력사', 2),
        ]

        for dept_id, parent_id, dept_name, level in dept_hierarchy:
            cursor.execute("""
                INSERT INTO department_hierarchy
                (dept_id, parent_dept_id, dept_name, dept_level)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (dept_id) DO UPDATE SET
                    parent_dept_id = EXCLUDED.parent_dept_id,
                    dept_name = EXCLUDED.dept_name,
                    dept_level = EXCLUDED.dept_level
            """, (dept_id, parent_id, dept_name, level))

        conn.commit()
        logger.info(f"✓ {len(dept_hierarchy)}개 부서 계층 구조 설정")

        # 권한 상속 설정
        cursor.execute("""
            INSERT INTO dept_permission_inheritance
            (dept_id, inherit_from_parent, inherit_to_children)
            SELECT dept_id, TRUE, TRUE
            FROM department_hierarchy
            ON CONFLICT (dept_id) DO NOTHING
        """)

        # 특별 설정: 외부협력사는 상속 비활성화
        cursor.execute("""
            UPDATE dept_permission_inheritance
            SET inherit_from_parent = FALSE,
                inherit_to_children = FALSE
            WHERE dept_id = 'DEPT_EXT'
        """)

        conn.commit()
        logger.info("✓ 부서 권한 상속 설정 완료")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"부서 계층 설정 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_dept_permissions_with_inheritance(emp_id, menu_code):
    """부서 권한 상속 포함 조회"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Recursive CTE로 부서 계층 조회
        cursor.execute("""
            WITH RECURSIVE dept_tree AS (
                -- 사용자의 직접 부서
                SELECT d.dept_id, d.parent_dept_id, d.dept_level, 0 as distance
                FROM department_hierarchy d
                JOIN system_users u ON d.dept_id = u.dept_id
                WHERE u.emp_id = %s

                UNION ALL

                -- 상위 부서들 (권한 상속이 활성화된 경우)
                SELECT p.dept_id, p.parent_dept_id, p.dept_level, dt.distance + 1
                FROM department_hierarchy p
                JOIN dept_tree dt ON p.dept_id = dt.parent_dept_id
                JOIN dept_permission_inheritance dpi ON p.dept_id = dpi.dept_id
                WHERE dpi.inherit_to_children = TRUE
            )
            SELECT DISTINCT
                dmp.dept_id,
                dmp.can_view,
                dmp.can_create,
                dmp.can_edit,
                dmp.can_delete,
                dmp.data_scope,
                dt.distance
            FROM dept_tree dt
            JOIN dept_menu_permissions dmp ON dt.dept_id = dmp.dept_id
            WHERE dmp.menu_code = %s
            ORDER BY dt.distance  -- 가장 가까운 부서 권한 우선
            LIMIT 1
        """, (emp_id, menu_code))

        result = cursor.fetchone()

        if result:
            logger.info(f"부서 권한 찾음: {emp_id} -> {menu_code} (거리: {result[6]})")
            return {
                'dept_id': result[0],
                'can_view': result[1],
                'can_create': result[2],
                'can_edit': result[3],
                'can_delete': result[4],
                'data_scope': result[5],
                'distance': result[6]
            }
        else:
            logger.info(f"부서 권한 없음: {emp_id} -> {menu_code}")
            return None

    except Exception as e:
        logger.error(f"부서 권한 조회 실패: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def display_dept_tree():
    """부서 계층 구조 표시"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 계층 구조 조회
        cursor.execute("""
            WITH RECURSIVE dept_tree AS (
                SELECT dept_id, parent_dept_id, dept_name, dept_level,
                       CAST(dept_id AS VARCHAR(500)) as path
                FROM department_hierarchy
                WHERE parent_dept_id IS NULL

                UNION ALL

                SELECT d.dept_id, d.parent_dept_id, d.dept_name, d.dept_level,
                       dt.path || ' > ' || d.dept_id
                FROM department_hierarchy d
                JOIN dept_tree dt ON d.parent_dept_id = dt.dept_id
            )
            SELECT path, dept_name, dept_level
            FROM dept_tree
            ORDER BY path
        """)

        results = cursor.fetchall()

        logger.info("\n=== 부서 계층 구조 ===")
        for path, name, level in results:
            indent = "  " * (level - 1)
            logger.info(f"{indent}├─ {name} ({path.split(' > ')[-1]})")

        return True

    except Exception as e:
        logger.error(f"부서 계층 표시 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def test_inheritance():
    """권한 상속 테스트"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        logger.info("\n=== 권한 상속 테스트 ===")

        # IT부서에 권한 부여
        cursor.execute("""
            INSERT INTO dept_menu_permissions
            (dept_id, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            VALUES ('DEPT_IT', 'accident', TRUE, TRUE, TRUE, FALSE, 'dept')
            ON CONFLICT (dept_id, menu_code) DO UPDATE SET
                can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                data_scope = EXCLUDED.data_scope
        """)

        conn.commit()
        logger.info("✓ IT부서에 accident 권한 부여")

        # test_user를 IT 개발팀에 배치
        cursor.execute("""
            UPDATE system_users
            SET dept_id = 'DEPT_IT_DEV'
            WHERE emp_id = 'test_user'
        """)

        conn.commit()
        logger.info("✓ test_user를 IT 개발팀에 배치")

        # 상속된 권한 확인
        result = get_dept_permissions_with_inheritance('test_user', 'accident')
        if result:
            logger.info(f"✓ 상속된 권한 확인: {result}")
        else:
            logger.warning("⚠ 권한 상속 실패")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"상속 테스트 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def main():
    """메인 실행 함수"""

    logger.info("부서 계층 권한 상속 구현 시작")
    logger.info("="*60)

    # 1. 부서 계층 설정
    if setup_dept_hierarchy():
        logger.info("✅ 부서 계층 구조 설정 완료")
    else:
        logger.error("❌ 부서 계층 구조 설정 실패")
        return False

    # 2. 부서 트리 표시
    display_dept_tree()

    # 3. 상속 테스트
    test_inheritance()

    logger.info("\n✅ 부서 계층 권한 상속 구현 완료!")
    logger.info("다음 단계: permission_delegation.py로 권한 위임 기능 구현")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)