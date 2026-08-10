# -*- coding: utf-8 -*-
"""
Thingerz upload screening — scans a submitted video's TITLE + DESCRIPTION for
restricted wording / content that must never appear on thingerz.com.
Returns a reason string (non-empty => REJECT the upload) or None (allow).

Self-contained so it runs on Render (no dependency on the Hermes skill path).
Mirrors the editor's screen_content.py rules for the upload path: politics,
Taiwan, UK, 短劇, adult, crime-news, econ-doom, foreign property/stocks.
"""
import re

# ─────────────────────────────────────────────────────────────────────────
# Blocklist keywords (substring / word-boundary). Politics / TW media / 短劇 /
# adult / crime / gossip.
# ─────────────────────────────────────────────────────────────────────────
KEYWORDS = [
    # Politics — HK
    "李家超", "特首", "行政长官", "行政長官", "施政报告", "施政報告", "立法会", "立法會",
    "区议会", "區議會", "选委", "政改", "中联办", "中聯辦", "港澳办", "港澳辦",
    "港区国安法", "港區國安法", "国安法", "國安法", "一国两制", "一國兩制", "基本法",
    "爱国者治港", "愛國者治港", "庆回归", "慶回歸", "国旗", "國旗", "爱党", "愛黨",
    "两会", "兩會", "人大", "政协", "政協", "人大代表",
    # protests / elections
    "选举", "選舉", "政党", "政黨", "票站", "民调", "民調", "选民", "選民", "竞選", "反對派",
    "抗议", "抗議", "示威", "游行", "遊行", "抗争", "抗爭", "集会", "集會", "请愿", "請願",
    "罢工", "占领", "佔領", "黑警", "港独", "港獨", "台独", "台獨", "六四", "天安门", "天安門",
    "法轮功", "法輪功", "反送中", "占中", "佔中", "白纸", "白紙", "雨伞运动", "雨傘運動",
    "新疆", "維吾爾", "集中营", "集中營", "藏独", "疆独", "东突", "東突",
    # TW politics
    "民进党", "民進黨", "立法院", "国民党", "國民黨", "赖清德", "賴清德", "蔡英文",
    "柯文哲", "韩国瑜", "韓國瑜", "台湾政治", "台灣政治", "立委", "葉元之", "范雲", "爆噴",
    "52直播間", "52新聞聚樂部", "開南中學", "开南中学",
    # Taiwan media
    "tvbs", "setn", "ettoday", "cna", "三立", "中天", "東森", "東森", "民視", "台視", "華視",
    "鏡新聞", "中央社", "自由時報", "中時", "聯合報", "壹電視", "苹果日报", "蘋果日報",
    # UK (living/study/working there)
    "移居英國", "英國留學", "英國簽證", "英國生活", "英國移民", "移英", "移民英國",
    "uk visa", "living in uk", "life in uk", "study in uk", "british",
    # 短劇
    "短劇", "短剧", "一口氣看完", "一口气看完", "全集", "大結局", "大结局", "贅婿", "赘婿",
    "霸道總裁", "霸道总裁", "穿越剧", "穿越劇", "甜宠", "甜寵", "女總裁", "女总裁",
    # adult
    "自慰", "性爱", "性愛", "做爱", "做愛", "色情", "A片", "嫖娼", "卖淫", "賣淫",
    "性侵", "强奸", "強姦", "裸聊", "约炮", "約炮", "援交", "色播", "裸体", "全裸",
    "裸照", "偷拍", "露点", "露點", "调教", "制服诱惑", "porn", "nude", "naked", "sex", "fuck",
    # crime / fear
    "人贩子", "人販子", "拐卖", "拐賣", "贩卖人口", "販賣人口", "绑架", "綁架",
    "碎尸", "碎屍", "杀人", "殺人", "虐童", "儿童色情",
    # gossip / tabloid
    "娛樂新聞", "娱乐新闻", "明星私生活", "藝人動態", "八卦周刊", "狗仔隊", "偷拍藝人",
]

