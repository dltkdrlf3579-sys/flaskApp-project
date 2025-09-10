"""
안전한 UPSERT 유틸리티 - Phase 3
SQLite의 INSERT OR REPLACE를 PostgreSQL의 ON CONFLICT로 변환
"""
import logging
from typing import Dict, Any, List, Optional, Tuple
import sqlite3


# 테이블별 UPSERT 레지스트리
UPSERT_REGISTRY = {
    # 드롭다운 옵션 코드
    'dropdown_option_codes_v2': {
        'conflict_cols': ['board_type', 'column_key', 'option_code'],
        'update_cols': ['option_value', 'display_order', 'is_active', 'updated_at']
    },
    
    # 상세 정보 테이블들
    'safety_instruction_details': {
        'conflict_cols': ['issue_number'],
        'update_cols': ['detailed_content', 'updated_at']
    },
    'change_request_details': {
        'conflict_cols': ['request_number'], 
        'update_cols': ['detailed_content', 'updated_at']
    },
    'accident_details': {
        'conflict_cols': ['accident_number'],
        'update_cols': ['detailed_content', 'updated_at']
    },
    'partner_details': {
        'conflict_cols': ['business_number'],
        'update_cols': ['detailed_content', 'updated_at']
    },
    'followsop_details': {
        'conflict_cols': ['work_req_no'],
        'update_cols': ['detailed_content', 'updated_at']
    },
    'fullprocess_details': {
        'conflict_cols': ['fullprocess_number'],
        'update_cols': ['detailed_content', 'updated_at']
    },
    
    # 캐시 테이블들
    'partners_cache': {
        'conflict_cols': ['business_number'],
        'update_cols': ['company_name', 'partner_class', 'address']
    },
    'safety_instructions_cache': {
        'conflict_cols': ['issue_number'],
        'update_cols': ['detailed_content', 'custom_data', 'updated_at']
    },
    'followsop_cache': {
        'conflict_cols': ['work_req_no'],
        'update_cols': ['custom_data']
    },
    'fullprocess_cache': {
        'conflict_cols': ['fullprocess_number'],
        'update_cols': ['custom_data']
    },
    
    # 메인 테이블들
    'follow_sop': {
        'conflict_cols': ['work_req_no'],
        'update_cols': ['custom_data', 'is_deleted']
    },
    'full_process': {
        'conflict_cols': ['fullprocess_number'],
        'update_cols': ['custom_data', 'is_deleted']
    },
    
    # Sync 상태 테이블들
    'sync_state': {
        'conflict_cols': ['id'],
        'update_cols': ['last_full_sync']
    },
    'master_sync_state': {
        'conflict_cols': ['id'],
        'update_cols': ['last_master_sync']
    },
    'content_sync_state': {
        'conflict_cols': ['name'],
        'update_cols': ['first_sync_done', 'first_sync_at']
    },
    'safety_instructions_sync_history': {
        'conflict_cols': ['id'],
        'update_cols': ['first_sync_done', 'sync_date', 'record_count']
    }
}


def safe_upsert(conn, table: str, data: Dict[str, Any], 
                conflict_cols: Optional[List[str]] = None,
                update_cols: Optional[List[str]] = None) -> int:
    """
    안전한 UPSERT 함수
    
    Args:
        conn: CompatConnection 객체
        table: 테이블명
        data: 삽입/업데이트할 데이터 딕셔너리
        conflict_cols: 충돌 감지 컬럼들 (None이면 레지스트리에서 자동 조회)
        update_cols: 업데이트할 컬럼들 (None이면 레지스트리에서 자동 조회)
    
    Returns:
        int: 영향받은 행의 수
    """
    
    # 레지스트리에서 기본값 조회
    if conflict_cols is None or update_cols is None:
        registry_entry = UPSERT_REGISTRY.get(table)
        if registry_entry:
            conflict_cols = conflict_cols or registry_entry['conflict_cols']
            update_cols = update_cols or registry_entry['update_cols']
        else:
            logging.warning(f"No UPSERT registry found for table '{table}'. Using fallback.")
            # 기본값: 모든 컬럼을 업데이트 대상으로
            conflict_cols = conflict_cols or ['id']
            update_cols = update_cols or list(data.keys())
    
    cursor = conn.cursor()
    
    # PostgreSQL 모드인지 확인
    if hasattr(conn, 'is_postgres') and conn.is_postgres:
        return _upsert_postgresql(cursor, table, data, conflict_cols, update_cols)
    else:
        return _upsert_sqlite(cursor, table, data)


