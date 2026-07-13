#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
권한 시스템 데이터베이스 초기화 스크립트
권한 테이블 생성 및 초기 데이터 설정
"""

import os
import sys
from db_connection import get_db_connection
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def check_tables_exist(cursor):
    """권한 테이블 존재 여부 확인"""
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN ('user_menu_permissions', 'dept_menu_roles', 'permission_levels')
    """)
    existing_tables = [row[0] for row in cursor.fetchall()]
    return existing_tables

def backup_old_tables(cursor, conn):
    """기존 테이블이 있으면 백업"""
    old_tables = ['user_menu_permissions_old', 'dept_menu_roles_old']

    # 이미 백업된 테이블 확인
    cursor.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_name IN %s
    """, (tuple(old_tables),))

    existing_backups = [row[0] for row in cursor.fetchall()]

    if existing_backups:
        logger.info(f"✅ 백업 테이블이 이미 존재합니다: {existing_backups}")
        return True

    # 기존 테이블 백업 (SQL 파일에 이미 포함되어 있음)
    return False

def create_permission_tables(cursor, conn):
    """권한 테이블 생성"""
    sql_file = 'create_new_permission_tables.sql'

    if not os.path.exists(sql_file):
        logger.error(f"❌ SQL 파일을 찾을 수 없습니다: {sql_file}")
        return False

    try:
        with open(sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # SQL 내용을 개별 명령으로 분리
        sql_commands = []
        current_command = ""
        in_function = False
        in_do_block = False

        for line in sql_content.split('\n'):
            # DO 블록 시작/종료 체크
            if line.strip().startswith('DO $$'):
                in_do_block = True

            # 함수 정의 시작 체크
            if 'CREATE OR REPLACE FUNCTION' in line or 'CREATE FUNCTION' in line:
                in_function = True

            current_command += line + '\n'

            # DO 블록 종료
            if in_do_block and line.strip() == 'END$$;':
                in_do_block = False
                sql_commands.append(current_command.strip())
                current_command = ""
                continue

            # 함수 종료
            if in_function and line.strip() == '$$ LANGUAGE plpgsql;':
                in_function = False
                sql_commands.append(current_command.strip())
                current_command = ""
                continue

            # 일반 SQL 명령 처리 (DO 블록이나 함수 내부가 아닐 때)
            if not in_function and not in_do_block and line.strip().endswith(';') and not line.strip().startswith('--'):
                if current_command.strip():
                    sql_commands.append(current_command.strip())
                current_command = ""

        # 각 명령 실행
        for i, command in enumerate(sql_commands, 1):
            if command.strip() and not command.strip().startswith('--'):
                try:
                    cursor.execute(command)
                    logger.info(f"✅ SQL 명령 {i}/{len(sql_commands)} 실행 완료")
                except Exception as e:
                    if "already exists" in str(e):
                        logger.warning(f"⚠️ 이미 존재하는 객체 (건너뜀): {str(e)[:100]}")
                    else:
                        logger.error(f"❌ SQL 명령 {i} 실행 실패: {e}")
                        raise

        conn.commit()
        logger.info("✅ 모든 권한 테이블이 성공적으로 생성되었습니다!")
        return True

    except Exception as e:
        logger.error(f"❌ 테이블 생성 중 오류 발생: {e}")
        conn.rollback()
        return False

def insert_sample_data(cursor, conn):
    """샘플 데이터 삽입 (테스트용)"""
    try:
        # 샘플 사용자 권한 추가
        sample_permissions = [
            ('admin', 'ACCIDENT_MGT', 3, 3),  # 관리자: 전체 권한
            ('admin', 'VENDOR_MGT', 3, 3),
            ('admin', 'CORRECTIVE_ACTION', 3, 3),
            ('test_user', 'ACCIDENT_MGT', 1, 1),  # 일반 사용자: 본인 권한만
            ('test_user', 'VENDOR_MGT', 1, 0),    # 조회만 가능
        ]

        for login_id, menu_code, read_level, write_level in sample_permissions:
            cursor.execute("""
                INSERT INTO user_menu_permissions
                    (login_id, menu_code, read_level, write_level, granted_by)
                VALUES (%s, %s, %s, %s, 'system')
                ON CONFLICT (login_id, menu_code) DO UPDATE SET
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    updated_at = CURRENT_TIMESTAMP
            """, (login_id, menu_code, read_level, write_level))

        # 샘플 부서 권한 추가
        sample_dept_permissions = [
            ('ENV_SAFETY', None, None, 'ACCIDENT_MGT', 2, 2),  # 환경안전팀: 부서 권한
            ('ENV_SAFETY', None, None, 'VENDOR_MGT', 2, 1),
            ('QA_TEAM', None, None, 'CORRECTIVE_ACTION', 2, 2),
        ]

        for dept_id, dept_code, dept_path, menu_code, read_level, write_level in sample_dept_permissions:
            cursor.execute("""
                INSERT INTO dept_menu_roles
                    (dept_id, dept_code, dept_full_path, menu_code, read_level, write_level, granted_by)
                VALUES (%s, %s, %s, %s, %s, %s, 'system')
                ON CONFLICT (dept_id, menu_code) DO UPDATE SET
                    read_level = EXCLUDED.read_level,
                    write_level = EXCLUDED.write_level,
                    updated_at = CURRENT_TIMESTAMP
            """, (dept_id, dept_code, dept_path, menu_code, read_level, write_level))

        conn.commit()
        logger.info("✅ 샘플 데이터 삽입 완료!")
        return True

    except Exception as e:
        logger.error(f"❌ 샘플 데이터 삽입 실패: {e}")
        conn.rollback()
        return False

def verify_tables(cursor):
    """테이블 생성 검증"""
    required_tables = ['user_menu_permissions', 'dept_menu_roles', 'permission_levels']

    for table in required_tables:
        cursor.execute("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = %s
        """, (table,))

        if cursor.fetchone()[0] == 0:
            logger.error(f"❌ 테이블이 생성되지 않았습니다: {table}")
            return False

        # 각 테이블의 레코드 수 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        logger.info(f"✅ {table}: {count}개 레코드")

    # 함수 존재 확인
    cursor.execute("""
        SELECT COUNT(*) FROM pg_proc
        WHERE proname IN ('check_data_permission', 'can_read_data', 'can_write_data')
    """)
    func_count = cursor.fetchone()[0]
    logger.info(f"✅ 생성된 함수 개수: {func_count}/3")

    return True

