#!/usr/bin/env python3
"""
변경요청 등록 페이지 문제 해결 스크립트
1. change_request_column_config 테이블에 기본 컬럼 설정 추가
2. partner_change_requests 테이블에 requester_name, requester_department 컬럼 추가
"""

from db_connection import get_db_connection

def fix_change_request_table():
    """partner_change_requests 테이블에 필요한 컬럼들 추가"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("=== partner_change_requests 테이블 컬럼 추가 ===")
    
    # 현재 컬럼 확인
    try:
        result = cursor.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'partner_change_requests'
        """).fetchall()
        existing_columns = [row[0] for row in result]
        print(f"기존 컬럼들: {existing_columns}")
        
        # 필요한 컬럼들 추가
        columns_to_add = [
            ('requester_name', 'TEXT', '의뢰인'),
            ('requester_department', 'TEXT', '의뢰인부서'),
            ('current_value', 'TEXT', '현재값'),
            ('new_value', 'TEXT', '변경값'),
            ('change_reason', 'TEXT', '변경사유'),
            ('detailed_content', 'TEXT', '상세내용')
        ]
        
        for col_name, col_type, description in columns_to_add:
            if col_name not in existing_columns:
                cursor.execute(f"""
                    ALTER TABLE partner_change_requests 
                    ADD COLUMN {col_name} {col_type}
                """)
                print(f"  + {description} ({col_name}) 컬럼 추가됨")
            else:
                print(f"  - {description} ({col_name}) 컬럼 이미 존재")
        
        conn.commit()
        print("테이블 구조 업데이트 완료!")
        
    except Exception as e:
        print(f"테이블 업데이트 실패: {e}")
        conn.rollback()

def create_change_request_column_config():
    """change_request_column_config 테이블에 기본 컬럼 설정 생성"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 기존 데이터 삭제
    print("\n=== 변경요청 컬럼 설정 생성 ===")
    cursor.execute("DELETE FROM change_request_column_config")
    print("기존 컬럼 설정 삭제...")
    
    # 기본 컬럼 설정 (순서대로)
    column_configs = [
        # 기본 정보
        ('company_name', '협력사명', 'popup_company', 1, 1, 'business_number', 'basic'),
        ('business_number', '사업자번호', 'linked_text', 2, 1, 'company_name', 'basic'),
        ('requester_name', '의뢰인', 'popup_person', 3, 1, 'requester_department', 'basic'),
        ('requester_department', '의뢰인부서', 'linked_dept', 4, 1, 'requester_name', 'basic'),
        ('change_type', '변경유형', 'dropdown', 5, 1, None, 'basic'),
        ('current_value', '현재값', 'textarea', 6, 1, None, 'basic'),
        ('new_value', '변경값', 'textarea', 7, 1, None, 'basic'),
        ('change_reason', '변경사유', 'textarea', 8, 1, None, 'basic'),
        ('detailed_content', '상세내용', 'textarea', 9, 0, None, 'basic'),  # 선택사항
    ]
    
    print("컬럼 설정 생성...")
    for column_key, column_name, column_type, order, is_active, linked_key, tab in column_configs:
        cursor.execute("""
            INSERT INTO change_request_column_config 
            (column_key, column_name, column_type, column_order, is_active, linked_columns, tab, created_at) 
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """, (column_key, column_name, column_type, order, bool(is_active), linked_key, tab))
        print(f"  + {column_name} ({column_key}) - {column_type}")
    
    conn.commit()
    
    # 결과 확인
    print("\n생성된 컬럼 설정 확인:")
    result = cursor.execute("""
        SELECT column_key, column_name, column_order, is_active 
        FROM change_request_column_config 
        ORDER BY column_order
    """).fetchall()
    
    for row in result:
        status = "활성" if row[3] else "선택"
        print(f"  {row[2]:2d}. {row[1]} ({row[0]}) - {status}")
    
    conn.close()
    print(f"\n총 {len(column_configs)}개 컬럼 설정이 생성되었습니다!")

def create_dropdown_options():
    """변경유형 드롭다운 옵션 생성"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    print("\n=== 드롭다운 옵션 생성 ===")
    
    # 변경유형 옵션들
    change_types = [
        ('기본정보변경', '회사명, 주소, 대표자 등 기본정보 변경'),
        ('업종변경', '업종 분류 변경'),
        ('규모변경', '직원수, 매출액 등 회사 규모 변경'),
        ('위험작업변경', '위험작업 여부 변경'),
        ('기타', '기타 사유로 인한 변경')
    ]
    
    try:
        # 기존 옵션 삭제
        cursor.execute("""
            DELETE FROM dropdown_option_codes_v2 
            WHERE board_type = 'change_request' AND column_key = 'change_type'
        """)
        
        # 새 옵션 추가
        for option_code, option_name in change_types:
            cursor.execute("""
                INSERT INTO dropdown_option_codes_v2 
                (board_type, column_key, option_code, option_name, is_active, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, ('change_request', 'change_type', option_code, option_name, True))
            print(f"  + {option_name} ({option_code})")
        
        conn.commit()
        print("드롭다운 옵션 생성 완료!")
        
    except Exception as e:
        print(f"드롭다운 옵션 생성 실패: {e}")
        conn.rollback()
    
    conn.close()

if __name__ == "__main__":
    print("=== 변경요청 등록 페이지 문제 해결 ===")
    
    # 1. 테이블 구조 수정
    fix_change_request_table()
    
    # 2. 컬럼 설정 생성
    create_change_request_column_config()
    
    # 3. 드롭다운 옵션 생성
    create_dropdown_options()
    
    print("\n모든 수정이 완료되었습니다!")
    print("브라우저를 새로고침해서 확인하세요.")