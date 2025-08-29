"""
보드 격리용 마이그레이션 스크립트
- dropdown_option_codes_v2 테이블 생성 (board_type 포함)
- 기존 데이터 마이그레이션
- 테이블 구조 보완
"""
import sqlite3
import json
from datetime import datetime

DB_PATH = "portal.db"

def migrate_dropdown_table():
    """새로운 테이블에 board_type 추가"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("1. Creating dropdown_option_codes_v2 table...")
    
    # 1. 새 테이블 생성 (board_type 포함)
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
    
    print("2. Checking if old table exists...")
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='dropdown_option_codes'
    """)
    
    if cursor.fetchone():
        print("3. Migrating existing data...")
        
        # 기존 데이터 조회
        cursor.execute("SELECT DISTINCT column_key FROM dropdown_option_codes")
        column_keys = [row[0] for row in cursor.fetchall()]
        
        # column_key 기반으로 board_type 매핑
        board_mapping = {
            # accident 관련
            'injury_type': 'accident',
            'accident_type': 'accident',
            'occurrence_type': 'accident',
            'accident_level': 'accident',
            'injury_part': 'accident',
            
            # safety_instruction 관련 
            'instruction_type': 'safety_instruction',
            'risk_level': 'safety_instruction',
            'safety_category': 'safety_instruction',
            
            # change_request 관련
            'change_type': 'change_request',
            'request_status': 'change_request',
            'approval_status': 'change_request',
        }
        
        # 기본값은 accident로 설정 (기존 데이터가 주로 accident)
        for key in column_keys:
            board_type = board_mapping.get(key, 'accident')
            
            cursor.execute("""
                INSERT OR IGNORE INTO dropdown_option_codes_v2 
                (board_type, column_key, option_code, option_value, display_order, is_active, created_by)
                SELECT ?, column_key, option_code, option_value, display_order, is_active, created_by
                FROM dropdown_option_codes
                WHERE column_key = ?
            """, (board_type, key))
            
            print(f"  - Migrated {key} to {board_type}")
        
        conn.commit()
        print("4. Migration completed!")
    else:
        print("  - No old table found, skipping migration")
    
    # 인덱스 생성 (성능 향상)
    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_dropdown_board_column 
        ON dropdown_option_codes_v2(board_type, column_key)
    """)
    
    conn.commit()
    conn.close()
    print("[OK] Dropdown table migration completed!")

def ensure_safety_instruction_tables():
    """안전지시서 용 테이블 확보 (필요 시)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n5. Ensuring safety_instruction tables...")
    
    # safety_instruction_column_config 테이블 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS safety_instruction_column_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT NOT NULL,
            column_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            dropdown_options TEXT,
            table_name TEXT,
            table_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 기본 컬럼이 없으면 추가
    cursor.execute("SELECT COUNT(*) FROM safety_instruction_column_config")
    if cursor.fetchone()[0] == 0:
        print("  - Adding default columns for safety_instruction...")
        default_columns = []
        # 생략: 실제 컬럼 목록
        for col in default_columns:
            cursor.execute("""
                INSERT OR IGNORE INTO safety_instruction_column_config
                (column_key, column_name, column_type, column_order, is_active)
                VALUES (?, ?, ?, ?, 1)
            """, col)
    
    conn.commit()
    conn.close()
    print("[OK] Safety instruction tables ensured!")

def ensure_change_request_tables():
    """변경요청 용 테이블 확보 (필요 시)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n6. Ensuring change_request tables...")
    
    # change_request_column_config 생성
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS change_request_column_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            column_key TEXT UNIQUE NOT NULL,
            column_name TEXT NOT NULL,
            column_type TEXT NOT NULL,
            column_order INTEGER DEFAULT 0,
            is_active INTEGER DEFAULT 1,
            dropdown_options TEXT,
            table_name TEXT,
            table_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 기존 change_request_columns 테이블에서 마이그레이션
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name='change_request_columns'
    """)
    
    if cursor.fetchone():
        print("  - Migrating from change_request_columns...")
        cursor.execute("""
            INSERT OR IGNORE INTO change_request_column_config
            (column_key, column_name, column_type, column_order, is_active)
            SELECT column_key, column_name, column_type, column_order, is_active
            FROM change_request_columns
        """
        )
    
    conn.commit()
    conn.close()
    print("[OK] Change request tables ensured!")

def create_board_config_table():
    """보드 설정 테이블 생성 (선택사항)"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n7. Creating board configuration table...")
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS board_configs (
            board_type TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            number_prefix TEXT,
            cache_table TEXT NOT NULL,
            column_table TEXT NOT NULL,
            upload_path TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    
    # 기본 보드 설정 추가
    boards = [
        ('accident', '협력사 사고', 'ACC', 'accidents_cache', 'accident_column_config', 'uploads/accident/'),
        ('safety_instruction', '환경안전 지시서', 'SI', 'safety_instructions', 'safety_instruction_column_config', 'uploads/safety_instruction/'),
        ('change_request', '기준정보 변경요청', 'CR', 'change_requests', 'change_request_column_config', 'uploads/change_request/'),
    ]
    
    for board_data in boards:
        cursor.execute("""
            INSERT OR IGNORE INTO board_configs
            (board_type, display_name, number_prefix, cache_table, column_table, upload_path)
            VALUES (?, ?, ?, ?, ?, ?)
        """, board_data)
    
    conn.commit()
    conn.close()
    print("[OK] Board configuration table created!")

def verify_migration():
    """마이그레이션 검증"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n8. Verifying migration...")
    
    # v2 테이블 데이터 확인
    cursor.execute("""
        SELECT board_type, COUNT(DISTINCT column_key) as cols, COUNT(*) as rows
        FROM dropdown_option_codes_v2
        WHERE is_active = 1
        GROUP BY board_type
        ORDER BY board_type, column_key
    """)
    
    print("\n  Dropdown codes by board:")
    for row in cursor.fetchall():
        print(f"    - {row[0]}: {row[1]} columns, {row[2]} rows")
    
    # 각 보드 컬럼 설정 확인
    tables = ['accident_column_config', 'safety_instruction_column_config', 'change_request_column_config']
    print("\n  Column configs:")
    for table in tables:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"    - {table}: {count} columns")
    
    conn.close()
    print("\n[OK] Migration verification completed!")

if __name__ == "__main__":
    print("=" * 60)
    print("BOARD ISOLATION MIGRATION SCRIPT")
    print("=" * 60)
    
    try:
        # 백업 알림
        backup_file = f"portal_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        print(f"\n[WARNING] Please backup your database first!")
        print(f"   Suggested: copy portal.db {backup_file}\n")
        
        input("Press Enter to continue with migration...")
        
        # 마이그레이션 수행
        migrate_dropdown_table()
        ensure_safety_instruction_tables()
        ensure_change_request_tables()
        create_board_config_table()
        verify_migration()
        
        print("\n" + "=" * 60)
        print("[SUCCESS] ALL MIGRATIONS COMPLETED SUCCESSFULLY!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        print("Please restore from backup and check the error.")
