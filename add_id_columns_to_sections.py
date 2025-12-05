#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
follow_sop_sections와 full_process_sections 테이블에 ID 컬럼 추가
"""
import sys
import io

# UTF-8 encoding 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database_config import get_db_connection

def add_id_columns():
    """ID 컬럼 추가"""
    conn = get_db_connection()
    cursor = conn.cursor()

    tables = ['follow_sop_sections', 'full_process_sections']

    for table in tables:
        print(f"\n{'='*60}")
        print(f"📋 {table} 테이블 처리")
        print('='*60)

        try:
            # 1. 현재 구조 확인
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'id'
            """, (table,))

            if cursor.fetchone():
                print(f"✅ 이미 ID 컬럼이 존재합니다")
                continue

            # 2. ID 컬럼 추가 (AUTO INCREMENT)
            print(f"🔧 ID 컬럼 추가 중...")

            # PostgreSQL 방식
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # SERIAL 타입으로 추가
                cursor.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN id SERIAL
                """)
            else:
                # SQLite 방식
                # SQLite는 ALTER TABLE로 AUTOINCREMENT 추가가 복잡하므로
                # 테이블 재생성이 필요할 수 있음

                # 현재 최대값 찾기
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]

                # 임시 ID 컬럼 추가
                cursor.execute(f"""
                    ALTER TABLE {table}
                    ADD COLUMN id INTEGER
                """)

                # 기존 데이터에 순차적으로 ID 할당
                cursor.execute(f"SELECT section_key FROM {table} ORDER BY section_order")
                rows = cursor.fetchall()

                for idx, (section_key,) in enumerate(rows, 1):
                    cursor.execute(f"""
                        UPDATE {table}
                        SET id = %s
                        WHERE section_key = %s
                    """, (idx, section_key))

            conn.commit()
            print(f"✅ ID 컬럼 추가 완료")

            # 3. 데이터 확인
            cursor.execute(f"""
                SELECT id, section_key, section_name
                FROM {table}
                ORDER BY id
                LIMIT 5
            """)

            results = cursor.fetchall()
            print(f"\n📊 샘플 데이터:")
            for row in results:
                print(f"  ID: {row[0]}, Key: {row[1]}, Name: {row[2]}")

            # 4. Primary Key 확인 (정보용)
            cursor.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s
                    AND tc.constraint_type = 'PRIMARY KEY'
            """, (table,))

            pk = cursor.fetchall()
            if pk:
                print(f"\n🔑 현재 PRIMARY KEY: {', '.join([p[0] for p in pk])}")
                print(f"   (section_key는 그대로 PRIMARY KEY로 유지)")

        except Exception as e:
            print(f"❌ 오류 발생: {e}")
            conn.rollback()

    cursor.close()
    conn.close()

def test_deletion():
    """삭제 테스트"""
    print(f"\n{'='*60}")
    print("🧪 삭제 기능 테스트")
    print('='*60)

    from section_service import SectionConfigService

    # follow_sop 테스트
    service = SectionConfigService('follow_sop', None)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 테스트용 섹션 추가
    print("\n1️⃣ 테스트 섹션 추가")
    cursor.execute("""
        INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active, is_deleted)
        VALUES ('test_delete', '삭제테스트', 999, 1, 0)
        RETURNING id
    """)

    test_id = cursor.fetchone()[0]
    conn.commit()
    print(f"   테스트 섹션 추가됨 (ID: {test_id})")

    # 삭제 전 개수
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE is_deleted = 0")
    before_count = cursor.fetchone()[0]
    print(f"\n2️⃣ 삭제 전 활성 섹션 수: {before_count}")

    # 섹션 삭제 시도
    print(f"\n3️⃣ ID {test_id} 삭제 시도...")
    result = service.delete_section(test_id)

    if result['success']:
        print("   ✅ 삭제 성공")
    else:
        print(f"   ❌ 삭제 실패: {result.get('error')}")

    # 삭제 후 개수
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE is_deleted = 0")
    after_count = cursor.fetchone()[0]
    print(f"\n4️⃣ 삭제 후 활성 섹션 수: {after_count}")

    if after_count == before_count - 1:
        print("\n✅ 정상 작동: 하나의 섹션만 삭제됨")
    elif after_count < before_count - 1:
        print(f"\n❌ 문제: 여러 섹션이 삭제됨 ({before_count - after_count}개)")
    else:
        print("\n❌ 문제: 섹션이 삭제되지 않음")

    # 정리 - 테스트 섹션 완전 삭제
    cursor.execute("DELETE FROM follow_sop_sections WHERE section_key = 'test_delete'")
    conn.commit()

    cursor.close()
    conn.close()

if __name__ == "__main__":
    print("🚀 섹션 테이블 ID 컬럼 추가 시작")
    add_id_columns()
    test_deletion()
    print("\n✅ 완료!")