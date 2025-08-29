"""
공통 검색 모듈 - 동적 컬럼(JSON) 검색 지원
SQLite JSON 검색 및 PostgreSQL JSONB 마이그레이션 대비
"""
import sqlite3
import json
from typing import List, Dict, Tuple, Any, Optional
import logging

class DynamicSearchBuilder:
    """동적 컬럼 검색 쿼리 빌더"""
    
    def __init__(self, db_type: str = 'sqlite'):
        """
        Args:
            db_type: 'sqlite' 또는 'postgresql'
        """
        self.db_type = db_type
        
    def add_search_condition(
        self, 
        query: str, 
        params: List[Any],
        field_name: str,
        field_value: Any,
        search_type: str = 'like',
        is_dynamic: bool = True,
        fallback_column: Optional[str] = None,
        custom_data_field: str = 'custom_data'
    ) -> Tuple[str, List[Any]]:
        """
        검색 조건 추가 (동적 컬럼 지원)
        
        Args:
            query: 기존 SQL 쿼리
            params: 기존 파라미터 리스트
            field_name: 검색할 필드명
            field_value: 검색 값
            search_type: 'like', 'equals', 'gte', 'lte' 등
            is_dynamic: True면 JSON 필드에서 검색, False면 일반 컬럼
            fallback_column: 폴백용 기존 컬럼명 (옵션)
            custom_data_field: JSON 데이터가 저장된 컬럼명 (기본: custom_data)
            
        Returns:
            (수정된 쿼리, 수정된 파라미터)
        """
        if not field_value:
            return query, params
            
        if not is_dynamic:
            # 일반 컬럼 검색
            if search_type == 'like':
                query += f" AND {field_name} LIKE ?"
                params.append(f"%{field_value}%")
            elif search_type == 'equals':
                query += f" AND {field_name} = ?"
                params.append(field_value)
            elif search_type == 'gte':
                query += f" AND {field_name} >= ?"
                params.append(field_value)
            elif search_type == 'lte':
                query += f" AND {field_name} <= ?"
                params.append(field_value)
        else:
            # JSON/JSONB 필드 검색
            if self.db_type == 'sqlite':
                # SQLite JSON 검색
                json_path = f'$.{field_name}'
                
                if search_type == 'like':
                    if fallback_column:
                        # JSON 필드와 폴백 컬럼 동시 검색
                        query += f" AND (json_extract({custom_data_field}, '{json_path}') LIKE ? OR {fallback_column} LIKE ?)"
                        params.append(f"%{field_value}%")
                        params.append(f"%{field_value}%")
                    else:
                        # JSON 필드만 검색
                        query += f" AND json_extract({custom_data_field}, '{json_path}') LIKE ?"
                        params.append(f"%{field_value}%")
                        
                elif search_type == 'equals':
                    query += f" AND json_extract({custom_data_field}, '{json_path}') = ?"
                    params.append(field_value)
                    
                elif search_type == 'gte':
                    query += f" AND CAST(json_extract({custom_data_field}, '{json_path}') AS REAL) >= ?"
                    params.append(field_value)
                    
                elif search_type == 'lte':
                    query += f" AND CAST(json_extract({custom_data_field}, '{json_path}') AS REAL) <= ?"
                    params.append(field_value)
                    
            elif self.db_type == 'postgresql':
                # PostgreSQL JSONB 검색 (미래 대비)
                if search_type == 'like':
                    if fallback_column:
                        query += f" AND ({custom_data_field}->>{field_name} ILIKE %s OR {fallback_column} ILIKE %s)"
                        params.append(f"%{field_value}%")
                        params.append(f"%{field_value}%")
                    else:
                        query += f" AND {custom_data_field}->>{field_name} ILIKE %s"
                        params.append(f"%{field_value}%")
                        
                elif search_type == 'equals':
                    query += f" AND {custom_data_field} @> %s"
                    params.append(json.dumps({field_name: field_value}))
                    
                # PostgreSQL은 JSONB 인덱스로 더 빠른 검색 가능
                    
        return query, params
    
    def build_search_query(
        self,
        base_query: str,
        filters: Dict[str, Any],
        column_config: List[Dict[str, Any]],
        static_columns: Optional[List[str]] = None
    ) -> Tuple[str, List[Any]]:
        """
        필터 딕셔너리와 컬럼 설정을 기반으로 검색 쿼리 생성
        
        Args:
            base_query: 기본 SELECT 쿼리
            filters: 검색 필터 딕셔너리
            column_config: 컬럼 설정 리스트 (동적 컬럼 정보 포함)
            static_columns: 고정 컬럼명 리스트
            
        Returns:
            (완성된 쿼리, 파라미터 리스트)
        """
        query = base_query
        params = []
        
        # 고정 컬럼 리스트 (없으면 빈 리스트)
        static_columns = static_columns or []
        
        # 컬럼 설정에서 동적 컬럼 목록 추출
        dynamic_column_keys = {col['column_key'] for col in column_config}
        
        for field_name, field_value in filters.items():
            if not field_value:
                continue
                
            # 날짜 필드 특수 처리
            if field_name.endswith('_from'):
                base_field = field_name[:-5]  # _from 제거
                is_dynamic = base_field not in static_columns
                query, params = self.add_search_condition(
                    query, params, base_field, field_value, 
                    search_type='gte', is_dynamic=is_dynamic
                )
                
            elif field_name.endswith('_to'):
                base_field = field_name[:-3]  # _to 제거
                is_dynamic = base_field not in static_columns
                query, params = self.add_search_condition(
                    query, params, base_field, field_value,
                    search_type='lte', is_dynamic=is_dynamic
                )
                
            else:
                # 일반 필드
                is_dynamic = field_name not in static_columns
                
                # 폴백 컬럼 매핑 (필요시)
                fallback_map = {
                    'company_name': 'responsible_company1',
                    'business_number': 'responsible_company1_no'
                }
                fallback = fallback_map.get(field_name)
                
                query, params = self.add_search_condition(
                    query, params, field_name, field_value,
                    search_type='like', is_dynamic=is_dynamic,
                    fallback_column=fallback
                )
                
        return query, params