def main():
    """메인 실행 함수"""
    logger.info("=" * 50)
    logger.info("🚀 권한 시스템 데이터베이스 초기화 시작")
    logger.info("=" * 50)

    try:
        # 데이터베이스 연결
        conn = get_db_connection()
        cursor = conn.cursor()
        logger.info("✅ 데이터베이스 연결 성공")

        # 기존 테이블 확인
        existing_tables = check_tables_exist(cursor)
        if existing_tables:
            logger.info(f"ℹ️ 기존 테이블 발견: {existing_tables}")
            # 자동으로 진행 (기존 테이블이 있어도 CREATE IF NOT EXISTS 방식으로 처리)
            logger.info("✅ 기존 테이블 유지하고 필요한 부분만 업데이트합니다.")

        # 테이블 생성
        if create_permission_tables(cursor, conn):
            logger.info("✅ 권한 테이블 생성 완료")

            # 샘플 데이터 자동 삽입
            logger.info("📝 샘플 데이터를 삽입합니다...")
            insert_sample_data(cursor, conn)

            # 검증
            if verify_tables(cursor):
                logger.info("=" * 50)
                logger.info("🎉 권한 시스템 초기화 완료!")
                logger.info("=" * 50)
            else:
                logger.warning("⚠️ 일부 테이블 검증 실패")

        cursor.close()
        conn.close()

    except Exception as e:
        logger.error(f"❌ 초기화 실패: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()