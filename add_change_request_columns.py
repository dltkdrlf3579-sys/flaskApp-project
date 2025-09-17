#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
기준정보 변경요청 테이블에 컬럼 추가
"""

import psycopg2
from psycopg2 import sql

def add_columns():
    conn = psycopg2.connect(
        "postgresql://postgres:admin123@localhost:5432/portal_dev"
    )
    cursor = conn.cursor()

    try:
        # 1. 현재 테이블 구조 확인
        print("1. 현재 테이블 구조:")
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'partner_change_requests'
            ORDER BY ordinal_position
        """)

        existing_columns = cursor.fetchall()
        for col in existing_columns:
            print(f"   - {col[0]}: {col[1]}")

        # 2. other_info 컬럼 추가
        print("\n2. other_info 컬럼 추가 중...")
        try:
            cursor.execute("""
                ALTER TABLE partner_change_requests
                ADD COLUMN other_info TEXT
            """)
            print("   ✓ other_info 컬럼 추가됨")
        except psycopg2.errors.DuplicateColumn:
            print("   - other_info 컬럼이 이미 존재함")
            conn.rollback()

        # 3. final_check_date 컬럼 추가
        print("\n3. final_check_date 컬럼 추가 중...")
        try:
            cursor.execute("""
                ALTER TABLE partner_change_requests
                ADD COLUMN final_check_date DATE
            """)
            print("   ✓ final_check_date 컬럼 추가됨")
        except psycopg2.errors.DuplicateColumn:
            print("   - final_check_date 컬럼이 이미 존재함")
            conn.rollback()

        # 4. 캐시 테이블도 확인 (있다면)
        print("\n4. 캐시 테이블 확인...")
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'change_requests_cache'
        """)

        if cursor.fetchone():
            print("   캐시 테이블 발견, 컬럼 추가...")

            try:
                cursor.execute("""
                    ALTER TABLE change_requests_cache
                    ADD COLUMN other_info TEXT
                """)
                print("   ✓ 캐시 테이블에 other_info 추가됨")
            except psycopg2.errors.DuplicateColumn:
                print("   - 캐시 테이블에 other_info가 이미 존재함")
                conn.rollback()

            try:
                cursor.execute("""
                    ALTER TABLE change_requests_cache
                    ADD COLUMN final_check_date DATE
                """)
                print("   ✓ 캐시 테이블에 final_check_date 추가됨")
            except psycopg2.errors.DuplicateColumn:
                print("   - 캐시 테이블에 final_check_date가 이미 존재함")
                conn.rollback()
        else:
            print("   캐시 테이블 없음")

        # 5. 최종 확인
        print("\n5. 최종 컬럼 확인:")
        cursor.execute("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'partner_change_requests'
                AND column_name IN ('other_info', 'final_check_date')
        """)

        new_columns = cursor.fetchall()
        for col in new_columns:
            print(f"   ✓ {col[0]}: {col[1]}")

        # 6. 샘플 데이터 확인
        print("\n6. 샘플 데이터:")
        cursor.execute("""
            SELECT id, other_info, final_check_date
            FROM partner_change_requests
            LIMIT 3
        """)

        samples = cursor.fetchall()
        for row in samples:
            print(f"   ID {row[0]}: other_info={row[1]}, final_check_date={row[2]}")

        conn.commit()
        print("\n✅ 컬럼 추가 완료!")

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        conn.rollback()

    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    add_columns()