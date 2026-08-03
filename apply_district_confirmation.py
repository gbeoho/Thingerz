#!/usr/bin/env python3
"""
Apply district_confirmed labels to seed_crawled_videos.jsonl
============================================================
用 thingerz-crawler 嘅 DISTRICT_KEYWORDS(區名 + 子區別名)判斷每條片係咪
「確認」真係屬於標記嘅 district:
  - title / description / author_name 入面有提到該區或其別名 -> district_confirmed=True
  - 冇 -> False(視為「一般」內容,唔喺 district 搜尋度出)

用法: python3 apply_district_confirmation.py
輸出: 更新 seed 檔(加 district_confirmed 欄位),backup 存 seed_*.bak.jsonl
"""
import json
import os
import shutil
import sys
from datetime import datetime

SEED_PATH = "/opt/data/Thingerz/data/seed_crawled_videos.jsonl"

sys.path.insert(0, "/opt/data/thingerz-crawler")
try:
    from config import DISTRICT_KEYWORDS
except Exception:
    DISTRICT_KEYWORDS = {}


def confirmed_district(item: dict, district: str) -> bool:
    """True if the video's title/desc/author actually mentions the target district or its aliases."""
    if not district:
        return False
    keywords = DISTRICT_KEYWORDS.get(district, [district])
    haystack = " ".join([
        item.get("title") or "",
        item.get("description") or "",
        item.get("author_name") or "",
    ]).lower()
    return any(k.lower() in haystack for k in keywords)


def main() -> None:
    if not os.path.exists(SEED_PATH):
        print(f"Seed not found: {SEED_PATH}")
        sys.exit(1)

    # Backup
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = f"{SEED_PATH}.{stamp}.bak"
    shutil.copy2(SEED_PATH, backup)
    print(f"Backup: {backup}")

    # Load + relabel
    items = []
    with open(SEED_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                item = json.loads(line)
            except Exception:
                continue
            d = item.get("district") or ""
            item["district_confirmed"] = confirmed_district(item, d)
            items.append(item)

    # Write back
    with open(SEED_PATH, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    confirmed = sum(1 for i in items if i.get("district_confirmed"))
    print(f"Total: {len(items)}")
    print(f"district_confirmed=True : {confirmed} ({confirmed/len(items)*100:.1f}%)")
    print(f"district_confirmed=False: {len(items)-confirmed} ({100-confirmed/len(items)*100:.1f}%)")
    print(f"Written: {SEED_PATH}")


if __name__ == "__main__":
    main()
