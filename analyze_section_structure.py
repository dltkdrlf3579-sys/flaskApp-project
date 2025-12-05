#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
섹션 테이블 구조 분석 및 section_key 충돌 확인
"""
import sys
import io

# UTF-8 encoding 설정
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from database_config import get_db_connection

def analyze_section_structure():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # 모든 섹션 관련 테이블 확인
        print("=" * 60)
        print("섹션 관련 테이블 목록")
        print("=" * 60)

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND (table_name LIKE %s OR table_name LIKE %s)
            ORDER BY table_name
        """, ('%section%', '%_sections'))

        tables = cursor.fetchall()
        section_tables = []

        for table in tables:
            table_name = table[0]
            print(f"  - {table_name}")
            if '_sections' in table_name or table_name == 'section_config':
                section_tables.append(table_name)

        # 각 테이블의 구조 확인
        print("\n" + "=" * 60)
        print("각 테이블 구조 및 데이터 분석")
        print("=" * 60)

        for table_name in section_tables:
            print(f"\n### {table_name} ###")

            # 컬럼 구조
            cursor.execute("""
                SELECT column_name, data_type
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))

            columns = cursor.fetchall()
            print("  컬럼 구조:")
            for col in columns[:8]:  # 주요 컬럼만 표시
                print(f"    - {col[0]}: {col[1]}")

            # 데이터 샘플
            try:
                cursor.execute(f'SELECT COUNT(*) FROM {table_name}')
                count = cursor.fetchone()[0]
                print(f"  총 데이터 개수: {count}")

                # section_key가 있는 테이블에서 커스텀 섹션 확인
                col_names = [col[0] for col in columns]
                if 'section_key' in col_names:
                    # 모든 커스텀 섹션 확인
                    cursor.execute(f"""
                        SELECT section_key, section_name
                        FROM {table_name}
                        WHERE section_key LIKE %s
                        ORDER BY section_key
                    """, ('custom_section_%',))

                    customs = cursor.fetchall()
                    if customs:
                        print(f"  커스텀 섹션 ({len(customs)}개):")
                        for custom in customs:
                            print(f"    - {custom[0]}: {custom[1]}")

                    # board_type 컬럼이 있는지 확인
                    if 'board_type' in col_names:
                        cursor.execute(f"""
                            SELECT DISTINCT board_type
                            FROM {table_name}
                            WHERE board_type IS NOT NULL
                        """)
                        board_types = cursor.fetchall()
                        if board_types:
                            print("  board_type 값:")
                            for bt in board_types:
                                print(f"    - {bt[0]}")

            except Exception as e:
                print(f"  데이터 조회 실패: {e}")

        # section_key 충돌 분석
        print("\n" + "=" * 60)
        print("section_key 충돌 분석")
        print("=" * 60)

        # section_config 테이블에서 중복 section_key 확인
        if 'section_config' in [t[0] for t in tables]:
            cursor.execute("""
                SELECT section_key, COUNT(*) as cnt
                FROM section_config
                GROUP BY section_key
                HAVING COUNT(*) > 1
                ORDER BY cnt DESC, section_key
            """)

            duplicates = cursor.fetchall()
            if duplicates:
                print("\n❌ section_config 테이블에 중복된 section_key 발견:")
                for dup in duplicates:
                    print(f"  - {dup[0]}: {dup[1]}개")

                    # 어떤 board_type에서 중복되는지 확인
                    cursor.execute("""
                        SELECT section_key, section_name, board_type
                        FROM section_config
                        WHERE section_key = %s
                    """, (dup[0],))

                    details = cursor.fetchall()
                    for detail in details:
                        print(f"      → {detail[2]}: {detail[1]}")
            else:
                print("\n✅ section_config 테이블에 중복된 section_key 없음")

        # 각 board별 sections 테이블 분석
        board_sections = ['follow_sop_sections', 'full_process_sections',
                         'accident_sections', 'safety_instruction_sections']

        print("\n" + "=" * 60)
        print("각 보드별 섹션 테이블 분석")
        print("=" * 60)

        all_sections = {}
        for table_name in board_sections:
            if table_name in [t[0] for t in tables]:
                board_name = table_name.replace('_sections', '')

                cursor.execute(f"""
                    SELECT section_key, section_name
                    FROM {table_name}
                    WHERE section_key LIKE %s
                    ORDER BY section_key
                """, ('custom_section_%',))

                sections = cursor.fetchall()
                print(f"\n{board_name}:")

                for sec_key, sec_name in sections:
                    print(f"  - {sec_key}: {sec_name}")

                    # 전역 딕셔너리에 추가하여 충돌 확인
                    if sec_key not in all_sections:
                        all_sections[sec_key] = []
                    all_sections[sec_key].append(board_name)

        # 충돌 분석
        print("\n" + "=" * 60)
        print("🔍 section_key 충돌 결과")
        print("=" * 60)

        conflicts = {k: v for k, v in all_sections.items() if len(v) > 1}
        if conflicts:
            print("\n❌ 다음 section_key가 여러 보드에서 사용됨:")
            for sec_key, boards in conflicts.items():
                print(f"  - {sec_key}: {', '.join(boards)}")
        else:
            print("\n✅ 보드별 섹션 테이블 간 section_key 충돌 없음")

    except Exception as e:
        print(f"오류 발생: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    analyze_section_structure()