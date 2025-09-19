from db_connection import get_db_connection

def update_menu_names():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 메뉴 이름 업데이트 (실제 메뉴와 동일하게)
    updates = [
        ('VENDOR_MGT', '협력사 기준정보', '협력사 정보 관리'),
        ('REFERENCE_CHANGE', '기준정보 변경요청', '기준정보 변경 관리'),
        ('ACCIDENT_MGT', '협력사 사고', '사고 정보 관리'),
        ('SAFETY_INSTRUCTION', '환경안전 지시서', '안전지시 관리'),
        ('FOLLOW_SOP', 'Follow SOP', 'SOP 이행 관리'),
        ('FULL_PROCESS', 'FullProcess', '프로세스 전체 관리')
    ]
    
    for menu_code, menu_name, description in updates:
        cursor.execute("""
            INSERT INTO menu_names (menu_code, menu_name, description)
            VALUES (%s, %s, %s)
            ON CONFLICT (menu_code) DO UPDATE SET
                menu_name = EXCLUDED.menu_name,
                description = EXCLUDED.description
        """, (menu_code, menu_name, description))
    
    conn.commit()
    cursor.close()
    conn.close()
    print("Menu names updated successfully")

if __name__ == "__main__":
    update_menu_names()
