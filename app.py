import csv
import os
import re
import random
import uuid
import sqlite3
import json
import threading
import time
import urllib.request
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file, Response

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = os.urandom(24).hex()
DATA_DIR = os.environ.get('DATA_DIR', os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data'))
os.makedirs(DATA_DIR, exist_ok=True)

SEED_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
if DATA_DIR != SEED_DIR:
    for f in os.listdir(SEED_DIR):
        src = os.path.join(SEED_DIR, f)
        dst = os.path.join(DATA_DIR, f)
        if f.endswith('.csv') and os.path.isfile(src) and not os.path.exists(dst):
            import shutil
            shutil.copy2(src, dst)
DB_PATH = os.path.join(DATA_DIR, 'thingerz.db')

ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD', '')
API_KEY = os.environ.get('API_KEY', '')
CRAWLER_ALLOWED_PLATFORMS = {'youtube', 'bilibili', 'instagram', 'douyin', 'threads', 'xiaohongshu', 'facebook'}
FOUL_WORDS = ['fuck', 'shit', 'damn', 'ass', 'bitch', 'dick', 'piss', 'crap', 'bastard', 'slut', 'whore', '屌', '鳩', '柒', '撚', '閪', '屄', '𨳒', '仆街', '冚家鏟', '傻閪', 'on9', 'on99', 'diu', 'pkm', 'hihi', 'clsm', 'cls', 'mlg']

BLOCKED_WORDS = [
    'porn', 'xxx', 'sex', 'nude', 'naked', 'escort', 'onlyfans', 'camgirl', 'adult',
    '色情', '成人', '裸體', '裸露', '三級', '艷照', '援交', '一夜情', '約炮',
    '自慰', '打飛機', '做愛', '性交', '口交', '肛交', '性愛', '嫖妓', '叫雞', '叫鸭',
    'av', 'jav', 'hentai', 'a片', '黃片', '成人影片', '偷拍', '走光', '露點',
    'sm', 'bdsm', '換妻', '群交', '亂倫', '強姦', '迷姦', '性騷擾',
    '共產黨', '國民黨', '民進黨', '習近平', '蔡英文', '賴清德', '特朗普', '拜登',
    '政治', '示威', '抗議', '遊行', '港獨', '台獨', '藏獨', '疆獨', '六四', '天安門',
    '反送中', '國安法', '光復', '革命', '罷工', '佔中', '雨傘', '暴徒', '黑警',
    '暴亂', '香港暴亂', '暴動', '獨立', '分裂', '顛覆', '恐怖', '聖戰',
    'isis', 'terrorist', 'jihad', 'nazi', 'hitler',
]

def filter_profanity(text):
    result = text
    for word in FOUL_WORDS:
        result = result.replace(word, '*' * len(word))
    return result

def contains_blocked(text):
    if not text:
        return False
    tl = text.lower()
    for w in BLOCKED_WORDS:
        if w.lower() in tl:
            return True
    return False

HK_DISTRICTS = [
    '中西區', '灣仔區', '東區', '南區',
    '油尖旺區', '深水埗區', '九龍城區', '黃大仙區', '觀塘區',
    '葵青區', '荃灣區', '屯門區', '元朗區', '北區', '大埔區', '沙田區', '西貢區', '離島區',
]

PLATFORM_CONFIG = {
'youtube': {
        'name': 'YouTube',
        'embed_base': 'https://www.youtube-nocookie.com/embed/{id}',
        'embed_params': '?autoplay=1&rel=0&modestbranding=1&iv_load_policy=3&fs=1',
        'watch_base': 'https://www.youtube.com/watch?v={id}',
        'thumb_base': 'https://img.youtube.com/vi/{id}/hqdefault.jpg',
        'aspect_ratio': '16:9', 'color': '#FF0000',
    },
    'instagram': {
        'name': 'Instagram',
        'embed_base': 'https://www.instagram.com/p/{id}/embed/',
        'watch_base': 'https://www.instagram.com/p/{id}/',
        'thumb_base': None, 'aspect_ratio': '9:16', 'color': '#E4405F',
    },
    'tiktok': {
        'name': 'TikTok / 抖音',
        'embed_base': 'https://www.tiktok.com/embed/v2/{id}',
        'watch_base': 'https://www.tiktok.com/@{user}/video/{id}',
        'thumb_base': None, 'aspect_ratio': '9:16', 'color': '#000000',
    },
    'threads': {
        'name': 'Threads',
        'embed_base': 'https://www.threads.net/@{user}/post/{id}/embed',
        'watch_base': 'https://www.threads.net/@{user}/post/{id}',
        'thumb_base': None, 'aspect_ratio': '1:1', 'color': '#000000',
    },
    'xiaohongshu': {
        'name': '小紅書',
        'embed_base': 'https://www.xiaohongshu.com/explore/{id}',
        'watch_base': 'https://www.xiaohongshu.com/explore/{id}',
        'thumb_base': None, 'aspect_ratio': '3:4', 'color': '#FF2442',
    },
    'bilibili': {
        'name': 'Bilibili',
        'embed_base': 'https://player.bilibili.com/player.html?bvid={id}',
        'watch_base': 'https://www.bilibili.com/video/{id}',
        'thumb_base': None, 'aspect_ratio': '16:9', 'color': '#FB7299',
    },
    'douyin': {
        'name': '抖音',
        'embed_base': 'https://www.douyin.com/embed/{id}',
        'watch_base': 'https://www.douyin.com/video/{id}',
        'thumb_base': None, 'aspect_ratio': '9:16', 'color': '#000000',
    },
    'facebook': {
        'name': 'Facebook',
        'embed_base': 'https://www.facebook.com/plugins/video.php?href=https://www.facebook.com/watch/?v={id}',
        'watch_base': 'https://www.facebook.com/watch/?v={id}',
        'thumb_base': None, 'aspect_ratio': '16:9', 'color': '#1877F2',
    },
}

DIRECTIONS = {
    'fun': {'name_zh': 'Fun 頻道', 'name_en': 'Fun', 'color': 'fun'},
    'learning': {'name_zh': 'Learning 頻道', 'name_en': 'Learning', 'color': 'learning'},
    'business': {'name_zh': '商業配對', 'name_en': 'Business Matching', 'color': 'business'},
    'skills_exchange': {'name_zh': '技能互換', 'name_en': 'Skills Exchange', 'color': 'skills'},
}

HK_DISTRICTS = [
    '中西區', '灣仔區', '東區', '南區', '油尖旺區', '深水埗區',
    '九龍城區', '黃大仙區', '觀塘區', '荃灣區', '屯門區', '元朗區',
    '北區', '大埔區', '沙田區', '西貢區', '葵青區', '離島區'
]

LANGUAGES = {
    'zh-HK': {'name': '繁體中文', 'flag': '🇭🇰'},
    'zh-CN': {'name': '简体中文', 'flag': '🇨🇳'},
    'en': {'name': 'English', 'flag': '🇬🇧'},
    'ja': {'name': '日本語', 'flag': '🇯🇵'},
    'ko': {'name': '한국어', 'flag': '🇰🇷'},
    'es': {'name': 'Español', 'flag': '🇪🇸'},
    'fr': {'name': 'Français', 'flag': '🇫🇷'},
    'hi': {'name': 'हिन्दी', 'flag': '🇮🇳'},
    'ar': {'name': 'العربية', 'flag': '🇸🇦'},
    'bn': {'name': 'বাংলা', 'flag': '🇧🇩'},
    'ru': {'name': 'Русский', 'flag': '🇷🇺'},
    'pt': {'name': 'Português', 'flag': '🇧🇷'},
    'id': {'name': 'Bahasa Indonesia', 'flag': '🇮🇩'},
}

TABLE_SCHEMAS = {
    'categories': '''CREATE TABLE IF NOT EXISTS categories (
        id TEXT, category_id TEXT UNIQUE, name_slug TEXT, name_zh TEXT, name_en TEXT,
        track TEXT, direction TEXT, description_zh TEXT, description_en TEXT)''',
    'subcategories': '''CREATE TABLE IF NOT EXISTS subcategories (
        id TEXT UNIQUE, category_id TEXT, name_slug TEXT, name_zh TEXT, name_en TEXT)''',
    'videos': '''CREATE TABLE IF NOT EXISTS videos (
        id TEXT UNIQUE, subcategory_id TEXT, category_id TEXT, platform TEXT, platform_id TEXT,
        title_zh TEXT, title_en TEXT, description_zh TEXT, description_en TEXT,
        thumbnail_url TEXT, aspect_ratio TEXT, tags TEXT, status TEXT,
        track TEXT, direction TEXT, submitted_date TEXT)''',
    'news': '''CREATE TABLE IF NOT EXISTS news (
        id TEXT UNIQUE, title_zh TEXT, title_en TEXT, content_zh TEXT, content_en TEXT,
        summary_zh TEXT, summary_en TEXT, date TEXT, image_url TEXT, status TEXT, region TEXT)''',
    'comments': '''CREATE TABLE IF NOT EXISTS comments (
        id TEXT UNIQUE, video_id TEXT, author TEXT, content TEXT, date TEXT, status TEXT)''',
    'submissions': '''CREATE TABLE IF NOT EXISTS submissions (
        id TEXT UNIQUE, platform TEXT, platform_url TEXT, title_zh TEXT, title_en TEXT,
        category_id TEXT, subcategory_id TEXT, submitter_name TEXT, submitter_email TEXT,
        description_zh TEXT, direction TEXT, status TEXT, submitted_date TEXT, district TEXT)''',
    'contacts': '''CREATE TABLE IF NOT EXISTS contacts (
        id TEXT UNIQUE, name TEXT, email TEXT, subject TEXT, message TEXT, date TEXT, status TEXT)''',
    'view_counts': '''CREATE TABLE IF NOT EXISTS view_counts (\n        video_id TEXT UNIQUE, count INTEGER DEFAULT 0, clicks INTEGER DEFAULT 0)''',
    'page_views': '''CREATE TABLE IF NOT EXISTS page_views (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        page TEXT, ip_hash TEXT, viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)''',
    'crawled_videos': '''CREATE TABLE IF NOT EXISTS crawled_videos (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        platform TEXT NOT NULL, platform_id TEXT NOT NULL,\n        sub_category TEXT, district TEXT, title TEXT, url TEXT,\n        thumbnail_url TEXT, author_name TEXT, author_url TEXT,\n        description TEXT, view_count INTEGER DEFAULT 0,\n        like_count INTEGER DEFAULT 0, comment_count INTEGER DEFAULT 0,\n        duration_sec INTEGER DEFAULT 0, published_at TEXT,\n        score REAL DEFAULT 0, updated_at TEXT,\n        district_confirmed INTEGER DEFAULT 0,\n        UNIQUE(platform, platform_id))''',
}


def get_db():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    return db


def init_db():
    db = get_db()
    for table, schema in TABLE_SCHEMAS.items():
        db.execute(schema)
    # Migration: ensure crawled_videos has district_confirmed column (existing DBs)
    try:
        cols = [r[1] for r in db.execute("PRAGMA table_info(crawled_videos)").fetchall()]
        if 'district_confirmed' not in cols:
            db.execute("ALTER TABLE crawled_videos ADD COLUMN district_confirmed INTEGER DEFAULT 0")
    except Exception:
        pass
    # Migration: ensure news has region column (hk/foreign) so 好去處 can stay HK-focused
    try:
        ncols = [r[1] for r in db.execute("PRAGMA table_info(news)").fetchall()]
        if 'region' not in ncols:
            db.execute("ALTER TABLE news ADD COLUMN region TEXT DEFAULT 'hk'")
    except Exception:
        pass
    db.commit()

    csv_to_table = {
        'categories.csv': ('categories', ['id','category_id','name_slug','name_zh','name_en','track','direction','description_zh','description_en']),
        'subcategories.csv': ('subcategories', ['id','category_id','name_slug','name_zh','name_en']),
        'videos.csv': ('videos', ['id','subcategory_id','category_id','platform','platform_id','title_zh','title_en','description_zh','description_en','thumbnail_url','aspect_ratio','tags','status','track','direction','submitted_date']),
        'news.csv': ('news', ['id','title_zh','title_en','content_zh','content_en','summary_zh','summary_en','date','image_url','status','region']),
        'comments.csv': ('comments', ['id','video_id','author','content','date','status']),
        'submissions.csv': ('submissions', ['id','platform','platform_url','title_zh','title_en','category_id','subcategory_id','submitter_name','submitter_email','description_zh','direction','status','submitted_date']),
        'contacts.csv': ('contacts', ['id','name','email','subject','message','date','status']),
    }

    for csv_file, (table_name, fields) in csv_to_table.items():
        count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        if count > 0:
            continue
        csv_path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            continue
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                values = {k: row.get(k, '') for k in fields}
                placeholders = ', '.join(['?' for _ in fields])
                columns = ', '.join(fields)
                db.execute(f"INSERT OR IGNORE INTO {table_name} ({columns}) VALUES ({placeholders})",
                           [values[k] for k in fields])
    # Seed crawled_videos from JSONL if empty (survives Render ephemeral storage)
    seed_path = os.path.join(DATA_DIR, 'seed_crawled_videos.jsonl')
    if os.path.exists(seed_path):
        crawl_count = db.execute("SELECT COUNT(*) FROM crawled_videos").fetchone()[0]
        if crawl_count == 0:
            imported = 0
            with open(seed_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    platform = str(item.get('platform', '')).strip().lower()
                    platform_id = str(item.get('platform_id', '')).strip()
                    if not platform or not platform_id:
                        continue
                    try:
                        db.execute(
                            """INSERT OR IGNORE INTO crawled_videos
                            (platform, platform_id, sub_category, district, title, url,
                             thumbnail_url, author_name, author_url, description,
                             view_count, like_count, comment_count, duration_sec,
                             published_at, score, updated_at, district_confirmed)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (platform, platform_id,
                             str(item.get('sub_category', '')).strip(),
                             str(item.get('district', '')).strip(),
                             str(item.get('title', '')).strip(),
                             str(item.get('url', '')).strip(),
                             str(item.get('thumbnail_url', '')).strip(),
                             str(item.get('author_name', '')).strip(),
                             str(item.get('author_url', '')).strip(),
                             str(item.get('description', '')).strip()[:500],
                             int(item.get('view_count', 0) or 0),
                             int(item.get('like_count', 0) or 0),
                             int(item.get('comment_count', 0) or 0),
                             int(item.get('duration_sec', 0) or 0),
                             str(item.get('published_at', '')).strip(),
                             float(item.get('score', 0) or 0),
                             datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
                             1 if item.get('district_confirmed') else 0))
                        imported += 1
                    except Exception:
                        pass
            if imported > 0:
                db.commit()

    db.commit()
    db.close()


init_db()


def read_table(table_name):
    db = get_db()
    rows = [dict(r) for r in db.execute(f"SELECT * FROM {table_name}").fetchall()]
    db.close()
    return rows


def write_table(table_name, rows, fieldnames):
    db = get_db()
    db.execute(f"DELETE FROM {table_name}")
    for row in rows:
        values = {k: row.get(k, '') for k in fieldnames}
        placeholders = ', '.join(['?' for _ in fieldnames])
        columns = ', '.join(fieldnames)
        db.execute(f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})",
                   [values[k] for k in fieldnames])
    db.commit()
    db.close()


def append_table(table_name, row, fieldnames):
    db = get_db()
    values = {k: row.get(k, '') for k in fieldnames}
    placeholders = ', '.join(['?' for _ in fieldnames])
    columns = ', '.join(fieldnames)
    db.execute(f"INSERT OR REPLACE INTO {table_name} ({columns}) VALUES ({placeholders})",
               [values[k] for k in fieldnames])
    db.commit()
    db.close()


def read_csv(filename):
    return read_table(filename.replace('.csv', ''))


def write_csv(filename, rows, fieldnames):
    write_table(filename.replace('.csv', ''), rows, fieldnames)
    # Also sync to CSV for backup/deploy persistence
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(filename, row, fieldnames):
    append_table(filename.replace('.csv', ''), row, fieldnames)
    # Also sync to CSV
    rows = read_csv(filename)
    rows.append(row)
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def get_categories(track=None, direction=None):
    cats = read_csv('categories.csv')
    if track:
        cats = [c for c in cats if c.get('track', '') == track]
    if direction:
        cats = [c for c in cats if c.get('direction', '') == direction]
    return cats


def get_category(category_id):
    for c in get_categories():
        if c['category_id'] == category_id:
            return c
    return None


def get_category_by_slug(slug):
    for c in get_categories():
        if c['name_slug'] == slug:
            return c
    return None


def get_subcategories(category_id=None):
    subs = read_csv('subcategories.csv')
    if category_id:
        return [s for s in subs if s['category_id'] == category_id]
    return subs


def get_subcategory(subcategory_id):
    for s in read_csv('subcategories.csv'):
        if s['id'] == subcategory_id:
            return s
    return None


def get_videos(subcategory_id=None, category_id=None, track=None, direction=None, status='approved', district=None, limit=None):
    videos = read_csv('videos.csv')
    result = [v for v in videos if v.get('status', '') == status]

    # Merge crawled_videos (limited to avoid slow loads)
    try:
        db = get_db()
        crawl_rows = []
        # Fetch top videos per sub-category for balanced coverage
        subs = [r[0] for r in db.execute("SELECT DISTINCT sub_category FROM crawled_videos WHERE sub_category != ''").fetchall()]
        for sc in subs:
            crawl_rows.extend(db.execute(
                "SELECT * FROM crawled_videos WHERE sub_category=? ORDER BY view_count DESC LIMIT 10",
                (sc,)).fetchall())
        # Sort combined result by view_count
        crawl_rows.sort(key=lambda r: r['view_count'] or 0, reverse=True)
        db.close()
        for cr in crawl_rows:
            sc = cr['sub_category'] or ''
            # Map sub_category to category_id (s001-s008→cat001, s009-s014→cat002, etc.)
            sub_num = int(sc[1:]) if sc.startswith('s') and len(sc) == 4 and sc[1:].isdigit() else 0
            if 1 <= sub_num <= 8: cat_id = 'cat001'
            elif 9 <= sub_num <= 14: cat_id = 'cat002'
            elif 15 <= sub_num <= 22: cat_id = 'cat003'
            elif 23 <= sub_num <= 28: cat_id = 'cat004'
            elif 29 <= sub_num <= 35: cat_id = 'cat005'
            elif 36 <= sub_num <= 42: cat_id = 'cat006'
            elif 43 <= sub_num <= 48: cat_id = 'cat007'
            elif 49 <= sub_num <= 54: cat_id = 'cat008'
            elif sub_num == 55: cat_id = 'cat002'  # AI學習
            elif sub_num == 56: cat_id = 'cat003'  # COSPLAY教學
            elif sub_num == 57: cat_id = 'cat001'  # 風水命理
            elif sub_num == 58 or sub_num == 59: cat_id = 'cat004'  # 重氧運動, 小丑
            elif sub_num == 60: cat_id = 'cat003'  # 珠寶設計教學
            elif sub_num == 61: cat_id = 'cat008'  # 寵物/動物溝通
            else: cat_id = 'cat001'
            trk = 'fun' if cat_id in ('cat003','cat004','cat005','cat007') else 'learning'
            thumb = cr['thumbnail_url'] or ''
            if not thumb:
                if cr['platform'] == 'youtube':
                    thumb = f"https://img.youtube.com/vi/{cr['platform_id']}/hqdefault.jpg"
                elif cr['platform'] == 'bilibili':
                    fetched = get_bilibili_cover(cr['platform_id'])
                    if fetched:
                        thumb = fetched
                        db.execute('UPDATE crawled_videos SET thumbnail_url=? WHERE id=?', (fetched, cr['id']))
                        db.commit()
                    else:
                        thumb = f"https://picsum.photos/seed/bili_{cr['platform_id']}/400/225"
                elif cr['platform'] == 'xiaohongshu':
                    thumb = f"https://picsum.photos/seed/xhs_{cr['platform_id']}/300/400"
                else:
                    thumb = f"https://picsum.photos/seed/{cr['platform_id']}/400/225"
            result.append({
                'id': 'cv_' + str(cr['id']),
                'subcategory_id': sc,
                'category_id': cat_id,
                'platform': cr['platform'],
                'platform_id': cr['platform_id'],
                'title_zh': cr['title'] or '',
                'title_en': '',
                'description_zh': cr['description'] or '',
                'description_en': '',
                'thumbnail_url': thumb,
                'aspect_ratio': '16:9',
                'tags': cr['district'] or '',
                'district_confirmed': bool(cr['district_confirmed']),
                'status': 'approved',
                'track': trk,
                'direction': trk,
                'submitted_date': cr['published_at'] or '',
            })
    except:
        pass

    if subcategory_id and subcategory_id.startswith('s') and subcategory_id[1:].isdigit():
        # Show ALL crawled videos for this specific sub-category (not just the
        # top-10 fetched globally), so non-district-confirmed and lower-view
        # fresh videos also appear on the sub-category page.
        try:
            db = get_db()
            rows = db.execute(
                "SELECT * FROM crawled_videos WHERE sub_category=? ORDER BY view_count DESC",
                (subcategory_id,)).fetchall()
            db.close()
            sub_num = int(subcategory_id[1:])
            if 1 <= sub_num <= 8: cat_id = 'cat001'
            elif 9 <= sub_num <= 14: cat_id = 'cat002'
            elif 15 <= sub_num <= 22: cat_id = 'cat003'
            elif 23 <= sub_num <= 28: cat_id = 'cat004'
            elif 29 <= sub_num <= 35: cat_id = 'cat005'
            elif 36 <= sub_num <= 42: cat_id = 'cat006'
            elif 43 <= sub_num <= 48: cat_id = 'cat007'
            elif 49 <= sub_num <= 54: cat_id = 'cat008'
            elif sub_num == 55: cat_id = 'cat002'  # AI學習
            elif sub_num == 56: cat_id = 'cat003'  # COSPLAY教學
            elif sub_num == 57: cat_id = 'cat001'  # 風水命理
            elif sub_num in (58, 59): cat_id = 'cat004'  # 極限運動, 小丑
            elif sub_num == 60: cat_id = 'cat003'  # 珠寶設計教學
            elif sub_num == 61: cat_id = 'cat008'  # 寵物/動物溝通
            else: cat_id = 'cat001'
            trk = 'fun' if cat_id in ('cat003', 'cat004', 'cat005', 'cat007') else 'learning'
            seen = {v['id'] for v in result}
            for cr in rows:
                vid = 'cv_' + str(cr['id'])
                if vid in seen:
                    continue
                seen.add(vid)
                thumb = cr['thumbnail_url'] or ''
                if not thumb:
                    thumb = f"https://img.youtube.com/vi/{cr['platform_id']}/hqdefault.jpg"
                result.append({
                    'id': vid,
                    'subcategory_id': subcategory_id,
                    'category_id': cat_id,
                    'platform': cr['platform'],
                    'platform_id': cr['platform_id'],
                    'title_zh': cr['title'] or '',
                    'title_en': '',
                    'description_zh': cr['description'] or '',
                    'description_en': '',
                    'thumbnail_url': thumb,
                    'aspect_ratio': '16:9',
                    'tags': cr['district'] or '',
                    'district_confirmed': bool(cr['district_confirmed']),
                    'status': 'approved',
                    'track': trk,
                    'direction': trk,
                    'submitted_date': cr['published_at'] or '',
                })
        except Exception:
            pass

    if subcategory_id:
        result = [v for v in result if v['subcategory_id'] == subcategory_id]
    if category_id:
        result = [v for v in result if v['category_id'] == category_id]
    if track:
        result = [v for v in result if v.get('track', '') == track]
    if direction:
        result = [v for v in result if v.get('direction', '') == direction]
    if district:
        # District search: only show videos CONFIRMED to belong to that district.
        # (Videos from videos.csv without a flag default to confirmed = user-picked.)
        # Non-confirmed videos stay on the main page but never in district search.
        result = [v for v in result
                  if v.get('district_confirmed', True)
                  and (district in v.get('tags', '')
                       or district in v.get('title_zh', '')
                       or district in v.get('description_zh', ''))]
    # Ordering: curated/uploaded videos (videos.csv) always on top, newest upload first;
    # crawled videos after, keeping their existing (view-count) order.
    curated = [v for v in result if not str(v.get('id', '')).startswith('cv_')]
    crawled = [v for v in result if str(v.get('id', '')).startswith('cv_')]
    curated.sort(key=lambda v: str(v.get('submitted_date', '')), reverse=True)
    result = curated + crawled
    if limit:
        result = result[:limit]
    return result


def get_video(video_id):
    if video_id.startswith('cv_'):
        try:
            db = get_db()
            r = db.execute('SELECT * FROM crawled_videos WHERE id=?', (int(video_id[3:]),)).fetchone()
            db.close()
            if r:
                sc = r['sub_category'] or ''
                sub_num = int(sc[1:]) if sc.startswith('s') and len(sc) == 4 and sc[1:].isdigit() else 0
                if 1 <= sub_num <= 8: cat_id = 'cat001'
                elif 9 <= sub_num <= 14: cat_id = 'cat002'
                elif 15 <= sub_num <= 22: cat_id = 'cat003'
                elif 23 <= sub_num <= 28: cat_id = 'cat004'
                elif 29 <= sub_num <= 35: cat_id = 'cat005'
                elif 36 <= sub_num <= 42: cat_id = 'cat006'
                elif 43 <= sub_num <= 48: cat_id = 'cat007'
                elif 49 <= sub_num <= 54: cat_id = 'cat008'
                elif sub_num == 55: cat_id = 'cat002'
                elif sub_num == 56: cat_id = 'cat003'
                elif sub_num == 57: cat_id = 'cat001'
                elif sub_num == 58 or sub_num == 59: cat_id = 'cat004'
                elif sub_num == 60: cat_id = 'cat003'
                elif sub_num == 61: cat_id = 'cat008'
                else: cat_id = 'cat001'
                trk = 'fun' if cat_id in ('cat003','cat004','cat005','cat007') else 'learning'
                return {
                    'id': video_id, 'subcategory_id': sc, 'category_id': cat_id,
                    'platform': r['platform'], 'platform_id': r['platform_id'],
                    'title_zh': r['title'] or '', 'title_en': '',
                    'description_zh': r['description'] or '', 'description_en': '',
                    'thumbnail_url': r['thumbnail_url'] or '',
                    'aspect_ratio': '16:9', 'tags': r['district'] or '',
                    'district_confirmed': bool(r['district_confirmed']),
                    'status': 'approved', 'track': trk, 'direction': trk,
                    'submitted_date': r['published_at'] or '',
                }
        except:
            pass
        return None
    for v in read_csv('videos.csv'):
        if v['id'] == video_id:
            return v
    return None


def get_comments(video_id):
    comments = [c for c in read_csv('comments.csv') if c['video_id'] == video_id and c['status'] == 'approved']
    comments.sort(key=lambda c: c.get('date', ''), reverse=True)
    return comments


def _strip_tags(text):
    """Remove HTML tags entirely -> plain text (safe to auto-escape)."""
    if not text:
        return ''
    text = re.sub(r'<[^>]+>', '', str(text))
    return text


def _sanitize_news_item(n):
    """Remove raw HTML / Google-News RSS artifacts from a news (好去處) row."""
    if not isinstance(n, dict):
        return n
    # Unescape any HTML entities so code is not shown as text
    import html as _html
    for k in ('title_zh', 'title_en', 'summary_zh', 'summary_en'):
        if n.get(k):
            n[k] = _html.unescape(_strip_tags(n[k])).strip()
    for k in ('content_zh', 'content_en'):
        if n.get(k):
            c = str(n[k])
            # Drop any <a> pointing at Google News / any raw RSS url junk
            c = re.sub(r'<a[^>]*href=["\']?https?://news\.google\.com[^"\'>]*["\']?[^>]*>.*?</a>', '', c, flags=re.S | re.I)
            c = re.sub(r'https?://news\.google\.com/rss/articles/\S+', '', c)
            # Drop stray Google News list markup
            c = re.sub(r'</?ol[^>]*>|</?li[^>]*>', '', c, flags=re.I)
            n[k] = c
    return n


def get_news(news_id=None):
    news_list = [_sanitize_news_item(n) for n in read_csv('news.csv')]
    for n in news_list:
        # Extract YouTube ID so 好去處 detail can embed the video player inline
        vid = extract_youtube_id(str(n.get('content_zh', '') or '')
                                 + str(n.get('image_url', '') or ''))
        n['video_id'] = vid if vid else ''
        n['video_url'] = f"https://www.youtube.com/watch?v={vid}" if vid else ''
    if news_id:
        for n in news_list:
            if n['id'] == news_id:
                return n
        return None
    result = [n for n in news_list if n['status'] == 'published' and n.get('region', 'hk') != 'foreign']
    result.sort(key=lambda n: n.get('date', ''), reverse=True)
    return result


def get_related_videos(video, limit=4):
    all_videos = read_csv('videos.csv')
    same_sub = [v for v in all_videos if v['subcategory_id'] == video['subcategory_id'] and v['id'] != video['id'] and v['status'] == 'approved']
    if len(same_sub) >= limit:
        return same_sub[:limit]
    same_cat = [v for v in all_videos if v['category_id'] == video['category_id'] and v['id'] != video['id'] and v['status'] == 'approved']
    combined = same_sub + [v for v in same_cat if v not in same_sub]
    others = [v for v in all_videos if v['id'] != video['id'] and v['status'] == 'approved' and v not in combined]
    combined.extend(others)
    return combined[:limit]


def get_view_counts():
    db = get_db()
    rows = db.execute("SELECT video_id, count FROM view_counts").fetchall()
    db.close()
    return {r['video_id']: r['count'] for r in rows}


def increment_view(video_id):
    db = get_db()
    db.execute("INSERT INTO view_counts (video_id, count) VALUES (?, 1) ON CONFLICT(video_id) DO UPDATE SET count = count + 1", (video_id,))
    db.commit()
    db.close()


def record_page_view(page=''):
    """Record a page view with a hashed IP for unique-visitor estimation."""
    try:
        ip = request.headers.get('X-Forwarded-For', '') or request.remote_addr or ''
        import hashlib
        ip_hash = hashlib.sha256(ip.encode('utf-8')).hexdigest()[:16] if ip else 'unknown'
        db = get_db()
        db.execute("INSERT INTO page_views (page, ip_hash) VALUES (?, ?)", (str(page)[:200], ip_hash))
        db.commit()
        db.close()
    except Exception:
        pass


def get_page_stats():
    """Return aggregated visitor/view stats for /api/stats."""
    db = get_db()
    total_views = db.execute("SELECT COUNT(*) as c FROM page_views").fetchone()['c']
    unique_visitors = db.execute("SELECT COUNT(DISTINCT ip_hash) as c FROM page_views WHERE ip_hash != 'unknown'").fetchone()['c']
    today_views = db.execute("SELECT COUNT(*) as c FROM page_views WHERE date(viewed_at) = date('now')").fetchone()['c']
    month_views = db.execute("SELECT COUNT(*) as c FROM page_views WHERE strftime('%Y-%m', viewed_at) = strftime('%Y-%m', 'now')").fetchone()['c']
    db.close()
    return {
        "available": True,
        "total_views": total_views,
        "today_views": today_views,
        "month_views": month_views,
        "unique_visitors": unique_visitors,
    }


@app.route('/api/stats', methods=['GET'])
def api_stats():
    return jsonify(get_page_stats())


@app.route('/sitemap.xml')
def sitemap():
    """Generate an SEO sitemap covering all static, category, subcategory,
    news and video pages for Google Search Console."""
    base = 'https://thingerz.com'
    from xml.etree.ElementTree import Element, SubElement, tostring
    from xml.dom import minidom

    urls = []

    def add(path, priority=0.5, changefreq='weekly'):
        urls.append((base + path, priority, changefreq))

    # Static pages
    add('/', priority=1.0, changefreq='daily')
    add('/about', priority=0.4)
    add('/news', priority=0.8, changefreq='daily')
    add('/track/fun', priority=0.6)
    add('/track/learning', priority=0.6)

    # Categories (slides)
    for c in get_categories():
        slug = c.get('name_slug', '')
        if slug:
            add(f'/category/{slug}', priority=0.7)

    # Subcategories
    for s in get_subcategories():
        sid = s.get('id', '')
        if sid:
            add(f'/subcategory/{sid}', priority=0.6)

    # Crawled videos (district searchable)
    video_ids = set()
    try:
        db = get_db()
        rows = db.execute("SELECT id FROM crawled_videos WHERE district_confirmed=1 LIMIT 2000").fetchall()
        for r in rows:
            video_ids.add('cv_' + str(r['id']))
        db.close()
    except Exception:
        pass

    # Manually approved videos
    video_ids.update(v['id'] for v in get_videos(limit=10000)
                     if v.get('id') and v.get('status') == 'approved')

    for vid in list(video_ids)[:3000]:
        add(f'/video/{vid}', priority=0.4)

    # News articles
    news_list = get_news() or []
    for n in news_list:
        if n.get('id') and n.get('status') == 'published':
            add(f'/news/{n["id"]}', priority=0.7, changefreq='monthly')

    # Build XML
    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    for loc, priority, changefreq in urls:
        u = SubElement(urlset, 'url')
        SubElement(u, 'loc').text = loc
        SubElement(u, 'changefreq').text = changefreq
        SubElement(u, 'priority').text = str(priority)
    xml_str = minidom.parseString(tostring(urlset)).toprettyxml(indent='  ')
    return Response(xml_str, mimetype='application/xml')


@app.route('/robots.txt')
def robots():
    content = (
        'User-agent: *\n'
        'Disallow: /admin\n'
        'Disallow: /api/\n'
        'Allow: /\n\n'
        'Sitemap: https://thingerz.com/sitemap.xml\n'
    )
    return Response(content, mimetype='text/plain')


def extract_youtube_id(url):
    """Extract YouTube video ID from various URL formats."""
    if not url:
        return ''
    patterns = [
        r'(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/shorts/|youtube\.com/embed/|m\.youtube\.com/watch\?v=)([a-zA-Z0-9_-]{11})',
        r'youtube\.com/live/([a-zA-Z0-9_-]{11})',
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    # If the input itself looks like a valid ID (11 chars)
    if re.match(r'^[a-zA-Z0-9_-]{11}$', url.strip()):
        return url.strip()
    return ''

def extract_instagram_id(url):
    if not url:
        return ''
    match = re.search(r'instagram\.com/(?:p|reel)/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else url.strip().split('/')[-1].split('?')[0]

def extract_tiktok_id(url):
    if not url:
        return ''
    match = re.search(r'tiktok\.com/@[\w.-]+/video/(\d+)', url)
    return match.group(1) if match else url.strip().split('/')[-1].split('?')[0]


def extract_xiaohongshu_id(url):
    """Extract Xiaohongshu note ID from URL."""
    if not url:
        return ''
    match = re.search(r'xiaohongshu\.com/(?:explore|discovery/item)/([a-zA-Z0-9]+)', url)
    if match:
        return match.group(1)
    match = re.search(r'xhslink\.com/([a-zA-Z0-9]+)', url)
    if match:
        return 'xh_' + match.group(1)
    return url.strip().split('/')[-1].split('?')[0]


def extract_bilibili_id(url):
    """Extract Bilibili BV/AV ID from URL."""
    if not url:
        return ''
    match = re.search(r'bilibili\.com/video/(BV[a-zA-Z0-9]+|av\d+)', url)
    if match:
        return match.group(1)
    match_short = re.search(r'b23\.tv/([a-zA-Z0-9]+)', url)
    if match_short:
        return 'b23_' + match_short.group(1)
    return url.strip().split('/')[-1].split('?')[0]


def get_platform_thumb(platform, platform_id, api_url=''):
    """Get thumbnail URL for any platform."""
    if platform == 'youtube':
        return f"https://img.youtube.com/vi/{platform_id}/hqdefault.jpg"
    elif platform == 'instagram':
        return f"https://www.instagram.com/p/{platform_id}/media/?size=m"
    elif platform == 'bilibili':
        return api_url or f"https://picsum.photos/seed/bili_{platform_id}/400/225"
    elif platform == 'xiaohongshu':
        return api_url or f"https://picsum.photos/seed/xhs_{platform_id}/300/400"
    else:
        return api_url or f"https://picsum.photos/seed/{platform_id}/400/711"


BACKUP_FILE = os.path.join(DATA_DIR, '_auto_backup.json')


def auto_backup():
    all_data = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith('.csv') and not f.startswith('_'):
            all_data[f] = read_csv(f)
    backup = {'data': all_data, 'backup_time': datetime.now().isoformat(), 'video_count': len(all_data.get('videos.csv', [])), 'submission_count': len(all_data.get('submissions.csv', [])), 'comment_count': len(all_data.get('comments.csv', [])), 'contact_count': len(all_data.get('contacts.csv', []))}
    with open(BACKUP_FILE, 'w', encoding='utf-8') as f:
        json.dump(backup, f, ensure_ascii=False)


def start_auto_backup():
    def run():
        while True:
            time.sleep(7200)
            try:
                auto_backup()
            except:
                pass
    t = threading.Thread(target=run, daemon=True)
    t.start()


def get_backup_status():
    if os.path.exists(BACKUP_FILE):
        try:
            with open(BACKUP_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            back_time = data.get('backup_time', '')
            if back_time:
                dt = datetime.fromisoformat(back_time)
                hours_ago = (datetime.now() - dt).total_seconds() / 3600
                return {'last_backup': back_time, 'hours_ago': round(hours_ago, 1), 'video_count': data.get('video_count', 0), 'submission_count': data.get('submission_count', 0), 'comment_count': data.get('comment_count', 0), 'contact_count': data.get('contact_count', 0)}
        except:
            pass
    return {'last_backup': None, 'hours_ago': None}


def generate_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def get_bilibili_cover(bvid):
    """Fetch Bilibili cover image URL via API. Returns '' on failure."""
    try:
        u = f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}'
        r = urllib.request.Request(u, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.bilibili.com'})
        with urllib.request.urlopen(r, timeout=5) as resp:
            d = json.loads(resp.read())
            if d.get('code') == 0 and d.get('data'):
                return d['data'].get('pic', '') or ''
    except:
        pass
    return ''


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ==================== PUBLIC ROUTES ====================

def _map_subcat(sub_num):
    """Map a sub_category numeric id to category_id (cat001..cat008)."""
    if 1 <= sub_num <= 8: return 'cat001'
    elif 9 <= sub_num <= 14: return 'cat002'
    elif 15 <= sub_num <= 22: return 'cat003'
    elif 23 <= sub_num <= 28: return 'cat004'
    elif 29 <= sub_num <= 35: return 'cat005'
    elif 36 <= sub_num <= 42: return 'cat006'
    elif 43 <= sub_num <= 48: return 'cat007'
    elif 49 <= sub_num <= 54: return 'cat008'
    elif sub_num == 55: return 'cat002'   # AI學習
    elif sub_num == 56: return 'cat003'   # COSPLAY教學
    elif sub_num == 57: return 'cat001'   # 風水命理
    elif sub_num in (58, 59): return 'cat004'  # 重氧運動 / 小丑
    elif sub_num == 60: return 'cat003'   # 珠寶設計教學
    elif sub_num == 61: return 'cat008'   # 寵物/動物溝通
    return 'cat001'


def get_top_viewed(limit=100):
    """Homepage 精選影片 pool: top N videos by view count across crawled_videos."""
    result = []
    try:
        db = get_db()
        rows = db.execute(
            "SELECT * FROM crawled_videos ORDER BY view_count DESC LIMIT ?",
            (limit,)).fetchall()
        db.close()
    except Exception:
        return result
    for cr in rows:
        sc = cr['sub_category'] or ''
        sub_num = int(sc[1:]) if (sc.startswith('s') and len(sc) == 4 and sc[1:].isdigit()) else 0
        cat = _map_subcat(sub_num)
        trk = 'fun' if cat in ('cat003', 'cat004', 'cat005', 'cat007') else 'learning'
        thumb = cr['thumbnail_url'] or f"https://img.youtube.com/vi/{cr['platform_id']}/hqdefault.jpg"
        result.append({
            'id': 'cv_' + str(cr['id']),
            'subcategory_id': sc, 'category_id': cat,
            'platform': cr['platform'], 'platform_id': cr['platform_id'],
            'title_zh': cr['title'] or '', 'title_en': '',
            'description_zh': cr['description'] or '', 'description_en': '',
            'thumbnail_url': thumb, 'aspect_ratio': '16:9',
            'tags': cr['district'] or '', 'district_confirmed': bool(cr['district_confirmed']),
            'status': 'approved', 'track': trk, 'direction': trk,
            'submitted_date': cr['published_at'] or '',
        })
    return result


@app.route('/')
def index():
    record_page_view('/')
    categories = get_categories()
    fun_categories = [c for c in categories if c.get('track', '') == 'fun']
    learning_categories = [c for c in categories if c.get('track', '') == 'learning']
    # 精選影片: top 100 by view count, randomly show up to 8 each load
    pool = get_top_viewed(100)
    featured_videos = random.sample(pool, min(8, len(pool))) if pool else get_videos(limit=8)
    latest_news = get_news()[:3]
    return render_template('index.html', fun_categories=fun_categories, learning_categories=learning_categories, featured_videos=featured_videos, latest_news=latest_news, platform_config=PLATFORM_CONFIG)


@app.route('/about')
def about():
    content = ''
    about_path = os.path.join(DATA_DIR, 'about.txt')
    if os.path.exists(about_path):
        with open(about_path, 'r', encoding='utf-8') as f:
            content = f.read()
    return render_template('about.html', about_content=content)


@app.route('/downloads')
def downloads():
    return render_template('downloads.html')


@app.route('/admin/about', methods=['GET', 'POST'])
@admin_required
def admin_about():
    about_path = os.path.join(DATA_DIR, 'about.txt')
    if request.method == 'POST':
        with open(about_path, 'w', encoding='utf-8') as f:
            f.write(request.form.get('content', ''))
        return redirect(url_for('admin_about'))
    content = ''
    if os.path.exists(about_path):
        with open(about_path, 'r', encoding='utf-8') as f:
            content = f.read()
    return render_template('admin/about_edit.html', content=content)


@app.route('/api/ping', methods=['GET'])
def api_ping():
    return jsonify({'version': '1.2', 'api_key_set': bool(os.environ.get('API_KEY')), 'db_ok': True})


@app.route('/track/<track>')
def track_page(track):
    if track not in ('fun', 'learning'):
        return redirect(url_for('index'))
    categories = [c for c in get_categories() if c.get('track', '') == track]
    videos = get_videos(track=track, limit=12)
    return render_template('track.html', track=track, categories=categories, videos=videos, platform_config=PLATFORM_CONFIG)


@app.route('/category/<slug>')
def category_page(slug):
    category = get_category_by_slug(slug)
    if not category:
        return redirect(url_for('index'))
    subcategories = get_subcategories(category['category_id'])
    videos = get_videos(category_id=category['category_id'])
    district = request.args.get('district', '').strip()
    if district:
        videos = [v for v in videos if v.get('district_confirmed', True) and (district in v.get('tags', '') or district in v.get('title_zh', '') or district in v.get('description_zh', ''))]
    return render_template('category.html', category=category, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG, selected_district=district)


@app.route('/subcategory/<subcategory_id>')
def subcategory_page(subcategory_id):
    sub = get_subcategory(subcategory_id)
    if not sub:
        return redirect(url_for('index'))
    category = get_category(sub['category_id'])
    subcategories = get_subcategories(sub['category_id'])
    videos = get_videos(subcategory_id=subcategory_id)
    district = request.args.get('district', '').strip()
    if district:
        videos = [v for v in videos if v.get('district_confirmed', True) and (district in v.get('tags', '') or district in v.get('title_zh', '') or district in v.get('description_zh', ''))]
    return render_template('subcategory.html', category=category, sub=sub, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG, selected_district=district)


@app.route('/video/<video_id>')
def video_detail(video_id):
    video = get_video(video_id)
    if not video:
        return redirect(url_for('index'))
    increment_view(video_id)
    category = get_category(video['category_id'])
    sub = get_subcategory(video['subcategory_id'])
    comments = get_comments(video_id)
    related = get_related_videos(video)
    platform = PLATFORM_CONFIG.get(video.get('platform', 'youtube'), PLATFORM_CONFIG['youtube'])
    views = get_view_counts().get(video_id, 0)
    return render_template('video_detail.html', video=video, category=category, sub=sub, comments=comments, related_videos=related, platform=platform, platform_config=PLATFORM_CONFIG, views=views)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))
    all_videos = get_videos()
    results = [v for v in all_videos if q.lower() in v.get('title_zh', '').lower() or q.lower() in v.get('title_en', '').lower() or q.lower() in v.get('tags', '').lower() or q.lower() in v.get('description_zh', '').lower()]
    return render_template('search.html', query=q, results=results, platform_config=PLATFORM_CONFIG)


@app.route('/submit', methods=['GET', 'POST'])
def submit_video():
    categories = get_categories()
    if request.method == 'POST':
        subcategory_id = request.form.get('subcategory_id', '')
        category_id = ''
        if subcategory_id:
            sub = get_subcategory(subcategory_id)
            if sub:
                category_id = sub['category_id']
        title_zh = request.form.get('title_zh', '')
        desc_zh = request.form.get('description_zh', '')
        district = (request.form.get('district', '') or '').strip()  # 選填 18區
        if contains_blocked(title_zh) or contains_blocked(desc_zh):
            return render_template('submit.html', categories=categories, districts=HK_DISTRICTS, platform_config=PLATFORM_CONFIG, success=False, blocked=True)
        # Auto-approve clean submissions
        submission = {
            'id': generate_id('sub_'),
            'platform': request.form.get('platform', 'youtube'),
            'platform_url': request.form.get('platform_url', ''),
            'title_zh': title_zh,
            'title_en': request.form.get('title_en', ''),
            'category_id': category_id,
            'subcategory_id': subcategory_id,
            'submitter_name': request.form.get('submitter_name', ''),
            'submitter_email': request.form.get('submitter_email', ''),
            'description_zh': desc_zh,
            'direction': request.form.get('direction', ''),
            'status': 'approved',
            'submitted_date': datetime.now().strftime('%Y-%m-%d'),
            'district': district
        }
        fieldnames = ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date', 'district']
        append_csv('submissions.csv', submission, fieldnames)
        # Auto-add to videos
        platform = submission['platform']
        url = submission.get('platform_url', '')
        if platform == 'youtube':
            platform_id = extract_youtube_id(url)
        elif platform == 'instagram':
            platform_id = extract_instagram_id(url)
        elif platform == 'tiktok':
            platform_id = extract_tiktok_id(url)
        elif platform == 'xiaohongshu':
            platform_id = extract_xiaohongshu_id(url)
        elif platform == 'bilibili':
            platform_id = extract_bilibili_id(url)
        else:
            platform_id = url.split('/')[-1].split('?')[0]
        thumb = get_platform_thumb(platform, platform_id)
        vids = read_csv('videos.csv')
        max_num = max(int(v['id'].replace('v', '')) for v in vids) if vids else 0
        track_val = 'fun'
        cat = get_category(category_id)
        if cat:
            track_val = cat.get('track', 'fun')
        vids.append({
            'id': f"v{max_num + 1:03d}",
            'subcategory_id': subcategory_id,
            'category_id': category_id,
            'platform': platform,
            'platform_id': platform_id,
            'title_zh': title_zh,
            'title_en': request.form.get('title_en', ''),
            'description_zh': desc_zh,
            'description_en': '',
            'thumbnail_url': thumb,
            'aspect_ratio': PLATFORM_CONFIG.get(platform, {}).get('aspect_ratio', '16:9'),
            'tags': district,
            'status': 'approved',
            'track': track_val,
            'direction': request.form.get('direction', track_val),
            'submitted_date': datetime.now().strftime('%Y-%m-%d')
        })
        vfieldnames = ['id','subcategory_id','category_id','platform','platform_id','title_zh','title_en','description_zh','description_en','thumbnail_url','aspect_ratio','tags','status','track','direction','submitted_date']
        write_csv('videos.csv', vids, vfieldnames)
        return render_template('submit.html', categories=categories, districts=HK_DISTRICTS, platform_config=PLATFORM_CONFIG, success=True)
    return render_template('submit.html', categories=categories, districts=HK_DISTRICTS, platform_config=PLATFORM_CONFIG, success=False, blocked=False)


@app.route('/news')
def news_list():
    return render_template('news_list.html', news_items=get_news())


@app.route('/news/<news_id>')
def news_detail(news_id):
    item = get_news(news_id)
    if not item:
        return redirect(url_for('news_list'))
    return render_template('news_detail.html', news_item=item, all_news=get_news())


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        append_csv('contacts.csv', {
            'id': generate_id('ct_'), 'name': request.form.get('name', ''),
            'email': request.form.get('email', ''), 'subject': request.form.get('subject', ''),
            'message': request.form.get('message', ''), 'date': datetime.now().strftime('%Y-%m-%d'), 'status': 'new'
        }, ['id', 'name', 'email', 'subject', 'message', 'date', 'status'])
        return render_template('contact.html', success=True)
    return render_template('contact.html', success=False)


@app.route('/video/<video_id>/comment', methods=['POST'])
def add_comment(video_id):
    content = request.form.get('content', '').strip()
    author = request.form.get('author', '').strip() or '匿名用戶'
    if not content:
        return redirect(url_for('video_detail', video_id=video_id))
    if contains_blocked(content) or contains_blocked(author):
        return redirect(url_for('video_detail', video_id=video_id))
    content = filter_profanity(content)
    author = filter_profanity(author)
    append_csv('comments.csv', {
        'id': generate_id('cm_'), 'video_id': video_id, 'author': author,
        'content': content, 'date': datetime.now().strftime('%Y-%m-%d'), 'status': 'approved'
    }, ['id', 'video_id', 'author', 'content', 'date', 'status'])
    return redirect(url_for('video_detail', video_id=video_id))


@app.route('/api/subcategories/<category_id>')
def api_subcategories(category_id):
    return jsonify(get_subcategories(category_id))


# ==================== ADMIN ROUTES ====================

# Brute-force protection: per-IP failed-login tracking with temporary lockout.
import hmac as _hmac
_LOGIN_ATTEMPTS = {}   # ip -> [fail_count, lockout_until_epoch]
LOGIN_MAX_FAILS = 5
LOGIN_LOCKOUT_SEC = 900  # 15 min after 5 failed attempts


def _login_allowed(ip):
    now = time.time()
    rec = _LOGIN_ATTEMPTS.get(ip)
    if not rec:
        return True, None
    cnt, until = rec
    if until and now < until:
        return False, int(until - now)
    return True, None


@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        ip = request.remote_addr or '?'
        ok, wait = _login_allowed(ip)
        if not ok:
            return render_template('admin/login.html',
                                   error=f'嘗試太多，請 {(wait or 0)//60} 分鐘後再試'), 429
        submitted = request.form.get('password', '')
        if ADMIN_PASSWORD and _hmac.compare_digest(submitted.encode(), ADMIN_PASSWORD.encode()):
            _LOGIN_ATTEMPTS.pop(ip, None)
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        cnt, until = _LOGIN_ATTEMPTS.get(ip, (0, 0))
        cnt += 1
        if cnt >= LOGIN_MAX_FAILS:
            _LOGIN_ATTEMPTS[ip] = [0, time.time() + LOGIN_LOCKOUT_SEC]
            return render_template('admin/login.html',
                                   error='失敗次數過多，已鎖定 15 分鐘'), 429
        _LOGIN_ATTEMPTS[ip] = [cnt, 0]
        return render_template('admin/login.html', error='密碼錯誤'), 401
    return render_template('admin/login.html', error=None)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


@app.route('/api/track-click/<video_id>', methods=['POST'])
def track_click(video_id):
    vc = read_csv('view_counts.csv')
    found = False
    for r in vc:
        if r['video_id'] == video_id:
            r['count'] = str(int(r.get('count', 0)) + 1)
            r['clicks'] = str(int(r.get('clicks', 0)) + 1)
            found = True
            break
    if not found:
        vc.append({'video_id': video_id, 'count': '1', 'clicks': '1'})
    else:
        fieldnames = list(vc[0].keys())
        if 'clicks' not in fieldnames:
            for r in vc:
                r['clicks'] = r.get('clicks', '0')
    write_csv('view_counts.csv', vc, ['video_id', 'count', 'clicks'] if 'clicks' in vc[0] else ['video_id', 'count'])
    return jsonify({'ok': True})


@app.route('/admin/statistics')
@admin_required
def admin_statistics():
    vids = read_csv('videos.csv')
    vc = read_csv('view_counts.csv')
    vc_map = {}
    for r in vc:
        vc_map[r['video_id']] = {'views': int(r.get('count', 0)), 'clicks': int(r.get('clicks', 0))}
    video_stats = []
    total_views = 0
    total_clicks = 0
    for v in vids:
        s = vc_map.get(v['id'], {'views': 0, 'clicks': 0})
        video_stats.append({
            'id': v['id'],
            'title': v.get('title_zh', ''),
            'platform': v.get('platform', ''),
            'views': s['views'],
            'clicks': s['clicks'],
            'track': v.get('track', ''),
            'category_id': v.get('category_id', ''),
        })
        total_views += s['views']
        total_clicks += s['clicks']
    video_stats.sort(key=lambda x: x['views'], reverse=True)
    cats = get_categories()
    cat_stats = []
    for cat in cats:
        cat_vids = [vs for vs in video_stats if vs['category_id'] == cat['category_id']]
        cat_stats.append({
            'name': cat['name_zh'],
            'views': sum(v['views'] for v in cat_vids),
            'clicks': sum(v['clicks'] for v in cat_vids),
            'count': len(cat_vids),
            'track': cat.get('track', ''),
        })
    return render_template('admin/statistics.html',
                           video_stats=video_stats[:20],
                           total_views=total_views,
                           total_clicks=total_clicks,
                           total_videos=len(vids),
                            cat_stats=cat_stats,
                            platform_config=PLATFORM_CONFIG)


@app.route('/admin/dashboard')
@admin_required
def admin_dashboard():
    cats = get_categories()
    vids = read_csv('videos.csv')
    news = read_csv('news.csv')
    subs = read_csv('submissions.csv')
    contacts = read_csv('contacts.csv')
    pending = [s for s in subs if s.get('status') == 'pending']
    return render_template('admin/dashboard.html', cat_count=len(cats), vid_count=len(vids), news_count=len(news), pending_count=len(pending), contact_count=len(contacts), subs=read_csv('subcategories.csv'), categories=cats)


# --- Admin Categories ---
@app.route('/admin/categories', methods=['GET', 'POST'])
@admin_required
def admin_categories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            cats = read_csv('categories.csv')
            max_id = max(int(c['id']) for c in cats) if cats else 0
            cats.append({
                'id': str(max_id + 1),
                'category_id': request.form.get('category_id', '').strip(),
                'name_slug': request.form.get('name_slug', '').strip(),
                'name_zh': request.form.get('name_zh', '').strip(),
                'name_en': request.form.get('name_en', '').strip(),
                'track': request.form.get('track', 'fun'),
                'direction': request.form.get('direction', 'fun'),
                'description_zh': request.form.get('description_zh', ''),
                'description_en': request.form.get('description_en', ''),
            })
            write_csv('categories.csv', cats, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en', 'track', 'direction', 'description_zh', 'description_en'])
            return redirect(url_for('admin_categories'))
        elif action == 'delete':
            cat_id = request.form.get('cat_id')
            cats = [c for c in read_csv('categories.csv') if c['category_id'] != cat_id]
            write_csv('categories.csv', cats, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en', 'track', 'direction', 'description_zh', 'description_en'])
            return redirect(url_for('admin_categories'))
    return render_template('admin/categories.html', categories=read_csv('categories.csv'))


@app.route('/admin/categories/edit/<category_id>', methods=['GET', 'POST'])
@admin_required
def admin_category_edit(category_id):
    cats = read_csv('categories.csv')
    cat = None
    for c in cats:
        if c['category_id'] == category_id:
            cat = c
            break
    if not cat:
        return redirect(url_for('admin_categories'))
    if request.method == 'POST':
        for c in cats:
            if c['category_id'] == category_id:
                c['name_slug'] = request.form.get('name_slug', c['name_slug'])
                c['name_zh'] = request.form.get('name_zh', c['name_zh'])
                c['name_en'] = request.form.get('name_en', c['name_en'])
                c['track'] = request.form.get('track', c.get('track', 'fun'))
                c['direction'] = request.form.get('direction', c.get('direction', 'fun'))
                c['description_zh'] = request.form.get('description_zh', c.get('description_zh', ''))
                c['description_en'] = request.form.get('description_en', c.get('description_en', ''))
                break
        write_csv('categories.csv', cats, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en', 'track', 'direction', 'description_zh', 'description_en'])
        return redirect(url_for('admin_categories'))
    return render_template('admin/category_edit.html', category=cat)


# --- Admin Subcategories ---
@app.route('/admin/subcategories', methods=['GET', 'POST'])
@admin_required
def admin_subcategories():
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            subs = read_csv('subcategories.csv')
            max_num = max(int(s['id'].replace('s', '')) for s in subs) if subs else 0
            sub_id = f"s{max_num + 1:03d}"
            subs.append({
                'id': sub_id, 'category_id': request.form.get('category_id', ''),
                'name_slug': request.form.get('name_slug', ''),
                'name_zh': request.form.get('name_zh', ''),
                'name_en': request.form.get('name_en', ''),
            })
            write_csv('subcategories.csv', subs, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en'])
            return redirect(url_for('admin_subcategories'))
        elif action == 'delete':
            sub_id = request.form.get('sub_id')
            subs = [s for s in read_csv('subcategories.csv') if s['id'] != sub_id]
            write_csv('subcategories.csv', subs, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en'])
            return redirect(url_for('admin_subcategories'))
    return render_template('admin/subcategories.html', subcategories=read_csv('subcategories.csv'), categories=get_categories())


@app.route('/admin/subcategories/edit/<sub_id>', methods=['GET', 'POST'])
@admin_required
def admin_subcategory_edit(sub_id):
    subs = read_csv('subcategories.csv')
    sub = None
    for s in subs:
        if s['id'] == sub_id:
            sub = s
            break
    if not sub:
        return redirect(url_for('admin_subcategories'))
    if request.method == 'POST':
        for s in subs:
            if s['id'] == sub_id:
                s['category_id'] = request.form.get('category_id', s['category_id'])
                s['name_slug'] = request.form.get('name_slug', s['name_slug'])
                s['name_zh'] = request.form.get('name_zh', s['name_zh'])
                s['name_en'] = request.form.get('name_en', s['name_en'])
                break
        write_csv('subcategories.csv', subs, ['id', 'category_id', 'name_slug', 'name_zh', 'name_en'])
        return redirect(url_for('admin_subcategories'))
    return render_template('admin/subcategory_edit.html', sub=sub, categories=get_categories())


# --- Admin Videos ---
@app.route('/admin/videos')
@admin_required
def admin_videos():
    return render_template('admin/videos.html', videos=read_csv('videos.csv'), categories=get_categories(), subcategories=read_csv('subcategories.csv'), platform_config=PLATFORM_CONFIG)


@app.route('/admin/videos/add', methods=['POST'])
@admin_required
def admin_video_add():
    vids = read_csv('videos.csv')
    max_num = max(int(v['id'].replace('v', '')) for v in vids) if vids else 0
    platform = request.form.get('platform', 'youtube')
    platform_id_raw = request.form.get('platform_id', '').strip()
    if platform == 'youtube':
        platform_id = extract_youtube_id(platform_id_raw) or platform_id_raw
    elif platform == 'instagram':
        platform_id = extract_instagram_id(platform_id_raw) or platform_id_raw
    elif platform == 'tiktok':
        platform_id = extract_tiktok_id(platform_id_raw) or platform_id_raw
    elif platform == 'xiaohongshu':
        platform_id = extract_xiaohongshu_id(platform_id_raw) or platform_id_raw
    elif platform == 'bilibili':
        platform_id = extract_bilibili_id(platform_id_raw) or platform_id_raw
    else:
        platform_id = platform_id_raw
    thumb = request.form.get('thumbnail_url', '') or get_platform_thumb(platform, platform_id)
    vid = {
        'id': f"v{max_num + 1:03d}",
        'subcategory_id': request.form.get('subcategory_id', ''),
        'category_id': request.form.get('category_id', ''),
        'platform': platform,
        'platform_id': platform_id,
        'title_zh': request.form.get('title_zh', ''),
        'title_en': request.form.get('title_en', ''),
        'description_zh': request.form.get('description_zh', ''),
        'description_en': request.form.get('description_en', ''),
        'thumbnail_url': thumb,
        'aspect_ratio': request.form.get('aspect_ratio', '16:9'),
        'tags': request.form.get('tags', ''),
        'status': request.form.get('status', 'approved'),
        'track': request.form.get('track', 'fun'),
        'direction': request.form.get('direction', 'fun'),
        'submitted_date': datetime.now().strftime('%Y-%m-%d')
    }
    vids.append(vid)
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date']
    write_csv('videos.csv', vids, fieldnames)
    return redirect(url_for('admin_videos'))


@app.route('/admin/videos/edit/<video_id>', methods=['POST'])
@admin_required
def admin_video_edit(video_id):
    vids = read_csv('videos.csv')
    for v in vids:
        if v['id'] == video_id:
            v['subcategory_id'] = request.form.get('subcategory_id', v.get('subcategory_id', ''))
            v['category_id'] = request.form.get('category_id', v.get('category_id', ''))
            v['platform'] = request.form.get('platform', v.get('platform', 'youtube'))
            v['platform_id'] = request.form.get('platform_id', v.get('platform_id', ''))
            v['title_zh'] = request.form.get('title_zh', v.get('title_zh', ''))
            v['title_en'] = request.form.get('title_en', v.get('title_en', ''))
            v['description_zh'] = request.form.get('description_zh', v.get('description_zh', ''))
            v['description_en'] = request.form.get('description_en', v.get('description_en', ''))
            v['thumbnail_url'] = request.form.get('thumbnail_url', v.get('thumbnail_url', ''))
            v['aspect_ratio'] = request.form.get('aspect_ratio', v.get('aspect_ratio', '16:9'))
            v['tags'] = request.form.get('tags', v.get('tags', ''))
            v['status'] = request.form.get('status', v.get('status', 'approved'))
            v['track'] = request.form.get('track', v.get('track', 'fun'))
            v['direction'] = request.form.get('direction', v.get('direction', 'fun'))
            break
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date']
    write_csv('videos.csv', vids, fieldnames)
    return redirect(url_for('admin_videos'))


@app.route('/admin/videos/delete/<video_id>', methods=['POST'])
@admin_required
def admin_video_delete(video_id):
    vids = [v for v in read_csv('videos.csv') if v['id'] != video_id]
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date']
    write_csv('videos.csv', vids, fieldnames)
    return redirect(url_for('admin_videos'))


# --- Admin Submissions ---
@app.route('/admin/submissions')
@admin_required
def admin_submissions():
    return render_template('admin/submissions.html', submissions=read_csv('submissions.csv'), categories=get_categories(), subcategories=read_csv('subcategories.csv'), platform_config=PLATFORM_CONFIG)


@app.route('/admin/submissions/approve/<submission_id>', methods=['POST'])
@admin_required
def admin_approve_submission(submission_id):
    subs = read_csv('submissions.csv')
    submission = None
    for s in subs:
        if s['id'] == submission_id:
            submission = s
            s['status'] = 'approved'
            break
    write_csv('submissions.csv', subs, ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date', 'district'])
    if submission:
        platform = submission.get('platform', 'youtube')
        url = submission.get('platform_url', '')
        if platform == 'youtube':
            platform_id = extract_youtube_id(url)
        elif platform == 'instagram':
            platform_id = extract_instagram_id(url)
        elif platform == 'tiktok':
            platform_id = extract_tiktok_id(url)
        else:
            platform_id = url.split('/')[-1].split('?')[0]

        if platform == 'youtube':
            thumb = f"https://img.youtube.com/vi/{platform_id}/hqdefault.jpg"
        elif platform == 'instagram':
            thumb = get_platform_thumb(platform, platform_id)
        else:
            thumb = f"https://picsum.photos/seed/{platform_id}/400/711"
        vids = read_csv('videos.csv')
        max_num = max(int(v['id'].replace('v', '')) for v in vids) if vids else 0
        vids.append({
            'id': f"v{max_num + 1:03d}",
            'subcategory_id': submission.get('subcategory_id', ''),
            'category_id': submission.get('category_id', ''),
            'platform': platform,
            'platform_id': platform_id,
            'title_zh': submission.get('title_zh', ''),
            'title_en': submission.get('title_en', ''),
            'description_zh': submission.get('description_zh', ''),
            'description_en': '',
            'thumbnail_url': thumb,
            'aspect_ratio': PLATFORM_CONFIG.get(platform, {}).get('aspect_ratio', '16:9'),
            'tags': submission.get('district', ''),
            'status': 'approved',
            'track': 'fun',
            'direction': submission.get('direction', 'fun'),
            'submitted_date': datetime.now().strftime('%Y-%m-%d')
        })
        fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date']
        write_csv('videos.csv', vids, fieldnames)
    return redirect(url_for('admin_submissions'))


@app.route('/admin/submissions/reject/<submission_id>', methods=['POST'])
@admin_required
def admin_reject_submission(submission_id):
    subs = read_csv('submissions.csv')
    for s in subs:
        if s['id'] == submission_id:
            s['status'] = 'rejected'
            break
    write_csv('submissions.csv', subs, ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date', 'district'])
    return redirect(url_for('admin_submissions'))


# --- Admin News ---
@app.route('/admin/news', methods=['GET', 'POST'])
@admin_required
def admin_news():
    if request.method == 'POST':
        news_list = read_csv('news.csv')
        max_num = max(int(n['id'].replace('n', '')) for n in news_list) if news_list else 0
        news_list.append({
            'id': f"n{max_num + 1:03d}",
            'title_zh': request.form.get('title_zh', ''),
            'title_en': request.form.get('title_en', ''),
            'content_zh': request.form.get('content_zh', ''),
            'content_en': request.form.get('content_en', ''),
            'summary_zh': request.form.get('summary_zh', ''),
            'summary_en': request.form.get('summary_en', ''),
            'date': request.form.get('date', datetime.now().strftime('%Y-%m-%d')),
            'image_url': request.form.get('image_url', ''),
            'status': request.form.get('status', 'published'),
            'region': request.form.get('region', 'hk'),
        })
        write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region'])
        return redirect(url_for('admin_news'))
    return render_template('admin/news.html', news_items=read_csv('news.csv'))


@app.route('/admin/news/edit/<news_id>', methods=['POST'])
@admin_required
def admin_news_edit(news_id):
    news_list = read_csv('news.csv')
    for n in news_list:
        if n['id'] == news_id:
            n['title_zh'] = request.form.get('title_zh', n.get('title_zh', ''))
            n['title_en'] = request.form.get('title_en', n.get('title_en', ''))
            n['content_zh'] = request.form.get('content_zh', n.get('content_zh', ''))
            n['content_en'] = request.form.get('content_en', n.get('content_en', ''))
            n['summary_zh'] = request.form.get('summary_zh', n.get('summary_zh', ''))
            n['summary_en'] = request.form.get('summary_en', n.get('summary_en', ''))
            n['date'] = request.form.get('date', n.get('date', ''))
            n['image_url'] = request.form.get('image_url', n.get('image_url', ''))
            n['status'] = request.form.get('status', n.get('status', 'published'))
            n['region'] = request.form.get('region', n.get('region', 'hk'))
            break
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region'])
    return redirect(url_for('admin_news'))


@app.route('/admin/news/delete/<news_id>', methods=['POST'])
@admin_required
def admin_news_delete(news_id):
    news_list = [n for n in read_csv('news.csv') if n['id'] != news_id]
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region'])
    return redirect(url_for('admin_news'))


# --- Admin Contacts ---
@app.route('/admin/contacts')
@admin_required
def admin_contacts():
    contacts = read_csv('contacts.csv')
    return render_template('admin/contacts.html', contacts=contacts)


@app.route('/admin/contacts/mark/<contact_id>/<status>')
@admin_required
def admin_contact_mark(contact_id, status):
    contacts = read_csv('contacts.csv')
    for c in contacts:
        if c['id'] == contact_id:
            c['status'] = status
            break
    write_csv('contacts.csv', contacts, ['id', 'name', 'email', 'subject', 'message', 'date', 'status'])
    return redirect(url_for('admin_contacts'))


# --- Admin Comments ---
@app.route('/admin/comments')
@admin_required
def admin_comments():
    return render_template('admin/comments.html', comments=read_csv('comments.csv'))


@app.route('/admin/comments/approve/<comment_id>')
@admin_required
def admin_comment_approve(comment_id):
    comments = read_csv('comments.csv')
    for c in comments:
        if c['id'] == comment_id:
            c['status'] = 'approved'
            break
    write_csv('comments.csv', comments, ['id', 'video_id', 'author', 'content', 'date', 'status'])
    return redirect(url_for('admin_comments'))


@app.route('/admin/comments/delete/<comment_id>')
@admin_required
def admin_comment_delete(comment_id):
    comments = [c for c in read_csv('comments.csv') if c['id'] != comment_id]
    write_csv('comments.csv', comments, ['id', 'video_id', 'author', 'content', 'date', 'status'])
    return redirect(url_for('admin_comments'))


# --- Backup / Restore ---
@app.route('/admin/backup')
@admin_required
def admin_backup():
    import json, io
    all_data = {}
    for f in os.listdir(DATA_DIR):
        if f.endswith('.csv'):
            all_data[f] = read_csv(f)
    backup = {'data': all_data, 'backup_date': datetime.now().isoformat()}
    content = json.dumps(backup, ensure_ascii=False, indent=2)
    buf = io.BytesIO()
    buf.write(content.encode('utf-8'))
    buf.seek(0)
    return send_file(buf, mimetype='application/json', as_attachment=True, download_name=f'thingerz_backup_{datetime.now().strftime("%Y%m%d_%H%M")}.json')


@app.route('/admin/restore', methods=['POST'])
@admin_required
def admin_restore():
    import json
    file = request.files.get('backup_file')
    if not file:
        return redirect(url_for('admin_dashboard'))
    content = file.read().decode('utf-8')
    backup = json.loads(content)
    if 'data' not in backup:
        return 'Invalid backup file', 400
    for filename, rows in backup['data'].items():
        if rows:
            write_csv(filename, rows, list(rows[0].keys()))
    return redirect(url_for('admin_dashboard'))


# --- Content Freshness ---
@app.route('/admin/freshness')
@admin_required
def admin_freshness():
    today = datetime.now()
    vids = read_csv('videos.csv')
    news = read_csv('news.csv')
    def age_days(date_str):
        try:
            return (today - datetime.strptime(date_str, '%Y-%m-%d')).days
        except:
            return 999
    stale_videos = []
    stale_news = []
    fresh_videos = []
    for v in vids:
        d = age_days(v.get('submitted_date', ''))
        if d > 60:
            stale_videos.append({**v, 'age_days': d})
        elif d <= 14:
            fresh_videos.append({**v, 'age_days': d})
    for n in news:
        d = age_days(n.get('date', ''))
        if d > 90:
            stale_news.append({**n, 'age_days': d})
    return render_template('admin/freshness.html', stale_videos=stale_videos, stale_news=stale_news, fresh_videos=fresh_videos, today=today.strftime('%Y-%m-%d'))


# --- Competitor Comparison ---
@app.route('/admin/competitors')
@admin_required
def admin_competitors():
    checks = [
        {'feature': '首頁英雄區搜尋', 'us': True, 'fiverr': True, 'toby': True},
        {'feature': '雙軌分流 (Fun/Learning)', 'us': True, 'fiverr': False, 'toby': False},
        {'feature': '3 層 CMS (類別→子類→影片)', 'us': True, 'fiverr': True, 'toby': True},
        {'feature': '影片策展 + YouTube 嵌入', 'us': True, 'fiverr': False, 'toby': False},
        {'feature': '管理後台 (CRUD)', 'us': True, 'fiverr': True, 'toby': True},
        {'feature': '訪客提交 + 審核流程', 'us': True, 'fiverr': False, 'toby': False},
        {'feature': '新聞 CMS + 自動獲取', 'us': True, 'fiverr': False, 'toby': False},
        {'feature': '會員系統', 'us': False, 'fiverr': True, 'toby': True},
        {'feature': '評分/評論系統 (1-5星)', 'us': False, 'fiverr': True, 'toby': True},
        {'feature': '支付系統', 'us': False, 'fiverr': True, 'toby': True},
        {'feature': 'AI / CS Bot', 'us': '預留', 'fiverr': True, 'toby': 'AI Beta'},
        {'feature': '手機 App', 'us': '預留', 'fiverr': True, 'toby': True},
        {'feature': '多語言', 'us': False, 'fiverr': True, 'toby': '繁中為主'},
        {'feature': 'SEO 頁尾', 'us': True, 'fiverr': True, 'toby': True},
        {'feature': '搜尋功能', 'us': True, 'fiverr': True, 'toby': True},
        {'feature': '社交分享', 'us': True, 'fiverr': False, 'toby': False},
        {'feature': '聯絡表單', 'us': True, 'fiverr': True, 'toby': True},
    ]
    return render_template('admin/competitors.html', checks=checks)


@app.route('/admin/health')
@admin_required
def admin_health():
    now = datetime.now()
    vids = read_csv('videos.csv')
    news = read_csv('news.csv')
    comments = read_csv('comments.csv')
    subs = read_csv('submissions.csv')

    stale_videos = []
    for v in vids:
        try:
            d = datetime.strptime(v.get('submitted_date', '2000-01-01'), '%Y-%m-%d')
            days = (now - d).days
            if days > 60:
                stale_videos.append({'title': v['title_zh'], 'days': days, 'id': v['id']})
        except:
            pass
    stale_videos.sort(key=lambda x: x['days'], reverse=True)

    total_views = sum(int(v.get('count', 0)) for v in read_csv('view_counts.csv'))
    approved_vids = len([v for v in vids if v.get('status') == 'approved'])
    pending_subs = len([s for s in subs if s.get('status') == 'pending'])
    total_comments = len([c for c in comments if c.get('status') == 'approved'])

    insights = {
        'total_videos': len(vids),
        'approved_videos': approved_vids,
        'stale_videos': stale_videos[:10],
        'stale_count': len(stale_videos),
        'total_news': len([n for n in news if n.get('status') == 'published']),
        'total_views': total_views,
        'pending_submissions': pending_subs,
        'total_comments': total_comments,
        'competitor_notes': [
            {'platform': 'Fiverr', 'strength': '全球最大自由工作者平台，AI matching 成熟', 'weakness': '缺乏本地香港內容，廣東話支援不足', 'to_watch': 'AI 提案匹配、賣家評級系統'},
            {'platform': 'HelloToby', 'strength': '全港最大生活服務配對，80K+ 專家，Alipay 整合', 'weakness': '以服務為主，非影音內容策展', 'to_watch': 'AI 模式 Beta、透明報價、合作夥伴生態'},
        ],
        'self_improve': [
            '定期檢查影片連結是否仍有效（YouTube 影片可能被刪除）',
            '每週從 Google News 獲取最新本地新聞',
            '留意 Toby/Fiverr 新功能（AI matching、評分系統）',
            '收集用戶提交的影片類型偏好，調整分類',
        ]
    }
    return render_template('admin/health.html', insights=insights, now=now)


@app.route('/admin/news/fetch', methods=['POST'])
@admin_required
def admin_news_fetch():
    import urllib.request
    import xml.etree.ElementTree as ET
    fetched = 0
    try:
        url = 'https://news.google.com/rss?hl=zh-HK&gl=HK&ceid=HK:zh-Hant'
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            tree = ET.parse(resp)
        existing = read_csv('news.csv')
        existing_titles = {n['title_zh'] for n in existing}
        max_num = max(int(n['id'].replace('n', '')) for n in existing) if existing else 0
        for item in tree.findall('.//item')[:10]:
            title = item.find('title').text or ''
            if title in existing_titles:
                continue
            link = item.find('link').text or ''
            pub_date = item.find('pubDate')
            date_str = datetime.strptime(pub_date.text, '%a, %d %b %Y %H:%M:%S %Z').strftime('%Y-%m-%d') if pub_date is not None else datetime.now().strftime('%Y-%m-%d')
            description = item.find('description')
            desc_text = description.text[:200] if description is not None and description.text else ''
            source = item.find('source')
            source_name = source.text if source is not None else 'Google News'
            max_num += 1
            existing.append({
                'id': f"n{max_num:03d}",
                'title_zh': title,
                'title_en': '',
                'content_zh': f'<p>{desc_text}</p><p>來源：{source_name} | <a href="{link}" target="_blank">閱讀原文</a></p>',
                'content_en': '',
                'summary_zh': desc_text,
                'summary_en': '',
                'date': date_str,
                'image_url': f'https://picsum.photos/seed/{max_num}/800/400',
                'status': 'published',
                'region': 'hk',
            })
            existing_titles.add(title)
            fetched += 1
        write_csv('news.csv', existing, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region'])
    except Exception as e:
        return f'<p>獲取失敗：{e}</p><a href="{url_for("admin_news")}">返回</a>', 500
    return redirect(url_for('admin_news'))


@app.context_processor
def inject_globals():
    return {
        'categories': get_categories(),
        'platform_config': PLATFORM_CONFIG,
        'directions': DIRECTIONS,
        'now': datetime.now(),
        'get_backup_status': get_backup_status,
    }


@app.route('/api/content', methods=['POST', 'DELETE', 'OPTIONS'])
def api_content():
    if request.method == 'OPTIONS':
        return '', 204

    provided = (request.headers.get('X-API-Key') or '').strip()
    if not provided:
        body = request.get_json(silent=True) or {}
        provided = str(body.get('key', '')).strip()
    if not provided or provided != API_KEY:
        return jsonify({'status': 'error', 'message': 'Invalid API key'}), 401

    # DELETE endpoint - remove bad crawled content
    if request.method == 'DELETE':
        body = request.get_json(silent=True) or {}
        platform = str(body.get('platform', '')).strip()
        ids = body.get('ids', [])
        platform_ids = body.get('platform_ids', [])
        db = get_db()
        deleted = 0
        if platform_ids:
            placeholders = ','.join(['?' for _ in platform_ids])
            cur = db.execute(f"DELETE FROM crawled_videos WHERE platform=? AND platform_id IN ({placeholders})", [platform] + platform_ids)
            deleted = cur.rowcount
        elif ids:
            placeholders = ','.join(['?' for _ in ids])
            cur = db.execute(f"DELETE FROM crawled_videos WHERE platform=? AND id IN ({placeholders})", [platform] + ids)
            deleted = cur.rowcount
        elif platform:
            cur = db.execute("DELETE FROM crawled_videos WHERE platform=?", (platform,))
            deleted = cur.rowcount
        db.commit()
        db.close()
        return jsonify({'status': 'ok', 'deleted': deleted})

    body = request.get_json(silent=True) or {}
    content = body.get('content')
    if not isinstance(content, list):
        return jsonify({'status': 'error', 'message': 'content must be a list'}), 400

    updated_at = str(body.get('updated_at', '')) or datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

    db = get_db()
    received = len(content)
    duplicates = 0
    errors = 0
    inserted = 0

    for item in content:
        if not isinstance(item, dict):
            errors += 1
            continue
        try:
            platform = str(item.get('platform', '')).strip().lower()
            platform_id = str(item.get('platform_id', '')).strip()
            sub_category = str(item.get('sub_category', '')).strip()
            if platform not in CRAWLER_ALLOWED_PLATFORMS or not platform_id:
                errors += 1
                continue
            if sub_category and not re.fullmatch(r's\d{3}', sub_category):
                errors += 1
                continue

            exists = db.execute(
                "SELECT 1 FROM crawled_videos WHERE platform=? AND platform_id=?",
                (platform, platform_id)).fetchone()
            if exists:
                duplicates += 1
                continue

            description = str(item.get('description', '')).strip()[:500]
            cur = db.execute(
                """INSERT OR IGNORE INTO crawled_videos
                (platform, platform_id, sub_category, district, title, url,
                 thumbnail_url, author_name, author_url, description,
                 view_count, like_count, comment_count, duration_sec,
                 published_at, score, updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (platform, platform_id,
                 sub_category,
                 str(item.get('district', '')).strip(),
                 str(item.get('title', '')).strip(),
                 str(item.get('url', '')).strip(),
                 str(item.get('thumbnail_url', '')).strip(),
                 str(item.get('author_name', '')).strip(),
                 str(item.get('author_url', '')).strip(),
                 description,
                 int(item.get('view_count') or 0),
                 int(item.get('like_count') or 0),
                 int(item.get('comment_count') or 0),
                 int(item.get('duration_sec') or 0),
                 str(item.get('published_at', '')).strip(),
                 float(item.get('score') or 0),
                 updated_at))
            if cur.rowcount > 0:
                inserted += 1
            else:
                duplicates += 1
        except (ValueError, TypeError):
            errors += 1
    db.commit()
    db.close()

    return jsonify({'status': 'ok', 'received': received,
                    'duplicates_skipped': duplicates, 'errors': errors})


@app.after_request
def add_utf8_header(response):
    ct = response.headers.get('Content-Type', '')
    if ct and 'text/html' in ct:
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


@app.errorhandler(500)
def internal_error(e):
    import traceback
    return f"<pre>500 Internal Server Error\n\n{traceback.format_exc()}</pre>", 500


if __name__ == '__main__':
    import sys
    start_auto_backup()
    try:
        auto_backup()
    except:
        pass
    port = int(os.environ.get('PORT', 5000))
    debug = '--debug' in sys.argv
    app.run(host='0.0.0.0', port=port, debug=debug)
else:
    start_auto_backup()
    try:
        auto_backup()
    except:
        pass