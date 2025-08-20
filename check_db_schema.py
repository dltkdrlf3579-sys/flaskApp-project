#!/usr/bin/env python3
"""
DB 스키마 확인 및 수정 스크립트
partner_attachments 테이블의 스키마를 확인하고 필요한 컬럼이 없으면 추가/이관
"""
import sqlite3
import os

def check_and_fix_schema():
    db_path = 'portal.db'
    
    if not os.path.exists(db_path):
        print(f"DB 파일이 존재하지 않습니다: {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # partner_attachments 테이블 정보 확인
    cursor.execute("PRAGMA table_info(partner_attachments)")
    columns = cursor.fetchall()
    
    print("현재 partner_attachments 테이블 구조:")
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # 필요한 컬럼들
    required_columns = {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'business_number': 'TEXT NOT NULL',
        'file_name': 'TEXT NOT NULL',
        'file_path': 'TEXT NOT NULL',
        'file_size': 'INTEGER NOT NULL',
        'description': 'TEXT DEFAULT ""',
        'upload_date': 'TEXT DEFAULT CURRENT_TIMESTAMP'
    }
    
    existing_columns = {col[1]: col[2] for col in columns}
    
    # 누락된 컬럼 확인
    missing_columns = set(required_columns.keys()) - set(existing_columns.keys())
    
    if missing_columns:
        print(f"\n누락된 컬럼들: {missing_columns}")
        
        # 백업 테이블 생성
        print("기존 테이블 백업 중...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS partner_attachments_backup AS 
            SELECT * FROM partner_attachments
        """)
        
        # 새 테이블 생성
        print("새 테이블 생성 중...")
        cursor.execute("DROP TABLE IF EXISTS partner_attachments_new")
        
        create_sql = f"""
        CREATE TABLE partner_attachments_new (
            {', '.join([f'{col} {dtype}' for col, dtype in required_columns.items()])}
        )
        """
        cursor.execute(create_sql)
        
        # 기존 데이터가 있다면 이관
        if existing_columns:
            common_columns = list(set(existing_columns.keys()) & set(required_columns.keys()))
            if common_columns:
                print(f"기존 데이터 이관 중... (컬럼: {common_columns})")
                
                # business_number가 없는 경우 기본값 설정
                if 'business_number' not in existing_columns:
                    # 샘플 데이터의 business_number를 사용하거나 기본값 설정
                    insert_sql = f"""
                    INSERT INTO partner_attachments_new ({', '.join(common_columns)}, business_number)
                    SELECT {', '.join(common_columns)}, '1234567890' as business_number
                    FROM partner_attachments
                    """
                else:
                    insert_sql = f"""
                    INSERT INTO partner_attachments_new ({', '.join(common_columns)})
                    SELECT {', '.join(common_columns)}
                    FROM partner_attachments
                    """
                
                try:
                    cursor.execute(insert_sql)
                    print("데이터 이관 완료")
                except Exception as e:
                    print(f"데이터 이관 실패: {e}")
        
        # 테이블 교체
        print("테이블 교체 중...")
        cursor.execute("DROP TABLE partner_attachments")
        cursor.execute("ALTER TABLE partner_attachments_new RENAME TO partner_attachments")
        
        conn.commit()
        print("스키마 수정 완료!")
        
    else:
        print("\n스키마가 올바르게 구성되어 있습니다.")
    
    # 최종 확인
    cursor.execute("SELECT COUNT(*) FROM partner_attachments")
    count = cursor.fetchone()[0]
    print(f"\n최종 partner_attachments 레코드 수: {count}")
    
    conn.close()

if __name__ == "__main__":
    check_and_fix_schema()