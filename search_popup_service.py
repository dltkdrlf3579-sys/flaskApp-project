"""
검색 팝업 공통 서비스
모든 보드에서 사용하는 검색 팝업 통합 관리
실시간 외부 DB 연계 지원
"""
import sqlite3
import logging
import configparser
import os
import sys
from typing import List, Dict, Any, Optional
import math
from db_connection import get_db_connection
from datetime import datetime, timedelta
import hashlib
import json

class SearchPopupService:
    """검색 팝업 서비스 - 실시간 외부 DB 연계"""
    
    # 캐시 저장소 (메모리 캐시)
    _cache = {}
    _cache_ttl = 300  # 5분 캐시 TTL
    
    def __init__(self, db_path: str, board_type: str = None):
        """
        Args:
            db_path: 데이터베이스 경로
            board_type: 보드 타입 (동적 컬럼 사용시)
        """
        self.db_path = db_path
        self.board_type = board_type
        self.config = self._load_config()
        self.external_conn = None
        
        # 기본 검색 타입별 설정 (실시간 쿼리 매핑)
        self.search_configs = {
            'company': {
                'table': 'partners_cache',  # 로컬 캐시 테이블 사용
                'query_key': 'PARTNERS_QUERY',  # config.ini의 쿼리 키
                'search_fields': [
                    {'field': 'company_name', 'label': '협력사명'},
                    {'field': 'business_number', 'label': '사업자번호'}
                ],
                'default_search_field': 'company_name',
                'display_fields': ['company_name', 'business_number', 'partner_class', 'transaction_count', 'permanent_workers'],
                'display_labels': {'company_name': '협력사명', 'business_number': '사업자번호', 'partner_class': 'Class', 'transaction_count': '거래차수', 'permanent_workers': '상시근로자'},
                'id_field': 'business_number',
                'title': '협력사 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'company_name',
                'use_cache': True  # 캐시 사용 (partners_cache 테이블)
            },
            'person': {
                'table': 'employees_cache',  # cache 테이블 사용
                'search_fields': [
                    {'field': 'employee_name', 'label': '이름'},
                    {'field': 'employee_id', 'label': 'ID'},
                    {'field': 'department_name', 'label': '부서'}
                ],
                'default_search_field': 'employee_name',
                'display_fields': ['employee_name', 'employee_id', 'department_name'],
                'display_labels': {'employee_name': '이름', 'employee_id': 'ID', 'department_name': '부서'},
                'id_field': 'employee_id',
                'title': '담당자 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'employee_name',
                'use_cache': True  # 로컬 테이블 사용
            },
            'department': {
                'table': 'departments_cache',  # cache 테이블 사용
                'search_fields': [
                    {'field': 'dept_name', 'label': '부서명'},
                    {'field': 'dept_code', 'label': '부서코드'}
                ],
                'default_search_field': 'dept_name',
                'display_fields': ['dept_name', 'dept_code', 'parent_dept_code'],
                'display_labels': {'dept_name': '부서명', 'dept_code': '부서코드', 'parent_dept_code': '상위부서코드'},
                'id_field': 'dept_code',
                'title': '부서 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'dept_name',
                'use_cache': True  # 로컬 테이블 사용
            },
            'building': {
                'table': 'buildings_cache',  # cache 테이블 사용
                'search_fields': [
                    {'field': 'building_name', 'label': '건물명'},
                    {'field': 'building_code', 'label': '건물코드'}
                ],
                'default_search_field': 'building_name',
                'display_fields': ['SITE', 'SITE_TYPE', 'building_name', 'building_code'],
                'display_labels': {'SITE': '사업장', 'SITE_TYPE': '구역', 'building_name': '건물명', 'building_code': '건물코드'},
                'id_field': 'building_code',
                'title': '건물 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'building_name',
                'use_cache': True  # 로컬 테이블 사용
            },
            'contractor': {
                'table': 'contractors_cache',  # cache 테이블 사용
                'search_fields': [
                    {'field': 'worker_name', 'label': '근로자명'},
                    {'field': 'worker_id', 'label': '근로자ID'},
                    {'field': 'company_name', 'label': '소속회사'}
                ],
                'default_search_field': 'worker_name',
                'display_fields': ['worker_name', 'worker_id', 'company_name', 'business_number'],
                'display_labels': {'worker_name': '근로자명', 'worker_id': '근로자ID', 'company_name': '소속회사', 'business_number': '사업자번호'},
                'id_field': 'worker_id',
                'title': '협력사 근로자 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'worker_name',
                'use_cache': True,  # 로컬 테이블 사용
                'advanced_filters': [
                    {'field': 'worker_name', 'label': '근로자명'},
                    {'field': 'worker_id', 'label': '근로자ID'},
                    {'field': 'company_name', 'label': '소속회사'}
                ],
                'advanced_filter_operator': 'and'
            },
            'division': {
                'table': 'divisions_cache',  # cache 테이블 사용
                'query_key': 'DIVISION_QUERY',  # config.ini의 쿼리 키
                'search_fields': [
                    {'field': 'division_name', 'label': '사업부명'},
                    {'field': 'division_code', 'label': '사업부코드'}
                ],
                'default_search_field': 'division_name',
                'display_fields': ['division_name', 'division_code', 'parent_division_code', 'division_level'],
                'display_labels': {
                    'division_name': '사업부명',
                    'division_code': '사업부코드',
                    'parent_division_code': '상위사업부',
                    'division_level': '레벨'
                },
                'id_field': 'division_code',
                'title': '사업부 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'division_name',
                'use_cache': True  # 로컬 테이블 사용
            }
        }
        
        # 보드 타입이 있으면 동적 컬럼 로드
        if board_type:
            self._load_dynamic_columns()
    
    def _load_config(self):
        """config.ini 파일 로드"""
        config = configparser.ConfigParser()
        config_path = 'config.ini'
        
        if os.path.exists(config_path):
            config.read(config_path, encoding='utf-8')
        
        return config
    
    def _get_cache_key(
        self,
        search_type: str,
        query: str,
        search_field: str = None,
        filters: Optional[List[Dict[str, Any]]] = None,
        limit: Optional[int] = None,
        page: Optional[int] = None,
    ) -> str:
        """캐시 키 생성"""
        parts = [search_type, search_field or 'default', query or '']
        if limit is not None:
            parts.append(str(limit))
        if page is not None:
            parts.append(str(page))
        if filters:
            normalized = []
            for filt in filters:
                field = filt.get('field', '')
                value = filt.get('value', '')
                if value:
                    normalized.append({'field': field, 'value': value})
            if normalized:
                normalized.sort(key=lambda item: item['field'])
                parts.append(json.dumps(normalized, ensure_ascii=False))
        key_str = '::'.join(parts)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def _is_cache_valid(self, cache_entry: Dict) -> bool:
        """캐시 유효성 검사"""
        if not cache_entry:
            return False
        
        cached_time = cache_entry.get('timestamp')
        if not cached_time:
            return False
        
        # TTL 체크
        elapsed = (datetime.now() - cached_time).total_seconds()
        return elapsed < self._cache_ttl
    
    def _get_external_connection(self):
        """외부 DB 연결 가져오기 (연결 풀링)"""
        try:
            if self.external_conn:
                return self.external_conn
            
            # 외부 DB 활성화 확인
            if not self.config.getboolean('DATABASE', 'EXTERNAL_DB_ENABLED', fallback=False):
                return None
            
            # IQADB 모듈 경로 설정
            module_path = self.config.get('DATABASE', 'IQADB_MODULE_PATH', fallback=None)
            if module_path and os.path.exists(module_path):
                if module_path not in sys.path:
                    sys.path.insert(0, module_path)
            
            # IQADB_CONNECT310 임포트
            from IQADB_CONNECT310 import iqaconn
            
            # DB 연결
            self.external_conn = iqaconn()
            return self.external_conn
            
        except ImportError as e:
            logging.warning(f"IQADB 모듈을 찾을 수 없습니다: {e}")
            return None
        except Exception as e:
            logging.error(f"외부 DB 연결 실패: {e}")
            return None
    
    def _execute_realtime_query(self, query_key: str, search_condition: str = None, params: List = None) -> List[Dict]:
        """실시간 외부 DB 쿼리 실행"""
        results = []
        total_count = 0
        
        try:
            # 외부 DB 연결
            conn = self._get_external_connection()
            if not conn:
                logging.info("외부 DB 미연결 - 샘플 데이터 사용")
                return self._get_sample_data(query_key)
            
            cursor = conn.cursor()
            
            # config.ini에서 쿼리 가져오기
            if query_key in ['EMPLOYEE_QUERY', 'BUILDING_QUERY', 'DEPARTMENT_QUERY', 'CONTRACTOR_QUERY']:
                base_query = self.config.get('MASTER_DATA_QUERIES', query_key)
            else:
                base_query = self.config.get('SQL_QUERIES', query_key)
            
            # 검색 조건 추가
            if search_condition:
                # WHERE 1=1이 있으면 AND로 추가
                if 'WHERE 1=1' in base_query:
                    query = base_query.replace('WHERE 1=1', f'WHERE 1=1 AND {search_condition}')
                # WHERE가 있으면 AND로 추가
                elif 'WHERE' in base_query.upper():
                    # ORDER BY 전에 추가
                    if 'ORDER BY' in base_query.upper():
                        parts = base_query.split('ORDER BY')
                        query = f"{parts[0]} AND {search_condition} ORDER BY {parts[1]}"
                    else:
                        query = f"{base_query} AND {search_condition}"
                else:
                    # WHERE 절 추가
                    if 'ORDER BY' in base_query.upper():
                        parts = base_query.split('ORDER BY')
                        query = f"{parts[0]} WHERE {search_condition} ORDER BY {parts[1]}"
                    else:
                        query = f"{base_query} WHERE {search_condition}"
            else:
                query = base_query
            
            # 쿼리 실행
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # 결과 가져오기
            columns = [desc[0].lower() for desc in cursor.description]
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            cursor.close()
            
        except Exception as e:
            logging.error(f"실시간 쿼리 실행 실패 ({query_key}): {e}")
            return self._get_sample_data(query_key)
        
        return results
    
    def _get_sample_data(self, query_key: str) -> List[Dict]:
        """테스트용 샘플 데이터 반환"""
        sample_data = {
            'EMPLOYEE_QUERY': [
                {'employee_id': 'E001', 'employee_name': '김철수', 'department_name': '안전환경팀'},
                {'employee_id': 'E002', 'employee_name': '이영희', 'department_name': '안전환경팀'},
                {'employee_id': 'E003', 'employee_name': '박민수', 'department_name': '시설관리팀'}
            ],
            'BUILDING_QUERY': [
                {'building_code': 'BLD001', 'building_name': '본관', 'SITE': '서울특별시 강남구', 'SITE_TYPE': '본사'},
                {'building_code': 'BLD002', 'building_name': '연구동', 'SITE': '서울특별시 강남구', 'SITE_TYPE': '연구소'}
            ],
            'DEPARTMENT_QUERY': [
                {'dept_code': 'DEPT001', 'dept_name': '안전관리팀', 'parent_dept_code': '안전환경본부'},
                {'dept_code': 'DEPT002', 'dept_name': '환경관리팀', 'parent_dept_code': '안전환경본부'}
            ],
            'CONTRACTOR_QUERY': [
                {'worker_id': 'W001', 'worker_name': '홍길동', 'company_name': '(주)안전건설', 'business_number': '123-45-67890', 'access_status': '허가', 'birth_date': '1980-05-15'},
                {'worker_id': 'W002', 'worker_name': '김영수', 'company_name': '(주)환경기술', 'business_number': '234-56-78901', 'access_status': '차단', 'birth_date': '1985-08-22'}
            ]
        }
        
        return sample_data.get(query_key, [])
    
    def _load_dynamic_columns(self):
        """보드별 동적 컬럼을 검색 설정에 추가"""
        if not self.board_type:
            return
            
        try:
            conn = get_db_connection(self.db_path, row_factory=True)
            cursor = conn.cursor()
            
            # 보드별 컬럼 설정 테이블명
            column_table = f"{self.board_type}_column_config"
            
            # 테이블 존재 확인
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (column_table,))
            
            if cursor.fetchone()[0] == 0:
                conn.close()
                return
            
            # 활성화된 동적 컬럼 조회
            cursor.execute(f"""
                SELECT column_key, column_name, column_type
                FROM {column_table}
                WHERE is_active = 1
                ORDER BY column_order
            """)
            
            dynamic_columns = cursor.fetchall()
            
            # company 검색 타입에 동적 컬럼 추가
            if 'company' in self.search_configs and dynamic_columns:
                # 기존 필드 유지하면서 동적 컬럼 추가
                existing_fields = {f['field'] for f in self.search_configs['company']['search_fields']}
                
                for col in dynamic_columns:
                    # custom_data에 저장된 동적 컬럼
                    if col['column_key'] not in existing_fields:
                        self.search_configs['company']['search_fields'].append({
                            'field': col['column_key'],
                            'label': col['column_name'],
                            'is_dynamic': True  # 동적 컬럼 표시
                        })
                        
                        # display_fields에도 추가
                        if col['column_key'] not in self.search_configs['company']['display_fields']:
                            self.search_configs['company']['display_fields'].append(col['column_key'])
            
            conn.close()
            logging.info(f"동적 컬럼 로드 완료: {self.board_type}")
            
        except Exception as e:
            logging.error(f"동적 컬럼 로드 실패: {e}")
    
    def search(
        self,
        search_type: str,
        query: str = '',
        search_field: str = None,
        limit: int = 50,
        page: int = 1,
        filters: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        검색 수행
        
        Args:
            search_type: 검색 타입 (company, person, department, building)
            query: 검색어
            search_field: 검색할 필드 (None이면 default_search_field 사용)
            limit: 페이지당 결과 제한 수
            page: 페이지 번호 (1부터 시작)
            
        Returns:
            검색 결과와 설정 정보
        """
        logging.info(
            "[search-popup] type=%s query=%s field=%s limit=%s page=%s filters=%s",
            search_type,
            query,
            search_field,
            limit,
            page,
            filters,
        )
        if search_type not in self.search_configs:
            logging.warning(f"Unknown search type: {search_type}")
            return {
                'results': [],
                'config': {},
                'error': f'Unknown search type: {search_type}',
                'total': 0,
                'page': 1,
                'has_more': False,
            }
        
        config = self.search_configs[search_type]
        results = []

        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 50
        if limit < 1:
            limit = 1

        try:
            page = int(page)
        except (TypeError, ValueError):
            page = 1
        if page < 1:
            page = 1

        offset = (page - 1) * limit
        query_limit = limit + 1
        has_more_flag = False
        prepared_filters: List[Dict[str, Any]] = []
        if filters:
            for filt in filters:
                field = (filt.get('field') or '').strip()
                value = (filt.get('value') or '').strip()
                if field and value:
                    prepared_filters.append({'field': field, 'value': value})
        use_filters = len(prepared_filters) > 0
        
        try:
            # 캐시 확인 (person, department, building, contractor는 메모리 캐시 사용)
            if search_type != 'company' and (query or use_filters):
                cache_key = self._get_cache_key(search_type, query, search_field, prepared_filters, limit, page)
                cache_entry = self._cache.get(cache_key)
                
                if self._is_cache_valid(cache_entry):
                    logging.info(f"캐시 히트: {search_type} - {query}")
                    cached_data = cache_entry['data']
                    if 'page' not in cached_data or 'has_more' not in cached_data:
                        rebuilt = dict(cached_data)
                        rebuilt.setdefault('page', page)
                        rebuilt.setdefault('has_more', len(rebuilt.get('results', [])) == limit)
                        rebuilt.setdefault('total', len(rebuilt.get('results', [])))
                        if 'total_pages' not in rebuilt:
                            total_val = rebuilt.get('total', len(rebuilt.get('results', [])))
                            rebuilt['total_pages'] = math.ceil(total_val / limit) if total_val else 0
                        cached_data = rebuilt
                        cache_entry['data'] = cached_data
                    return cached_data

            if not query and not use_filters:
                return {
                    'results': [],
                    'config': config,
                    'total': 0,
                    'message': '검색어를 입력해주세요.',
                    'page': page,
                    'has_more': False,
                    'total_pages': 0,
                }

            # 검색 필드 결정
            if not search_field:
                search_field = config.get('default_search_field')

            # 모든 타입이 로컬 캐시 테이블 사용
            if config.get('use_cache') and config.get('table'):
                conn = get_db_connection(self.db_path, row_factory=True)
                cursor = conn.cursor()

                table_name = config['table']

                # 헬퍼: 필드가 동적인지 확인
                def is_dynamic_field(field_name: str) -> bool:
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict) and field_info.get('field') == field_name:
                            return field_info.get('is_dynamic', False)
                    return False

                query_sql = None
                query_params: List[Any] = []
                count_sql = None
                count_params: List[Any] = []

                if use_filters:
                    where_clauses = []
                    base_params = []
                    for filt in prepared_filters:
                        field = filt['field']
                        value = filt['value']
                        dynamic_field = is_dynamic_field(field)
                        like_param = f"%{value}%"
                        if hasattr(conn, 'is_postgres') and conn.is_postgres:
                            if dynamic_field:
                                where_clauses.append(f"(custom_data->>'{field}') ILIKE %s")
                            else:
                                where_clauses.append(f"{field} ILIKE %s")
                        else:
                            if dynamic_field:
                                where_clauses.append(f"json_extract(custom_data, '$.{field}') LIKE ?")
                            else:
                                where_clauses.append(f"{field} LIKE ?")
                        base_params.append(like_param)

                    if not where_clauses:
                        conn.close()
                        return {
                            'results': [],
                            'config': config,
                            'total': 0,
                            'message': '검색 조건을 입력해주세요.',
                            'page': page,
                            'has_more': False,
                            'total_pages': 0,
                        }

                    where_sql = ' AND '.join(where_clauses) if config.get('advanced_filter_operator', 'and').lower() == 'and' else ' OR '.join(where_clauses)
                    order_clause = config.get('order_by', config.get('id_field', 'id'))

                    if hasattr(conn, 'is_postgres') and conn.is_postgres:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {where_sql}
                            ORDER BY {order_clause}
                            LIMIT %s OFFSET %s
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {where_sql}
                        """
                    else:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {where_sql}
                            ORDER BY {order_clause}
                            LIMIT ? OFFSET ?
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {where_sql}
                        """

                    count_params = list(base_params)
                    query_params = list(base_params)
                    query_params.extend([query_limit, offset])

                elif search_field:
                    is_dynamic = is_dynamic_field(search_field)
                    order_clause = config.get('order_by', config.get('id_field', 'id'))
                    like_param = f"%{query}%"

                    if is_dynamic:
                        if hasattr(conn, 'is_postgres') and conn.is_postgres:
                            condition = f"(custom_data->>'{search_field}') ILIKE %s"
                        else:
                            condition = f"json_extract(custom_data, '$.{search_field}') LIKE ?"
                    else:
                        condition = f"{search_field} ILIKE %s" if hasattr(conn, 'is_postgres') and conn.is_postgres else f"{search_field} LIKE ?"

                    if hasattr(conn, 'is_postgres') and conn.is_postgres:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {condition}
                            ORDER BY {order_clause}
                            LIMIT %s OFFSET %s
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {condition}
                        """
                    else:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {condition}
                            ORDER BY {order_clause}
                            LIMIT ? OFFSET ?
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {condition}
                        """

                    count_params = [like_param]
                    query_params = [like_param, query_limit, offset]

                else:
                    where_clauses = []
                    base_params = []
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict):
                            field = field_info['field']
                            is_dynamic = field_info.get('is_dynamic', False)
                            like_param = f"%{query}%"
                            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                                if is_dynamic:
                                    where_clauses.append(f"(custom_data->>'{field}') ILIKE %s")
                                else:
                                    where_clauses.append(f"{field} ILIKE %s")
                            else:
                                if is_dynamic:
                                    where_clauses.append(f"json_extract(custom_data, '$.{field}') LIKE ?")
                                else:
                                    where_clauses.append(f"{field} LIKE ?")
                            base_params.append(like_param)
                        else:
                            field = field_info
                            like_param = f"%{query}%"
                            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                                where_clauses.append(f"{field} ILIKE %s")
                            else:
                                where_clauses.append(f"{field} LIKE ?")
                            base_params.append(like_param)

                    where_sql = ' OR '.join(where_clauses)
                    order_clause = config.get('order_by', config.get('id_field', 'id'))

                    if hasattr(conn, 'is_postgres') and conn.is_postgres:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {where_sql}
                            ORDER BY {order_clause}
                            LIMIT %s OFFSET %s
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {where_sql}
                        """
                    else:
                        query_sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {where_sql}
                            ORDER BY {order_clause}
                            LIMIT ? OFFSET ?
                        """
                        count_sql = f"""
                            SELECT COUNT(*) FROM {table_name}
                            WHERE {where_sql}
                        """

                    count_params = list(base_params)
                    query_params = list(base_params)
                    query_params.extend([query_limit, offset])

                if not query_sql or not count_sql:
                    conn.close()
                    return {
                        'results': [],
                        'config': config,
                        'total': 0,
                        'page': page,
                        'has_more': False,
                        'total_pages': 0,
                    }

                cursor.execute(query_sql, query_params)
                logging.info("[search-popup] local-sql type=%s sql=%s params=%s", search_type, query_sql, query_params)
                rows = cursor.fetchall()
                has_more_flag = len(rows) > limit
                rows = rows[:limit]
                results = [dict(row) for row in rows]

                cursor.execute(count_sql, count_params)
                count_row = cursor.fetchone()
                total_count = count_row[0] if count_row else 0

                conn.close()
            else:
                # 실시간 쿼리 실행 (person, department, building, contractor)
                query_key = config.get('query_key')
                if not query_key:
                    raise ValueError(f"query_key not found for {search_type}")

                # 검색 조건 구성
                search_conditions = []
                params = []

                if use_filters:
                    operator = config.get('advanced_filter_operator', 'and').lower()
                    clause_joiner = ' AND ' if operator == 'and' else ' OR '
                    filter_clauses = []
                    for filt in prepared_filters:
                        field = filt['field']
                        value = filt['value']
                        filter_clauses.append(f"{field} LIKE ?")
                        params.append(f"%{value}%")
                    if filter_clauses:
                        search_conditions.append(clause_joiner.join(filter_clauses))
                elif search_field:
                    # 특정 필드 검색
                    search_conditions.append(f"{search_field} LIKE ?")
                    params.append(f"%{query}%")
                else:
                    # 모든 검색 필드에서 검색
                    field_conditions = []
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict):
                            field = field_info['field']
                        else:
                            field = field_info
                        field_conditions.append(f"{field} LIKE ?")
                        params.append(f"%{query}%")

                    if field_conditions:
                        search_conditions.append(f"({' OR '.join(field_conditions)})")

                # LIMIT 추가
                search_condition = ' AND '.join(search_conditions) if search_conditions else '1=1'

                all_results = self._execute_realtime_query(query_key, search_condition, params)
                logging.info(
                    "[search-popup] realtime type=%s condition=%s params=%s results=%s",
                    search_type,
                    search_condition,
                    params,
                    len(all_results),
                )

                # fallback 데이터에 대해서는 파이썬에서 필터링 수행
                def matches_filters(row_dict):
                    def value_contains(field_key, target_value):
                        val = row_dict.get(field_key)
                        if val is None:
                            return False
                        return target_value in str(val).lower()

                    if use_filters:
                        operator = config.get('advanced_filter_operator', 'and').lower()
                        prepared = [{'field': f['field'], 'value': f['value'].lower()} for f in prepared_filters]
                        if operator == 'and':
                            return all(value_contains(f['field'], f['value']) for f in prepared)
                        return any(value_contains(f['field'], f['value']) for f in prepared)
                    if query:
                        search_fields = []
                        if search_field:
                            search_fields.append(search_field)
                        else:
                            for field_info in config.get('search_fields', []):
                                if isinstance(field_info, dict):
                                    search_fields.append(field_info.get('field'))
                                else:
                                    search_fields.append(field_info)
                        lowered = query.lower()
                        for field in search_fields:
                            if field and value_contains(field, lowered):
                                return True
                        return False
                    return True

                filtered_results = [row for row in all_results if matches_filters(row)]

                # LIMIT 적용
                results = filtered_results[offset: offset + limit]
                has_more_flag = len(filtered_results) > (offset + limit)
                total_count = len(filtered_results)

                # 캐시 저장 (company 제외)
                if search_type != 'company':
                    cache_key = self._get_cache_key(search_type, query, search_field, prepared_filters, limit, page)
                    cache_data = {
                        'results': results,
                        'config': config,
                        'total': total_count,
                        'total_pages': math.ceil(total_count / limit) if total_count else 0,
                        'has_more': has_more_flag,
                        'page': page,
                    }
                    self._cache[cache_key] = {
                        'data': cache_data,
                        'timestamp': datetime.now()
                    }
        
        except Exception as e:
            logging.error(
                "Search error for %s: %s (query_key=%s)",
                search_type,
                e,
                locals().get('query_key'),
            )
            return {
                'results': [],
                'config': config,
                'error': str(e),
                'total': 0,
                'page': page,
                'has_more': False,
                'total_pages': 0,
            }

        # 키 대/소문자 동시 접근 가능하도록 보강
        for result in results:
            for key in list(result.keys()):
                value = result[key]
                lower = key.lower()
                upper = key.upper()
                if lower not in result:
                    result[lower] = value
                if upper not in result:
                    result[upper] = value

        # person 타입의 경우 필드명 매핑 (기존 페이지들과의 호환성을 위해)
        if search_type == 'person':
            for result in results:
                # employee_name -> name 매핑
                if 'employee_name' in result:
                    result['name'] = result['employee_name']
                # department_name -> department 매핑
                if 'department_name' in result:
                    result['department'] = result['department_name']

        return {
            'results': results,
            'config': config,
            'total': total_count,
            'total_pages': math.ceil(total_count / limit) if total_count else 0,
            'page': page,
            'has_more': has_more_flag,
        }
    
    def cleanup_cache(self):
        """만료된 캐시 정리"""
        now = datetime.now()
        expired_keys = []
        
        for key, entry in self._cache.items():
            if not self._is_cache_valid(entry):
                expired_keys.append(key)
        
        for key in expired_keys:
            del self._cache[key]
        
        if expired_keys:
            logging.info(f"캐시 정리 완료: {len(expired_keys)}개 항목 삭제")
    
    def get_item(self, search_type: str, item_id: str) -> Optional[Dict[str, Any]]:
        """
        특정 항목 조회
        
        Args:
            search_type: 검색 타입
            item_id: 항목 ID
        
        Returns:
            항목 정보 또는 None
        """
        if search_type not in self.search_configs:
            return None
        
        config = self.search_configs[search_type]
        
        try:
            # 모든 타입이 로컬 캐시 테이블에서 조회
            if config.get('use_cache') and config.get('table'):
                conn = get_db_connection(self.db_path, row_factory=True)
                cursor = conn.cursor()
                
                table_name = config['table']
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE {config['id_field']} = ?
                """, (item_id,))
                
                row = cursor.fetchone()
                conn.close()
                
                if row:
                    return dict(row)
            else:
                # 실시간 쿼리로 특정 항목 조회 (현재는 사용 안함)
                query_key = config.get('query_key')
                if query_key:
                    search_condition = f"{config['id_field']} = ?"
                    results = self._execute_realtime_query(query_key, search_condition, [item_id])
                    
                    if results:
                        return results[0]
            
        except Exception as e:
            logging.error(f"Get item error for {search_type}: {e}")
        
        return None
    
    def __del__(self):
        """소멸자 - 외부 DB 연결 종료"""
        if self.external_conn:
            try:
                self.external_conn.close()
            except:
                pass
