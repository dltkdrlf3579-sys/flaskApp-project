#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 관리 API 엔드포인트
사용자별/부서별 권한 관리
"""

from flask import jsonify, request, session
from db_connection import get_db_connection
import logging

logger = logging.getLogger(__name__)

def register_permission_routes(app):
    """권한 관리 API 라우트 등록"""

    @app.route('/api/menu-roles/users', methods=['GET'])
    def get_user_permissions():
        """사용자별 권한 목록 조회"""
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 50))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            # 전체 카운트 조회
            cursor.execute("""
                SELECT COUNT(DISTINCT login_id)
                FROM user_menu_permissions
                WHERE is_active = true
            """)
            total = cursor.fetchone()[0]

            # 사용자별 권한 조회 (페이지네이션 적용)
            cursor.execute("""
                SELECT
                    login_id,
                    json_object_agg(
                        menu_code,
                        json_build_object(
                            'read', read_level,
                            'write', write_level
                        )
                    ) as permissions
                FROM user_menu_permissions
                WHERE is_active = true
                GROUP BY login_id
                ORDER BY login_id
                LIMIT %s OFFSET %s
            """, (size, offset))

            users = []
            rows = cursor.fetchall()
            for row in rows:
                # RowCompat 객체에서 데이터 추출
                if hasattr(row, '__getitem__'):
                    login_id = row[0]
                    permissions = row[1]
                else:
                    # fallback - tuple로 처리
                    login_id, permissions = row

                users.append({
                    'login_id': login_id,
                    'permissions': permissions or {}
                })

            cursor.close()
            conn.close()

            return jsonify({
                'items': users,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as e:
            logger.error(f"Error getting user permissions: {e}")
            return jsonify({
                'error': '권한 조회 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/departments', methods=['GET'])
    def get_dept_permissions():
        """부서별 권한 목록 조회"""
        try:
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 50))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            # 전체 카운트
            cursor.execute("""
                SELECT COUNT(DISTINCT dept_id)
                FROM dept_menu_roles
                WHERE is_active = true
            """)
            total = cursor.fetchone()[0]

            # 부서별 권한 조회
            cursor.execute("""
                SELECT
                    dept_id,
                    dept_code,
                    json_object_agg(
                        menu_code,
                        json_build_object(
                            'read', read_level,
                            'write', write_level
                        )
                    ) as permissions
                FROM dept_menu_roles
                WHERE is_active = true
                GROUP BY dept_id, dept_code
                ORDER BY dept_id
                LIMIT %s OFFSET %s
            """, (size, offset))

            departments = []
            rows = cursor.fetchall()
            for row in rows:
                # RowCompat 객체에서 데이터 추출
                if hasattr(row, '__getitem__'):
                    dept_id = row[0]
                    dept_code = row[1]
                    permissions = row[2]
                else:
                    # fallback - tuple로 처리
                    dept_id, dept_code, permissions = row
                departments.append({
                    'dept_id': dept_id,
                    'dept_code': dept_code,
                    'permissions': permissions or {}
                })

            cursor.close()
            conn.close()

            return jsonify({
                'items': departments,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as e:
            logger.error(f"Error getting department permissions: {e}")
            return jsonify({
                'error': '부서 권한 조회 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/users/<user_id>', methods=['POST'])
    def save_user_permission(user_id):
        """사용자 권한 저장/업데이트"""
        try:
            data = request.json
            menu_code = data.get('menu_code')
            read_level = data.get('read_level', 0)
            write_level = data.get('write_level', 0)

            # 유효성 검증
            if not menu_code:
                return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

            if read_level not in [0, 1, 2, 3] or write_level not in [0, 1, 2, 3]:
                return jsonify({'error': '잘못된 권한 레벨입니다'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # UPSERT 실행
            cursor.execute("""
                INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, granted_by, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (login_id, menu_code)
                DO UPDATE SET
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = EXCLUDED.granted_by,
                    is_active = true
            """, (user_id, menu_code, read_level, write_level, session.get('user_id', 'system')))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission updated: user={user_id}, menu={menu_code}, read={read_level}, write={write_level}")
            return jsonify({'status': 'success', 'message': '권한이 저장되었습니다'})

        except Exception as e:
            logger.error(f"Error saving user permission: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 저장 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/departments/<dept_id>', methods=['POST'])
    def save_dept_permission(dept_id):
        """부서 권한 저장/업데이트"""
        try:
            data = request.json
            menu_code = data.get('menu_code')
            read_level = data.get('read_level', 0)
            write_level = data.get('write_level', 0)
            dept_code = data.get('dept_code', '')

            # 유효성 검증
            if not menu_code:
                return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

            if read_level not in [0, 1, 2, 3] or write_level not in [0, 1, 2, 3]:
                return jsonify({'error': '잘못된 권한 레벨입니다'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # UPSERT 실행
            cursor.execute("""
                INSERT INTO dept_menu_roles
                    (dept_id, dept_code, menu_code, read_level, write_level, granted_by, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, true)
                ON CONFLICT (dept_id, menu_code)
                DO UPDATE SET
                    dept_code = EXCLUDED.dept_code,
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = EXCLUDED.granted_by,
                    is_active = true
            """, (dept_id, dept_code, menu_code, read_level, write_level, session.get('user_id', 'system')))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Department permission updated: dept={dept_id}, menu={menu_code}, read={read_level}, write={write_level}")
            return jsonify({'status': 'success', 'message': '부서 권한이 저장되었습니다'})

        except Exception as e:
            logger.error(f"Error saving department permission: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '부서 권한 저장 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/users/<user_id>', methods=['DELETE'])
    def delete_user_permissions(user_id):
        """사용자 권한 삭제 (soft delete)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Soft delete: is_active를 false로 설정
            cursor.execute("""
                UPDATE user_menu_permissions
                SET is_active = false,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = %s
                WHERE login_id = %s
            """, (session.get('user_id', 'system'), user_id))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"User permissions deleted (soft): user={user_id}, affected={affected}")
            return jsonify({
                'status': 'success',
                'message': f'{affected}개 권한이 삭제되었습니다'
            })

        except Exception as e:
            logger.error(f"Error deleting user permissions: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 삭제 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/departments/<dept_id>', methods=['DELETE'])
    def delete_dept_permissions(dept_id):
        """부서 권한 삭제 (soft delete)"""
        try:
            conn = get_db_connection()
            cursor = conn.cursor()

            # Soft delete
            cursor.execute("""
                UPDATE dept_menu_roles
                SET is_active = false,
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = %s
                WHERE dept_id = %s
            """, (session.get('user_id', 'system'), dept_id))

            affected = cursor.rowcount
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Department permissions deleted (soft): dept={dept_id}, affected={affected}")
            return jsonify({
                'status': 'success',
                'message': f'{affected}개 부서 권한이 삭제되었습니다'
            })

        except Exception as e:
            logger.error(f"Error deleting department permissions: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '부서 권한 삭제 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/check', methods=['GET'])
    def check_user_permission():
        """현재 사용자의 특정 메뉴 권한 체크"""
        try:
            menu_code = request.args.get('menu_code')
            action = request.args.get('action', 'read')  # read or write

            if not menu_code:
                return jsonify({'error': '메뉴 코드가 필요합니다'}), 400

            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            # scoped_permission_check 모듈 사용
            from scoped_permission_check import get_permission_level

            level = get_permission_level(login_id, dept_id, menu_code, action)

            return jsonify({
                'has_permission': level > 0,
                'level': level,
                'action': action,
                'menu_code': menu_code
            })

        except Exception as e:
            logger.error(f"Error checking permission: {e}")
            return jsonify({
                'error': '권한 체크 실패',
                'message': str(e)
            }), 500

    @app.route('/api/menu-roles/summary', methods=['GET'])
    def get_permission_summary():
        """현재 사용자의 전체 권한 요약"""
        try:
            login_id = session.get('user_id')
            dept_id = session.get('deptid')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            # scoped_permission_check 모듈 사용
            from scoped_permission_check import get_user_permission_summary

            permissions = get_user_permission_summary(login_id, dept_id)

            return jsonify({
                'user_id': login_id,
                'dept_id': dept_id,
                'permissions': permissions
            })

        except Exception as e:
            logger.error(f"Error getting permission summary: {e}")
            return jsonify({
                'error': '권한 요약 조회 실패',
                'message': str(e)
            }), 500

    # ==================== 권한 신청 관련 API ====================

    @app.route('/api/permission-requests', methods=['POST'])
    def create_permission_request():
        """권한 신청 생성"""
        try:
            data = request.json

            # 세션에서 사용자 정보 가져오기 (SSO 데이터)
            login_id = session.get('user_id')
            user_name = session.get('name', '')
            deptid = session.get('deptid', '')
            dept_name = session.get('department', '')

            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            # 필수 데이터 검증
            menu_code = data.get('menu_code')
            permission_type = data.get('permission_type')  # 'read' or 'read_write'
            reason = data.get('reason', '').strip()

            if not menu_code:
                return jsonify({'error': '메뉴를 선택해주세요'}), 400
            if not permission_type:
                return jsonify({'error': '권한 유형을 선택해주세요'}), 400
            if not reason or len(reason) < 10:
                return jsonify({'error': '신청 사유를 10자 이상 입력해주세요'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # 메뉴명 가져오기
            cursor.execute("SELECT menu_name FROM menu_names WHERE menu_code = %s", (menu_code,))
            menu_result = cursor.fetchone()
            menu_name = menu_result[0] if menu_result else menu_code

            # 이미 대기중인 신청이 있는지 확인
            cursor.execute("""
                SELECT id FROM permission_requests
                WHERE login_id = %s AND menu_code = %s AND status = 'pending'
            """, (login_id, menu_code))

            if cursor.fetchone():
                cursor.close()
                conn.close()
                return jsonify({'error': '이미 대기중인 신청이 있습니다'}), 400

            # 신청 생성
            cursor.execute("""
                INSERT INTO permission_requests
                (login_id, user_name, deptid, dept_name, menu_code, menu_name,
                 permission_type, reason, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'pending')
                RETURNING id
            """, (login_id, user_name, deptid, dept_name, menu_code, menu_name,
                  permission_type, reason))

            request_id = cursor.fetchone()[0]
            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission request created: id={request_id}, user={login_id}, menu={menu_code}")
            return jsonify({
                'status': 'success',
                'message': '권한 신청이 완료되었습니다',
                'request_id': request_id
            })

        except Exception as e:
            logger.error(f"Error creating permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 신청 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests', methods=['GET'])
    def get_permission_requests():
        """권한 신청 목록 조회"""
        try:
            status = request.args.get('status', 'pending')  # pending, approved, rejected, all
            page = int(request.args.get('page', 1))
            size = int(request.args.get('size', 50))
            offset = (page - 1) * size

            conn = get_db_connection()
            cursor = conn.cursor()

            # WHERE 조건 구성
            where_clause = "WHERE is_active = true"
            params = []

            if status != 'all':
                where_clause += " AND status = %s"
                params.append(status)

            # 전체 카운트
            cursor.execute(f"""
                SELECT COUNT(*) FROM permission_requests {where_clause}
            """, params)
            total = cursor.fetchone()[0]

            # 데이터 조회
            params.extend([size, offset])
            cursor.execute(f"""
                SELECT
                    id, login_id, user_name, deptid, dept_name,
                    menu_code, menu_name, permission_type, reason,
                    status, created_at, reviewed_by, reviewed_at, review_comment
                FROM permission_requests
                {where_clause}
                ORDER BY created_at DESC
                LIMIT %s OFFSET %s
            """, params)

            rows = cursor.fetchall()
            requests = []

            for row in rows:
                requests.append({
                    'id': row[0],
                    'login_id': row[1],
                    'user_name': row[2],
                    'deptid': row[3],
                    'dept_name': row[4],
                    'menu_code': row[5],
                    'menu_name': row[6],
                    'permission_type': row[7],
                    'reason': row[8],
                    'status': row[9],
                    'created_at': row[10].isoformat() if row[10] else None,
                    'reviewed_by': row[11],
                    'reviewed_at': row[12].isoformat() if row[12] else None,
                    'review_comment': row[13]
                })

            cursor.close()
            conn.close()

            return jsonify({
                'data': requests,
                'total': total,
                'page': page,
                'size': size
            })

        except Exception as e:
            logger.error(f"Error getting permission requests: {e}")
            return jsonify({
                'error': '권한 신청 목록 조회 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/<int:request_id>/approve', methods=['POST'])
    def approve_permission_request(request_id):
        """권한 신청 승인"""
        try:
            data = request.json
            reviewer_id = session.get('user_id')
            review_comment = data.get('comment', '')

            if not reviewer_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            conn = get_db_connection()
            cursor = conn.cursor()

            # 신청 정보 조회
            cursor.execute("""
                SELECT login_id, menu_code, permission_type, status
                FROM permission_requests
                WHERE id = %s AND is_active = true
            """, (request_id,))

            request_info = cursor.fetchone()
            if not request_info:
                cursor.close()
                conn.close()
                return jsonify({'error': '신청을 찾을 수 없습니다'}), 404

            login_id, menu_code, permission_type, status = request_info

            if status != 'pending':
                cursor.close()
                conn.close()
                return jsonify({'error': '이미 처리된 신청입니다'}), 400

            # 권한 부여 - read_write인 경우 읽기/쓰기 모두 3, read인 경우 읽기만 3
            read_level = 3
            write_level = 3 if permission_type == 'read_write' else 0

            # 사용자 권한 업데이트 (UPSERT)
            cursor.execute("""
                INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, granted_by, is_active)
                VALUES (%s, %s, %s, %s, %s, true)
                ON CONFLICT (login_id, menu_code)
                DO UPDATE SET
                    read_level = GREATEST(user_menu_permissions.read_level, EXCLUDED.read_level),
                    write_level = GREATEST(user_menu_permissions.write_level, EXCLUDED.write_level),
                    updated_at = CURRENT_TIMESTAMP,
                    granted_by = EXCLUDED.granted_by
            """, (login_id, menu_code, read_level, write_level, reviewer_id))

            # 신청 상태 업데이트
            cursor.execute("""
                UPDATE permission_requests
                SET status = 'approved',
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_comment = %s
                WHERE id = %s
            """, (reviewer_id, review_comment, request_id))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission request approved: id={request_id}, user={login_id}, menu={menu_code}")
            return jsonify({
                'status': 'success',
                'message': '권한 신청이 승인되었습니다'
            })

        except Exception as e:
            logger.error(f"Error approving permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 승인 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/<int:request_id>/reject', methods=['POST'])
    def reject_permission_request(request_id):
        """권한 신청 거절"""
        try:
            data = request.json
            reviewer_id = session.get('user_id')
            review_comment = data.get('comment', '')

            if not reviewer_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            if not review_comment:
                return jsonify({'error': '거절 사유를 입력해주세요'}), 400

            conn = get_db_connection()
            cursor = conn.cursor()

            # 신청 상태 확인
            cursor.execute("""
                SELECT status FROM permission_requests
                WHERE id = %s AND is_active = true
            """, (request_id,))

            result = cursor.fetchone()
            if not result:
                cursor.close()
                conn.close()
                return jsonify({'error': '신청을 찾을 수 없습니다'}), 404

            if result[0] != 'pending':
                cursor.close()
                conn.close()
                return jsonify({'error': '이미 처리된 신청입니다'}), 400

            # 신청 거절
            cursor.execute("""
                UPDATE permission_requests
                SET status = 'rejected',
                    reviewed_by = %s,
                    reviewed_at = CURRENT_TIMESTAMP,
                    review_comment = %s
                WHERE id = %s
            """, (reviewer_id, review_comment, request_id))

            conn.commit()
            cursor.close()
            conn.close()

            logger.info(f"Permission request rejected: id={request_id}")
            return jsonify({
                'status': 'success',
                'message': '권한 신청이 거절되었습니다'
            })

        except Exception as e:
            logger.error(f"Error rejecting permission request: {e}")
            if conn:
                conn.rollback()
            return jsonify({
                'error': '권한 거절 실패',
                'message': str(e)
            }), 500

    @app.route('/api/permission-requests/my', methods=['GET'])
    def get_my_permission_requests():
        """내 권한 신청 내역 조회"""
        try:
            login_id = session.get('user_id')
            if not login_id:
                return jsonify({'error': '로그인이 필요합니다'}), 401

            conn = get_db_connection()
            cursor = conn.cursor()

            cursor.execute("""
                SELECT
                    id, menu_code, menu_name, permission_type, reason,
                    status, created_at, reviewed_by, reviewed_at, review_comment
                FROM permission_requests
                WHERE login_id = %s AND is_active = true
                ORDER BY created_at DESC
            """, (login_id,))

            rows = cursor.fetchall()
            requests = []

            for row in rows:
                requests.append({
                    'id': row[0],
                    'menu_code': row[1],
                    'menu_name': row[2],
                    'permission_type': row[3],
                    'reason': row[4],
                    'status': row[5],
                    'created_at': row[6].isoformat() if row[6] else None,
                    'reviewed_by': row[7],
                    'reviewed_at': row[8].isoformat() if row[8] else None,
                    'review_comment': row[9]
                })

            cursor.close()
            conn.close()

            return jsonify({'data': requests})

        except Exception as e:
            logger.error(f"Error getting my permission requests: {e}")
            return jsonify({
                'error': '내 신청 내역 조회 실패',
                'message': str(e)
            }), 500