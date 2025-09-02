import sqlite3
import json
import logging
from datetime import datetime

class SectionConfigService:
    """섹션 설정 관리 서비스 클래스"""
    
    def __init__(self, board_type, db_path):
        self.board_type = board_type
        self.db_path = db_path
        
    def get_sections(self):
        """특정 보드 타입의 모든 활성 섹션 가져오기"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # follow_sop과 full_process는 별도 테이블 사용
            if self.board_type == 'follow_sop':
                cursor.execute("""
                    SELECT * FROM follow_sop_sections 
                    WHERE is_active = 1 
                    ORDER BY section_order
                """)
            elif self.board_type == 'full_process':
                cursor.execute("""
                    SELECT * FROM full_process_sections 
                    WHERE is_active = 1 
                    ORDER BY section_order
                """)
            else:
                # safety_instruction 등은 기존 section_config 테이블 사용
                cursor.execute("""
                    SELECT * FROM section_config 
                    WHERE board_type = ? AND is_active = 1 
                    ORDER BY section_order
                """, (self.board_type,))
            
            sections = [dict(row) for row in cursor.fetchall()]
            return sections
            
        except Exception as e:
            logging.error(f"섹션 조회 오류: {e}")
            # 오류 시 기본 섹션 반환 (하드코딩 폴백)
            return self._get_default_sections()
        finally:
            conn.close()
    
    def get_sections_with_columns(self):
        """섹션과 해당 컬럼들을 함께 가져오기"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        try:
            # 섹션 가져오기
            sections = self.get_sections()
            
            # 각 섹션에 대한 컬럼 가져오기
            table_name = f"{self.board_type}_column_config"
            
            for section in sections:
                cursor.execute(f"""
                    SELECT * FROM {table_name}
                    WHERE tab = ? AND is_active = 1
                    ORDER BY column_order
                """, (section['section_key'],))
                
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
        return []
    
    def add_section(self, section_data):
        """새 섹션 추가"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 자동으로 section_key 생성 (custom_section_1, custom_section_2 등)
            cursor.execute("""
                SELECT COUNT(*) FROM section_config 
                WHERE board_type = ? AND section_key LIKE 'custom_section_%'
            """, (self.board_type,))
            
            custom_count = cursor.fetchone()[0]
            section_key = f"custom_section_{custom_count + 1}"
            
            # 마지막 순서 가져오기
            cursor.execute("""
                SELECT MAX(section_order) FROM section_config 
                WHERE board_type = ?
            """, (self.board_type,))
            
            max_order = cursor.fetchone()[0] or 0
            
            cursor.execute("""
                INSERT INTO section_config 
                (board_type, section_key, section_name, section_order, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, (
                self.board_type,
                section_key,
                section_data['section_name'],
                max_order + 1
            ))
            
            conn.commit()
            section_id = cursor.lastrowid
            
            return {
                'success': True,
                'section_id': section_id,
                'section_key': section_key
            }
            
        except Exception as e:
            logging.error(f"섹션 추가 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()
    
    def update_section(self, section_id, section_data):
        """섹션 정보 수정 (섹션명만 수정 가능)"""
        conn = sqlite3.connect(self.db_path)
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
            
            query = f"""
                UPDATE section_config 
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
        """섹션 삭제 (컬럼이 없는 경우에만)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # 섹션 정보 가져오기
            cursor.execute("""
                SELECT section_key FROM section_config 
                WHERE id = ? AND board_type = ?
            """, (section_id, self.board_type))
            
            section = cursor.fetchone()
            if not section:
                return {'success': False, 'error': '섹션을 찾을 수 없습니다'}
            
            section_key = section[0]
            
            # 해당 섹션에 컬럼이 있는지 확인
            table_name = f"{self.board_type}_column_config"
            cursor.execute(f"""
                SELECT COUNT(*) FROM {table_name} 
                WHERE tab = ?
            """, (section_key,))
            
            column_count = cursor.fetchone()[0]
            if column_count > 0:
                return {'success': False, 'error': f'해당 섹션에 {column_count}개의 컬럼이 있어 삭제할 수 없습니다'}
            
            # 섹션 삭제
            cursor.execute("""
                DELETE FROM section_config 
                WHERE id = ? AND board_type = ?
            """, (section_id, self.board_type))
            
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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            for section_id, order in section_orders.items():
                cursor.execute("""
                    UPDATE section_config 
                    SET section_order = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ? AND board_type = ?
                """, (order, section_id, self.board_type))
            
            conn.commit()
            return {'success': True}
            
        except Exception as e:
            logging.error(f"섹션 순서 변경 오류: {e}")
            conn.rollback()
            return {'success': False, 'error': str(e)}
        finally:
            conn.close()