"""메뉴와 권한 코드 매핑 (permission_helpers의 정규화 함수 사용)"""
from permission_helpers import resolve_menu_code

def get_filtered_menu_config(user_accessible_menus):
    """
    사용자가 접근 가능한 메뉴만 필터링하여 반환
    """
    from config.menu import MENU_CONFIG

    # 접근 가능한 메뉴 코드 목록
    accessible_codes = {menu['code'] for menu in user_accessible_menus}

    filtered_menu = []

    for main_menu in MENU_CONFIG:
        filtered_submenu = []

        for submenu in main_menu.get('submenu', []):
            # URL에서 권한 코드 정규화
            permission_code = resolve_menu_code(submenu.get('url'))

            # 권한이 있는 경우에만 서브메뉴 추가
            if permission_code and permission_code in accessible_codes:
                filtered_submenu.append(submenu)

        # 서브메뉴가 하나라도 있으면 메인 메뉴 추가
        if filtered_submenu:
            filtered_menu.append({
                'title': main_menu['title'],
                'submenu': filtered_submenu
            })

    return filtered_menu
