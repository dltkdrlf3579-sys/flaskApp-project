"""
보드 서비스 계층
각 보드에 대한 공통 서비스 로직을 제공합니다.
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from db_connection import get_db_connection
from db.upsert import safe_upsert

# 보드 설정
BOARD_CONFIGS = {
    'accident': {
        'board_type': 'accident',
        'display_name': '협력사 사고',
        'number_prefix': 'ACC',
        'cache_table': 'accidents_cache',
        'column_table': 'accident_column_config',
        'upload_path': 'uploads/accident/',
    },
    'safety_instruction': {
        'board_type': 'safety_instruction',
        'display_name': '환경안전 지시서',
        'number_prefix': 'SI',
        'cache_table': 'safety_instructions',
        'column_table': 'safety_instruction_column_config',
        'upload_path': 'uploads/safety_instruction/',
    },
    'change_request': {
        'board_type': 'change_request',
        'display_name': '기준정보 변경요청',
        'number_prefix': 'CR',
        'cache_table': 'change_requests',
        'column_table': 'change_request_column_config',
        'upload_path': 'uploads/change_request/',
    },
    # 추가: Follow SOP / Full Process 보드 지원
    'follow_sop': {
        'board_type': 'follow_sop',
        'display_name': 'Follow SOP',
        'number_prefix': 'FS',
        'cache_table': 'follow_sop',
        'column_table': 'follow_sop_column_config',
        'upload_path': 'uploads/follow_sop/',
    },
    'full_process': {
        'board_type': 'full_process',
        'display_name': 'Full Process',
        'number_prefix': 'FP',
        'cache_table': 'full_process',
        'column_table': 'full_process_column_config',
        'upload_path': 'uploads/full_process/',
    }
}

class ColumnService:
    """컬럼 관리 서비스"""
    
    def __init__(self, board_type: str, db_path: str):
        self.board_type = board_type
        self.db_path = db_path
        self.config = BOARD_CONFIGS.get(board_type)
        if not self.config:
            raise ValueError(f"Unknown board type: {board_type}")
    
    def list(self, active_only=True) -> List[Dict]:
        """컬럼 목록 조회 (관리 UI용 보호 컬럼 제외)

        - 시스템/보호 컬럼은 목록에서 숨긴다
        - 기본 필터: is_deleted=0, (옵션) is_active=1
        """
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row

        # 보호 키: 폼 전용/기본키/등록일은 숨김
        protected_common = {"attachments","detailed_content","notes","note","created_at"}
        per_board = {
            'accident': {"accident_number"},
            'safety_instruction': {"issue_number"},
            'change_request': {"request_number"},
            'follow_sop': {"work_req_no"},
            'full_process': {"fullprocess_number"},
        }
        protected = protected_common | per_board.get(self.board_type, set())

        # f-string 내 중첩 중괄호/따옴표로 SyntaxError가 나므로, 별도로 구성
        protected_lowers = sorted({(k or '').lower() for k in protected})
        protected_sql_list = ','.join("'" + k.replace("'", "''") + "'" for k in protected_lowers)

        where_clauses = [
            "COALESCE(is_deleted, 0) = 0",
            "COALESCE(is_system, 0) = 0",
            f"LOWER(column_key) NOT IN ({protected_sql_list})",
        ]
        if active_only:
            where_clauses.append("COALESCE(is_active, 1) = 1")

        query = (
            f"SELECT * FROM {self.config['column_table']} "
            f"WHERE {' AND '.join(where_clauses)} "
            f"ORDER BY column_order"
        )

        columns = conn.execute(query).fetchall()
        conn.close()

        return [dict(col) for col in columns]

    @staticmethod
    def _is_protected_key(column_key: str) -> bool:
        return column_key in {"attachments", "detailed_content", "notes"}
    
    def add(self, data: Dict) -> int:
        """컬럼 추가"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        # column_key 자동 생성 (필요시)
        column_key = data.get('column_key')
        if not column_key:
            cursor.execute(f"""
                SELECT MAX(CAST(SUBSTR(column_key, 7) AS INTEGER))
                FROM {self.config['column_table']}
                WHERE column_key LIKE 'column%'
            """)
            max_num = cursor.fetchone()[0] or 0
            column_key = f"column{max_num + 1}"
        
        # 최대 순서 번호 조회
        cursor.execute(f"SELECT MAX(column_order) FROM {self.config['column_table']}")
        max_order = cursor.fetchone()[0] or 0
        
        # 테이블에 따라 동적으로 컬럼 구성
        columns = ['column_key', 'column_name', 'column_type', 'column_order', 'is_active']
        values = [column_key, data['column_name'], data['column_type'], max_order + 1, 1]
        
        # dropdown_options 처리
        columns.append('dropdown_options')
        if data['column_type'] == 'dropdown':
            values.append(json.dumps(data.get('dropdown_options', [])))
        else:
            values.append(None)
        
        # table_name과 table_type이 테이블에 있는지 확인
        # PostgreSQL: information_schema를 통해 컬럼 정보 조회
        cursor.execute("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = %s
        """, (self.config['column_table'],))
        existing_columns = [row[0] for row in cursor.fetchall()]
        
        if 'table_name' in existing_columns and 'table_name' in data:
            columns.append('table_name')
            values.append(data['table_name'])
        
        if 'table_type' in existing_columns and 'table_type' in data:
            columns.append('table_type')
            values.append(data['table_type'])
        
        # created_at, updated_at 추가
        columns.extend(['created_at', 'updated_at'])
        
        # 쿼리 구성
        placeholders = ', '.join(['%s' for _ in values])
        columns_str = ', '.join(columns)
        
        cursor.execute_with_returning_id(f"""
            INSERT INTO {self.config['column_table']}
            ({columns_str})
            VALUES ({placeholders}, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, values)
        
        column_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return column_id
    
    def update(self, column_id: int, data: Dict) -> bool:
        """컬럼 수정"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()

        # 보호 컬럼 편집 방지
        try:
            row = cursor.execute(
                f"SELECT column_key, COALESCE(is_system,0) FROM {self.config['column_table']} WHERE id = %s",
                (column_id,)
            ).fetchone()
            if row:
                col_key = row[0] if not isinstance(row, sqlite3.Row) else row[0]
                is_system = row[1] if not isinstance(row, sqlite3.Row) else row[1]
                if is_system == 1 or self._is_protected_key(str(col_key)):
                    raise ValueError("Protected column cannot be modified")
        except Exception:
            # 조회 실패 시에도 안전하게 진행 차단
            raise

        update_fields = []
        params = []
        
        if 'column_name' in data:
            update_fields.append("column_name = %s")
            params.append(data['column_name'])
        
        if 'column_type' in data:
            update_fields.append("column_type = %s")
            params.append(data['column_type'])
        
        if 'dropdown_options' in data:
            update_fields.append("dropdown_options = %s")
            params.append(json.dumps(data['dropdown_options']))
        
        if 'is_active' in data:
            update_fields.append("is_active = %s")
            params.append(1 if data['is_active'] else 0)
        
        if 'column_order' in data:
            update_fields.append("column_order = %s")
            params.append(data['column_order'])
        
        if update_fields:
            update_fields.append("updated_at = CURRENT_TIMESTAMP")
            params.append(column_id)
            
            query = f"""
                UPDATE {self.config['column_table']}
                SET {', '.join(update_fields)}
                WHERE id = %s
            """
            cursor.execute(query, params)
            conn.commit()
        
        conn.close()
        return True
    
    def delete(self, column_id: int, hard_delete=False) -> bool:
        """컬럼 삭제 (기본: 비활성화)"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()

        # 보호 컬럼 삭제 방지
        row = cursor.execute(
            f"SELECT column_key, COALESCE(is_system,0) FROM {self.config['column_table']} WHERE id = %s",
            (column_id,)
        ).fetchone()
        if row:
            # sqlite3.Row/tuple 모두 대응
            col_key = row[0]
            is_system = row[1]
            if is_system == 1 or self._is_protected_key(str(col_key)):
                conn.close()
                raise ValueError("Protected column cannot be deleted")

        if hard_delete:
            cursor.execute(f"DELETE FROM {self.config['column_table']} WHERE id = %s", (column_id,))
        else:
            cursor.execute(f"""
                UPDATE {self.config['column_table']}
                SET is_active = 0, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (column_id,))
        
        conn.commit()
        conn.close()
        return True
    
    def reorder(self, items: List[Dict]) -> bool:
        """컬럼 순서 변경"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        for item in items:
            cursor.execute(f"""
                UPDATE {self.config['column_table']}
                SET column_order = %s, updated_at = CURRENT_TIMESTAMP
                WHERE id = %s
            """, (item['column_order'], item['id']))
        
        conn.commit()
        conn.close()
        return True


class CodeService:
    """드롭다운 코드 관리 서비스"""
    
    def __init__(self, board_type: str, db_path: str):
        self.board_type = board_type
        self.db_path = db_path
    
    def list(self, column_key: str) -> List[Dict]:
        """드롭다운 코드 목록 조회"""
        conn = get_db_connection(self.db_path)
        # PostgreSQL에서는 row_factory 불필요 (psycopg이 자동 처리)
        
        # v2 테이블 우선 조회
        codes = conn.execute("""
            SELECT * FROM dropdown_option_codes_v2
            WHERE board_type = %s AND column_key = %s AND is_active = 1
            ORDER BY display_order
        """, (self.board_type, column_key)).fetchall()
        
        # v2에 없으면 레거시 테이블 조회 (임시 호환)
        if not codes:
            codes = conn.execute("""
                SELECT * FROM dropdown_option_codes
                WHERE column_key = %s AND is_active = 1
                ORDER BY display_order
            """, (column_key,)).fetchall()
        
        conn.close()
        
        return [dict(code) for code in codes]
    
    def save(self, column_key: str, codes: List[Dict]) -> bool:
        """드롭다운 코드 일괄 저장"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        # Ensure unique index for ON CONFLICT target in PostgreSQL
        try:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                cursor.execute(
                    """
                    CREATE UNIQUE INDEX IF NOT EXISTS idx_doc_v2_uniq
                    ON dropdown_option_codes_v2 (board_type, column_key, option_code)
                    """
                )
        except Exception as e:
            # If creation fails, continue; UPSERT may still work if constraint already exists
            import logging as _log
            _log.debug(f"Ensure unique index skipped/failed: {e}")

        # 기존 코드 비활성화
        cursor.execute("""
            UPDATE dropdown_option_codes_v2
            SET is_active = 0
            WHERE board_type = %s AND column_key = %s
        """, (self.board_type, column_key))
        
        # 새 코드 추가 (safe_upsert 사용)
        for i, code in enumerate(codes):
            option_data = {
                'board_type': self.board_type,
                'column_key': column_key,
                'option_code': code['code'],
                'option_value': code['value'],
                'display_order': i,
                'is_active': 1,
                'created_at': None,  # 자동으로 처리됨
                'updated_at': None   # 자동으로 처리됨
            }
            safe_upsert(conn, 'dropdown_option_codes_v2', option_data)
        
        conn.commit()
        conn.close()
        return True
    
    def delete(self, code_id: int) -> bool:
        """드롭다운 코드 삭제"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dropdown_option_codes_v2
            SET is_active = 0
            WHERE id = %s
        """, (code_id,))
        
        conn.commit()
        conn.close()
        return True


class ItemService:
    """보드 아이템 관리 서비스"""
    
    def __init__(self, board_type: str, db_path: str):
        self.board_type = board_type
        self.db_path = db_path
        self.config = BOARD_CONFIGS.get(board_type)
        if not self.config:
            raise ValueError(f"Unknown board type: {board_type}")
    
    def list(self, filters: Dict = None, page: int = 1, per_page: int = 10) -> Dict:
        """아이템 목록 조회"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        
        # WHERE 절 구성
        where_clauses = ["is_deleted = 0"]
        params = []
        
        if filters:
            if filters.get('company_name'):
                where_clauses.append("company_name LIKE %s")
                params.append(f"%{filters['company_name']}%")
            
            if filters.get('business_number'):
                where_clauses.append("business_number LIKE %s")
                params.append(f"%{filters['business_number']}%")
            
            if filters.get('date_start'):
                where_clauses.append(f"{self.board_type}_date >= %s")
                params.append(filters['date_start'])
            
            if filters.get('date_end'):
                where_clauses.append(f"{self.board_type}_date <= %s")
                params.append(filters['date_end'])
        
        where_sql = " AND ".join(where_clauses)
        
        # 전체 개수 조회
        total_count = conn.execute(
            f"SELECT COUNT(*) FROM {self.config['cache_table']} WHERE {where_sql}",
            params
        ).fetchone()[0]
        
        # 페이징 처리
        offset = (page - 1) * per_page
        params.extend([per_page, offset])
        
        # 데이터 조회
        items = conn.execute(f"""
            SELECT * FROM {self.config['cache_table']}
            WHERE {where_sql}
            ORDER BY id DESC
            LIMIT %s OFFSET %s
        """, params).fetchall()
        
        conn.close()
        
        return {
            'items': [dict(item) for item in items],
            'total': total_count,
            'page': page,
            'per_page': per_page,
            'total_pages': (total_count + per_page - 1) // per_page
        }
    
    def detail(self, item_id: int) -> Optional[Dict]:
        """아이템 상세 조회"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        
        item = conn.execute(f"""
            SELECT * FROM {self.config['cache_table']}
            WHERE id = %s AND is_deleted = 0
        """, (item_id,)).fetchone()
        
        conn.close()
        
        return dict(item) if item else None
    
    def register(self, data: Dict) -> Dict:
        """아이템 등록"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        # 번호 생성
        year = datetime.now().year
        month = datetime.now().month
        
        cursor.execute(f"""
            SELECT MAX(CAST(SUBSTR({self.board_type}_number, -4) AS INTEGER))
            FROM {self.config['cache_table']}
            WHERE {self.board_type}_number LIKE %s
        """, (f"{self.config['number_prefix']}-{year:04d}-{month:02d}-%",))
        
        max_seq = cursor.fetchone()[0] or 0
        number = f"{self.config['number_prefix']}-{year:04d}-{month:02d}-{max_seq + 1:04d}"
        
        # 데이터 저장
        cursor.execute_with_returning_id(f"""
            INSERT INTO {self.config['cache_table']}
            ({self.board_type}_number, {self.board_type}_date, title, content, 
             custom_data, created_by, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        """, (
            number,
            data.get('date'),
            data.get('title'),
            data.get('content'),
            json.dumps(data.get('custom_data', {})),
            data.get('created_by', 'system')
        ))
        
        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return {
            'id': item_id,
            'number': number
        }
    
    def update(self, item_id: int, data: Dict) -> bool:
        """아이템 수정"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(f"""
            UPDATE {self.config['cache_table']}
            SET title = %s, content = %s, custom_data = %s, 
                updated_at = CURRENT_TIMESTAMP, updated_by = %s
            WHERE id = %s
        """, (
            data.get('title'),
            data.get('content'),
            json.dumps(data.get('custom_data', {})),
            data.get('updated_by', 'system'),
            item_id
        ))
        
        conn.commit()
        conn.close()
        return True
    
    def delete(self, item_ids: List[int], hard_delete=False) -> bool:
        """아이템 삭제"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        if hard_delete:
            cursor.execute(
                f"DELETE FROM {self.config['cache_table']} WHERE id IN ({','.join('%s' * len(item_ids))})",
                item_ids
            )
        else:
            cursor.execute(
                f"""UPDATE {self.config['cache_table']}
                   SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP
                   WHERE id IN ({','.join('%s' * len(item_ids))})""",
                item_ids
            )
        
        conn.commit()
        conn.close()
        return True


def get_board_type_from_path(path: str) -> Optional[str]:
    """경로에서 보드 타입 추출"""
    # /api/accident/columns -> accident
    # /api/safety-instruction/columns -> safety_instruction
    
    parts = path.split('/')
    if len(parts) >= 3 and parts[1] == 'api':
        board_name = parts[2]
        # 하이픈을 언더스코어로 변환
        board_type = board_name.replace('-', '_')
        return board_type if board_type in BOARD_CONFIGS else None
    return None

class AttachmentService:
    """첨부파일 관리 서비스 - 보드 격리 원칙 준수"""
    
    # 게시판별 ID 컬럼 매핑 (중앙화)
    ID_COLUMN_MAP = {
        'accident': 'accident_number',
        'safety_instruction': 'issue_number',
        'follow_sop': 'work_req_no',
        'full_process': 'fullprocess_number',
        'change_request': 'request_number'
    }
    
    def __init__(self, board_type: str, db_path: str, conn=None):
        """
        첨부파일 서비스 초기화
        
        Args:
            board_type: 보드 타입 (accident, safety_instruction, change_request)
            db_path: 데이터베이스 경로
            conn: 기존 DB 연결 (없으면 새로 생성)
        """
        self.board_type = board_type
        self.db_path = db_path
        self.conn = conn  # 기존 연결 재사용
        self.config = BOARD_CONFIGS.get(board_type)
        if not self.config:
            raise ValueError(f"Unknown board type: {board_type}")
        
        # 보드별 첨부파일 테이블명 설정
        self.attachment_table = f"{board_type}_attachments"
        
        # ID 컬럼명 설정 (매핑 테이블 사용)
        self.id_column = self.ID_COLUMN_MAP.get(board_type, 'item_id')
        
        # 테이블 생성 (없으면)
        self._ensure_table_exists()
    
    def _ensure_table_exists(self):
        """첨부파일 테이블 생성 (없으면)"""
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        cursor = conn.cursor()
        
        # 보드별 테이블 전략 사용 - 통일화된 id_column 사용 (PostgreSQL 호환)
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {self.attachment_table} (
                id SERIAL PRIMARY KEY,
                {self.id_column} TEXT NOT NULL,  -- 보드별 식별자 (accident_number, issue_number, request_number 등)
                file_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                file_size INTEGER,
                mime_type TEXT,
                description TEXT,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                uploaded_by TEXT DEFAULT 'system',
                is_deleted INTEGER DEFAULT 0
            )
        """)

        # 호환성: 기존 테이블에 is_deleted 컬럼이 없을 수도 있으므로 보강
        def _col_exists(table: str, col: str) -> bool:
            try:
                if hasattr(conn, 'is_postgres') and conn.is_postgres:
                    cursor.execute(
                        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                        (table.lower(), col.lower())
                    )
                    return cursor.fetchone() is not None
                else:
                    # SQLite는 지원하지 않음 - PostgreSQL만 사용
                    return False
            except Exception:
                return False

        try:
            if not _col_exists(self.attachment_table, 'is_deleted'):
                cursor.execute(f"ALTER TABLE {self.attachment_table} ADD COLUMN is_deleted INTEGER DEFAULT 0")
        except Exception:
            # 이미 추가되어 있거나 권한 문제 등은 무시 (list()에서 동적 WHERE 처리로 회피)
            pass

        # uploaded_at 누락 테이블 보강 (정렬 안정성)
        try:
            if not _col_exists(self.attachment_table, 'uploaded_at'):
                cursor.execute(f"ALTER TABLE {self.attachment_table} ADD COLUMN uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        except Exception:
            # 이미 존재하거나 권한 이슈는 무시 (list()에서 id로 정렬 폴백)
            pass
        
        # 인덱스 추가 (중앙화된 id_column 사용)
        cursor.execute(f"""
            CREATE INDEX IF NOT EXISTS idx_{self.attachment_table}_{self.id_column}
            ON {self.attachment_table}({self.id_column})
        """)
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.commit()
            conn.close()
        else:
            conn.commit()  # 커밋은 하지만 연결은 닫지 않음
    
    def list(self, item_id: str) -> List[Dict]:
        """
        특정 아이템의 첨부파일 목록 조회
        
        Args:
            item_id: 아이템 식별자
            
        Returns:
            첨부파일 목록
        """
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()
        
        # 컬럼 존재 여부 체크
        def _has_col(col: str) -> bool:
            try:
                cursor.execute(
                    "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                    (self.attachment_table.lower(), col.lower())
                )
                return cursor.fetchone() is not None
            except Exception:
                return False

        # PostgreSQL native query
        where_deleted = " AND is_deleted = 0" if _has_col('is_deleted') else ""
        order_col = 'uploaded_at' if _has_col('uploaded_at') else 'id'

        query = f"SELECT * FROM {self.attachment_table} WHERE {self.id_column} = %s{where_deleted} ORDER BY {order_col} DESC"
        cursor.execute(query, (item_id,))
        attachments = cursor.fetchall()
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        return [dict(attachment) for attachment in attachments]

    def get_list(self, item_id: str) -> List[Dict]:
        """
        list 메서드의 별칭 (호환성 유지)
        """
        return self.list(item_id)
    
    def add(self, item_id: str, file, meta: Dict = None) -> int:
        """
        첨부파일 추가
        
        Args:
            item_id: 아이템 식별자
            file: 업로드된 파일 객체 (werkzeug.FileStorage)
            meta: 추가 메타데이터 (description, uploaded_by 등)
            
        Returns:
            첨부파일 ID
        """
        import os
        import time
        from werkzeug.utils import secure_filename
        
        if not file or not file.filename:
            raise ValueError("파일이 없습니다.")
        
        # 안전한 파일명 생성
        original_filename = secure_filename(file.filename)
        timestamp = str(int(time.time()))
        safe_filename = f"{timestamp}_{original_filename}"
        
        # 업로드 경로 생성
        upload_folder = self.config['upload_path']
        os.makedirs(upload_folder, exist_ok=True)
        
        # 파일 저장
        file_path = os.path.join(upload_folder, safe_filename)
        file.save(file_path)
        
        # 파일 크기 계산
        file_size = os.path.getsize(file_path)
        
        # MIME 타입 추출
        mime_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
        
        # DB에 저장
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()

        # PostgreSQL RETURNING clause
        sql = f"""
            INSERT INTO {self.attachment_table}
            ({self.id_column}, file_name, file_path, file_size, mime_type, description, uploaded_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id
        """

        cursor.execute(sql, (
            item_id,
            original_filename,
            file_path,
            file_size,
            mime_type,
            meta.get('description', '') if meta else '',
            meta.get('uploaded_by', 'system') if meta else 'system'
        ))

        # PostgreSQL에서 RETURNING 결과 가져오기
        result = cursor.fetchone()
        attachment_id = result['id'] if result else None
        conn.commit()
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        logging.info(f"[{self.board_type}] 첨부파일 추가: {original_filename} (ID: {attachment_id})")
        
        return attachment_id
    
    def update_meta(self, attachment_id: int, meta: Dict) -> bool:
        """
        첨부파일 메타데이터 수정
        
        Args:
            attachment_id: 첨부파일 ID
            meta: 수정할 메타데이터
            
        Returns:
            성공 여부
        """
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()
        
        update_fields = []
        params = []
        
        if 'description' in meta:
            update_fields.append("description = %s")
            params.append(meta['description'])

        if 'uploaded_by' in meta:
            update_fields.append("uploaded_by = %s")
            params.append(meta['uploaded_by'])
        
        if not update_fields:
            if should_close:
                conn.close()
            return False
        
        params.append(attachment_id)
        
        cursor.execute(f"""
            UPDATE {self.attachment_table}
            SET {', '.join(update_fields)}
            WHERE id = %s AND is_deleted = 0
        """, params)
        
        conn.commit()
        success = cursor.rowcount > 0
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        return success
    
    def delete(self, ids: List[int], hard_delete: bool = False) -> int:
        """
        첨부파일 삭제 (기본: soft delete)
        
        Args:
            ids: 삭제할 첨부파일 ID 목록
            hard_delete: True면 실제 파일도 삭제
            
        Returns:
            삭제된 개수
        """
        if not ids:
            return 0
        
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        cursor = conn.cursor()
        
        if hard_delete:
            # 파일 경로 먼저 조회
            cursor.execute(f"""
                SELECT file_path FROM {self.attachment_table}
                WHERE id IN ({','.join(['%s'] * len(ids))})
            """, ids)
            file_paths = [row[0] for row in cursor.fetchall()]
            
            # DB에서 삭제
            cursor.execute(f"""
                DELETE FROM {self.attachment_table}
                WHERE id IN ({','.join(['%s'] * len(ids))})
            """, ids)
            
            # 실제 파일 삭제
            import os
            for file_path in file_paths:
                if os.path.exists(file_path):
                    try:
                        os.remove(file_path)
                        logging.info(f"파일 삭제: {file_path}")
                    except Exception as e:
                        logging.error(f"파일 삭제 실패: {file_path}, {e}")
        else:
            # Soft delete
            cursor.execute(f"""
                UPDATE {self.attachment_table}
                SET is_deleted = 1
                WHERE id IN ({','.join(['%s'] * len(ids))})
            """, ids)
        
        deleted_count = cursor.rowcount
        conn.commit()
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        logging.info(f"[{self.board_type}] {deleted_count}개 첨부파일 삭제")
        
        return deleted_count
    
    def download(self, attachment_id: int) -> Optional[Dict]:
        """
        첨부파일 다운로드 정보 조회
        
        Args:
            attachment_id: 첨부파일 ID
            
        Returns:
            파일 정보 (path, name, mime_type)
        """
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()

        cursor.execute(f"""
            SELECT file_path, file_name, mime_type
            FROM {self.attachment_table}
            WHERE id = %s AND is_deleted = 0
        """, (attachment_id,))
        attachment = cursor.fetchone()
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        if attachment:
            import os
            # PostgreSQL returns tuple, not dict
            file_path, file_name, mime_type = attachment
            if os.path.exists(file_path):
                return {
                    'path': file_path,
                    'name': file_name,
                    'mime_type': mime_type
                }
        
        return None
    
    def bulk_add(self, item_id: str, files: List, meta: Dict = None) -> List[int]:
        """
        여러 파일 일괄 업로드
        
        Args:
            item_id: 아이템 식별자
            files: 파일 목록
            meta: 공통 메타데이터
            
        Returns:
            첨부파일 ID 목록
        """
        import os
        import time
        from werkzeug.utils import secure_filename
        
        attachment_ids = []
        
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()
        
        for file in files:
            if file and file.filename:
                try:
                    # 안전한 파일명 생성
                    original_filename = secure_filename(file.filename)
                    timestamp = str(int(time.time()))
                    safe_filename = f"{timestamp}_{original_filename}"
                    
                    # 업로드 경로 생성
                    upload_folder = self.config['upload_path']
                    os.makedirs(upload_folder, exist_ok=True)
                    
                    # 파일 저장
                    file_path = os.path.join(upload_folder, safe_filename)
                    file.save(file_path)
                    
                    # 파일 크기 계산
                    file_size = os.path.getsize(file_path)
                    
                    # MIME 타입 추출
                    mime_type = file.content_type if hasattr(file, 'content_type') else 'application/octet-stream'
                    
                    # DB에 저장 - PostgreSQL RETURNING 사용
                    sql = f"""
                        INSERT INTO {self.attachment_table}
                        ({self.id_column}, file_name, file_path, file_size, mime_type, description, uploaded_by)
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """

                    cursor.execute(sql, (
                        item_id,
                        original_filename,
                        file_path,
                        file_size,
                        mime_type,
                        meta.get('description', '') if meta else '',
                        meta.get('uploaded_by', 'system') if meta else 'system'
                    ))

                    # PostgreSQL에서 RETURNING 결과 가져오기
                    result = cursor.fetchone()
                    attachment_id = result[0] if result else None
                    attachment_ids.append(attachment_id)
                    logging.info(f"[{self.board_type}] 첨부파일 추가: {original_filename} (ID: {attachment_id})")
                    
                except Exception as e:
                    logging.error(f"파일 업로드 실패: {file.filename}, {e}")
        
        # 커밋
        conn.commit()
        
        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()
        
        return attachment_ids
    
    def get_stats(self, item_id: str = None) -> Dict:
        """
        첨부파일 통계 조회
        
        Args:
            item_id: 특정 아이템만 조회 (None이면 전체)
            
        Returns:
            통계 정보
        """
        # 기존 연결이 있으면 재사용, 없으면 새로 생성
        if self.conn:
            conn = self.conn
            should_close = False
        else:
            conn = get_db_connection(self.db_path)
            should_close = True
        
        cursor = conn.cursor()

        if item_id:
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(file_size) as total_size,
                    AVG(file_size) as avg_size,
                    MAX(file_size) as max_size
                FROM {self.attachment_table}
                WHERE {self.id_column} = %s AND is_deleted = 0
            """, (item_id,))
        else:
            cursor.execute(f"""
                SELECT
                    COUNT(*) as total_count,
                    SUM(file_size) as total_size,
                    AVG(file_size) as avg_size,
                    MAX(file_size) as max_size,
                    COUNT(DISTINCT {self.id_column}) as item_count
                FROM {self.attachment_table}
                WHERE is_deleted = 0
            """)

        stats = cursor.fetchone()

        # 새로 생성한 연결만 닫기
        if should_close:
            conn.close()

        # Convert tuple to dict
        if item_id:
            return {
                'total_count': stats[0] or 0,
                'total_size': stats[1] or 0,
                'avg_size': stats[2] or 0,
                'max_size': stats[3] or 0
            }
        else:
            return {
                'total_count': stats[0] or 0,
                'total_size': stats[1] or 0,
                'avg_size': stats[2] or 0,
                'max_size': stats[3] or 0,
                'item_count': stats[4] or 0
            }
