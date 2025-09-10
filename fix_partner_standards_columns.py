#!/usr/bin/env python3
"""
협력사 기준정보 페이지 컬럼 설정 복구 스크립트
"""

from db_connection import get_db_connection

def create_partner_standards_column_config():
    """partner_standards_column_config 테이블에 기본 컬럼 설정 생성"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 기존 데이터 삭제
    print("기존 컬럼 설정 삭제...")
    cursor.execute("DELETE FROM partner_standards_column_config")
    
    # 기본 컬럼 설정 (partners_cache 테이블의 컬럼들 기반)
    column_configs = [
        ('company_name', '협력사명', 'text', 1, 1),
        ('business_number', '사업자번호', 'text', 2, 1),
        ('partner_class', '협력사구분', 'text', 3, 1),
        ('business_type_major', '업종(대분류)', 'text', 4, 1),
        ('business_type_minor', '업종(소분류)', 'text', 5, 1),
        ('hazard_work_flag', '위험작업여부', 'text', 6, 1),
        ('representative', '대표자', 'text', 7, 1),
        ('address', '주소', 'text', 8, 1),
        ('permanent_workers', '상시근로자수', 'integer', 9, 1),
        ('average_age', '평균연령', 'integer', 10, 1),
        ('annual_revenue', '연매출액', 'bigint', 11, 1),
        ('transaction_count', '거래건수', 'text', 12, 1)
    ]
    
    print("컬럼 설정 생성...")
    for column_key, column_name, column_type, order, is_active in column_configs:
        cursor.execute("""
            INSERT INTO partner_standards_column_config 
            (column_key, column_name, column_type, column_order, is_active, created_at) 
            VALUES (%s, %s, %s, %s, %s, NOW())
        """, (column_key, column_name, column_type, order, is_active))
        print(f"  + {column_name} ({column_key})")
    
    conn.commit()
    
    # 결과 확인
    print("\n생성된 컬럼 설정 확인:")
    result = cursor.execute("""
        SELECT column_key, column_name, column_order, is_active 
        FROM partner_standards_column_config 
        ORDER BY column_order
    """).fetchall()
    
    for row in result:
        status = "활성" if row[3] else "비활성"
        print(f"  {row[2]:2d}. {row[1]} ({row[0]}) - {status}")
    
    conn.close()
    print(f"\n✅ 총 {len(column_configs)}개 컬럼 설정이 생성되었습니다!")

if __name__ == "__main__":
    print("=== 협력사 기준정보 컬럼 설정 복구 ===")
    create_partner_standards_column_config()
    print("복구 완료! 브라우저를 새로고침해서 확인하세요.")