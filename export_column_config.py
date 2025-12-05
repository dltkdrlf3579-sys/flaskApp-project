#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Column Config 설정을 JSON으로 내보내기
개발환경의 설정을 운영환경으로 이관할 때 사용
"""

import json
import os
from datetime import datetime
from database_config import get_db_connection

def export_column_configs():
    conn = get_db_connection()
    cursor = conn.cursor()

    config_tables = [
        'full_process_column_config',
        'follow_sop_column_config',
        'safety_instruction_column_config',
        'accident_column_config',
        'change_request_column_config'
    ]

    export_data = {
        'export_date': datetime.now().isoformat(),
        'export_type': 'column_configs',
        'configs': {}
    }

    try:
        for table_name in config_tables:
            print(f"\n{table_name} 내보내기 중...")

            # 테이블 존재 확인
            cursor.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = %s
                )
            """, (table_name,))

            if not cursor.fetchone()[0]:
                print(f"  - {table_name} 테이블이 존재하지 않습니다. 건너뜁니다.")
                continue

            # 모든 컬럼 설정 가져오기 (삭제된 것 포함)
            cursor.execute(f"""
                SELECT
                    column_key, column_name, column_type, column_order,
                    is_active, is_required, is_deleted, column_span,
                    tab, input_type, list_item_type, default_value,
                    placeholder, description, validation_rules,
                    created_at, updated_at
                FROM {table_name}
                ORDER BY tab, column_order
            """)

            columns = cursor.fetchall()

            export_data['configs'][table_name] = []

            for col in columns:
                col_data = {
                    'column_key': col[0],
                    'column_name': col[1],
                    'column_type': col[2],
                    'column_order': col[3],
                    'is_active': col[4],
                    'is_required': col[5],
                    'is_deleted': col[6],
                    'column_span': col[7],
                    'tab': col[8],
                    'input_type': col[9],
                    'list_item_type': col[10],
                    'default_value': col[11],
                    'placeholder': col[12],
                    'description': col[13],
                    'validation_rules': col[14],
                    'created_at': col[15].isoformat() if col[15] else None,
                    'updated_at': col[16].isoformat() if col[16] else None
                }
                export_data['configs'][table_name].append(col_data)

            print(f"  - {len(columns)}개 컬럼 설정 내보내기 완료")

        # JSON 파일로 저장
        output_file = f"column_configs_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"\n✅ 내보내기 완료: {output_file}")
        print(f"총 {len(export_data['configs'])}개 테이블 설정 내보내기 완료")

        # 섹션별 통계
        print("\n📊 섹션별 컬럼 통계:")
        for table_name, configs in export_data['configs'].items():
            print(f"\n{table_name}:")
            sections = {}
            for config in configs:
                if not config['is_deleted']:
                    tab = config['tab'] or 'default'
                    sections[tab] = sections.get(tab, 0) + 1
            for section, count in sorted(sections.items()):
                print(f"  - {section}: {count}개 컬럼")

        return output_file

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        return None
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    export_column_configs()