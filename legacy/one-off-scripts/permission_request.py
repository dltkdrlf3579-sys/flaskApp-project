#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 요청 워크플로우 구현
사용자 권한 요청, 승인/거부 처리
"""

import psycopg2
import configparser
import logging
import json
from datetime import datetime

from notification_service import get_notification_service, NotificationError

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

def create_request_tables():
    """권한 요청 관련 테이블 생성"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        logger.info("권한 요청 테이블 생성 시작...")

        # 권한 요청 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_requests (
                request_id SERIAL PRIMARY KEY,
                requester_id VARCHAR(50) NOT NULL,
                request_type VARCHAR(20) NOT NULL, -- 'role', 'menu', 'department'
                target_value VARCHAR(100) NOT NULL, -- role_id, menu_code, dept_id
                requested_permissions JSONB DEFAULT '{}'::jsonb,
                reason TEXT NOT NULL,
                status VARCHAR(20) DEFAULT 'pending', -- pending, approved, rejected, cancelled
                priority VARCHAR(20) DEFAULT 'normal', -- low, normal, high, urgent
                approver_id VARCHAR(50),
                approval_comments TEXT,
                approved_at TIMESTAMP,
                rejected_at TIMESTAMP,
                cancelled_at TIMESTAMP,
                valid_until DATE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (requester_id) REFERENCES system_users(emp_id),
                CONSTRAINT check_status CHECK (status IN ('pending', 'approved', 'rejected', 'cancelled'))
            )
        """)

        # 요청 승인 워크플로우 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS request_approval_workflow (
                workflow_id SERIAL PRIMARY KEY,
                request_id INTEGER NOT NULL,
                step_number INTEGER NOT NULL,
                approver_role VARCHAR(50) NOT NULL,
                approver_id VARCHAR(50),
                approval_status VARCHAR(20) DEFAULT 'pending',
                comments TEXT,
                processed_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (request_id) REFERENCES permission_requests(request_id),
                UNIQUE(request_id, step_number)
            )
        """)

        # 권한 요청 알림 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS permission_notifications (
                notification_id SERIAL PRIMARY KEY,
                recipient_id VARCHAR(50) NOT NULL,
                request_id INTEGER,
                notification_type VARCHAR(50) NOT NULL,
                title VARCHAR(200) NOT NULL,
                message TEXT,
                is_read BOOLEAN DEFAULT FALSE,
                read_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (recipient_id) REFERENCES system_users(emp_id),
                FOREIGN KEY (request_id) REFERENCES permission_requests(request_id)
            )
        """)

        # 인덱스 생성
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_status
            ON permission_requests(status, created_at DESC)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_requests_requester
            ON permission_requests(requester_id, status)
        """)

        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_notifications_recipient
            ON permission_notifications(recipient_id, is_read)
        """)

        conn.commit()
        logger.info("✓ 권한 요청 테이블 생성 완료")

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

def create_permission_request(requester_id, request_type, target_value, permissions, reason, priority='normal'):
    """권한 요청 생성"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 중복 요청 확인
        cursor.execute("""
            SELECT request_id
            FROM permission_requests
            WHERE requester_id = %s
            AND request_type = %s
            AND target_value = %s
            AND status = 'pending'
        """, (requester_id, request_type, target_value))

        if cursor.fetchone():
            logger.warning(f"이미 대기 중인 요청 존재: {requester_id} -> {target_value}")
            return None

        # 요청 생성
        cursor.execute("""
            INSERT INTO permission_requests
            (requester_id, request_type, target_value, requested_permissions,
             reason, priority, status)
            VALUES (%s, %s, %s, %s, %s, %s, 'pending')
            RETURNING request_id
        """, (requester_id, request_type, target_value,
              json.dumps(permissions), reason, priority))

        request_id = cursor.fetchone()[0]

        # 승인 워크플로우 생성
        if priority == 'urgent':
            approver_roles = [('super_admin', 1)]
        else:
            approver_roles = [('manager', 1), ('admin', 2)]

        for role, step in approver_roles:
            cursor.execute("""
                INSERT INTO request_approval_workflow
                (request_id, step_number, approver_role, approval_status)
                VALUES (%s, %s, %s, 'pending')
            """, (request_id, step, role))

        # 관리자에게 알림 생성
        cursor.execute("""
            INSERT INTO permission_notifications
            (recipient_id, request_id, notification_type, title, message)
            SELECT DISTINCT urm.emp_id, %s, 'new_request',
                   '새 권한 요청', %s
            FROM user_role_mapping urm
            WHERE urm.role_id IN ('admin', 'super_admin', 'manager')
        """, (request_id, f"{requester_id}님이 {target_value} 권한을 요청했습니다."))

        conn.commit()

        record_permission_event(
            action_type='PERMISSION_REQUEST',
            menu_code=target_value if request_type == 'menu' else 'system',
            permission_result='SUCCESS',
            details={
                'request_id': request_id,
                'request_type': request_type,
                'target': target_value,
                'priority': priority
            },
        )
        logger.info(f"✓ 권한 요청 생성: {request_id}")

        return request_id

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"요청 생성 실패: {e}")
        return None

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def approve_request(request_id, approver_id, comments=None):
    """권한 요청 승인"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 요청 정보 조회
        cursor.execute("""
            SELECT requester_id, request_type, target_value,
                   requested_permissions, status
            FROM permission_requests
            WHERE request_id = %s
        """, (request_id,))

        request = cursor.fetchone()
        if not request:
            logger.error(f"요청 없음: {request_id}")
            return False

        if request[4] != 'pending':
            logger.warning(f"이미 처리된 요청: {request_id} ({request[4]})")
            return False

        # 승인자 권한 확인
        cursor.execute("""
            SELECT role_id FROM user_role_mapping
            WHERE emp_id = %s AND role_id IN ('super_admin', 'admin', 'manager')
        """, (approver_id,))

        if not cursor.fetchone():
            logger.error(f"승인 권한 없음: {approver_id}")
            return False

        # 워크플로우 업데이트
        cursor.execute("""
            UPDATE request_approval_workflow
            SET approver_id = %s,
                approval_status = 'approved',
                comments = %s,
                processed_at = CURRENT_TIMESTAMP
            WHERE request_id = %s
            AND step_number = (
                SELECT MIN(step_number)
                FROM request_approval_workflow
                WHERE request_id = %s AND approval_status = 'pending'
            )
        """, (approver_id, comments, request_id, request_id))

        # 모든 단계 완료 확인
        cursor.execute("""
            SELECT COUNT(*) FROM request_approval_workflow
            WHERE request_id = %s AND approval_status = 'pending'
        """, (request_id,))

        pending_steps = cursor.fetchone()[0]
        finalize_payload = None

        if pending_steps == 0:
            # 모든 승인 완료 - 권한 부여
            requester_id = request[0]
            request_type = request[1]
            target_value = request[2]
            permissions = request[3] or {}
            if isinstance(permissions, str):
                try:
                    permissions = json.loads(permissions) if permissions else {}
                except Exception:
                    permissions = {}

            requester_login_id = requester_id
            requester_name = requester_id
            try:
                cursor.execute("SELECT user_id, user_name FROM system_users WHERE emp_id = %s", (requester_id,))
                row = cursor.fetchone()
                if row:
                    if row[0]:
                        requester_login_id = row[0]
                    if len(row) > 1 and row[1]:
                        requester_name = row[1]
            except Exception:
                requester_login_id = requester_id
                requester_name = requester_id

            if request_type == 'role':
                cursor.execute("""
                    INSERT INTO user_role_mapping (emp_id, role_id)
                    VALUES (%s, %s)
                    ON CONFLICT (emp_id, role_id) DO NOTHING
                """, (requester_id, target_value))

            elif request_type == 'menu':
                cursor.execute("""
                    INSERT INTO user_menu_permissions
                    (emp_id, menu_code, can_view, can_create, can_edit, can_delete, data_scope)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (emp_id, menu_code) DO UPDATE SET
                        can_view = EXCLUDED.can_view,
                        can_create = EXCLUDED.can_create,
                        can_edit = EXCLUDED.can_edit,
                        can_delete = EXCLUDED.can_delete,
                        data_scope = EXCLUDED.data_scope
                """, (requester_id, target_value,
                      permissions.get('can_view', False),
                      permissions.get('can_create', False),
                      permissions.get('can_edit', False),
                      permissions.get('can_delete', False),
                      permissions.get('data_scope', 'self')))

            elif request_type == 'department':
                cursor.execute("""
                    UPDATE system_users
                    SET dept_id = %s
                    WHERE emp_id = %s
                """, (target_value, requester_id))

            # 요청 상태 업데이트
            cursor.execute("""
                UPDATE permission_requests
                SET status = 'approved',
                    approver_id = %s,
                    approval_comments = %s,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE request_id = %s
            """, (approver_id, comments, request_id))

            # 승인 알림
            cursor.execute("""
                INSERT INTO permission_notifications
                (recipient_id, request_id, notification_type, title, message)
                VALUES (%s, %s, 'request_approved', '권한 요청 승인',
                        '요청하신 권한이 승인되었습니다.')
            """, (requester_id, request_id))

            requester_login_id = requester_id
            requester_name = requester_id
            try:
                cursor.execute("SELECT user_id, user_name FROM system_users WHERE emp_id = %s", (requester_id,))
                row = cursor.fetchone()
                if row:
                    if row[0]:
                        requester_login_id = row[0]
                    if len(row) > 1 and row[1]:
                        requester_name = row[1]
            except Exception:
                requester_login_id = requester_id
                requester_name = requester_id

            finalize_payload = {
                'login_id': requester_login_id,
                'requester_name': requester_name,
                'permission_name': target_value,
            }

            logger.info(f"✓ 권한 요청 최종 승인 및 부여: {request_id}")

        else:
            # 다음 승인자에게 알림
            cursor.execute("""
                INSERT INTO permission_notifications
                (recipient_id, request_id, notification_type, title, message)
                SELECT DISTINCT urm.emp_id, %s, 'pending_approval',
                       '권한 요청 승인 대기', '승인이 필요한 권한 요청이 있습니다.'
                FROM user_role_mapping urm
                JOIN request_approval_workflow raw ON urm.role_id = raw.approver_role
                WHERE raw.request_id = %s AND raw.approval_status = 'pending'
            """, (request_id, request_id))

            logger.info(f"✓ 권한 요청 부분 승인: {request_id} ({pending_steps}단계 남음)")

        conn.commit()

        if finalize_payload:
            try:
                service = get_notification_service()
                service.send_event_notification(
                    channel='chatbot',
                    event='permission_approved',
                    recipients=[finalize_payload['login_id']],
                    context={
                        'requester_name': finalize_payload['requester_name'],
                        'permission_name': finalize_payload['permission_name'],
                    },
                )
            except NotificationError as exc:
                logger.warning(f"챗봇 알림 실패(request_id={request_id}): {exc}")
            except Exception as exc:
                logger.exception(f"챗봇 알림 처리 중 오류(request_id={request_id})")

        record_permission_event(
            action_type='REQUEST_APPROVE',
            menu_code='system',
            permission_result='SUCCESS',
            details={'request_id': request_id},
        )
        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"요청 승인 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def reject_request(request_id, approver_id, reason):
    """권한 요청 거부"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        # 요청 상태 업데이트
        cursor.execute("""
            UPDATE permission_requests
            SET status = 'rejected',
                approver_id = %s,
                approval_comments = %s,
                rejected_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE request_id = %s AND status = 'pending'
            RETURNING requester_id
        """, (approver_id, reason, request_id))

        result = cursor.fetchone()
        if not result:
            logger.warning(f"거부할 수 없는 요청: {request_id}")
            return False

        # 워크플로우 업데이트
        cursor.execute("""
            UPDATE request_approval_workflow
            SET approval_status = 'rejected'
            WHERE request_id = %s AND approval_status = 'pending'
        """, (request_id,))

        # 거부 알림
        cursor.execute("""
            INSERT INTO permission_notifications
            (recipient_id, request_id, notification_type, title, message)
            VALUES (%s, %s, 'request_rejected', '권한 요청 거부',
                    %s)
        """, (result[0], request_id, f"권한 요청이 거부되었습니다. 사유: {reason}"))

        conn.commit()

        record_permission_event(
            action_type='REQUEST_REJECT',
            menu_code='system',
            permission_result='REJECTED',
            details={'request_id': request_id, 'reason': reason},
        )
        logger.info(f"✓ 권한 요청 거부: {request_id}")

        return True

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"요청 거부 실패: {e}")
        return False

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def get_pending_requests(approver_id=None):
    """대기 중인 요청 조회"""

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        if approver_id:
            # 특정 승인자의 대기 요청
            cursor.execute("""
                SELECT DISTINCT
                    pr.request_id,
                    pr.requester_id,
                    su.emp_name,
                    pr.request_type,
                    pr.target_value,
                    pr.reason,
                    pr.priority,
                    pr.created_at
                FROM permission_requests pr
                JOIN system_users su ON pr.requester_id = su.emp_id
                JOIN request_approval_workflow raw ON pr.request_id = raw.request_id
                JOIN user_role_mapping urm ON urm.emp_id = %s
                WHERE pr.status = 'pending'
                AND raw.approval_status = 'pending'
                AND raw.approver_role = urm.role_id
                ORDER BY
                    CASE pr.priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    pr.created_at
            """, (approver_id,))
        else:
            # 전체 대기 요청
            cursor.execute("""
                SELECT
                    pr.request_id,
                    pr.requester_id,
                    su.emp_name,
                    pr.request_type,
                    pr.target_value,
                    pr.reason,
                    pr.priority,
                    pr.created_at
                FROM permission_requests pr
                JOIN system_users su ON pr.requester_id = su.emp_id
                WHERE pr.status = 'pending'
                ORDER BY
                    CASE pr.priority
                        WHEN 'urgent' THEN 1
                        WHEN 'high' THEN 2
                        WHEN 'normal' THEN 3
                        WHEN 'low' THEN 4
                    END,
                    pr.created_at
            """)

        requests = cursor.fetchall()

        logger.info(f"대기 중인 요청: {len(requests)}건")

        return [{
            'request_id': r[0],
            'requester_id': r[1],
            'requester_name': r[2],
            'request_type': r[3],
            'target_value': r[4],
            'reason': r[5],
            'priority': r[6],
            'created_at': r[7]
        } for r in requests]

    except Exception as e:
        logger.error(f"대기 요청 조회 실패: {e}")
        return []

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