def _upsert_postgresql(cursor, table: str, data: Dict[str, Any],
                      conflict_cols: List[str], update_cols: List[str]) -> int:
    """PostgreSQL용 ON CONFLICT UPSERT"""
    
    # timestamp 컬럼들을 INSERT에서 제거하고 DEFAULT 적용되도록 처리
    timestamp_columns = ['updated_at', 'last_master_sync', 'last_full_sync', 'sync_date', 'first_sync_at', 'created_at']
    
    # INSERT용 컬럼과 값 준비 (timestamp 컬럼은 None이면 제외)
    insert_columns = []
    insert_placeholders = []
    insert_values = []
    
    for col, val in data.items():
        # 빈 문자열('')도 None처럼 취급하여 TIMESTAMP 캐스팅 오류 방지
        if isinstance(val, str) and val.strip() == '':
            val = None

        if col in timestamp_columns and (val is None or val == 'now'):
            # timestamp 컬럼이 None이거나 'now'면 INSERT에서 제외 (DEFAULT 적용)
            continue
        else:
            insert_columns.append(col)
            insert_placeholders.append('%s')
            insert_values.append(val)
    
    # UPDATE SET 구성
    update_sets = []
    for col in update_cols:
        if col in timestamp_columns:
            update_sets.append(f"{col} = CURRENT_TIMESTAMP")
        elif col in data and col in insert_columns:
            # INSERT에 포함된 컬럼만 EXCLUDED 사용 가능
            update_sets.append(f"{col} = EXCLUDED.{col}")
    
    # ON CONFLICT 쿼리 구성
    conflict_cols_str = ', '.join(conflict_cols)
    update_sets_str = ', '.join(update_sets)
    
    sql = f"""
        INSERT INTO {table} ({', '.join(insert_columns)})
        VALUES ({', '.join(insert_placeholders)})
        ON CONFLICT ({conflict_cols_str}) 
        DO UPDATE SET {update_sets_str}
    """
    
    logging.debug(f"PostgreSQL UPSERT SQL: {sql}")
    logging.debug(f"Values: {insert_values}")
    
    cursor.execute(sql, insert_values)
    return cursor.rowcount


def _upsert_sqlite(cursor, table: str, data: Dict[str, Any]) -> int:
    """SQLite용 INSERT OR REPLACE"""
    
    columns = list(data.keys())
    placeholders = ['?'] * len(columns)
    values = list(data.values())
    
    # timestamp 컬럼들 자동 처리: SQLite에서는 datetime('now') 사용
    timestamp_columns = ['updated_at', 'last_master_sync', 'last_full_sync', 'sync_date', 'first_sync_at', 'created_at']
    for ts_col in timestamp_columns:
        if ts_col in data:
            ts_idx = columns.index(ts_col)
            placeholders[ts_idx] = "datetime('now')"
            values.pop(ts_idx)  # datetime('now')는 바인딩하지 않음
    
    sql = f"""
        INSERT OR REPLACE INTO {table} ({', '.join(columns)})
        VALUES ({', '.join(placeholders)})
    """
    
    logging.debug(f"SQLite UPSERT SQL: {sql}")
    logging.debug(f"Values: {values}")
    
    cursor.execute(sql, values)
    return cursor.rowcount


def bulk_upsert(conn, table: str, data_list: List[Dict[str, Any]],
                conflict_cols: Optional[List[str]] = None,
                update_cols: Optional[List[str]] = None) -> int:
    """
    배치 UPSERT 함수
    
    Args:
        conn: CompatConnection 객체
        table: 테이블명
        data_list: 삽입/업데이트할 데이터 리스트
        conflict_cols: 충돌 감지 컬럼들
        update_cols: 업데이트할 컬럼들
    
    Returns:
        int: 처리된 총 행의 수
    """
    if not data_list:
        return 0
    
    total_rows = 0
    for data in data_list:
        total_rows += safe_upsert(conn, table, data, conflict_cols, update_cols)
    
    return total_rows


def get_upsert_info(table: str) -> Optional[Dict[str, List[str]]]:
    """테이블의 UPSERT 정보 조회"""
    return UPSERT_REGISTRY.get(table)


def register_upsert_config(table: str, conflict_cols: List[str], update_cols: List[str]):
    """새로운 테이블의 UPSERT 설정 등록"""
    UPSERT_REGISTRY[table] = {
        'conflict_cols': conflict_cols,
        'update_cols': update_cols
    }
    logging.info(f"UPSERT registry updated for table '{table}'")
