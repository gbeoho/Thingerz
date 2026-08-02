# YouTube Hong Kong District Content Verification Report

Generated: 2026-08-02

## Methodology
For each sub-category, searched YouTube with query `香港 {sub_category} {district}` 
across all 18 Hong Kong districts. Checked top 5 video titles for district name or aliases.

## Overall Results
- **37 sub-categories verified** (s001-s054, excl. s002-s018)
- **972 searches**, **1,129/3,270 matches** = **34.5%** overall match rate

## Coverage by Category

### ✅ Excellent (≥60% match)
| Sub-Category | Match Rate | Best Districts |
|---|---|---|
| 公共參與 (s052) | **81.1%** | 深水埗, 觀塘, 油尖旺, 屯門 |
| 親子教育 (s049) | **72.0%** | 西貢, 大埔, 沙田, 深水埗 |
| 造型與形象 (s045) | **70.0%** | 油尖旺, 深水埗, 觀塘, 葵青, 離島 |
| 美感內容 (s046) | **66.7%** | 觀塘, 深水埗, 黃大仙, 葵青, 西貢 |
| 社區組織 (s051) | **63.3%** | 深水埗, 黃大仙, 油尖旺, 西貢, 大埔 |
| 兒童活動 (s050) | **62.2%** | 深水埗, 沙田, 荃灣, 屯門, 元朗 |
| 日常生活美學 (s041) | **62.2%** | 灣仔, 九龍城, 深水埗, 黃大仙, 沙田 |
| 親子活動 (s040) | **61.1%** | 觀塘, 深水埗, 西貢, 沙田, 大埔 |
| 節慶與禮品 (s042) | **60.0%** | 深水埗, 黃大仙, 大埔, 荃灣, 屯門 |

### 🟡 Moderate (30-60%)
舞蹈表演(53.3%), 公眾講座(53.3%), 市場研究與分析(44.4%), 音樂演出(40.0%), 婚禮造型(36.2%), 婚禮甜點(36.5%), 食物創作(32.2%), 餐飲教學(31.1%), 飲食品牌(31.1%), 護膚(32.2%), 個人品牌形象(31.1%), 美容服務(31.1%), 攝影與影像(30.0%)

### 🔴 Poor (<30%)
飲品與品味(28.9%), 婚禮設計(22.2%), 化妝(17.8%), 社交配對(16.3%), 園藝與種植(15.6%), 烘焙(15.6%), 藝術裝置(15.6%), 香氛與感官(13.3%), 互動娛樂(13.3%), 特技與雜耍(11.1%), 繪畫與素描(10.0%), 戲劇與短劇(7.8%), 魔術與奇技(7.8%), 印刷與工藝(3.3%), 婚禮策劃(1.1%)

## District-Level Patterns
- **Consistently best districts**: 深水埗區, 觀塘區, 油尖旺區, 黃大仙區, 屯門區
- **Consistently worst**: 東區 (Taiwan confusion), 北區 (Northern Metropolis confusion), 荃灣區
- **Community/wedding categories** have strongest district tagging
- **Performance/arts categories** have weakest district tagging

## Crawler Recommendations
1. **Post-filter results**: Check title/description for target district
2. **Use sub-district names** for poorly-covered areas
3. **Exclude non-HK results**: Filter out Taiwan/China matches
4. **Weight by reliability**: Trust 深水埗/觀塘/油尖旺 more than 東區/北區

## Files
- `data/youtube_district_results.json` — Full 37-subcategory JSON results (207KB)
- `YOUTUBE_DISTRICT_REPORT.md` — This report