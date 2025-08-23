"""
드롭다운 코드 변경 이력 테이블 초기화
"""
import sqlite3

def init_audit_tables():
    conn = sqlite3.connect('portal.db')
    cursor = conn.cursor()
    
    # 감사 로그 테이블 생성
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS dropdown_code_audit (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        column_key TEXT NOT NULL,
        option_code TEXT NOT NULL,
        action_type TEXT NOT NULL,
        old_value TEXT,
        new_value TEXT,
        old_order INTEGER,
        new_order INTEGER,
        changed_by TEXT,
        changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ip_address TEXT,
        user_agent TEXT,
        notes TEXT
    )
    """)
    
    # 인덱스 생성
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_column_key ON dropdown_code_audit(column_key)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_changed_at ON dropdown_code_audit(changed_at)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_action_type ON dropdown_code_audit(action_type)")
    
    # 통계 뷰 생성
    cursor.execute("""
    CREATE VIEW IF NOT EXISTS dropdown_code_stats AS
    SELECT 
        column_key,
        COUNT(CASE WHEN action_type = 'CREATE' THEN 1 END) as total_created,
        COUNT(CASE WHEN action_type = 'UPDATE' THEN 1 END) as total_updated,
        COUNT(CASE WHEN action_type = 'DELETE' THEN 1 END) as total_deleted,
        MAX(changed_at) as last_changed,
        COUNT(DISTINCT DATE(changed_at)) as active_days
    FROM dropdown_code_audit
    GROUP BY column_key
    """)
    
    conn.commit()
    
    print("변경 이력 추적 테이블 생성 완료")
    
    # 테이블 확인
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='dropdown_code_audit'")
    if cursor.fetchone():
        print("- dropdown_code_audit 테이블 확인됨")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='dropdown_code_stats'")
    if cursor.fetchone():
        print("- dropdown_code_stats 뷰 확인됨")
    
    conn.close()

if __name__ == "__main__":
    init_audit_tables()