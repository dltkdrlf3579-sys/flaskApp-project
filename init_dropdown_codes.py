"""
드롭다운 코드 매핑 테이블 초기화 스크립트
"""
import sqlite3
import json
from datetime import datetime

def init_dropdown_codes():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    # 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dropdown_option_codes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT NOT NULL,
        option_code TEXT NOT NULL,
        option_value TEXT NOT NULL,
        display_order INTEGER DEFAULT 0,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        created_by TEXT,
        updated_by TEXT,
        UNIQUE(column_key, option_code)
    )
    """)
    
    # 인덱스 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dropdown_column_key ON dropdown_option_codes(column_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dropdown_active ON dropdown_option_codes(is_active)")
    
    # 마이그레이션 로그 테이블
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dropdown_migration_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT,
        old_value TEXT,
        new_codes TEXT,
        migration_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT
    )
    """)
    
    print("드롭다운 코드 매핑 테이블 생성 완료")
    
    # 기존 dropdown_options 데이터 마이그레이션
    cursor.execute("""
        SELECT id, column_key, column_name, dropdown_options 
        FROM accident_column_config 
        WHERE column_type = 'dropdown' AND dropdown_options IS NOT NULL
    """)
    
    columns_with_dropdown = cursor.fetchall()
    
    for col_id, col_key, col_name, dropdown_json in columns_with_dropdown:
        if not dropdown_json:
            continue
            
        try:
            # JSON 파싱
            if isinstance(dropdown_json, str):
                options = json.loads(dropdown_json)
            else:
                options = dropdown_json
            
            if not isinstance(options, list):
                continue
            
            print(f"\n마이그레이션: {col_name} ({col_key})")
            
            # 각 옵션에 대해 코드 생성 및 삽입
            for idx, option_value in enumerate(options, 1):
                # 코드 생성 (컬럼키_순번 형식)
                option_code = f"{col_key.upper()}_{str(idx).zfill(3)}"
                
                try:
                    cursor.execute("""
                        INSERT INTO dropdown_option_codes 
                        (column_key, option_code, option_value, display_order, is_active)
                        VALUES (?, ?, ?, ?, 1)
                    """, (col_key, option_code, option_value, idx))
                    
                    print(f"  - {option_code}: {option_value}")
                except sqlite3.IntegrityError:
                    print(f"  - 이미 존재: {option_code}")
            
            # 마이그레이션 로그 기록
            cursor.execute("""
                INSERT INTO dropdown_migration_log 
                (column_key, old_value, new_codes, status)
                VALUES (?, ?, ?, 'completed')
            """, (col_key, dropdown_json, f"Migrated {len(options)} options", ))
            
        except Exception as e:
            print(f"  - 마이그레이션 실패: {e}")
            cursor.execute("""
                INSERT INTO dropdown_migration_log 
                (column_key, old_value, new_codes, status)
                VALUES (?, ?, ?, 'failed')
            """, (col_key, dropdown_json, str(e)))
    
    conn.commit()
    
    # 결과 확인
    cursor.execute("SELECT COUNT(*) FROM dropdown_option_codes")
    total_codes = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(DISTINCT column_key) FROM dropdown_option_codes")
    total_columns = cursor.fetchone()[0]
    
    print(f"\n마이그레이션 완료!")
    print(f"   - 총 {total_codes}개 코드 생성")
    print(f"   - {total_columns}개 컬럼 처리")
    
    conn.close()

if __name__ == "__main__":
    init_dropdown_codes()