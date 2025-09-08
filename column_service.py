"""
동적 컬럼 관리 공통 서비스
모든 보드의 동적 컬럼 설정을 통합 관리
"""
import sqlite3
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from db_connection import get_db_connection

class ColumnConfigService:
    """동적 컬럼 설정 관리 서비스"""
    
    def __init__(self, board_type: str, db_path: str):
        """
        Args:
            board_type: 보드 타입 (accident, safety_instruction, change_request)
            db_path: 데이터베이스 경로
        """
        self.board_type = board_type
        self.db_path = db_path
        self.table_name = f"{board_type}_column_config"
        self.data_table = self._get_data_table_name()
        
        # 테이블 생성 (없으면)
        self._ensure_tables_exist()
    
    
    def _get_data_table_name(self) -> str:
        """보드별 데이터 테이블명 반환"""
        table_map = {
            'accident': 'accidents_cache',
            'safety_instruction': 'safety_instructions',
            'change_request': 'change_requests',
            'partner_standards': 'partner_standards',
            'follow_sop': 'follow_sop',
            'full_process': 'full_process'
        }
        return table_map.get(self.board_type, f"{self.board_type}s")
    
    def _ensure_tables_exist(self):
        """필요한 테이블 생성"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        # 컬럼 설정 테이블
        # Postgres에서는 AUTOINCREMENT 문법이 없어 CREATE는 생략하고
        # 아래 보강 로직(ALTER)만 수행한다.
        if not (hasattr(conn, 'is_postgres') and conn.is_postgres):
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    column_key TEXT UNIQUE NOT NULL,
                    column_name TEXT NOT NULL,
                    column_type TEXT NOT NULL,
                    column_order INTEGER DEFAULT 999,
                    is_active INTEGER DEFAULT 1,
                    is_required INTEGER DEFAULT 0,
                    dropdown_options TEXT,  -- JSON 형식
                    tab TEXT,
                    column_span INTEGER DEFAULT 1,
                    linked_columns TEXT,
                    is_deleted INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        # 데이터 테이블 체크는 스킵 - 컬럼 설정에는 불필요
        # IQADB 테이블은 존재하지 않을 수 있음
        
        # 누락 컬럼 보강 (PostgreSQL/SQLite 공용)
        def _has_column_pg(table: str, col: str) -> bool:
            try:
                cursor.execute(
                    "SELECT COUNT(*) FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                    (table, col,)
                )
                return (cursor.fetchone() or [0])[0] > 0
            except Exception:
                return False

        def _has_column_sqlite(table: str, col: str) -> bool:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM pragma_table_info('{table}') WHERE name = ?", (col,))
                return (cursor.fetchone() or [0])[0] > 0
            except Exception:
                return False

        def has_column(table: str, col: str) -> bool:
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # information_schema는 소문자 기준
                return _has_column_pg(table.lower(), col.lower())
            return _has_column_sqlite(table, col)

        def add_column(col: str, ddl: str):
            try:
                cursor.execute(f"ALTER TABLE {self.table_name} ADD COLUMN {col} {ddl}")
            except Exception:
                # 이미 존재하거나 권한 문제 등은 조용히 무시 (다음 단계로 진행)
                pass

        # 필수 컬럼 체크/추가
        if not has_column(self.table_name, 'is_required'):
            add_column('is_required', 'INTEGER DEFAULT 0')
        if not has_column(self.table_name, 'tab'):
            add_column('tab', 'TEXT')
        if not has_column(self.table_name, 'column_span'):
            add_column('column_span', 'INTEGER DEFAULT 1')
        if not has_column(self.table_name, 'linked_columns'):
            add_column('linked_columns', 'TEXT')
        if not has_column(self.table_name, 'is_deleted'):
            add_column('is_deleted', 'INTEGER DEFAULT 0')
        if not has_column(self.table_name, 'input_type'):
            add_column('input_type', 'TEXT')
        # 테이블 메타 컬럼 보강
        if not has_column(self.table_name, 'table_group'):
            add_column('table_group', 'TEXT')
        if not has_column(self.table_name, 'table_type'):
            add_column('table_type', 'TEXT')
        if not has_column(self.table_name, 'table_name'):
            add_column('table_name', 'TEXT')

        conn.commit()
        conn.close()
    
    def list_columns(self, active_only: bool = False) -> List[Dict[str, Any]]:
        """
        컬럼 목록 조회
        
        Args:
            active_only: True면 활성 컬럼만 조회
        
        Returns:
            컬럼 설정 리스트
        """
        conn = get_db_connection(self.db_path, row_factory=True)
        
        # 쿼리 구성 - is_deleted 컬럼이 이제 모든 테이블에 존재
        query = f"SELECT * FROM {self.table_name}"
        conditions = ["(is_deleted = 0 OR is_deleted IS NULL)"]  # 삭제되지 않은 것만
        
        if active_only:
            conditions.append("is_active = 1")
        
        query += " WHERE " + " AND ".join(conditions)
        query += " ORDER BY column_order, id"
        
        columns = conn.execute(query).fetchall()
        conn.close()
        
        result = []
        for col in columns:
            column_dict = dict(col)
            # dropdown_options JSON 파싱
            if column_dict.get('dropdown_options'):
                try:
                    column_dict['dropdown_options'] = json.loads(column_dict['dropdown_options'])
                except json.JSONDecodeError:
                    column_dict['dropdown_options'] = []
            result.append(column_dict)
        
        return result
    
    def get_column(self, column_id: int) -> Optional[Dict[str, Any]]:
        """
        특정 컬럼 조회
        
        Args:
            column_id: 컬럼 ID
        
        Returns:
            컬럼 정보 또는 None
        """
        conn = get_db_connection(self.db_path, row_factory=True)
        
        column = conn.execute(
            f"SELECT * FROM {self.table_name} WHERE id = ?", 
            (column_id,)
        ).fetchone()
        conn.close()
        
        if column:
            column_dict = dict(column)
            if column_dict.get('dropdown_options'):
                try:
                    column_dict['dropdown_options'] = json.loads(column_dict['dropdown_options'])
                except json.JSONDecodeError:
                    column_dict['dropdown_options'] = []
            return column_dict
        
        return None
    
    def add_column(self, column_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        컬럼 추가
        
        Args:
            column_data: 컬럼 정보
        
        Returns:
            추가된 컬럼 정보
        """
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 트랜잭션 시작
            conn.execute("BEGIN IMMEDIATE")
            
            # column_key 자동 생성 (필요시)
            column_key = column_data.get('column_key')
            if not column_key:
                cursor.execute(
                    f"SELECT MAX(CAST(SUBSTR(column_key, 7) AS INTEGER)) FROM {self.table_name} WHERE column_key LIKE 'column%'"
                )
                max_num = cursor.fetchone()[0] or 10
                column_key = f"column{max_num + 1}"
            
            # 같은 column_key의 삭제된 컬럼이 있는지 확인 (복구 가능)
            cursor.execute(
                f"SELECT id FROM {self.table_name} WHERE column_key = ? AND is_deleted = 1",
                (column_key,)
            )
            deleted_column = cursor.fetchone()
            
            if deleted_column:
                # 삭제된 컬럼 복구
                column_id = deleted_column[0]
                cursor.execute(f"""
                    UPDATE {self.table_name}
                    SET column_name = ?, column_type = ?, is_active = 1, is_deleted = 0,
                        dropdown_options = ?, column_span = ?, tab = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (
                    column_data['column_name'],
                    column_data.get('column_type', 'text'),
                    json.dumps(column_data.get('dropdown_options', []), ensure_ascii=False) if column_data.get('dropdown_options') else None,
                    column_data.get('column_span', 1),
                    column_data.get('tab', 'additional'),
                    column_id
                ))
                
                conn.commit()
                logging.info(f"삭제된 컬럼 복구: {column_key}")
                return {
                    'success': True, 
                    'message': '이전에 삭제된 컬럼이 복구되었습니다.',
                    'id': column_id
                }
            
            # 최대 순서 조회
            cursor.execute(f"SELECT MAX(column_order) FROM {self.table_name}")
            max_order = cursor.fetchone()[0] or 0
            
            # dropdown_options JSON 변환
            dropdown_options = column_data.get('dropdown_options', [])
            if isinstance(dropdown_options, list):
                dropdown_options = json.dumps(dropdown_options, ensure_ascii=False)
            
            # input_type 처리 (follow_sop, full_process용)
            input_type = None
            if 'input_type' in column_data:
                input_type = column_data.get('input_type')
            elif column_data.get('column_type') == 'table':
                # column_type이 table인 경우 input_type을 table로 설정
                input_type = 'table'
            
            # 테이블 컬럼 존재 여부 확인
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            cols = [col[1] for col in cursor.fetchall()]
            has_input_type = 'input_type' in cols
            has_table_group = 'table_group' in cols
            has_table_type = 'table_type' in cols
            has_table_name = 'table_name' in cols

            # 동적 INSERT 구성
            fields = ['column_key', 'column_name', 'column_type', 'column_order', 'is_active',
                      'is_required', 'dropdown_options', 'column_span', 'tab']
            # Postgres boolean 호환: 드라이버에 따라 0/1로 전송될 수 있으므로 명시적으로 처리
            _to_bool = lambda v: (v in (1, '1', True, 'true', 't', 'T'))
            if hasattr(conn, 'is_postgres') and conn.is_postgres:
                # 문자열 'true'/'false'로 전달 (BOOLEAN으로 안전 캐스팅됨)
                is_active_val = 'true' if _to_bool(column_data.get('is_active', 1)) else 'false'
                is_required_val = 'true' if _to_bool(column_data.get('is_required', 0)) else 'false'
            else:
                is_active_val = True if _to_bool(column_data.get('is_active', 1)) else False
                is_required_val = True if _to_bool(column_data.get('is_required', 0)) else False
            values = [
                column_key,
                column_data['column_name'],
                column_data.get('column_type', 'text'),
                max_order + 1,
                is_active_val,
                is_required_val,
                dropdown_options,
                column_data.get('column_span', 1),
                column_data.get('tab', 'additional')
            ]
            if has_input_type:
                fields.append('input_type')
                values.append(input_type)
            if has_table_group:
                fields.append('table_group')
                values.append(column_data.get('table_group'))
            if has_table_type:
                fields.append('table_type')
                values.append(column_data.get('table_type'))
            if has_table_name:
                fields.append('table_name')
                values.append(column_data.get('table_name'))

            placeholders = ', '.join(['?'] * len(fields))
            cursor.execute_with_returning_id(
                f"INSERT INTO {self.table_name} ({', '.join(fields)}) VALUES ({placeholders})",
                tuple(values)
            )
            
            column_id = cursor.lastrowid
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            raise
        finally:
            conn.close()
        
        logging.info(f"컬럼 추가됨: {column_key} ({column_data['column_name']})")
        
        return {
            'id': column_id,
            'column_key': column_key,
            'column_name': column_data['column_name'],
            'success': True,
            'message': '컬럼이 추가되었습니다.'
        }
    
    def update_column(self, column_id: int, column_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        컬럼 수정
        
        Args:
            column_id: 컬럼 ID
            column_data: 수정할 컬럼 정보
        
        Returns:
            작업 결과
        """
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 트랜잭션 시작
            conn.execute("BEGIN IMMEDIATE")
            
            # 현재 컬럼 정보 조회
            cursor.execute(
                f"SELECT column_key FROM {self.table_name} WHERE id = ?", 
                (column_id,)
            )
            if not cursor.fetchone():
                conn.rollback()
                return {'success': False, 'message': '컬럼을 찾을 수 없습니다.'}
            
            # is_deleted 플래그만 업데이트하는 경우 (soft delete/복구)
            if 'is_deleted' in column_data and len(column_data) == 1:
                cursor.execute(f"""
                    UPDATE {self.table_name}
                    SET is_deleted = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """, (column_data['is_deleted'], column_id))
                
                conn.commit()
                action = "삭제" if column_data['is_deleted'] == 1 else "복구"
                logging.info(f"컬럼 {action} 처리: {column_id}, is_deleted={column_data['is_deleted']}")
                return {'success': True, 'message': f'컬럼이 {action} 처리되었습니다.'}
            
            # dropdown_options JSON 변환
            if 'dropdown_options' in column_data:
                dropdown_options = column_data['dropdown_options']
                if isinstance(dropdown_options, list):
                    column_data['dropdown_options'] = json.dumps(dropdown_options, ensure_ascii=False)
            
            # 업데이트할 필드 구성
            update_fields = []
            update_values = []
            
            # input_type이 지원되는지 확인
            cursor.execute(f"PRAGMA table_info({self.table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            has_input_type = 'input_type' in columns
            
            allowed_fields = ['column_name', 'column_type', 'is_active', 
                             'is_required', 'dropdown_options', 'column_order', 'column_span', 'tab',
                             'table_group', 'table_type', 'table_name']
            
            # input_type이 있으면 허용 필드에 추가
            if has_input_type:
                allowed_fields.append('input_type')
                # column_type이 table인 경우 자동으로 input_type 설정
                if column_data.get('column_type') == 'table' and 'input_type' not in column_data:
                    column_data['input_type'] = 'table'
            
            for field in allowed_fields:
                if field in column_data:
                    update_fields.append(f"{field} = ?")
                    if field in ('is_active','is_required'):
                        _to_bool = lambda v: (v in (1, '1', True, 'true', 't', 'T'))
                        if hasattr(conn, 'is_postgres') and conn.is_postgres:
                            update_values.append('true' if _to_bool(column_data[field]) else 'false')
                        else:
                            update_values.append(True if _to_bool(column_data[field]) else False)
                    else:
                        update_values.append(column_data[field])
            
            if update_fields:
                update_fields.append("updated_at = CURRENT_TIMESTAMP")
                update_values.append(column_id)
                
                cursor.execute(
                    f"UPDATE {self.table_name} SET {', '.join(update_fields)} WHERE id = ?",
                    update_values
                )
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logging.error(f"컬럼 수정 중 오류: {e}")
            raise
        finally:
            conn.close()
        
        logging.info(f"컬럼 수정됨: ID {column_id}")
        
        return {'success': True, 'message': '컬럼이 수정되었습니다.'}
    
    def delete_column(self, column_id: int) -> Dict[str, Any]:
        """
        컬럼 삭제 (소프트 삭제)
        
        Args:
            column_id: 컬럼 ID
        
        Returns:
            작업 결과
        """
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 트랜잭션 시작
            conn.execute("BEGIN IMMEDIATE")
            
            # 소프트 삭제 (is_deleted = 1로 설정)
            cursor.execute(f"""
                UPDATE {self.table_name} 
                SET is_deleted = 1, updated_at = CURRENT_TIMESTAMP 
                WHERE id = ?
            """, (column_id,))
            
            if cursor.rowcount == 0:
                conn.rollback()
                return {'success': False, 'message': '컬럼을 찾을 수 없습니다.'}
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logging.error(f"컬럼 삭제 중 오류: {e}")
            raise
        finally:
            conn.close()
        
        logging.info(f"컬럼 삭제됨 (soft delete): ID {column_id}")
        
        return {'success': True, 'message': '컬럼이 삭제되었습니다.'}
    
    def update_columns_order(self, order_data: List[Dict[str, int]]) -> Dict[str, Any]:
        """
        컬럼 순서 변경
        
        Args:
            order_data: [{id: 1, column_order: 0}, ...]
        
        Returns:
            작업 결과
        """
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 트랜잭션 시작
            conn.execute("BEGIN IMMEDIATE")
            
            for item in order_data:
                cursor.execute(f"""
                    UPDATE {self.table_name} 
                    SET column_order = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE id = ?
                """, (item['column_order'], item['id']))
            
            conn.commit()
            
        except Exception as e:
            conn.rollback()
            logging.error(f"컬럼 순서 변경 중 오류: {e}")
            raise
        finally:
            conn.close()
        
        logging.info(f"컬럼 순서 변경됨: {len(order_data)}개")
        
        return {'success': True, 'message': '컬럼 순서가 변경되었습니다.'}
    
    def sync_with_external(self, external_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        외부 데이터와 동기화 (더미 데이터용)
        
        Args:
            external_data: 외부 데이터 리스트
        
        Returns:
            동기화 결과
        """
        # 더미 데이터 환경에서는 동기화 건너뛰기
        logging.info(f"더미 데이터 모드 - {self.board_type} 동기화 건너뜀")
        return {
            'success': True, 
            'message': '더미 데이터 모드에서 실행 중',
            'synced': 0
        }
