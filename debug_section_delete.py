#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
섹션 삭제 문제 디버깅
"""
import sys
import io

# UTF-8 encoding 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database_config import get_db_connection

def check_follow_sop_sections():
    """follow_sop_sections 테이블 상태 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("=" * 60)
    print("follow_sop_sections 테이블 현재 상태")
    print("=" * 60)

    # 모든 섹션 조회 (삭제된 것 포함)
    cursor.execute("""
        SELECT id, section_key, section_name, is_deleted
        FROM follow_sop_sections
        ORDER BY id
    """)

    sections = cursor.fetchall()

    print("\n모든 섹션:")
    for id, key, name, is_deleted in sections:
        status = "삭제됨" if is_deleted else "활성"
        print(f"  ID: {id}, Key: {key}, Name: {name} [{status}]")

    # 활성 섹션만 조회
    cursor.execute("""
        SELECT COUNT(*)
        FROM follow_sop_sections
        WHERE is_deleted = 0 OR is_deleted IS NULL
    """)

    active_count = cursor.fetchone()[0]
    print(f"\n활성 섹션 개수: {active_count}")

    cursor.close()
    conn.close()

def check_full_process_sections():
    """full_process_sections 테이블 상태 확인"""
    conn = get_db_connection()
    cursor = conn.cursor()

    print("\n" + "=" * 60)
    print("full_process_sections 테이블 현재 상태")
    print("=" * 60)

    # 모든 섹션 조회 (삭제된 것 포함)
    cursor.execute("""
        SELECT section_key, section_name, is_deleted
        FROM full_process_sections
        ORDER BY section_order
    """)

    sections = cursor.fetchall()

    print("\n모든 섹션:")
    for key, name, is_deleted in sections:
        status = "삭제됨" if is_deleted else "활성"
        print(f"  Key: {key}, Name: {name} [{status}]")

    # 활성 섹션만 조회
    cursor.execute("""
        SELECT COUNT(*)
        FROM full_process_sections
        WHERE is_deleted = 0 OR is_deleted IS NULL
    """)

    active_count = cursor.fetchone()[0]
    print(f"\n활성 섹션 개수: {active_count}")

    cursor.close()
    conn.close()

def test_delete_section():
    """섹션 삭제 테스트"""
    from section_service import SectionConfigService

    print("\n" + "=" * 60)
    print("섹션 삭제 로직 테스트")
    print("=" * 60)

    # follow_sop 테스트
    service = SectionConfigService('follow_sop', None)

    conn = get_db_connection()
    cursor = conn.cursor()

    # 테스트용 섹션 추가
    cursor.execute("""
        INSERT INTO follow_sop_sections (section_key, section_name, section_order, is_active, is_deleted)
        VALUES ('test_section_1', '테스트섹션1', 100, 1, 0)
    """)
    conn.commit()

    # 방금 추가한 섹션의 ID 가져오기
    cursor.execute("""
        SELECT id FROM follow_sop_sections
        WHERE section_key = 'test_section_1'
        ORDER BY id DESC
        LIMIT 1
    """)
    test_id = cursor.fetchone()[0]

    print(f"\n테스트 섹션 추가됨 - ID: {test_id}")

    # 삭제 전 상태
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE is_deleted = 0")
    before_count = cursor.fetchone()[0]
    print(f"삭제 전 활성 섹션 개수: {before_count}")

    # 섹션 삭제
    result = service.delete_section(test_id)
    print(f"삭제 결과: {result}")

    # 삭제 후 상태
    cursor.execute("SELECT COUNT(*) FROM follow_sop_sections WHERE is_deleted = 0")
    after_count = cursor.fetchone()[0]
    print(f"삭제 후 활성 섹션 개수: {after_count}")

    # 실제로 삭제된 섹션 확인
    cursor.execute("""
        SELECT id, section_key, is_deleted
        FROM follow_sop_sections
        WHERE is_deleted = 1
    """)
    deleted = cursor.fetchall()

    print("\n삭제된 섹션들:")
    for id, key, is_deleted in deleted:
        print(f"  ID: {id}, Key: {key}")

    # 문제 진단
    if after_count < before_count - 1:
        print("\n❌ 문제 발견: 여러 섹션이 삭제됨!")
        print(f"   예상: {before_count - 1}, 실제: {after_count}")
    elif after_count == before_count:
        print("\n❌ 문제 발견: 섹션이 삭제되지 않음!")
    else:
        print("\n✅ 정상: 하나의 섹션만 삭제됨")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    check_follow_sop_sections()
    check_full_process_sections()
    test_delete_section()