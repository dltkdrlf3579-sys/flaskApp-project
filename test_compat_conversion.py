#!/usr/bin/env python3
"""
CompatConnection이 SQLite 문법을 PostgreSQL로 제대로 변환하는지 테스트
"""
from db.compat import CompatConnection
import configparser

def test_placeholder_conversion():
    """? → %s 변환 테스트"""
    
    config = configparser.ConfigParser()
    config.read('config.ini', encoding='utf-8')
    dsn = config.get('DATABASE', 'postgres_dsn')
    
    conn = CompatConnection(dsn)
    
    print("=== Placeholder 변환 테스트 ===\n")
    
    # 테스트할 SQL들 (database_config.py에서 사용하는 패턴)
    test_sqls = [
        "INSERT INTO test (a, b) VALUES (?, ?)",
        "INSERT INTO accidents_cache (col1, col2) VALUES (?, ?, ?, ?, '{}', 0)",
        "SELECT * FROM table WHERE id = ? AND name = ?",
    ]
    
    for sql in test_sqls:
        converted = conn._convert_sql(sql)
        print(f"원본: {sql}")
        print(f"변환: {converted}")
        print()
    
    # 실제 executemany 테스트
    cursor = conn.cursor()
    
    # 테스트 테이블 생성
    try:
        cursor.execute("DROP TABLE IF EXISTS test_compat")
        cursor.execute("""
            CREATE TABLE test_compat (
                id SERIAL PRIMARY KEY,
                value1 TEXT,
                value2 INTEGER
            )
        """)
        
        # SQLite 문법으로 executemany
        data = [
            ('test1', 1),
            ('test2', 2),
            ('test3', 3)
        ]
        
        cursor.executemany(
            "INSERT INTO test_compat (value1, value2) VALUES (?, ?)",
            data
        )
        
        conn.commit()
        
        # 결과 확인
        cursor.execute("SELECT * FROM test_compat")
        rows = cursor.fetchall()
        
        print("=== executemany 테스트 결과 ===")
        for row in rows:
            print(f"  {row}")
        
        # 정리
        cursor.execute("DROP TABLE test_compat")
        conn.commit()
        
        print("\n✅ CompatConnection이 정상 작동합니다!")
        
    except Exception as e:
        print(f"\n❌ 에러 발생: {e}")
        conn.rollback()
    
    cursor.close()
    conn.close()

if __name__ == "__main__":
    test_placeholder_conversion()