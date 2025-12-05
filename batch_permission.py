#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
대량 권한 처리 최적화
"""

import psycopg2
import configparser
import logging
from typing import List, Dict
from datetime import datetime
from simple_cache import get_cache

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """데이터베이스 연결"""
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')

    if config.has_option('DATABASE', 'postgres_dsn'):
        dsn = config.get('DATABASE', 'postgres_dsn')
        return psycopg2.connect(dsn)
    else:
        return psycopg2.connect(
            host='localhost',
            database='portal_db',
            user='postgres',
            password='postgres'
        )

def batch_grant_permissions(assignments: List[Dict]) -> Dict:
    """
    대량 권한 부여

    Parameters:
    assignments = [
        {
            'emp_id': 'user1',
            'menu_code': 'accident',
            'can_view': True,
            'can_create': False,
            'can_edit': False,
            'can_delete': False
        },
        ...
    ]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cache = get_cache()

    try:
        # 배치 데이터 준비
        values = []
        affected_users = set()

        for a in assignments:
            values.append((
                a['emp_id'],
                a['menu_code'],
                a.get('can_view', False),
                a.get('can_create', False),
                a.get('can_edit', False),
                a.get('can_delete', False),
                datetime.now(),
                'BATCH_GRANT'
            ))
            affected_users.add(a['emp_id'])

        # 한 번에 실행
        cursor.executemany("""
            INSERT INTO user_menu_permissions
            (emp_id, menu_code, can_view, can_create, can_edit, can_delete, updated_at, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (emp_id, menu_code)
            DO UPDATE SET
                can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by
        """, values)

        affected_rows = cursor.rowcount
        conn.commit()

        # 캐시 무효화
        for emp_id in affected_users:
            cache.clear_user(emp_id)

        logger.info(f"Batch granted {affected_rows} permissions for {len(affected_users)} users")

        return {
            'success': True,
            'count': len(assignments),
            'affected_users': len(affected_users),
            'affected_rows': affected_rows
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Batch grant failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

    finally:
        cursor.close()
        conn.close()

def batch_copy_permissions(source_emp_id: str, target_emp_ids: List[str]) -> Dict:
    """
    한 사용자의 권한을 여러 사용자에게 복사

    Parameters:
    - source_emp_id: 원본 사용자 ID
    - target_emp_ids: 대상 사용자 ID 리스트
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cache = get_cache()

    try:
        # 원본 권한 가져오기
        cursor.execute("""
            SELECT menu_code, can_view, can_create, can_edit, can_delete
            FROM user_menu_permissions
            WHERE emp_id = %s
        """, (source_emp_id,))

        source_perms = cursor.fetchall()

        if not source_perms:
            return {
                'success': False,
                'error': f"No permissions found for user {source_emp_id}"
            }

        # 배치 데이터 준비
        values = []
        for target_id in target_emp_ids:
            for menu_code, can_view, can_create, can_edit, can_delete in source_perms:
                values.append((
                    target_id,
                    menu_code,
                    can_view,
                    can_create,
                    can_edit,
                    can_delete,
                    datetime.now(),
                    f'COPIED_FROM_{source_emp_id}'
                ))

        # 배치 실행
        cursor.executemany("""
            INSERT INTO user_menu_permissions
            (emp_id, menu_code, can_view, can_create, can_edit, can_delete, updated_at, updated_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (emp_id, menu_code)
            DO UPDATE SET
                can_view = EXCLUDED.can_view,
                can_create = EXCLUDED.can_create,
                can_edit = EXCLUDED.can_edit,
                can_delete = EXCLUDED.can_delete,
                updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by
        """, values)

        conn.commit()

        # 캐시 무효화
        for target_id in target_emp_ids:
            cache.clear_user(target_id)

        logger.info(f"Copied {len(source_perms)} permissions from {source_emp_id} to {len(target_emp_ids)} users")

        return {
            'success': True,
            'copied_to': len(target_emp_ids),
            'permissions_copied': len(source_perms),
            'total_operations': len(values)
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Batch copy failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

    finally:
        cursor.close()
        conn.close()

def batch_revoke_permissions(emp_ids: List[str], menu_codes: List[str] = None) -> Dict:
    """
    대량 권한 회수

    Parameters:
    - emp_ids: 사용자 ID 리스트
    - menu_codes: 메뉴 코드 리스트 (None이면 모든 권한 회수)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cache = get_cache()

    try:
        if menu_codes:
            # 특정 메뉴 권한만 회수
            cursor.execute("""
                DELETE FROM user_menu_permissions
                WHERE emp_id = ANY(%s) AND menu_code = ANY(%s)
            """, (emp_ids, menu_codes))
        else:
            # 모든 권한 회수
            cursor.execute("""
                DELETE FROM user_menu_permissions
                WHERE emp_id = ANY(%s)
            """, (emp_ids,))

        deleted_rows = cursor.rowcount
        conn.commit()

        # 캐시 무효화
        for emp_id in emp_ids:
            cache.clear_user(emp_id)

        logger.info(f"Revoked {deleted_rows} permissions from {len(emp_ids)} users")

        return {
            'success': True,
            'deleted_rows': deleted_rows,
            'affected_users': len(emp_ids)
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Batch revoke failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

    finally:
        cursor.close()
        conn.close()

def batch_update_role_permissions(role_id: str, permissions: List[Dict]) -> Dict:
    """
    역할의 모든 권한 일괄 업데이트

    Parameters:
    - role_id: 역할 ID
    - permissions: 권한 리스트
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 기존 권한 삭제
        cursor.execute("""
            DELETE FROM role_menu_permissions
            WHERE role_id = %s
        """, (role_id,))

        # 새 권한 추가
        values = []
        for perm in permissions:
            values.append((
                role_id,
                perm['menu_code'],
                perm.get('can_view', False),
                perm.get('can_create', False),
                perm.get('can_edit', False),
                perm.get('can_delete', False)
            ))

        cursor.executemany("""
            INSERT INTO role_menu_permissions
            (role_id, menu_code, can_view, can_create, can_edit, can_delete)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, values)

        conn.commit()

        # 역할을 가진 모든 사용자의 캐시 무효화 필요
        # (구현 생략 - 실제로는 user_role_mapping을 조회해야 함)

        logger.info(f"Updated {len(permissions)} permissions for role {role_id}")

        return {
            'success': True,
            'role_id': role_id,
            'permissions_updated': len(permissions)
        }

    except Exception as e:
        conn.rollback()
        logger.error(f"Role permission update failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # 테스트
    print("Batch Permission System Test")
    print("-" * 40)

    # 1. 대량 권한 부여 테스트
    test_assignments = [
        {
            'emp_id': 'TEST001',
            'menu_code': 'accident',
            'can_view': True,
            'can_create': True,
            'can_edit': False,
            'can_delete': False
        },
        {
            'emp_id': 'TEST001',
            'menu_code': 'safety_instruction',
            'can_view': True,
            'can_create': False,
            'can_edit': False,
            'can_delete': False
        },
        {
            'emp_id': 'TEST002',
            'menu_code': 'accident',
            'can_view': True,
            'can_create': False,
            'can_edit': False,
            'can_delete': False
        }
    ]

    result = batch_grant_permissions(test_assignments)
    print(f"Batch grant result: {result}")

    # 2. 권한 복사 테스트
    result = batch_copy_permissions('TEST001', ['TEST003', 'TEST004'])
    print(f"Batch copy result: {result}")

    # 3. 권한 회수 테스트
    result = batch_revoke_permissions(['TEST003', 'TEST004'])
    print(f"Batch revoke result: {result}")

    print("\nBatch permission tests completed!")