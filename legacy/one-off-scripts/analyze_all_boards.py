#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
모든 게시판 섹션/컬럼 구성 분석
"""

import psycopg2
from tabulate import tabulate

def analyze_all_boards():
    conn = psycopg2.connect("postgresql://postgres:admin123@localhost:5432/portal_dev")
    cursor = conn.cursor()

    boards = [
        ('follow_sop', 'Follow SOP'),
        ('full_process', 'Full Process'),
        ('safety_instruction', 'Safety Instruction'),
        ('accident', 'Accident'),
        ('change_request', 'Change Request'),
        ('partner_change_requests', 'Partner Change Requests')
    ]

    print("="*100)
    print("전체 게시판 섹션/컬럼 구성 분석 리포트")
    print("="*100)

    all_issues = []

    for board_key, board_name in boards:
        print(f"\n{'='*50}")
        print(f"[{board_name}] ({board_key})")
        print(f"{'='*50}")

        issues = []

        # 1. 섹션 테이블 확인
        sections_table = f"{board_key}_sections"
        columns_table = f"{board_key}_column_config"

        # 섹션 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (sections_table,))

        if not cursor.fetchone()[0]:
            print(f"  [ERROR] 섹션 테이블 없음: {sections_table}")
            issues.append(f"섹션 테이블 없음: {sections_table}")
            continue

        # 컬럼 테이블 존재 확인
        cursor.execute("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_name = %s
            )
        """, (columns_table,))

        if not cursor.fetchone()[0]:
            print(f"  [ERROR] 컬럼 설정 테이블 없음: {columns_table}")
            issues.append(f"컬럼 설정 테이블 없음: {columns_table}")
            continue

        # 2. 섹션 정보 조회
        print(f"\n  [섹션 구성]")

        # 컬럼 존재 확인
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
        """, (sections_table,))

        columns = [col[0] for col in cursor.fetchall()]

        # display_order 또는 section_order 사용
        order_col = 'display_order' if 'display_order' in columns else 'section_order'

        cursor.execute(f"""
            SELECT section_key, section_name,
                   {order_col} as order_num,
                   is_active
            FROM {sections_table}
            WHERE is_active = 1 OR is_active IS NULL
            ORDER BY {order_col}
        """)

        sections = cursor.fetchall()
        section_data = []
        active_sections = []

        for section in sections:
            status = "O" if section[3] else "X"
            section_data.append([section[0], section[1], section[2], status])
            if section[3]:
                active_sections.append(section[0])

        if section_data:
            print(tabulate(section_data,
                         headers=["Section Key", "Display Name", "Order", "Active"],
                         tablefmt="simple"))
        else:
            print("    섹션 없음")
            issues.append("섹션이 정의되지 않음")

        # 3. 각 섹션의 컬럼 수 확인
        print(f"\n  [섹션별 컬럼 수]")
        column_counts = []

        for section_key in active_sections:
            # tab 또는 table_group으로 확인
            cursor.execute(f"""
                SELECT COUNT(*)
                FROM {columns_table}
                WHERE (tab = %s OR table_group = %s)
                AND is_active = 1
            """, (section_key, section_key))

            count = cursor.fetchone()[0]
            column_counts.append([section_key, count])

            if count == 0:
                issues.append(f"빈 섹션: {section_key} (컬럼 0개)")

        if column_counts:
            print(tabulate(column_counts,
                         headers=["Section", "Column Count"],
                         tablefmt="simple"))

        # 4. 매핑되지 않은 컬럼 확인
        print(f"\n  [매핑 문제 확인]")

        # tab이 섹션 키와 맞지 않는 경우
        cursor.execute(f"""
            SELECT DISTINCT tab
            FROM {columns_table}
            WHERE tab IS NOT NULL
            AND tab NOT IN (
                SELECT section_key FROM {sections_table}
            )
        """)

        unmapped_tabs = cursor.fetchall()
        if unmapped_tabs:
            print(f"    매핑되지 않은 tab 값:")
            for tab in unmapped_tabs:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {columns_table}
                    WHERE tab = %s
                """, (tab[0],))
                count = cursor.fetchone()[0]
                print(f"      - {tab[0]}: {count}개 컬럼")
                issues.append(f"매핑 안된 tab: {tab[0]} ({count}개 컬럼)")

        # 5. 전체 통계
        cursor.execute(f"""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN is_active = 1 THEN 1 END) as active,
                COUNT(CASE WHEN is_active = 0 THEN 1 END) as inactive
            FROM {columns_table}
        """)

        stats = cursor.fetchone()
        print(f"\n  [전체 통계]")
        print(f"    - 총 컬럼: {stats[0]}개")
        print(f"    - 활성: {stats[1]}개")
        print(f"    - 비활성: {stats[2]}개")

        # 6. 이슈 요약
        if issues:
            print(f"\n  [발견된 이슈] {len(issues)}개")
            for issue in issues:
                print(f"    - {issue}")
            all_issues.append((board_name, issues))
        else:
            print(f"\n  [OK] 이슈 없음")

    # 전체 요약
    print("\n" + "="*100)
    print("[전체 요약]")
    print("="*100)

    if all_issues:
        print("\n[수정이 필요한 게시판]")
        for board_name, issues in all_issues:
            print(f"\n  {board_name}:")
            for issue in issues:
                print(f"    - {issue}")
    else:
        print("\n[OK] 모든 게시판 정상")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    analyze_all_boards()