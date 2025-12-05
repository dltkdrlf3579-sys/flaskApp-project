"""
dev_user에게 모든 권한 부여
"""
from db_connection import get_db_connection

def grant_dev_user_permissions():
    conn = get_db_connection()
    cursor = conn.cursor()

    # dev_user에게 모든 메뉴 전체 권한(Level 3) 부여
    menus = [
        'VENDOR_MGT',
        'REFERENCE_CHANGE',
        'ACCIDENT_MGT',
        'SAFETY_INSTRUCTION',
        'CORRECTIVE_ACTION',
        'FOLLOW_SOP',
        'FULL_PROCESS'
    ]

    for menu in menus:
        cursor.execute("""
            INSERT INTO user_menu_permissions
            (login_id, menu_code, read_level, write_level, is_active)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (login_id, menu_code)
            DO UPDATE SET
                read_level = EXCLUDED.read_level,
                write_level = EXCLUDED.write_level,
                is_active = EXCLUDED.is_active
        """, ('dev_user', menu, 3, 3, True))

    conn.commit()
    print("dev_user에게 모든 권한 부여 완료!")
    print("이제 '개발자'로 로그인하면 모든 메뉴에 접근 가능합니다.")

    cursor.close()
    conn.close()

if __name__ == "__main__":
    grant_dev_user_permissions()