# 헬퍼 함수들
def get_column_config(conn: sqlite3.Connection, board_type: str) -> List[Dict[str, Any]]:
    """
    특정 보드의 컬럼 설정 가져오기
    
    Args:
        conn: 데이터베이스 연결
        board_type: 보드 타입 (accident, safety_instruction 등)
        
    Returns:
        컬럼 설정 리스트
    """
    cursor = conn.cursor()
    
    # 보드별 컬럼 설정 테이블명
    table_name = f"{board_type}_column_config"
    
    try:
        cursor.execute(f"""
            SELECT column_key, column_name, column_type, is_active
            FROM {table_name}
            WHERE is_active = 1
            ORDER BY column_order
        """)
        columns = cursor.fetchall()
        
        return [
            {
                'column_key': col[0],
                'column_name': col[1],
                'column_type': col[2],
                'is_active': col[3]
            }
            for col in columns
        ]
    except sqlite3.OperationalError:
        logging.warning(f"테이블 {table_name}이 없습니다.")
        return []


def get_static_columns(board_type: str) -> List[str]:
    """
    보드별 고정 컬럼 목록 반환
    
    Args:
        board_type: 보드 타입
        
    Returns:
        고정 컬럼명 리스트
    """
    # 보드별 고정 컬럼 정의
    static_columns_map = {
        'accident': [
            'id', 'accident_number', 'accident_date', 'accident_type',
            'accident_location', 'accident_name', 'accident_time',
            'accident_grade', 'injury_type', 'injury_form', 'workplace',
            'building', 'floor', 'location_detail', 'day_of_week',
            'responsible_company1', 'responsible_company1_no',
            'responsible_company2', 'responsible_company2_no',
            'is_deleted', 'major_category', 'location_category'
        ],
        'safety_instruction': [
            'id', 'issue_number', 'violation_date', 'discipline_date',
            'issuer', 'issuer_department', 'classification', 'employment_type',
            'disciplined_person', 'disciplined_person_id', 'violation_content',
            'detailed_content', 'is_deleted'
        ],
        'change_request': [
            'id', 'request_number', 'request_date', 'requester',
            'change_content', 'approval_status', 'is_deleted'
        ]
    }
    
    return static_columns_map.get(board_type, [])


# 사용 예시
if __name__ == "__main__":
    # 테스트 코드
    builder = DynamicSearchBuilder('sqlite')
    
    # 기본 쿼리
    query = "SELECT * FROM accidents_cache WHERE is_deleted = 0"
    params = []
    
    # 필터
    filters = {
        'company_name': '삼성',  # 동적 컬럼
        'business_number': '123',  # 동적 컬럼
        'accident_date_from': '2024-01-01',  # 고정 컬럼
        'accident_date_to': '2024-12-31'  # 고정 컬럼
    }
    
    # 고정 컬럼 리스트
    static_cols = get_static_columns('accident')
    
    # 각 필터 적용
    for field, value in filters.items():
        if value:
            is_dynamic = field.replace('_from', '').replace('_to', '') not in static_cols
            query, params = builder.add_search_condition(
                query, params, field, value, 
                is_dynamic=is_dynamic
            )
    
    print("Query:", query)
    print("Params:", params)