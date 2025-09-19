#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
간단한 권한 시스템 데이터베이스 초기화
"""

import psycopg2
from db_connection import get_db_connection

def main():
    print("[START] Permission system database initialization...")

    try:
        # 데이터베이스 연결
        conn = get_db_connection()
        cursor = conn.cursor()
        print("[OK] Database connection successful")

        # SQL 파일 실행
        with open('create_new_permission_tables.sql', 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # psycopg2로 직접 실행 (세미콜론으로 분리된 명령들 처리)
        # psycopg2는 여러 명령을 한 번에 실행할 수 있음
        cursor.execute(sql_content)
        conn.commit()

        print("[OK] Permission tables created successfully!")

        # 검증
        cursor.execute("""
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('user_menu_permissions', 'dept_menu_roles', 'permission_levels')
        """)
        tables = [row[0] for row in cursor.fetchall()]
        print(f"[OK] Created tables: {tables}")

        # 레코드 수 확인
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  - {table}: {count}개 레코드")

        cursor.close()
        conn.close()
        print("[DONE] Initialization complete!")

    except Exception as e:
        print(f"[ERROR] Error occurred: {e}")
        if conn:
            conn.rollback()

if __name__ == "__main__":
    main()