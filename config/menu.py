# 상단 대메뉴/소메뉴는 여기서만 관리
MENU_CONFIG = [
    {
        "title": "협력사 정보",
        "submenu": [
            {"title": "협력사 기준정보", "url": "partner-standards"},
            {"title": "기준정보 변경요청", "url": "partner-change-request"},
        ],
    },
    {
        "title": "사고예방",
        "submenu": [
            {"title": "협력사 사고", "url": "partner-accident"},
            {"title": "환경안전 지시서", "url": "safety-instruction"},
        ],
    },
    # 작업안전과 안전문화는 개발 중이라 임시로 숨김
    # {
    #     "title": "작업안전",
    #     "submenu": [
    #         {"title": "Follow SOP", "url": "follow-sop"},
    #     ],
    # },
    # {
    #     "title": "안전문화",
    #     "submenu": [
    #         {"title": "FullProcess", "url": "full-process"},
    #     ],
    # },
]