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
ECON_DOOM_TITLE = ["大崩盤", "崩盤", "崩盘", "联系汇率", "聯繫匯率", "金管局"]

# ─────────────────────────────────────────────────────────────────────────
# Extra classes discovered during 2026-08 content sweeps: ghost/horror stories,
# mobile-gaming livestreams, finance/property TV, HK online-gossip talk shows,
# war news, mainland re-uploads (抖音/快手).
# ─────────────────────────────────────────────────────────────────────────
EXTRA_TITLE_BLOCK = [
    # ghost / horror
    "凶宅", "鬼故", "靈異", "鬼故事", "猛鬼", "撞鬼", "見鬼", "驅魔", "怪談", "冤魂", "亡魂",
    "鬼上身", "靈異事件", "鬼單", "鬼樓", "撞邪", "邪靈", "百鬼", "陰魂",
    # war / foreign-conflict news
    "戰爭", "普京", "澤倫斯基", "烏俄", "俄烏", "頓涅茨克", "轟炸", "導彈", "导弹", "烏軍", "烏軍",
    # gaming livestream / gacha
    "手遊", "逆水寒", "原神", "絕區零", "崩壞", "王者榮耀", "英雄聯盟", "開局一座島", "禮包碼",
    "兌換碼", "課金", "遊戲直播", "排位賽", "實況主",
    # finance / property TV + gambling
    "港股", "美股", "A股", "股市", "樓市", "樓盤", "按揭", "財經直播", "賽馬直播", "六合彩", "投注",
    # HK online-gossip talk-show saga
    "何伯", "咸圈", "廢門", "診西", "口水台", "直播訪問",
    # mainland re-uploads / douyin-style
    "抖音", "快手", "搬運",
]

# ─────────────────────────────────────────────────────────────────────────
# Foreign content (no HK opt-out)
# ─────────────────────────────────────────────────────────────────────────
FOREIGN_PROP = ["溫哥華", "温哥華", "vancouver", "台山房产", "台山房產", "多倫多地產",
                "多伦多地产", "悉尼樓", "悉尼楼", "列治文"]

# ─────────────────────────────────────────────────────────────────────────
# 呃人 / negative-news shops — shops named in recent HK consumer-scam /
# bad-sales / food-safety news (2026-08). Never curate/feature these brands:
#   "opatra"      → Opatra London 美容店 (沙田/元朗分店突停業, 海關拘兩管理層涉不良銷售)
#   "極上帝王水產"  → 旺角兆萬中心 放題, 食物中毒事件 + 已結業 (2025 food-safety, closed 2026-03)
# Substring match (case-insensitive) so brand variants/URLs are caught too.
SCAM_SHOPS = ["opatra", "極上帝王水產"]

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

    # 呃人/negative-news shops — generic reject (never name the brand to users)
    for s in SCAM_SHOPS:
        if s.lower() in text_all:
            return f"blocked shop: {s}"

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
    for w in EXTRA_TITLE_BLOCK:
        if w.lower() in t:
            return f"restricted title: {w}"

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


