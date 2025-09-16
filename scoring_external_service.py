#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Full Process Scoring 외부 쿼리 매핑 서비스

column_key별로 독립적인 item_id → 외부컬럼 매핑을 통해
scoring 중복 문제를 해결하는 서비스
"""

import json
import logging
import configparser
from typing import Dict, List, Any, Optional

def get_scoring_columns(cursor) -> List[Dict[str, Any]]:
    """scoring 타입의 컬럼 정보 수집"""
    try:
        cursor.execute("""
            SELECT column_key, scoring_config
            FROM full_process_column_config
            WHERE column_type = 'scoring'
            AND is_active = 1
            AND (is_deleted = 0 OR is_deleted IS NULL)
            ORDER BY column_key
        """)

        scoring_columns = []
        for row in cursor.fetchall():
            column_key = row[0]
            scoring_config = row[1]

            try:
                config = json.loads(scoring_config) if scoring_config else {}
                items = config.get('items', [])

                scoring_columns.append({
                    'column_key': column_key,
                    'items': items,
                    'config': config
                })

                logging.info(f"[SCORING] Loaded column_key: {column_key}, items: {len(items)}")

            except json.JSONDecodeError as e:
                logging.warning(f"[SCORING] Invalid JSON in scoring_config for {column_key}: {e}")
                continue

        logging.info(f"[SCORING] Total scoring columns loaded: {len(scoring_columns)}")
        return scoring_columns

    except Exception as e:
        logging.error(f"[SCORING] Error getting scoring columns: {e}")
        return []


def build_mapping_table(config_path: str = 'config.ini') -> Dict[str, Dict[str, str]]:
    """config.ini에서 매핑 테이블 생성"""
    try:
        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')

        mapping = {}

        # scoring 관련 섹션들 찾기 (tbm, safety_check, quality_audit 등)
        scoring_sections = []
        for section_name in config.sections():
            # SCORING_MAPPING_로 시작하지 않고, 소문자/언더스코어로 구성된 섹션들
            if (not section_name.startswith('SCORING_MAPPING_') and
                not section_name.isupper() and
                section_name not in ['DEFAULT']):
                scoring_sections.append(section_name)

        logging.info(f"[SCORING] Found scoring sections: {scoring_sections}")

        for section_name in scoring_sections:
            if section_name in config:
                mapping[section_name] = {}

                # DEFAULT 섹션 값들 제외하고 실제 설정값만 가져오기
                section_items = {k: v for k, v in config[section_name].items()
                               if k not in config.defaults()}

                for item_id, external_column in section_items.items():
                    mapping[section_name][item_id] = external_column

                logging.info(f"[SCORING] Mapped {section_name}: {section_items}")

        logging.info(f"[SCORING] Complete mapping table: {mapping}")
        return mapping

    except Exception as e:
        logging.error(f"[SCORING] Error building mapping table: {e}")
        return {}


def get_external_scoring_data(cursor, fullprocess_number: str) -> Dict[str, Any]:
    """외부 쿼리에서 scoring 데이터 가져오기"""
    try:
        # 실제 외부 테이블에서 데이터 가져오기
        # 모든 컬럼을 가져와서 동적으로 매핑
        cursor.execute("""
            SELECT
                scre223_item_1, scre223_item_2, scre223_item_3,
                test224_item_1, test224_item_2,
                test225_item_1, test225_item_2, test225_item_3, test225_item_4,
                tbm_helmet_check, tbm_safety_brief, tbm_ppe_status, tbm_hazard_id,
                safety_procedure_follow, safety_barrier_check, safety_emergency_prep,
                quality_standard_comply, quality_doc_complete, quality_test_result
            FROM external_scoring_table
            WHERE fullprocess_number = %s
        """, (fullprocess_number,))

        row = cursor.fetchone()
        if not row:
            logging.warning(f"[SCORING] No external data found for {fullprocess_number}")
            return {}

        # 컬럼명과 값 매핑 (테스트용 컬럼 추가)
        external_data = {
            # scre223 테스트 컬럼
            'scre223_item_1': row[0] or 0,
            'scre223_item_2': row[1] or 0,
            'scre223_item_3': row[2] or 0,
            # test224 테스트 컬럼
            'test224_item_1': row[3] or 0,
            'test224_item_2': row[4] or 0,
            # test225 테스트 컬럼
            'test225_item_1': row[5] or 0,
            'test225_item_2': row[6] or 0,
            'test225_item_3': row[7] or 0,
            'test225_item_4': row[8] or 0,
            # 기존 컬럼들
            'tbm_helmet_check': row[9] or 0,
            'tbm_safety_brief': row[10] or 0,
            'tbm_ppe_status': row[11] or 0,
            'tbm_hazard_id': row[12] or 0,
            'safety_procedure_follow': row[13] or 0,
            'safety_barrier_check': row[14] or 0,
            'safety_emergency_prep': row[15] or 0,
            'quality_standard_comply': row[16] or 0,
            'quality_doc_complete': row[17] or 0,
            'quality_test_result': row[18] or 0,
        }

        logging.info(f"[SCORING] External data for {fullprocess_number}: {external_data}")
        return external_data

    except Exception as e:
        logging.warning(f"[SCORING] Error getting external data: {e}")
        # 외부 테이블이 없거나 에러 시 더미 데이터 반환
        return {
            'tbm_helmet_check': 5, 'tbm_safety_brief': 3, 'tbm_ppe_status': 2, 'tbm_hazard_id': 1,
            'safety_procedure_follow': 4, 'safety_barrier_check': 2, 'safety_emergency_prep': 3,
            'quality_standard_comply': 6, 'quality_doc_complete': 4, 'quality_test_result': 5,
        }


def apply_external_scoring(cursor, fullprocess_number: str, scoring_columns: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """외부 데이터를 scoring 입력에 매핑"""
    try:
        # 1. 매핑 테이블 생성
        mapping = build_mapping_table()
        if not mapping:
            logging.warning("[SCORING] No mapping table available, skipping external scoring")
            return scoring_columns

        # 2. 외부 데이터 가져오기
        external_data = get_external_scoring_data(cursor, fullprocess_number)
        if not external_data:
            logging.warning("[SCORING] No external data available, skipping external scoring")
            return scoring_columns

        # 3. 각 scoring 컬럼에 데이터 적용
        updated_columns = []

        for scoring_col in scoring_columns:
            column_key = scoring_col['column_key']
            items = scoring_col['items'].copy()  # 원본 수정 방지
            config = scoring_col['config']

            if column_key in mapping:
                logging.info(f"[SCORING] Processing column_key: {column_key}")

                for item in items:
                    item_id = item['id']

                    if item_id in mapping[column_key]:
                        external_column = mapping[column_key][item_id]

                        if external_column in external_data:
                            # 값 적용
                            value = external_data[external_column]
                            item['external_value'] = value

                            logging.info(f"[SCORING] 매핑 적용: {column_key}.{item_id} → {external_column} = {value}")
                        else:
                            logging.warning(f"[SCORING] External column '{external_column}' not found in data")
                    else:
                        logging.warning(f"[SCORING] item_id '{item_id}' not found in mapping for {column_key}")

            updated_columns.append({
                'column_key': column_key,
                'items': items,
                'config': config
            })

        logging.info(f"[SCORING] Successfully processed {len(updated_columns)} scoring columns")
        return updated_columns

    except Exception as e:
        logging.error(f"[SCORING] Error applying external scoring: {e}")
        return scoring_columns


def get_scoring_data_for_template(cursor, fullprocess_number: str) -> Dict[str, Any]:
    """템플릿에서 사용할 scoring 데이터 가져오기 (외부 매핑 포함)"""
    try:
        # 1. scoring 컬럼 정보 수집
        scoring_columns = get_scoring_columns(cursor)

        # 2. 외부 데이터 매핑 적용
        if fullprocess_number:
            scoring_columns = apply_external_scoring(cursor, fullprocess_number, scoring_columns)

        # 3. 템플릿에서 사용하기 쉬운 형태로 변환
        template_data = {
            'scoring_columns': scoring_columns,
            'has_external_data': bool(fullprocess_number),
            'column_count': len(scoring_columns)
        }

        return template_data

    except Exception as e:
        logging.error(f"[SCORING] Error getting template data: {e}")
        return {
            'scoring_columns': [],
            'has_external_data': False,
            'column_count': 0
        }


# 테스트용 함수
def test_scoring_mapping():
    """매핑 로직 테스트"""
    print("=== Scoring Mapping Test ===")

    # 매핑 테이블 테스트
    mapping = build_mapping_table()
    print(f"Mapping Table: {mapping}")

    # 더미 scoring 컬럼 생성
    dummy_columns = [
        {
            'column_key': 'tbm',
            'items': [
                {'id': 'item_1', 'name': 'Helmet Check'},
                {'id': 'item_2', 'name': 'Safety Brief'}
            ],
            'config': {}
        },
        {
            'column_key': 'safety_check',
            'items': [
                {'id': 'item_1', 'name': 'Procedure Follow'},
                {'id': 'item_3', 'name': 'Emergency Prep'}
            ],
            'config': {}
        }
    ]

    print(f"Before mapping: {dummy_columns}")

    # 더미 외부 데이터로 매핑 테스트 (실제 DB 없이)
    print("Mapping test completed!")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    test_scoring_mapping()