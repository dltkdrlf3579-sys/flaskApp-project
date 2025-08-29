"""
검색 팝업 공통 서비스
모든 보드에서 사용하는 검색 팝업 통합 관리
"""
import sqlite3
import logging
from typing import List, Dict, Any, Optional
from db_connection import get_db_connection

class SearchPopupService:
    """검색 팝업 서비스"""
    
    def __init__(self, db_path: str, board_type: str = None):
        """
        Args:
            db_path: 데이터베이스 경로
            board_type: 보드 타입 (동적 컬럼 사용시)
        """
        self.db_path = db_path
        self.board_type = board_type
        
        # 기본 검색 타입별 설정
        self.search_configs = {
            'company': {
                'table': 'partners_cache',
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
                'order_by': 'company_name'
            },
            'person': {
                'table': 'person_master',
                'search_fields': [
                    {'field': 'name', 'label': '이름'},
                    {'field': 'employee_id', 'label': 'ID'}
                ],
                'default_search_field': 'name',
                'display_fields': ['name', 'employee_id', 'department'],
                'display_labels': {'name': '이름', 'employee_id': 'ID', 'department': '부서'},
                'id_field': 'employee_id',
                'title': '담당자 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'name'
            },
            'department': {
                'table': 'department_master',
                'search_fields': [
                    {'field': 'department_name', 'label': '부서명'},
                    {'field': 'department_code', 'label': '부서코드'}
                ],
                'default_search_field': 'department_name',
                'display_fields': ['department_name', 'department_code', 'parent_department'],
                'id_field': 'department_code',
                'title': '부서 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'department_name'
            },
            'building': {
                'table': 'building_master',
                'search_fields': [
                    {'field': 'building_name', 'label': '건물명'},
                    {'field': 'building_code', 'label': '건물코드'}
                ],
                'default_search_field': 'building_name',
                'display_fields': ['building_name', 'building_code', 'location'],
                'id_field': 'building_code',
                'title': '건물 검색',
                'placeholder': '검색어를 입력하세요',
                'order_by': 'building_name'
            }
        }
        
        # 보드 타입이 있으면 동적 컬럼 로드
        if board_type:
            self._load_dynamic_columns()
    
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
            conn = get_db_connection(self.db_path, row_factory=True)
            cursor = conn.cursor()
            
            # 테이블이 존재하는지 확인
            cursor.execute("""
                SELECT COUNT(*) FROM sqlite_master 
                WHERE type='table' AND name=?
            """, (config['table'],))
            
            if cursor.fetchone()[0] == 0:
                # 테이블이 없으면 생성
                self._create_default_table(cursor, search_type, config)
                conn.commit()
            
            # 검색 필드 결정
            if not search_field:
                search_field = config.get('default_search_field')
            
            # 검색 쿼리 구성
            if query:
                # 특정 필드로 검색
                if search_field:
                    # 선택된 필드가 동적 컬럼인지 확인
                    is_dynamic = False
                    for field_info in config['search_fields']:
                        if isinstance(field_info, dict) and field_info.get('field') == search_field:
                            is_dynamic = field_info.get('is_dynamic', False)
                            break
                    
                    if is_dynamic:
                        # 동적 컬럼(JSON) 검색
                        sql = f"""
                            SELECT * FROM {config['table']}
                            WHERE json_extract(custom_data, '$.{search_field}') LIKE ?
                            ORDER BY {config.get('order_by', 'id')}
                            LIMIT ?
                        """
                    else:
                        # 일반 컬럼 검색
                        sql = f"""
                            SELECT * FROM {config['table']}
                            WHERE {search_field} LIKE ?
                            ORDER BY {config.get('order_by', 'id')}
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
                        SELECT * FROM {config['table']}
                        WHERE {where_sql}
                        ORDER BY {config.get('order_by', 'id')}
                        LIMIT ?
                    """
                    params.append(limit)
            else:
                # 검색어가 없으면 빈 결과 반환 (성능상 이유로 전체 데이터 반환 방지)
                return {
                    'results': [],
                    'config': config,
                    'total': 0,
                    'message': '검색어를 입력해주세요.'
                }
            
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            results = [dict(row) for row in rows]
            conn.close()
            
        except Exception as e:
            logging.error(f"Search error for {search_type}: {e}")
            return {
                'results': [],
                'config': config,
                'error': str(e)
            }
        
        return {
            'results': results,
            'config': config,
            'total': len(results)
        }
    
    def _create_default_table(self, cursor, search_type: str, config: Dict[str, Any]):
        """
        기본 테이블 생성 (없는 경우)
        
        Args:
            cursor: DB 커서
            search_type: 검색 타입
            config: 검색 설정
        """
        if search_type == 'company':
            # partners_cache 테이블은 이미 존재하므로 생성 불필요
            pass
            
        elif search_type == 'person':
            # person_master 테이블은 이미 존재하므로 생성 불필요
            pass
            
        elif search_type == 'department':
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS department_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    department_code TEXT UNIQUE NOT NULL,
                    department_name TEXT NOT NULL,
                    parent_department TEXT,
                    manager TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 샘플 데이터 추가
            cursor.execute("""
                INSERT OR IGNORE INTO department_master 
                (department_code, department_name, parent_department) 
                VALUES 
                ('DEPT001', '안전관리팀', '안전환경본부'),
                ('DEPT002', '환경관리팀', '안전환경본부'),
                ('DEPT003', '품질관리팀', '품질본부')
            """)
            
        elif search_type == 'building':
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS building_master (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    building_code TEXT UNIQUE NOT NULL,
                    building_name TEXT NOT NULL,
                    location TEXT,
                    floors INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 샘플 데이터 추가
            cursor.execute("""
                INSERT OR IGNORE INTO building_master 
                (building_code, building_name, location) 
                VALUES 
                ('BLD001', '본관', '서울특별시 강남구'),
                ('BLD002', '연구동', '서울특별시 강남구'),
                ('BLD003', '생산동', '경기도 화성시')
            """)
    
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
            conn = get_db_connection(self.db_path, row_factory=True)
            cursor = conn.cursor()
            
            cursor.execute(f"""
                SELECT * FROM {config['table']}
                WHERE {config['id_field']} = ?
            """, (item_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            
        except Exception as e:
            logging.error(f"Get item error for {search_type}: {e}")
        
        return None