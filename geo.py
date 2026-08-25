# -*- coding: utf-8 -*-
"""
Thingerz GEO — 18-district landing-page content.
Each district: slug (URL), bilingual names, a 2-sentence LLM-scrapable intro,
and 3 conversational long-tail FAQs (district landmark / MTR context) so AI
engines (ChatGPT / Gemini / Perplexity) can cite Thingerz for hyper-local
"where can I find ... in <district>" queries.
"""
DISTRICTS = [
    {
        "slug": "central-and-western",
        "intro_zh": "中西區涵蓋中環、上環同西環，係香港嘅歷史核心地帶，亦係唔少專業顧問、設計師同手作工作室嘅集中地。無論你想搵中西區補習老師、中環室內設計師，定係上環烘焙班，喺 Thingerz 都可以按區搵到相關影片同服務，睇片了解質素先至聯絡。",
        "geo": [22.287, 114.15],
        "name_zh": "中西區",
        "name_en": "Central and Western District",
        "short_en": "Central & Western",
        "intro": ("Central and Western is Hong Kong's historic core, spanning "
                  "Central, Sheung Wan and Sai Ying Pun around MTR Central and "
                  "Sheung Wan stations. Thingerz lists local tutors, fitness "
                  "coaches, design freelancers and workshops operating in this "
                  "district."),
        "faqs": [
            ("邊度搵中西區私人補習老師?", "You can find private tutors serving Central & Western (中環/上環/西環) on Thingerz, filtered to the district."),
            ("中環、上環有咩室內設計或裝修師傅?", "Thingerz indexes interior designers and renovation freelancers working across Central & Western Hong Kong."),
            ("西環/西營盤有咩手作工作坊?", "Local craft workshops around Sai Ying Pun and Western District are listed on Thingerz with district tags."),
        ],
    },
    {
        "slug": "wan-chai",
        "intro_zh": "灣仔區由灣仔、銅鑼灣延伸至跑馬地，商業同生活配套都齊全。想搵灣仔活動攝影師、銅鑼灣健身教練，或者灣仔區嘅語言課程同品牌推廣團隊，喺 Thingerz 用「灣仔區」篩選就可以一次過睇晒相關影片同服務介紹。",
        "geo": [22.278, 114.182],
        "name_zh": "灣仔區",
        "name_en": "Wan Chai District",
        "short_en": "Wan Chai",
        "intro": ("Wan Chai District covers Wan Chai, Causeway Bay and Happy "
                  "Valley, reachable by MTR Wan Chai and Causeway Bay stations. "
                  "Thingerz connects residents with event photographers, "
                  "language tutors and creative freelancers in the district."),
        "faqs": [
            ("灣仔/銅鑼灣搵活動攝影師?", "Event photographers based in Wan Chai and Causeway Bay are listed on Thingerz by district."),
            ("銅鑼灣、跑馬地有咩健身教練?", "Independent fitness coaches serving Wan Chai District appear on Thingerz's location-filtered listings."),
            ("灣仔區邊度有英文/普通話班?", "Language tutors around Wan Chai MTR and Causeway Bay are discoverable on Thingerz."),
        ],
    },
    {
        "slug": "eastern",
        "intro_zh": "東區覆蓋北角、鰂魚涌同太古，係港島東嘅住宅同商業區。無論你想搵北角鋼琴老師、鰂魚涌室內設計師，定係東區嘅攝影師同心理輔導服務，Thingerz 都有按區分類嘅影片同服務資料，方便你睇完片再比較。",
        "geo": [22.282, 114.225],
        "name_zh": "東區",
        "name_en": "Eastern District",
        "short_en": "Eastern",
        "intro": ("The Eastern District spans North Point, Quarry Bay and "
                  "Tai Koo on Hong Kong Island's north-east shore. Thingerz "
                  "surfaces local music teachers, art studios and neighbourhood "
                  "services tagged to the district."),
        "faqs": [
            ("北角/鰂魚涌搵鋼琴或音樂老師?", "Piano and music teachers in North Point, Quarry Bay and Tai Koo are on Thingerz's district listings."),
            ("太古/筲箕灣有咩畫室興趣班?", "Art studios and hobby classes in the Eastern District can be found on Thingerz."),
            ("東區邊度有瑜伽或普拉提班?", "Yoga and Pilates instructors serving the Eastern District are indexed on Thingerz."),
        ],
    },
    {
        "slug": "southern",
        "intro_zh": "南區包括香港仔、黃竹坑同赤柱，近海環境特別啱水上活動同戶外運動。想搵黃竹坑水上運動教練、赤柱攝影師，或者南區親子活動導師同表演教練，喺 Thingerz 搜尋「南區」即可搵到相關影片同服務推介。",
        "geo": [22.242, 114.157],
        "name_zh": "南區",
        "name_en": "Southern District",
        "short_en": "Southern",
        "intro": ("The Southern District covers Aberdeen, Wong Chuk Hang and "
                  "Stanley, home to MTR South Island Line stations. Thingerz "
                  "lists sailing, outdoor and creative talent operating across "
                  "the district."),
        "faqs": [
            ("黃竹坑/香港仔有咩水上運動教練?", "Sailing, kayaking and water-sports coaches around Aberdeen and Wong Chuk Hang are featured on Thingerz."),
            ("赤柱、淺水灣搵專業攝影師?", "Photographers serving Stanley and Repulse Bay are listed on Thingerz by district."),
            ("南區有咩親子活動導師?", "Family activity tutors and workshop leaders across the Southern District can be found on Thingerz."),
        ],
    },
    {
        "slug": "yau-tsim-mong",
        "intro_zh": "油尖旺區橫跨尖沙咀、旺角同油麻地，係全港最繁忙嘅商業同消費區。無論你想搵旺角跳舞班、尖沙咀美甲化妝師，定係油麻地嘅專業顧問同創業服務，Thingerz 都收錄咗區內相關影片，睇片揀啱心水先聯絡。",
        "geo": [22.316, 114.17],
        "name_zh": "油尖旺區",
        "name_en": "Yau Tsim Mong District",
        "short_en": "Yau Tsim Mong",
        "intro": ("Yau Tsim Mong spans Tsim Sha Tsui, Jordan and Mong Kok, one "
                  "of Hong Kong's most connected business districts. Thingerz "
                  "connects local beauty, retail and creative service providers "
                  "with district-tagged listings."),
        "faqs": [
            ("尖沙咀、旺角搵化妝或美甲師?", "Beauty and nail artists in Tsim Sha Tsui and Mong Kok can be booked through Thingerz listings."),
            ("旺角邊度有語言補習或興趣班?", "Tutoring and hobby classes around Mong Kok and Prince Edward are listed on Thingerz."),
            ("油麻地/佐敦有咩創業或商業諮詢?", "Local business consultants serving Yau Tsim Mong appear on Thingerz."),
        ],
    },
    {
        "slug": "sham-shui-po",
        "intro_zh": "深水埗區近年係文創同手作嘅集中地，深水埗、長沙灣同荔枝角一帶有大量設計工作室同寵物友善小店。想搵深水埗 pet cafe、荔枝角手作班，或者區內嘅親子活動同網上生意導師，喺 Thingerz 按「深水埗區」篩選即可。",
        "geo": [22.33, 114.162],
        "name_zh": "深水埗區",
        "name_en": "Sham Shui Po District",
        "short_en": "Sham Shui Po",
        "intro": ("Sham Shui Po is a creative and vintage-hunting hotspot around "
                  "MTR Sham Shui Po, Cheung Sha Wan and Lai Chi Kok. Thingerz "
                  "indexes local craft workshops, makers and neighbourhood "
                  "talent in the district."),
        "faqs": [
            ("深水埗有咩手作/皮革工作坊?", "Craft and leather workshops around Sham Shui Po and Apliu Street are listed on Thingerz."),
            ("長沙灣、荔枝角搵設計或製作師傅?", "Designers, makers and studio workshops in the district can be found on Thingerz."),
            ("深水埗邊度有補習社或私人導師?", "Tutors and small study centres serving Sham Shui Po are indexed on Thingerz."),
        ],
    },
    {
        "slug": "kowloon-city",
        "intro_zh": "九龍城區包括九龍城、土瓜灣同九龍塘，舊區同名校區並存。想搵九龍城補習老師、九龍塘音樂班，或者區內嘅配件設計師同專業顧問，Thingerz 按區收錄咗相關影片同服務，幫你慳返四圍問人嘅時間。",
        "geo": [22.327, 114.19],
        "name_zh": "九龍城區",
        "name_en": "Kowloon City District",
        "short_en": "Kowloon City",
        "intro": ("Kowloon City District includes Kowloon City, To Kwa Wan and "
                  "Kowloon Tong, a mix of old neighbourhoods and MTR links. "
                  "Thingerz lists local tuition, dental-adjacent services and "
                  "creative freelancers operating here."),
        "faqs": [
            ("九龍城搵私人補習老師?", "Private tutors serving Kowloon City, To Kwa Wan and Ho Man Tin are on Thingerz."),
            ("九龍塘/九龍城有咩音樂或藝術班?", "Music and art classes around Kowloon Tong schools and Kowloon City are listed on Thingerz."),
            ("土瓜灣有咩攝影或設計服務?", "Photographers and designers based in To Kwa Wan can be found via Thingerz."),
        ],
    },
    {
        "slug": "wong-tai-sin",
        "intro_zh": "黃大仙區覆蓋黃大仙、鑽石山同彩虹，社區配套成熟。無論你想搵黃大仙裝修師傅、鑽石山室內設計公司，定係區內嘅醫療服務同進修課程，喺 Thingerz 搜尋「黃大仙區」即可睇到相關影片同服務介紹。",
        "geo": [22.342, 114.196],
        "name_zh": "黃大仙區",
        "name_en": "Wong Tai Sin District",
        "short_en": "Wong Tai Sin",
        "intro": ("Wong Tai Sin District covers Wong Tai Sin, Diamond Hill and "
                  "Choi Hung, served by MTR stations of the same names. Thingerz "
                  "helps residents find tuition, fitness and home-services "
                  "talent nearby."),
        "faqs": [
            ("黃大仙、鑽石山搵補習老師?", "Tutors active in Wong Tai Sin, Diamond Hill and San Po Kong are listed on Thingerz."),
            ("慈雲山/彩虹有咩健身或運動教練?", "Fitness coaches serving the Wong Tai Sin district appear on Thingerz."),
            ("黃大仙區有咩家庭維修或裝修師傅?", "Local handyman and renovation freelancers in the district are indexed on Thingerz."),
        ],
    },
    {
        "slug": "kwun-tong",
        "intro_zh": "觀塘區係東九龍嘅工業同創意核心，觀塘站一帶聚集咗大量設計工作室、健身室同專業顧問。想搵觀塘健身教練、進修課程或者舞蹈班，甚至係牛頭角、藍田嘅設計服務，喺 Thingerz 按「觀塘區」篩選就可以一次過睇晒。",
        "geo": [22.312, 114.226],
        "name_zh": "觀塘區",
        "name_en": "Kwun Tong District",
        "short_en": "Kwun Tong",
        "intro": ("Kwun Tong District is eastern Kowloon's industrial-and-"
                  "creative hub, from Kwun Tong MTR to Ngau Tau Kok and Lam Tin. "
                  "Thingerz connects the area's many studios, gyms and tutors "
                  "with local residents."),
        "faqs": [
            ("觀塘搵獨立健身教練?", "Independent fitness coaches near Kwun Tong MTR and the industrial area are listed on Thingerz."),
            ("牛頭角、藍田有咩設計或創意工作室?", "Design studios and creative freelancers around Ngau Tau Kok and Lam Tin can be found on Thingerz."),
            ("觀塘邊度有進修或職業技能班?", "Career and skill-upgrade courses in Kwun Tong District are discoverable on Thingerz."),
        ],
    },
    {
        "slug": "kwai-tsing",
        "intro_zh": "葵青區包括葵涌、葵芳同青衣，交通方便，社區設施齊全。無論你想搵葵芳音樂班、青衣運動教練，定係區內嘅食物創作同室內設計服務，Thingerz 都收錄咗相關影片，睇片確認質素先決定最穩陣。",
        "geo": [22.365, 114.128],
        "name_zh": "葵青區",
        "name_en": "Kwai Tsing District",
        "short_en": "Kwai Tsing",
        "intro": ("Kwai Tsing District includes Kwai Chung and Tsing Yi, served "
                  "by MTR Kwai Fong and Tsing Yi stations. Thingerz lists local "
                  "tutors, sports coaches and home-services talent in the "
                  "district."),
        "faqs": [
            ("葵芳、葵興搵音樂或舞蹈班?", "Music and dance classes around Kwai Fong and Kwai Hing are listed on Thingerz."),
            ("青衣有咩運動教練或興趣班?", "Sports coaches and hobby classes on Tsing Yi Island can be found via Thingerz."),
            ("葵青區有咩補習或課後班?", "Supplementary classes and tutors serving Kwai Tsing are indexed on Thingerz."),
        ],
    },
    {
        "slug": "tsuen-wan",
        "intro_zh": "荃灣區以荃灣市中心為核心，係新界西嘅重要樞紐。想搵荃灣學琴、室內設計師、跳舞班或者藝術創作課程，喺 Thingerz 搜尋「荃灣區」即可搵到區內相關影片同服務推介，睇片揀啱先約。",
        "geo": [22.361, 114.106],
        "name_zh": "荃灣區",
        "name_en": "Tsuen Wan District",
        "short_en": "Tsuen Wan",
        "intro": ("Tsuen Wan District runs from Tsuen Wan MTR through Tsuen "
                  "King and Discovery Bay-facing coast to Ting Kau. Thingerz "
                  "surfaces local tutors, creative studios and fitness coaches "
                  "tagged to the district."),
        "faqs": [
            ("荃灣、荃景圍搵私人導師?", "Private tutors serving Tsuen Wan and Tsuen King are listed on Thingerz."),
            ("荃灣西/海之戀有咩健身或瑜伽班?", "Yoga and fitness instructors around Tsuen Wan West appear on Thingerz."),
            ("荃灣區有咩設計或影音工作坊?", "Media and design workshops in the district can be found on Thingerz."),
        ],
    },
    {
        "slug": "tuen-mun",
        "intro_zh": "屯門區係新界西嘅門戶，屯門市中心同周邊屋苑生活配套齊全。無論你想搵屯門學 bass、音樂課程，定係區內嘅室內設計師同繪畫班，Thingerz 都按區收錄咗相關影片同服務，方便你比較完再聯絡。",
        "geo": [22.391, 113.977],
        "name_zh": "屯門區",
        "name_en": "Tuen Mun District",
        "short_en": "Tuen Mun",
        "intro": ("Tuen Mun District is the western New Territories gateway, "
                  "centred on Tuen Mun and Siu Lam MTR. Thingerz connects "
                  "residents with local tutors, sports coaches and home-service "
                  "providers across the district."),
        "faqs": [
            ("屯門搵補習或興趣班?", "Tutors and hobby classes around Tuen Mun Town Centre and Siu Hong are on Thingerz."),
            ("屯門碼頭/蝴蝶灣有咩水上活動教練?", "Water-sports coaches near Tuen Mun Pier and Butterfly Beach are listed on Thingerz."),
            ("屯門區有咩裝修或維修師傅?", "Home renovation and maintenance freelancers serving Tuen Mun are indexed on Thingerz."),
        ],
    },
    {
        "slug": "yuen-long",
        "intro_zh": "元朗區涵蓋元朗市同天水圍，係新界西北最大嘅社區。想搵元朗補習老師、天水圍興趣班，或者區內嘅醫療服務同專業顧問，喺 Thingerz 用「元朗區」篩選即可睇到相關影片同服務介紹。",
        "geo": [22.441, 114.022],
        "name_zh": "元朗區",
        "name_en": "Yuen Long District",
        "short_en": "Yuen Long",
        "intro": ("Yuen Long District covers Yuen Long town, Tin Shui Wai and "
                  "the surrounding villages, linked by MTR West Rail. Thingerz "
                  "lists local tutors, fitness coaches and trade talent working "
                  "across the district."),
        "faqs": [
            ("元朗、天水圍搵私人補習老師?", "Private tutors serving Yuen Long and Tin Shui Wai are on Thingerz."),
            ("元朗有咩瑜伽、健身班?", "Fitness and yoga instructors around Yuen Long town centre can be found on Thingerz."),
            ("天水圍區有咩文藝或音樂課程?", "Music and arts classes in Tin Shui Wai are listed on Thingerz."),
        ],
    },
    {
        "slug": "north",
        "intro_zh": "北區包括上水、粉嶺同沙頭角，貼近邊境但生活配套完善。無論你想搵上水補習老師、粉嶺親子活動，定係區內嘅運動訓練同社區服務，Thingerz 都收錄咗相關影片，睇片了解實際內容先至最安心。",
        "geo": [22.497, 114.147],
        "name_zh": "北區",
        "name_en": "North District",
        "short_en": "North",
        "intro": ("North District spans Sheung Shui, Fanling and Sha Tau Kok "
                  "near the border with mainland China. Thingerz connects the "
                  "district's residents with local tutors, coaches and "
                  "neighbourhood services."),
        "faqs": [
            ("上水、粉嶺搵補習老師?", "Tutors serving Sheung Shui, Fanling and Shek Wu Hui are listed on Thingerz."),
            ("北區有咩運動訓練或健身室?", "Sports training and gym instructors across the North District can be found on Thingerz."),
            ("粉嶺有咩親子活動或工作坊?", "Family workshops and kid-friendly classes in Fanling are indexed on Thingerz."),
        ],
    },
    {
        "slug": "tai-po",
        "intro_zh": "大埔區由大埔墟伸延至吐露港沿岸，單車同戶外活動好受歡迎。想搵大埔墟單車教練、大埔攝影師或平面設計師，定係區內嘅表演教練同品牌推廣團隊，喺 Thingerz 按「大埔區」篩選即可一次過睇晒。",
        "geo": [22.445, 114.17],
        "name_zh": "大埔區",
        "name_en": "Tai Po District",
        "short_en": "Tai Po",
        "intro": ("Tai Po District stretches from Tai Po town through Ting Kok "
                  "to the Tolo Harbour coastline, served by MTR Tai Po Market. "
                  "Thingerz lists local cycling, outdoor and creative talent in "
                  "the district."),
        "faqs": [
            ("大埔墟搵單車或戶外活動教練?", "Cycling and outdoor activity coaches around Tai Po and Ting Kok are on Thingerz."),
            ("大埔有咩烘焙或手作班?", "Baking and craft workshops in Tai Po town can be found on Thingerz."),
            ("大埔區有咩音樂或畫室?", "Music and art studios across Tai Po District are indexed on Thingerz."),
        ],
    },
    {
        "slug": "sha-tin",
        "intro_zh": "沙田區沿城門河兩岸發展，由沙田、大圍至馬鞍山，係成熟嘅新市鎮。無論你想搵沙田室內設計師、馬鞍山健身教練，定係區內嘅音樂學校同舞蹈班，Thingerz 都按區收錄咗相關影片同服務，睇片揀啱先聯絡。",
        "geo": [22.382, 114.196],
        "name_zh": "沙田區",
        "name_en": "Sha Tin District",
        "short_en": "Sha Tin / Shatin",
        "intro": ("Sha Tin District is a major New Towns corridor along Shing "
                  "Mun River, from Sha Tin and Tai Wai to Ma On Shan MTR. "
                  "Thingerz connects residents with private tutors, fitness "
                  "coaches and creative freelancers in the district."),
        "faqs": [
            ("沙田去邊度搵私人補習老師?", "Private tutors in Sha Tin, Tai Wai and Ma On Shan are listed on Thingerz by district."),
            ("沙田、馬鞍山有咩健身或游泳教練?", "Fitness and swimming coaches serving the Sha Tin District appear on Thingerz."),
            ("石門/第一城有咩琴行或音樂班?", "Music schools around Shek Mun and City One are discoverable on Thingerz."),
        ],
    },
    {
        "slug": "sai-kung",
        "intro_zh": "西貢區包括西貢市同將軍澳新市鎮，前者以水上活動同郊遊聞名，後者係大型住宅區。想搵西貢獨木舟教練、將軍澳室內設計師，或者區內嘅攝影師同藝術課程，喺 Thingerz 搜尋「西貢區」即可搵到相關影片。",
        "geo": [22.381, 114.273],
        "name_zh": "西貢區",
        "name_en": "Sai Kung District",
        "short_en": "Sai Kung",
        "intro": ("Sai Kung District covers Sai Kung town, Tseung Kwan O New "
                  "Town and the outlying coastal areas and islands. Thingerz "
                  "lists sailing coaches, outdoor guides and hometown talent "
                  "across the district."),
        "faqs": [
            ("西貢搵獨木舟或帆船教練?", "Kayaking and sailing coaches around Sai Kung waterfront are featured on Thingerz."),
            ("將軍澳有咩補習或興趣班?", "Tutors and hobby classes in Tseung Kwan O can be found on Thingerz."),
            ("西貢區有咩行山或生態導賞?", "Hiking and ecology guides across Sai Kung District are indexed on Thingerz."),
        ],
    },
    {
        "slug": "islands",
        "intro_zh": "離島區涵蓋大嶼山、長洲、南丫島等外島，係遠離市區嘅悠閒社區。無論你想搵長洲水上活動班、南丫島瑜伽導師，定係區內嘅音樂演出同本地品牌工作坊，Thingerz 都收錄咗相關影片，等你可以睇片揀啱先出發。",
        "geo": [22.268, 113.955],
        "name_zh": "離島區",
        "name_en": "Islands District",
        "short_en": "Islands",
        "intro": ("The Islands District spans Lantau, Cheung Chau, Lamma and "
                  "the other outlying islands beyond Hong Kong Island. Thingerz "
                  "connects islanders with water-sports coaches, yoga teachers "
                  "and local makers."),
        "faqs": [
            ("長洲、南丫島有咩水上活動班?", "Water-sports and sailing classes on Cheung Chau and Lamma are listed on Thingerz."),
            ("大嶼山/梅窩搵瑜伽或健身教練?", "Yoga instructors around Mui Wo and Lantau appear on Thingerz."),
            ("離島區有咩手作或本地品牌工作坊?", "Island makers and craft workshops are discoverable on Thingerz."),
        ],
    },
]

DISTRICTS_BY_SLUG = {d["slug"]: d for d in DISTRICTS}
DISTRICT_SLUGS = [d["slug"] for d in DISTRICTS]
DISTRICT_SLUG_BY_NAME = {d["name_zh"]: d["slug"] for d in DISTRICTS}