# ─────────────────────────────────────────────────────────────────────────
# Title-level HARD blocks — crime/society news + econ-doom clickbait
# ─────────────────────────────────────────────────────────────────────────
CRIME_NEWS_TITLE = [
    "召妓", "嫖妓", "一樓一", "鳳姐", "血案", "遇襲", "襲擊", "捉賊", "箍頸", "執法爭議",
    "查身份證", "非禮", "誤殺", "判刑", "被捕", "急症室", "插錯喉", "醫療事故",
    "倒斃", "逝世", "撞死", "墮樓", "被控", "危殆", "運毒", "洗錢", "洗米華",
    "內地男疑", "男遊客", "特賣場職員", "女戶主偷電", "筷子偷信", "馬桶蓋夾傷", "掀簾",
    "毒品", "刀襲", "走私", "網賭", "貴賓廳", "黑幕", "刑事恐嚇", "滋擾案",
    "現屆香港特別行政區政府", "上任四周年", "政綱主題巴士", "答問大會",
]
ECON_DOOM_TITLE = ["大崩盤", "崩盤", "蒸發", "死寂"]

# ─────────────────────────────────────────────────────────────────────────
# Foreign content (no HK opt-out)
# ─────────────────────────────────────────────────────────────────────────
FOREIGN_PROP = ["溫哥華", "温哥華", "vancouver", "台山房产", "台山房產", "多倫多地產",
                "多伦多地产", "悉尼樓", "悉尼楼", "列治文"]

# simplified-Chinese chars => mainland content signal
SIMP_CHARS = set("这为们个实设际销润让从现样买卖单东广车场产应网图学时书处头发开关兴长里问问确华职观员务财历专显标级联县经权机路线过分响应扩园年纪识计记认该部级环规达标价却据边总运输贺银华")
FOREIGN_STOCK = ["SK海力士", "韓股", "韓國股市", "韩国股市", "韩股", "美股夜視鏡", "存儲股", "存储股"]

# Taiwan city / HK opt-out (mirror is_taiwan conservatively)
TW_CITIES = ["台北", "臺北", "高雄", "台中", "臺中", "台南", "臺南", "新北", "桃園", "基隆",
             "新竹", "苗栗", "彰化", "南投", "雲林", "嘉義", "屏東", "宜蘭", "花蓮", "台東",
             "澎湖", "金門", "馬祖", "台灣", "台湾", "taiwan", "墾丁", "九份", "日月潭", "西門町"]
HK_MARKERS = ["屯門", "觀塘", "旺角", "荃灣", "元朗", "沙田", "大埔", "黃大仙", "深水埗", "西貢",
              "九龍", "香港", "離島", "油尖旺", "葵青", "天水圍", "東涌", "長洲", "赤柱", "馬鞍山",
              "北角", "紅磡", "上水", "粉嶺", "將軍澳", "中環", "上環", "尖沙咀", "銅鑼灣", "西環",
              "港島", "新界", "九龍城"]


def _word_boundary(text, word):
    if word.isascii() and word.isalpha():
        return re.search(rf"\b{re.escape(word)}\b", text) is not None
    return word in text


def screen_upload(title="", description="", author=""):
    """Return a reason string to REJECT the upload, or None to allow.
    Scans title + description (and submitter name) for restricted wording."""
    title = title or ""
    description = description or ""
    author = author or ""
    text_all = " ".join([title, description, author]).lower()

    # general blocklist (any-field, word-boundary for English)
    for w in KEYWORDS:
        if _word_boundary(text_all, w.lower()):
            return f"restricted wording: {w}"

    # title-level hard blocks
    t = title.lower()
    for w in CRIME_NEWS_TITLE:
        if w.lower() in t:
            return f"crime/society-news title: {w}"
    for w in ECON_DOOM_TITLE:
        if w.lower() in t:
            return f"econ-doom title: {w}"

    # foreign property (no opt-out)
    ht = (title + " " + author).lower()
    for w in FOREIGN_PROP:
        if w.lower() in ht:
            return f"foreign property: {w}"

    # foreign stocks — only when simplified-Chinese signal
    if any(_word_boundary(ht, w.lower()) or w.lower() in ht for w in FOREIGN_STOCK):
        simp = sum(1 for c in (title + author) if c in SIMP_CHARS)
        if simp >= 2:
            return "foreign-stock clickbait (simplified-Chinese)"

    # Taiwan content: TW city mentioned without HK proof
    hk = any(m in title or m in author for m in HK_MARKERS)
    if not hk:
        for c in TW_CITIES:
            if c.lower() in ht:
                return f"Taiwan content: {c}"

    return None


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else ""
    d = sys.argv[2] if len(sys.argv) > 2 else ""
    print(screen_upload(t, d) or "ALLOW")