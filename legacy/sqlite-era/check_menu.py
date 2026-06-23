import sqlite3

conn = sqlite3.connect('portal.db')
cursor = conn.cursor()

# 메뉴 테이블에서 safe-workplace 관련 항목 확인
cursor.execute("""
    SELECT menu_title, submenu_title, submenu_url, submenu_order, is_visible
    FROM menus
    WHERE submenu_url LIKE '%safe-workplace%'
    OR submenu_title LIKE '%안전한%'
    OR submenu_title LIKE '%일터%'
""")

results = cursor.fetchall()

if results:
    print("Safe-workplace 메뉴 발견:")
    for row in results:
        print(f"  메뉴: {row[0]}, 서브메뉴: {row[1]}, URL: {row[2]}, 순서: {row[3]}, 표시: {row[4]}")
else:
    print("Safe-workplace 메뉴가 없습니다!")
    print("\n현재 메뉴 목록:")
    cursor.execute("SELECT menu_title, submenu_title, submenu_url FROM menus WHERE is_visible = 1")
    for row in cursor.fetchall():
        print(f"  {row[0]} > {row[1]} ({row[2]})")

conn.close()