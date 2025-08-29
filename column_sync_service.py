"""
JSON 기반 컬럼 설정 동기화 서비스
JSON 파일의 컬럼 설정을 DB로 동기화
"""
import json
import sqlite3
import os
import logging
from typing import Dict, List, Any
from datetime import datetime

class ColumnSyncService:
    """
    JSON 파일의 컬럼 설정을 DB와 동기화
    - JSON이 진실의 원천(Source of Truth)
    - DB는 런타임 캐시 역할
    """
    
    def __init__(self, db_path: str, columns_dir: str = 'columns'):
        """
        Args:
            db_path: 데이터베이스 경로
            columns_dir: JSON 파일들이 있는 디렉토리
        """
        self.db_path = db_path
        self.columns_dir = columns_dir
        
        # columns 디렉토리가 없으면 생성
        os.makedirs(columns_dir, exist_ok=True)
        
    def sync_all_boards(self) -> Dict[str, int]:
        """
        모든 보드의 컬럼 설정 동기화
        
        Returns:
            각 보드별 동기화된 컬럼 수
        """
        results = {}
        
        # columns 디렉토리의 모든 JSON 파일 처리
        for filename in os.listdir(self.columns_dir):
            if filename.endswith('_columns.json'):
                board_type = filename.replace('_columns.json', '')
                try:
                    count = self.sync_board(board_type)
                    results[board_type] = count
                    logging.info(f"{board_type}: {count}개 컬럼 동기화 완료")
                except Exception as e:
                    logging.error(f"{board_type} 동기화 실패: {e}")
                    results[board_type] = -1
                    
        return results
    
    def sync_board(self, board_type: str) -> int:
        """
        특정 보드의 컬럼 설정 동기화
        
        Args:
            board_type: 보드 타입 (accident, safety_instruction 등)
            
        Returns:
            동기화된 컬럼 수
        """
        # JSON 파일 읽기
        json_path = os.path.join(self.columns_dir, f'{board_type}_columns.json')
        
        if not os.path.exists(json_path):
            raise FileNotFoundError(f"JSON 파일 없음: {json_path}")
            
        with open(json_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
            
        # DB 연결
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # 테이블명
        table_name = f'{board_type}_column_config'
        
        # 테이블이 없으면 생성
        self._create_column_table(cursor, table_name)
        
        # 기존 데이터 모두 비활성화 (JSON에 없는 것들)
        cursor.execute(f"""
            UPDATE {table_name} 
            SET is_active = 0,
                updated_at = CURRENT_TIMESTAMP
        """)
        
        # JSON 데이터로 업데이트
        count = 0
        for col in config.get('columns', []):
            # INSERT OR REPLACE로 업서트
            cursor.execute(f"""
                INSERT OR REPLACE INTO {table_name} (
                    column_key, column_name, column_type, 
                    column_order, is_active, is_required,
                    dropdown_options, dropdown_values,
                    table_name, table_type, tab,
                    created_at, updated_at
                ) VALUES (
                    ?, ?, ?, 
                    ?, ?, ?,
                    ?, ?,
                    ?, ?, ?,
                    COALESCE((SELECT created_at FROM {table_name} WHERE column_key = ?), CURRENT_TIMESTAMP),
                    CURRENT_TIMESTAMP
                )
            """, (
                col['key'],
                col['name'],
                col.get('type', 'text'),
                col.get('order', count),
                1 if col.get('active', True) else 0,
                1 if col.get('required', False) else 0,
                json.dumps(col.get('options', [])) if col.get('options') else None,
                col.get('dropdown_values'),  # 레거시 호환
                col.get('table_name'),
                col.get('table_type', 'dynamic'),  # dynamic 또는 static
                col.get('tab'),  # tab 필드 추가
                col['key']  # WHERE column_key = ? 용
            ))
            count += 1
            
        # 드롭다운 옵션 동기화 (있는 경우)
        self._sync_dropdown_options(cursor, board_type, config)
        
        conn.commit()
        conn.close()
        
        logging.info(f"{board_type} 보드: {count}개 컬럼 동기화 완료")
        return count
    
    def _create_column_table(self, cursor, table_name: str):
        """
        컬럼 설정 테이블 생성 (없는 경우)
        """
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                column_key TEXT UNIQUE NOT NULL,
                column_name TEXT NOT NULL,
                column_type TEXT DEFAULT 'text',
                column_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                is_required INTEGER DEFAULT 0,
                dropdown_options TEXT,  -- JSON 형식
                dropdown_values TEXT,   -- 레거시 호환
                table_name TEXT,        -- 참조 테이블
                table_type TEXT,        -- dynamic/static
                tab TEXT,               -- 탭 위치
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
    def _sync_dropdown_options(self, cursor, board_type: str, config: Dict):
        """
        드롭다운 옵션 동기화
        """
        # dropdown_option_codes_v2 테이블 확인
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dropdown_option_codes_v2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                board_type TEXT NOT NULL,
                column_key TEXT NOT NULL,
                option_code TEXT NOT NULL,
                option_value TEXT NOT NULL,
                display_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_by TEXT,
                updated_by TEXT,
                UNIQUE(board_type, column_key, option_code)
            )
        """)
        
        # 각 컬럼의 드롭다운 옵션 처리
        for col in config.get('columns', []):
            if col.get('type') == 'dropdown' and col.get('options'):
                # 기존 옵션 비활성화
                cursor.execute("""
                    UPDATE dropdown_option_codes_v2
                    SET is_active = 0
                    WHERE board_type = ? AND column_key = ?
                """, (board_type, col['key']))
                
                # 새 옵션 추가/업데이트
                for idx, option in enumerate(col['options']):
                    if isinstance(option, dict):
                        code = option.get('code', str(idx))
                        value = option.get('value', option.get('name', ''))
                    else:
                        # 단순 문자열인 경우
                        code = str(idx)
                        value = str(option)
                        
                    cursor.execute("""
                        INSERT OR REPLACE INTO dropdown_option_codes_v2
                        (board_type, column_key, option_code, option_value, 
                         display_order, is_active, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1, CURRENT_TIMESTAMP)
                    """, (board_type, col['key'], code, value, idx))
    
    def export_board_to_json(self, board_type: str) -> bool:
        """
        DB의 컬럼 설정을 JSON으로 내보내기 (백업용)
        
        Args:
            board_type: 보드 타입
            
        Returns:
            성공 여부
        """
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            table_name = f'{board_type}_column_config'
            
            # 컬럼 데이터 조회
            cursor.execute(f"""
                SELECT column_key, column_name, column_type, 
                       column_order, is_active, is_required,
                       dropdown_options, table_name, table_type
                FROM {table_name}
                WHERE is_active = 1
                ORDER BY column_order
            """)
            
            columns = []
            for row in cursor.fetchall():
                col_data = {
                    'key': row['column_key'],
                    'name': row['column_name'],
                    'type': row['column_type'],
                    'order': row['column_order'],
                    'active': bool(row['is_active']),
                    'required': bool(row['is_required']) if row['is_required'] else False
                }
                
                # 드롭다운 옵션 처리
                if row['dropdown_options']:
                    try:
                        col_data['options'] = json.loads(row['dropdown_options'])
                    except:
                        pass
                        
                if row['table_name']:
                    col_data['table_name'] = row['table_name']
                if row['table_type']:
                    col_data['table_type'] = row['table_type']
                    
                columns.append(col_data)
            
            # 보드 설정
            config = {
                'board': board_type,
                'display_name': {
                    'accident': '협력사 사고',
                    'safety_instruction': '환경안전 지시서',
                    'change_request': '변경요청'
                }.get(board_type, board_type),
                'columns': columns,
                'exported_at': datetime.now().isoformat()
            }
            
            # 백업 파일명 (타임스탬프 포함)
            backup_dir = os.path.join(self.columns_dir, 'backup')
            os.makedirs(backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(backup_dir, f'{board_type}_columns_{timestamp}.json')
            
            with open(backup_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
                
            logging.info(f"{board_type} 백업 완료: {backup_path}")
            
            conn.close()
            return True
            
        except Exception as e:
            logging.error(f"내보내기 실패: {e}")
            return False


# 사용 예시
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # 동기화 서비스 초기화
    sync_service = ColumnSyncService('portal.db')
    
    # 모든 보드 동기화
    results = sync_service.sync_all_boards()
    print("동기화 결과:", results)
    
    # 특정 보드만 동기화
    # sync_service.sync_board('accident')
    
    # DB → JSON 백업
    # sync_service.export_board_to_json('accident')