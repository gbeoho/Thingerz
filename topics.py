# -*- coding: utf-8 -*-
"""
Thingerz 專題 (Monthly Topics) — 情境式策展頁面，唔係分類。

U Community 參考：用「10 大周末好去處」「香港小店故事」呢類用戶實際會搜尋嘅
情境入口，兜 6-12 條影片 + 一段 <100 字粵語策展介紹，再連相關商戶頁面。

每個 topic：
  slug       — URL 路徑 /topic/<slug>
  title_zh   — 專題名稱（H1 / title tag）
  title_en   — 英文名
  intro      — 粵語 策展介紹（<100 字）
  video_ids  — 影片 cv_<id> 或 v<nnn> 列表（喺 live site 有內容）
  可選：merchants（相關商戶/服務連結）
"""

TOPICS = [
    {
        "slug": "hk-small-shops",
        "title_zh": "香港小店・老字號故事",
        "title_en": "Hong Kong Old Shops & Hidden Gems",
        "intro": (
            "一齊尋訪香港嘅老字號同隱世小店：由屹立 70 年嘅灣仔茶餐廳、"
            "50 年上海菜老店，到屯門 80 年海鮮酒家同本地手作品牌。"
            "睇片了解佢哋嘅故事，撐返本地好店。"
        ),
        "video_ids": [
            "cv_2313137100",  # 灣仔70年茶餐廳 老字號
            "cv_4243867818",  # 西貢街坊美食一日遊
            "cv_306917189",   # 屯門容龍海鮮酒家 80年老字號
            "cv_914934925",   # 觀塘50年米芝蓮上海菜老店 接手故事
            "cv_61265020",    # 觀塘中菜館 手作古式菜
            "cv_3780801976",  # 老字號酒樓班底 尖沙咀
            "cv_2094193640",  # 三間麵包店布甸蛋撻比拼
            "cv_1193025103",  # A-1 Bakery 38年品牌
            "cv_3194630365",  # 香港本地手作品牌 網購創業
            "cv_2535710387",  # 香港手作 手帳印章工作室
        ],
    },
]

TOPICS_BY_SLUG = {t["slug"]: t for t in TOPICS}
TOPIC_SLUGS = [t["slug"] for t in TOPICS]