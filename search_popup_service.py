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
                'table': 'employees_cache',  # 로컬 캐시 테이블 사용
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
                'table': 'department_master',  # master 테이블 사용 (cache가 비어있음)
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
                'table': 'building_master',  # master 테이블 사용 (cache가 비어있음)
                'search_fields': [
                    {'field': 'building_name', 'label': '건물명'},
                    {'field': 'building_code', 'label': '건물코드'}
                ],
                'default_search_field': 'building_name',
                'display_fields': ['SITE', 'SITE_TYPE','building_name', 'building_code'],
                'display_labels': {'SITE': '사업장', 'SITE_TYPE': '단위','building_name': '건물명', 'building_code': '건물코드'},
                'id_field': 'building_code',
                'title': '건물 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'building_name',
                'use_cache': True  # 로컬 테이블 사용
            },
            'contractor': {
                'table': 'contractors_cache',  # 로컬 캐시 테이블 사용
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
    
    def _get_cache_key(self, search_type: str, query: str, search_field: str = None) -> str:
        """캐시 키 생성"""
        key_str = f"{search_type}:{query}:{search_field or 'default'}"
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
    
    def search(self, search_type: str, query: str = '', search_field: str = None, limit: int = 50) -> Dict[str, Any]:
        """
        검색 수행
        
        Args:
            search_type: 검색 타입 (company, person, department, building)
            query: 검색어
            search_field: 검색할 필드 (None이면 default_search_field 사용)
            limit: 결과 제한 수
        
        Returns:
            검색 결과와 설정 정보
        """
        if search_type not in self.search_configs:
            logging.warning(f"Unknown search type: {search_type}")
            return {
                'results': [],
                'config': {},
                'error': f'Unknown search type: {search_type}'
            }
        
        config = self.search_configs[search_type]
        results = []
        
        try:
            # 캐시 확인 (person, department, building, contractor는 메모리 캐시 사용)
            if search_type != 'company' and query:
                cache_key = self._get_cache_key(search_type, query, search_field)
                cache_entry = self._cache.get(cache_key)
                
                if self._is_cache_valid(cache_entry):
                    logging.info(f"캐시 히트: {search_type} - {query}")
                    return cache_entry['data']
            
            # 검색어가 없으면 빈 결과 반환
            if not query:
                return {
                    'results': [],
                    'config': config,
                    'total': 0,
                    'message': '검색어를 입력해주세요.'
                }
            
            # 검색 필드 결정
            if not search_field:
                search_field = config.get('default_search_field')
            
            # 모든 타입이 로컬 캐시 테이블 사용
            if config.get('use_cache') and config.get('table'):
                conn = get_db_connection(self.db_path, row_factory=True)
                cursor = conn.cursor()
                
                table_name = config['table']
                
                # 특정 필드로 검색
                if search_field:
                    # 선택된 필드가 동적 컬럼인지 확인
                    is_dynamic = False
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict) and field_info.get('field') == search_field:
                            is_dynamic = field_info.get('is_dynamic', False)
                            break
                    
                    if is_dynamic:
                        # 동적 컬럼(JSON) 검색 (partners_cache만 해당)
                        sql = f"""
                            SELECT * FROM {table_name}
                            WHERE json_extract(custom_data, '$.{search_field}') LIKE ?
                            ORDER BY {config.get('order_by', config.get('id_field', 'id'))}
                            LIMIT ?
                        """
                    else:
                        # 일반 컬럼 검색
                        sql = f"""
                            SELECT * FROM {table_name}
                            WHERE {search_field} LIKE ?
                            ORDER BY {config.get('order_by', config.get('id_field', 'id'))}
                            LIMIT ?
                        """
                    params = [f"%{query}%", limit]
                else:
                    # 모든 검색 필드에서 검색
                    where_clauses = []
                    params = []
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict):
                            field = field_info['field']
                            is_dynamic = field_info.get('is_dynamic', False)
                            
                            if is_dynamic:
                                # 동적 컬럼(JSON) 검색
                                where_clauses.append(f"json_extract(custom_data, '$.{field}') LIKE ?")
                            else:
                                # 일반 컬럼 검색
                                where_clauses.append(f"{field} LIKE ?")
                        else:
                            field = field_info
                            where_clauses.append(f"{field} LIKE ?")
                        
                        params.append(f"%{query}%")
                    
                    where_sql = " OR ".join(where_clauses)
                    
                    sql = f"""
                        SELECT * FROM {table_name}
                        WHERE {where_sql}
                        ORDER BY {config.get('order_by', config.get('id_field', 'id'))}
                        LIMIT ?
                    """
                    params.append(limit)
                
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                results = [dict(row) for row in rows]
                conn.close()
            else:
                # 실시간 쿼리 실행 (person, department, building, contractor)
                query_key = config.get('query_key')
                if not query_key:
                    raise ValueError(f"query_key not found for {search_type}")
                
                # 검색 조건 구성
                search_conditions = []
                params = []
                
                if search_field:
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
                
                # 실시간 쿼리 실행
                all_results = self._execute_realtime_query(query_key, search_condition, params)
                
                # LIMIT 적용
                results = all_results[:limit]
                
                # 캐시 저장 (company 제외)
                if search_type != 'company':
                    cache_key = self._get_cache_key(search_type, query, search_field)
                    cache_data = {
                        'results': results,
                        'config': config,
                        'total': len(results)
                    }
                    self._cache[cache_key] = {
                        'data': cache_data,
                        'timestamp': datetime.now()
                    }
            
        except Exception as e:
            logging.error(f"Search error for {search_type}: {e}")
            return {
                'results': [],
                'config': config,
                'error': str(e)
            }
        
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
            'total': len(results)
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