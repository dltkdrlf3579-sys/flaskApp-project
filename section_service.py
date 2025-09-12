import sqlite3
import json
import logging
from datetime import datetime
from db_connection import get_db_connection

class SectionConfigService:
    """섹션 설정 관리 서비스 클래스"""
    
    def __init__(self, board_type, db_path):
        self.board_type = board_type
        self.db_path = db_path
        self.table_name = self._get_table_name()
    
    def _get_table_name(self):
        """board_type에 따른 테이블 이름 반환"""
        if self.board_type == 'follow_sop':
            return 'follow_sop_sections'
        elif self.board_type == 'full_process':
            return 'full_process_sections'
        else:
            return 'section_config'
        
    def get_sections(self):
        """특정 보드 타입의 모든 활성 섹션 가져오기"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        def _col_exists(table: str, col: str) -> bool:
            try:
                if hasattr(conn, 'is_postgres') and conn.is_postgres:
                    cursor.execute(
                        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                        (table.lower(), col.lower())
                    )
                    return cursor.fetchone() is not None
                else:
                    cursor.execute(f"PRAGMA table_info({table})")
                    return any(r[1].lower() == col.lower() for r in cursor.fetchall())
            except Exception:
                return False

        try:
            # follow_sop과 full_process는 별도 테이블 사용
            if self.board_type in ('follow_sop', 'full_process'):
                table = f"{self.board_type}_sections"
                where = "is_active = 1"
                if _col_exists(table, 'is_deleted'):
                    where += " AND (is_deleted = 0 OR is_deleted IS NULL)"
                cursor.execute(f"SELECT * FROM {table} WHERE {where} ORDER BY section_order")
            else:
                # safety_instruction 등은 기존 section_config 테이블 사용
                where = "board_type = ? AND is_active = 1"
                # section_config에는 is_deleted가 있을 수 있으므로 동적 확인
                add_deleted = _col_exists('section_config', 'is_deleted')
                if add_deleted:
                    where += " AND (is_deleted = 0 OR is_deleted IS NULL)"
                sql = f"SELECT * FROM section_config WHERE {where} ORDER BY section_order"
                if add_deleted:
                    cursor.execute(sql, (self.board_type,))
                else:
                    cursor.execute(sql, (self.board_type,))

            sections = [dict(row) for row in cursor.fetchall()]
            return sections

        except Exception as e:
            logging.error(f"섹션 조회 오류: {e}")
            return self._get_default_sections()
        finally:
            conn.close()
    
    def get_sections_with_columns(self):
        """섹션과 해당 컬럼들을 함께 가져오기"""
        conn = get_db_connection(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 섹션 가져오기
            sections = self.get_sections()
            
            # 각 섹션에 대한 컬럼 가져오기
            table_name = f"{self.board_type}_column_config"
            
            for section in sections:
                where = "tab = ? AND is_active = 1"
                # column_config에 is_deleted 있는지 확인
                def _has_col(col: str) -> bool:
                    try:
                        if hasattr(conn, 'is_postgres') and conn.is_postgres:
                            cursor.execute(
                                "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
                                (table_name.lower(), col.lower())
                            )
                            return cursor.fetchone() is not None
                        else:
                            cursor.execute(f"PRAGMA table_info({table_name})")
                            return any(r[1].lower() == col.lower() for r in cursor.fetchall())
                    except Exception:
                        return False
                if _has_col('is_deleted'):
                    where += " AND (is_deleted = 0 OR is_deleted IS NULL)"
                cursor.execute(f"SELECT * FROM {table_name} WHERE {where} ORDER BY column_order", (section['section_key'],))
                
                section['columns'] = [dict(row) for row in cursor.fetchall()]
            
            return sections
            
        except Exception as e:
            logging.error(f"섹션과 컬럼 조회 오류: {e}")
            return self._get_default_sections()
        finally:
            conn.close()
    
    def _get_default_sections(self):
        """기본 섹션 반환 (폴백용)"""
        if self.board_type == 'safety_instruction':
            return [
                {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
                {'section_key': 'violation_info', 'section_name': '위반정보', 'section_order': 2},
                {'section_key': 'additional', 'section_name': '추가기입정보', 'section_order': 3}
            ]
        if self.board_type == 'follow_sop':
            return [
                {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
                {'section_key': 'work_info', 'section_name': '작업정보', 'section_order': 2},
                {'section_key': 'additional', 'section_name': '추가기입정보', 'section_order': 3}
            ]
        if self.board_type == 'full_process':
            return [
                {'section_key': 'basic_info', 'section_name': '기본정보', 'section_order': 1},
                {'section_key': 'process_info', 'section_name': '프로세스정보', 'section_order': 2},
                {'section_key': 'additional', 'section_name': '추가기입정보', 'section_order': 3}
            ]
        return []
    
    def add_section(self, section_data):
        """새 섹션 추가

        - 클라이언트가 section_key를 제공하면 우선 사용 (유효성/중복 검사 후)
        - 제공되지 않았거나 중복일 경우 custom_section_N 형태로 자동 생성
        """
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 자동으로 section_key 생성 (custom_section_1, custom_section_2 등)
            # 1) 클라이언트 제공 key 우선 사용 시도
            raw_key = (section_data.get('section_key') or '').strip()
            use_client_key = False
            if raw_key:
                # 키 유효성: 소문자/숫자/언더스코어, 문자로 시작
                import re
                if re.fullmatch(r'[a-z][a-z0-9_]*', raw_key):
                    # 중복 검사 (보드 범위)
                    if self.table_name == 'section_config':
                        cursor.execute(
                            "SELECT COUNT(*) FROM section_config WHERE board_type = ? AND LOWER(section_key) = LOWER(?)",
                            (self.board_type, raw_key)
                        )
                    else:
                        cursor.execute(
                            f"SELECT COUNT(*) FROM {self.table_name} WHERE LOWER(section_key) = LOWER(?)",
                            (raw_key,)
                        )
                    exists = (cursor.fetchone() or [0])[0] > 0
                    if not exists:
                        section_key = raw_key
                        use_client_key = True
            # 2) 자동 생성 (client key 없거나/중복/무효)
            if not use_client_key:
                if self.table_name == 'section_config':
                    cursor.execute(
                        """
                        SELECT COUNT(*) FROM section_config 
                        WHERE board_type = ? AND section_key LIKE 'custom_section_%'
                        """,
                        (self.board_type,)
                    )
                else:
                    cursor.execute(
                        f"""
                        SELECT COUNT(*) FROM {self.table_name} 
                        WHERE section_key LIKE 'custom_section_%'
                        """
                    )
                custom_count = cursor.fetchone()[0]
                section_key = f"custom_section_{custom_count + 1}"
            
            # 마지막 순서 가져오기
            if self.table_name == 'section_config':
                cursor.execute("""
                    SELECT MAX(section_order) FROM section_config 
                    WHERE board_type = ?
                """, (self.board_type,))
            else:
                cursor.execute(f"""
                    SELECT MAX(section_order) FROM {self.table_name}
                """)
            
            max_order = cursor.fetchone()[0] or 0
            
            if self.table_name == 'section_config':
                cursor.execute_with_returning_id(
                    """
                    INSERT INTO section_config 
                    (board_type, section_key, section_name, section_order, is_active)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (
                        self.board_type,
                        section_key,
                        section_data['section_name'],
                        max_order + 1,
                    ),
                )
            else:
                cursor.execute_with_returning_id(
                    f"""
                    INSERT INTO {self.table_name} 
                    (section_key, section_name, section_order, is_active)
                    VALUES (?, ?, ?, 1)
                    """,
                    (
                        section_key,
                        section_data['section_name'],
                        max_order + 1,
                    ),
                )
            
            conn.commit()
            section_id = cursor.lastrowid
            
            return {
                'success': True,
                'section_id': section_id,
                'section_key': section_key,
            }
            
        except Exception as e:
            logging.error(f"섹션 추가 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def update_section(self, section_id, section_data):
        """섹션 정보 수정 (섹션명만 수정 가능)"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            update_fields = []
            update_values = []
            
            if 'section_name' in section_data:
                update_fields.append('section_name = ?')
                update_values.append(section_data['section_name'])
            
            if 'section_order' in section_data:
                update_fields.append('section_order = ?')
                update_values.append(section_data['section_order'])
            
            if 'is_active' in section_data:
                update_fields.append('is_active = ?')
                update_values.append(section_data['is_active'])
            
            if not update_fields:
                # 변경사항이 없으면 성공으로 리턴
                return {'success': True}
            
            update_fields.append('updated_at = CURRENT_TIMESTAMP')
            update_values.append(section_id)
            
            if self.table_name == 'section_config':
                update_values.append(self.board_type)
                query = f"""
                    UPDATE section_config 
                    SET {', '.join(update_fields)}
                    WHERE id = ? AND board_type = ?
                """
            else:
                query = f"""
                    UPDATE {self.table_name} 
                    SET {', '.join(update_fields)}
                    WHERE id = ?
                """
            
            cursor.execute(query, update_values)
            conn.commit()
            
            return {'success': True}
            
        except Exception as e:
            logging.error(f"섹션 수정 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def delete_section(self, section_id):
        """섹션 삭제 (soft delete)"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 섹션을 soft delete로 처리 (is_deleted = 1)
            if self.table_name == 'section_config':
                cursor.execute("""
                    UPDATE section_config 
                    SET is_deleted = 1
                    WHERE id = ? AND board_type = ?
                """, (section_id, self.board_type))
            else:
                cursor.execute(f"""
                    UPDATE {self.table_name} 
                    SET is_deleted = 1
                    WHERE id = ?
                """, (section_id,))
            
            conn.commit()
            return {'success': True}
            
        except Exception as e:
            logging.error(f"섹션 삭제 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def reorder_sections(self, section_orders):
        """섹션 순서 재정렬"""
        conn = get_db_connection(self.db_path)
        cursor = conn.cursor()
        
        try:
            for section_id, order in section_orders.items():
                if self.table_name == 'section_config':
                    cursor.execute("""
                        UPDATE section_config 
                        SET section_order = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND board_type = ?
                    """, (order, section_id, self.board_type))
                else:
                    cursor.execute(f"""
                        UPDATE {self.table_name} 
                        SET section_order = ?, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                    """, (order, section_id))
            
            conn.commit()
            return {'success': True}
            
        except Exception as e:
            logging.error(f"섹션 순서 변경 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
