"""
메뉴와 권한 코드 매핑
"""

# 메뉴 URL과 권한 코드 매핑
MENU_PERMISSION_MAP = {
    'partner-standards': 'VENDOR_MGT',
    'partner-change-request': 'REFERENCE_CHANGE',
    'accident': 'ACCIDENT_MGT',
    'safety-instruction': 'SAFETY_INSTRUCTION',
    'follow-sop': 'FOLLOW_SOP',
    'safe-workplace': 'SAFE_WORKPLACE',  # 안전한 일터 추가
    'full-process': 'FULL_PROCESS',
    'safety-council': 'SAFETY_COUNCIL'  # 안전보건 협의체도 추가
}

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
            # URL에서 권한 코드 가져오기
            permission_code = MENU_PERMISSION_MAP.get(submenu['url'])

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