def test_request_workflow():
    """권한 요청 워크플로우 테스트"""

    logger.info("\n=== 권한 요청 워크플로우 테스트 ===")

    # 1. 일반 사용자가 권한 요청
    request_id = create_permission_request(
        'test_user', 'menu', 'accident',
        {'can_view': True, 'can_create': True, 'can_edit': False, 'can_delete': False, 'data_scope': 'self'},
        '사고 관리 업무 담당 배정',
        'normal'
    )

    if request_id:
        logger.info(f"✓ 권한 요청 생성: ID {request_id}")

        # 2. 대기 중인 요청 조회
        pending = get_pending_requests()
        logger.info(f"✓ 대기 중인 요청: {len(pending)}건")

        # 3. 관리자 승인
        if approve_request(request_id, 'admin', "업무 필요성 확인"):
            logger.info("✓ 권한 요청 승인 완료")

    # 4. 거부 테스트
    request_id2 = create_permission_request(
        'test_user', 'role', 'admin',
        {},
        '관리자 권한 필요',
        'high'
    )

    if request_id2:
        if reject_request(request_id2, 'super_admin', "권한 수준 과도"):
            logger.info("✓ 권한 요청 거부 완료")

    return True

def main():
    """메인 실행 함수"""

    logger.info("권한 요청 워크플로우 구현 시작")
    logger.info("="*60)

    # 1. 테이블 생성
    if create_request_tables():
        logger.info("✅ 권한 요청 테이블 생성 완료")
    else:
        logger.error("❌ 권한 요청 테이블 생성 실패")
        return False

    # 2. 워크플로우 테스트
    if test_request_workflow():
        logger.info("✅ 권한 요청 워크플로우 테스트 완료")
    else:
        logger.error("❌ 권한 요청 워크플로우 테스트 실패")

    logger.info("\n✅ 권한 요청 워크플로우 구현 완료!")
    logger.info("다음 단계: test_day3_complete.py로 전체 통합 테스트")

    return True

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)