# ─────────────────────────────────────────────────────────────────────────
# Sub-category content matching (for uploads): verify the submitter picked
# the RIGHT category so uploaded links never auto-post in a wrong category.
# ─────────────────────────────────────────────────────────────────────────
SUB_CAT_KEYWORDS = {
    's001': ['市場研究','市調','市場調查','market research','問卷','行業報告'],
    's002': ['品牌','branding','brand','行銷','marketing','推廣'],
    's003': ['網上生意','電商','網店','開網店','網購','代購','shopify','淘寶開店','直播帶貨'],
    's004': ['顧問','consult','諮詢','專業顧問'],
    's005': ['室內設計','interior design','裝修','空間設計','家居設計'],
    's006': ['醫療','醫生','診所','醫療服務','hospital','看診'],
    's007': ['餐飲','餐廳','飲食業','餐飲業','酒吧','food & beverage'],
    's008': ['活動策劃','event','活動','配對','聯誼','networking'],
    's009': ['技能教學','tutorial','skill','技能班'],
    's010': ['表演教練','表演訓練','coaching'],
    's011': ['學琴','練琴','鋼琴','結他','吉他','小提琴','音樂班','樂理','口琴','ukulele','音樂學習','學鼓'],
    's012': ['視覺創作','藝術課程','視覺藝術','art course'],
    's013': ['英文','日文','韓文','翻譯','語言班','學英文','translate','普通話','日語','英語'],
    's014': ['心理','自我提升','self improvement','情緒','mindset','勵志','成長','壓力','抑鬱'],
    's015': ['平面設計','graphic design','photoshop','illustrator','排版','logo設計'],
    's016': ['服飾設計','時裝設計','fashion design','fashion'],
    's017': ['手作','手工','diy','craft','編織','鉤織','串珠','皮革','毛冷'],
    's018': ['配件設計','accessory','飾品設計','飾物'],
    's019': ['攝影','拍攝','photography','相機','剪片','影像','vlog','video editing'],
    's020': ['印刷','printmaking','版畫','絲網'],
    's021': ['藝術裝置','installation','藝術展','展覽','公共藝術'],
    's022': ['繪畫','素描','畫畫','水彩','油畫','drawing','painting','書法','水墨'],
    's023': ['音樂演出','演奏','concert','band','歌手','唱歌','live music'],
    's024': ['舞蹈','跳舞','dance','街舞','芭蕾','kpop'],
    's025': ['戲劇','話劇','drama','舞台劇'],
    's026': ['魔術','magic','魔術師','近景'],
    's027': ['特技','雜耍','特技表演','acrobatic','體操'],
    's028': ['互動娛樂','interactive','沉浸式','互動劇'],
    's029': ['烘焙','麵包','蛋糕','baking','曲奇','cupcake','muffin','班戟','焗蛋糕','焗包'],
    's030': ['烹飪','食譜','cooking','料理','下廚','家常菜','煮餸'],
    's031': ['手沖咖啡','咖啡','品酒','調酒','茶藝','品茶','飲品','拉花'],
    's032': ['食物創作','甜品創作','food art','分子料理','食品創作'],
    's033': ['香氛','香薰','香水','精油','感官','香味'],
    's034': ['園藝','種植','盆栽','植物','gardening','多肉'],
    's035': ['飲食品牌','食品品牌','餐廳品牌','food brand'],
    's036': ['婚禮策劃','婚禮統籌','wedding planner'],
    's037': ['婚禮佈置','wedding design'],
    's038': ['新娘化妝','wedding styling','婚紗','姊妹裙'],
    's039': ['結婚蛋糕','wedding cake'],
    's040': ['親子活動','parent-child','kids','親子好去處','親子館','小朋友'],
    's041': ['生活美學','lifestyle','居家','家居佈置','生活品味','生活小智慧','收納','執屋'],
    's042': ['節慶','禮品','gift','聖誕','農曆新年','中秋','禮物'],
    's043': ['化妝','makeup','化妝教學','眼妝','唇妝'],
    's044': ['護膚','skincare','保養','面膜','護膚品'],
    's045': ['造型','styling','穿搭','形象','髮型'],
    's046': ['美感內容','beauty content','美妝'],
    's047': ['個人品牌','personal branding','個人形象'],
    's048': ['美容服務','美容院','facial','美容療程'],
    's049': ['親子教育','育兒','親子教養','parenting'],
    's050': ['兒童活動','kids activity'],
    's051': ['社區組織','community','義工'],
    's052': ['公共參與','公共事務','公民','社區參與'],
    's053': ['社交配對','社交','交友','dating','配對'],
    's054': ['公眾講座','講座','seminar','演講','talk'],
    's055': ['人工智能','機器學習','chatgpt','生成式','ai學習','ai繪圖','prompt'],
    's056': ['cosplay','角色扮演'],
    's057': ['風水','命理','占卜','八字','紫微','塔羅'],
    's058': ['hyrox','重氧運動','hiit','crossfit','健身'],
    's059': ['小丑','氣球','clown','扭氣球','氣球藝術'],
    's060': ['珠寶設計','jewellery','首飾設計','金工','銀飾'],
    's061': ['寵物','動物','pet','寵物溝通','動物溝通','貓','狗'],
    's062': ['音響','耳機','喇叭','audio','音質','hifi'],
    's063': ['汽車維修','車房','car repair','整車','改裝'],
    's064': ['燒賣','腸粉','點心','dim sum','siu mai'],
    's065': ['身心靈','靈性','冥想','mindfulness','禪修'],
    's066': ['手錶','watch','鐘錶','修錶'],
    's067': ['動漫','動畫','anime','漫畫','卡通'],
    's068': ['四驅車','陀螺','beyblade','mini4wd','玩具'],
    's069': ['生活小配件','生活用品'],
    's070': ['運動教學','健身教學','足球教學','籃球教學','游泳','sports'],
    's071': ['asmr','助眠','白噪音','放鬆音效'],
    's072': ['唱歌教學','唱歌班','聲樂','練唱歌','學唱歌','vocal lesson','singing lesson'],
    's073': ['攝影教學','影相教學','學影相','影相班','學攝影','攝影班','影相課程'],
    's074': ['醫美','醫學美容','簡單醫美','針清','水光','脫毛','激光療程','hifu','皮秒','微針','美容療程','medical aesthetics'],
}

# length-1 / too-generic keys that must not trigger a category match alone
WEAK_KEYS = {'煮', '活動', '課程', '教學', '表演', '配件', '小物', '公園', '貼士'}


def match_subcategory(title="", description="", author=""):
    """Return the subcategory_id the submitted content best matches, or None
    when there is no confident match. Ignores WEAK_KEYS; a clear margin over
    every other category is required (ties/ambiguity → None)."""
    text = " ".join([title or "", description or "", author or ""]).lower()
    scores = {}
    for sid, kws in SUB_CAT_KEYWORDS.items():
        s = sum(1 for k in kws if len(k) > 1 and k not in WEAK_KEYS and k.lower() in text)
        if s:
            scores[sid] = s
    if not scores:
        return None
    best = max(scores, key=scores.get)
    best_score = scores[best]
    rest = [v for sid, v in scores.items() if sid != best]
    if rest and max(rest) >= best_score:
        return None  # ambiguous / no clear winner
    return best


if __name__ == "__main__":
    import sys
    t = sys.argv[1] if len(sys.argv) > 1 else ""
    d = sys.argv[2] if len(sys.argv) > 2 else ""
    print(screen_upload(t, d) or "ALLOW")
