#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 위임 기능 구현
임시 권한 위임 및 자동 만료 관리
"""

import psycopg2
import configparser
import logging
import json
from datetime import datetime, timedelta

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

def create_delegation_table():
    """권한 위임 테이블 생성"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        logger.info("권한 위임 테이블 생성 시작...")

        # 권한 위임 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_delegations (
                delegation_id SERIAL PRIMARY KEY,
                delegator_id VARCHAR(50) NOT NULL,  -- 위임자
                delegate_id VARCHAR(50) NOT NULL,   -- 수임자
                menu_code VARCHAR(100) NOT NULL,
                delegated_permissions JSONB DEFAULT '{}'::jsonb,
                start_date TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                end_date TIMESTAMP NOT NULL,
                reason TEXT,
                is_active BOOLEAN DEFAULT TRUE,
                approved_by VARCHAR(50),
                approved_at TIMESTAMP,
                revoked_by VARCHAR(50),
                revoked_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (delegator_id) REFERENCES system_users(emp_id),
                FOREIGN KEY (delegate_id) REFERENCES system_users(emp_id),
                FOREIGN KEY (menu_code) REFERENCES menu_registry(menu_code),
                CONSTRAINT check_dates CHECK (end_date > start_date)
            )
        """)

        # 인덱스 생성
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegation_active
            ON permission_delegations(delegate_id, menu_code)
            WHERE is_active = TRUE
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_delegation_delegator
            ON permission_delegations(delegator_id)
            WHERE is_active = TRUE
        """)

        conn.commit()
        logger.info("✓ 권한 위임 테이블 생성 완료")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"테이블 생성 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def create_delegation(delegator_id, delegate_id, menu_code, permissions, end_date, reason=None):
    """권한 위임 생성"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 기존 활성 위임 확인
        cursor.execute("""
            SELECT delegation_id
            FROM permission_delegations
            WHERE delegator_id = %s
            AND delegate_id = %s
            AND menu_code = %s
            AND is_active = TRUE
            AND CURRENT_TIMESTAMP BETWEEN start_date AND end_date
        """, (delegator_id, delegate_id, menu_code))

        if cursor.fetchone():
            logger.warning(f"이미 활성화된 위임 존재: {delegator_id} -> {delegate_id} ({menu_code})")
            return None

        # 위임자의 권한 확인
        cursor.execute("""
            WITH user_permissions AS (
                -- 개인 권한
                SELECT can_view, can_create, can_edit, can_delete, data_scope
                FROM user_menu_permissions
                WHERE emp_id = %s AND menu_code = %s

                UNION ALL

                -- 부서 권한
                SELECT dmp.can_view, dmp.can_create, dmp.can_edit, dmp.can_delete, dmp.data_scope
                FROM dept_menu_permissions dmp
                JOIN system_users u ON dmp.dept_id = u.dept_id
                WHERE u.emp_id = %s AND dmp.menu_code = %s

                UNION ALL

                -- 역할 권한
                SELECT rmp.can_view, rmp.can_create, rmp.can_edit, rmp.can_delete, rmp.data_scope
                FROM role_menu_permissions rmp
                JOIN user_role_mapping urm ON rmp.role_id = urm.role_id
                WHERE urm.emp_id = %s AND rmp.menu_code = %s
            )
            SELECT
                BOOL_OR(can_view) as can_view,
                BOOL_OR(can_create) as can_create,
                BOOL_OR(can_edit) as can_edit,
                BOOL_OR(can_delete) as can_delete,
                MAX(data_scope) as data_scope
            FROM user_permissions
        """, (delegator_id, menu_code, delegator_id, menu_code, delegator_id, menu_code))

        delegator_perms = cursor.fetchone()
        if not delegator_perms or not delegator_perms[0]:  # can_view가 False면 권한 없음
            logger.error(f"위임자에게 권한 없음: {delegator_id} -> {menu_code}")
            return None

        # 위임 가능한 권한 제한 (위임자가 가진 권한만)
        valid_permissions = {
            'can_view': permissions.get('can_view', False) and delegator_perms[0],
            'can_create': permissions.get('can_create', False) and delegator_perms[1],
            'can_edit': permissions.get('can_edit', False) and delegator_perms[2],
            'can_delete': permissions.get('can_delete', False) and delegator_perms[3],
            'data_scope': min(permissions.get('data_scope', 'self'), delegator_perms[4] or 'self')
        }

        # 위임 생성
        cursor.execute("""
            INSERT INTO permission_delegations
            (delegator_id, delegate_id, menu_code, delegated_permissions,
             end_date, reason, is_active)
            VALUES (%s, %s, %s, %s, %s, %s, TRUE)
            RETURNING delegation_id
        """, (delegator_id, delegate_id, menu_code,
              json.dumps(valid_permissions), end_date, reason))

        delegation_id = cursor.fetchone()[0]

        # 감사 로그
        cursor.execute("""
            INSERT INTO access_audit_log
            (emp_id, menu_code, action_type, request_path, permission_result, details)
            VALUES (%s, %s, 'DELEGATION_CREATE', 'permission_delegation', 'SUCCESS', %s)
        """, (delegator_id, menu_code, json.dumps({
            'delegation_id': delegation_id,
            'delegate_id': delegate_id,
            'permissions': valid_permissions,
            'end_date': end_date.isoformat()
        })))

        conn.commit()
        logger.info(f"✓ 권한 위임 생성: {delegation_id}")

        return delegation_id

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"위임 생성 실패: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_delegated_permissions(emp_id, menu_code):
    """위임받은 권한 조회"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                delegation_id,
                delegator_id,
                delegated_permissions,
                end_date,
                reason
            FROM permission_delegations
            WHERE delegate_id = %s
            AND menu_code = %s
            AND is_active = TRUE
            AND CURRENT_TIMESTAMP BETWEEN start_date AND end_date
            ORDER BY created_at DESC
            LIMIT 1
        """, (emp_id, menu_code))

        result = cursor.fetchone()

        if result:
            logger.info(f"위임 권한 찾음: {emp_id} <- {result[1]} ({menu_code})")
            return {
                'delegation_id': result[0],
                'delegator_id': result[1],
                'permissions': result[2],
                'end_date': result[3],
                'reason': result[4]
            }
        else:
            return None

    except Exception as e:
        logger.error(f"위임 권한 조회 실패: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def revoke_delegation(delegation_id, revoked_by):
    """권한 위임 취소"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 위임 정보 확인
        cursor.execute("""
            SELECT delegator_id, delegate_id, menu_code
            FROM permission_delegations
            WHERE delegation_id = %s AND is_active = TRUE
        """, (delegation_id,))

        delegation = cursor.fetchone()
        if not delegation:
            logger.warning(f"활성 위임 없음: {delegation_id}")
            return False

        # 취소 권한 확인 (위임자 본인 또는 관리자)
        cursor.execute("""
            SELECT role_id FROM user_role_mapping
            WHERE emp_id = %s AND role_id IN ('super_admin', 'admin')
        """, (revoked_by,))

        is_admin = cursor.fetchone() is not None

        if delegation[0] != revoked_by and not is_admin:
            logger.error(f"취소 권한 없음: {revoked_by}")
            return False

        # 위임 취소
        cursor.execute("""
            UPDATE permission_delegations
            SET is_active = FALSE,
                revoked_by = %s,
                revoked_at = CURRENT_TIMESTAMP
            WHERE delegation_id = %s
        """, (revoked_by, delegation_id))

        # 감사 로그
        cursor.execute("""
            INSERT INTO access_audit_log
            (emp_id, menu_code, action_type, request_path, permission_result, details)
            VALUES (%s, %s, 'DELEGATION_REVOKE', 'permission_delegation', 'SUCCESS', %s)
        """, (revoked_by, delegation[2], json.dumps({
            'delegation_id': delegation_id,
            'delegator_id': delegation[0],
            'delegate_id': delegation[1]
        })))

        conn.commit()
        logger.info(f"✓ 권한 위임 취소: {delegation_id}")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"위임 취소 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def cleanup_expired_delegations():
    """만료된 위임 정리"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE permission_delegations
            SET is_active = FALSE
            WHERE is_active = TRUE
            AND end_date < CURRENT_TIMESTAMP
            RETURNING delegation_id
        """)

        expired = cursor.fetchall()

        if expired:
            logger.info(f"✓ {len(expired)}개 만료 위임 비활성화")

            # 감사 로그
            for (delegation_id,) in expired:
                cursor.execute("""
                    INSERT INTO access_audit_log
                    (emp_id, menu_code, action_type, request_path,
                     permission_result, details)
                    SELECT delegator_id, menu_code, 'DELEGATION_EXPIRE',
                           'permission_delegation', 'SUCCESS',
                           json_build_object('delegation_id', delegation_id)
                    FROM permission_delegations
                    WHERE delegation_id = %s
                """, (delegation_id,))

        conn.commit()
        return len(expired) if expired else 0

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"만료 위임 정리 실패: {e}")
        return 0

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def test_delegation():
    """권한 위임 테스트"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        logger.info("\n=== 권한 위임 테스트 ===")

        # 테스트 사용자 생성
        test_users = [
            ('delegator1', '위임자1', 'DEPT_IT', 'DEV'),
            ('delegate1', '수임자1', 'DEPT_IT', 'DEV')
        ]

        for emp_id, name, dept_id, role_id in test_users:
            cursor.execute("""
                INSERT INTO system_users (emp_id, emp_name, dept_id, is_active)
                VALUES (%s, %s, %s, TRUE)
                ON CONFLICT (emp_id) DO UPDATE SET
                    emp_name = EXCLUDED.emp_name,
                    dept_id = EXCLUDED.dept_id
            """, (emp_id, name, dept_id))

            cursor.execute("""
                INSERT INTO user_role_mapping (emp_id, role_id)
                VALUES (%s, %s)
                ON CONFLICT (emp_id, role_id) DO NOTHING
            """, (emp_id, role_id))

        # 위임자에게 권한 부여
        cursor.execute("""
            INSERT INTO user_menu_permissions
            (emp_id, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
            VALUES ('delegator1', 'accident', TRUE, TRUE, TRUE, FALSE, 'dept')
            ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete
        """)

        conn.commit()
        logger.info("✓ 테스트 사용자 및 권한 설정")

        # 1주일 후 만료
        end_date = datetime.now() + timedelta(days=7)

        # 권한 위임
        delegation_id = create_delegation(
            'delegator1', 'delegate1', 'accident',
            {'can_view': True, 'can_create': True, 'can_edit': False, 'can_delete': False, 'data_scope': 'self'},
            end_date,
            "휴가 중 업무 대행"
        )

        if delegation_id:
            logger.info(f"✓ 권한 위임 생성: ID {delegation_id}")

            # 위임 권한 확인
            delegated = get_delegated_permissions('delegate1', 'accident')
            if delegated:
                logger.info(f"✓ 위임받은 권한: {delegated}")

            # 위임 취소 테스트
            if revoke_delegation(delegation_id, 'delegator1'):
                logger.info("✓ 권한 위임 취소 성공")

        # 만료된 위임 정리
        expired_count = cleanup_expired_delegations()
        logger.info(f"✓ {expired_count}개 만료 위임 정리")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"위임 테스트 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def main():
    """메인 실행 함수"""

    logger.info("권한 위임 기능 구현 시작")
    logger.info("="*60)

    # 1. 테이블 생성
    if create_delegation_table():
        logger.info("✅ 권한 위임 테이블 생성 완료")
    else:
        logger.error("❌ 권한 위임 테이블 생성 실패")
        return False

    # 2. 위임 테스트
    if test_delegation():
        logger.info("✅ 권한 위임 테스트 완료")
    else:
        logger.error("❌ 권한 위임 테스트 실패")

    logger.info("\n✅ 권한 위임 기능 구현 완료!")
    logger.info("다음 단계: permission_request.py로 권한 요청 워크플로우 구현")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)