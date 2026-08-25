import csv
import os
import re
import random
import uuid
import secrets
import sqlite3
import json
import threading
import time
import urllib.request
import urllib.parse
import zlib
from datetime import datetime
from collections import Counter
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file, Response, abort

import geo  # 18-district GEO landing pages

try:
    import screening  # restricted-word upload screening (self-contained, works on Render)
except Exception:
    screening = None

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
# Persistent secret from env when set, else random — sessions survive restarts
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or secrets.token_urlsafe(32)
# DDoS guard: cap request body size (16MB) — blocks oversized POST floods
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
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

def _secret(name):
    """Resolve a secret: env var first, then Render 'Secret File' mounts
    (e.g. /etc/secrets/NAME). Secret files are NOT env vars on Render, so
    we read the mounted file explicitly. Whitespace/newline trimmed."""
    v = os.environ.get(name, '').strip()
    if v:
        return v
    for base in ('/etc/secrets', '/var/run/secrets', '/run/secrets'):
        try:
            with open(os.path.join(base, name), encoding='utf-8') as f:
                v = f.read().strip()
            if v:
                return v
        except (OSError, IOError):
            continue
    return ''


ADMIN_PASSWORD = _secret('ADMIN_PASSWORD')
API_KEY = _secret('API_KEY')

# IndexNow key — served at /{key}.txt so Bing/Yandex/Naver/Seznam can verify
# URL submissions (fast crawling of new /location pages for AI/LLM citations).
INDEXNOW_KEY = 'e389115dc5f0ae53d885384d6bf1d12f'
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
    """Restricted/blood-block word scan (input gate for comments, submissions).

    English words use WHOLE-WORD boundary match (\\bword\\b) so legitimate text like
    "music" / "asmr" / "blogspot" / "photoshop" no longer false-positive on "
    'sm'/'x'/'av' substrings (seen 2026-08: kitsmusicproduction.com rejected for
    "sm"). Chinese words stay plain substring matches (no word boundaries in CJK).
    """
    if not text:
        return False
    tl = text.lower()
    for w in BLOCKED_WORDS:
        if w.isascii():
            if re.search(r'\b' + re.escape(w) + r'\b', tl):
                return True
        else:
            if w in tl:
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
        # Threads has NO username-less embed. We store the full path (@user/post/ID)
        # in platform_id, so {id} carries it and the URL becomes
        # https://www.threads.net/@user/post/ID[/embed]. ({user} is left unused.)
        'embed_base': 'https://www.threads.net/{id}/embed',
        'watch_base': 'https://www.threads.net/{id}',
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
        track TEXT, direction TEXT, submitted_date TEXT, submitter_name TEXT)''',
    'news': '''CREATE TABLE IF NOT EXISTS news (
        id TEXT UNIQUE, title_zh TEXT, title_en TEXT, content_zh TEXT, content_en TEXT,
        summary_zh TEXT, summary_en TEXT, date TEXT, image_url TEXT, status TEXT, region TEXT, district TEXT)''',
    'lifetips': '''CREATE TABLE IF NOT EXISTS lifetips (
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
    'upload_limits': '''CREATE TABLE IF NOT EXISTS upload_limits (
        ip_hash TEXT, day TEXT, cnt INTEGER DEFAULT 0, PRIMARY KEY(ip_hash, day))''',
    'crawled_videos': '''CREATE TABLE IF NOT EXISTS crawled_videos (\n        id INTEGER PRIMARY KEY AUTOINCREMENT,\n        platform TEXT NOT NULL, platform_id TEXT NOT NULL,\n        sub_category TEXT, district TEXT, title TEXT, url TEXT,\n        thumbnail_url TEXT, author_name TEXT, author_url TEXT,\n        description TEXT, view_count INTEGER DEFAULT 0,\n        like_count INTEGER DEFAULT 0, comment_count INTEGER DEFAULT 0,\n        duration_sec INTEGER DEFAULT 0, published_at TEXT,\n        score REAL DEFAULT 0, updated_at TEXT,\n        district_confirmed INTEGER DEFAULT 0, sport_tag TEXT,\n        UNIQUE(platform, platform_id))''',
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
        if 'sport_tag' not in cols:
            db.execute("ALTER TABLE crawled_videos ADD COLUMN sport_tag TEXT")
    except Exception:
        pass
    # Migration: ensure videos has submitter_name column (submitter credit on cards)
    try:
        vcols = [r[1] for r in db.execute("PRAGMA table_info(videos)").fetchall()]
        if 'submitter_name' not in vcols:
            db.execute("ALTER TABLE videos ADD COLUMN submitter_name TEXT")
    except Exception:
        pass
    # Migration: ensure news has region column (hk/foreign) so 好去處 can stay HK-focused
    try:
        ncols = [r[1] for r in db.execute("PRAGMA table_info(news)").fetchall()]
        if 'region' not in ncols:
            db.execute("ALTER TABLE news ADD COLUMN region TEXT DEFAULT 'hk'")
    except Exception:
        pass
    # Migration: ensure news has district column (18區) so 好去處 can be filtered by district
    try:
        ncols = [r[1] for r in db.execute("PRAGMA table_info(news)").fetchall()]
        if 'district' not in ncols:
            db.execute("ALTER TABLE news ADD COLUMN district TEXT")
        # Backfill: fill EMPTY district on existing rows from the curated news.csv
        # labels (never overwrite a value already set). This makes 好去處 district
        # filtering work on a persisted live DB right after deploy, not only on a
        # fresh reseed.
        _csv = os.path.join(DATA_DIR, 'news.csv')
        if os.path.exists(_csv):
            with open(_csv, 'r', encoding='utf-8-sig', newline='') as f:
                for row in csv.DictReader(f):
                    nid = (row.get('id') or '').strip()
                    dist = (row.get('district') or '').strip()
                    if nid and dist:
                        db.execute(
                            "UPDATE news SET district=? WHERE id=? AND (district IS NULL OR district='')",
                            (dist, nid))
    except Exception:
        pass
    # Migration: ensure submissions has district column (pre-existing DBs created
    # before the field was added — without this every /submit POST crashes)
    try:
        scols = [r[1] for r in db.execute("PRAGMA table_info(submissions)").fetchall()]
        if 'district' not in scols:
            db.execute("ALTER TABLE submissions ADD COLUMN district TEXT")
    except Exception:
        pass
    db.commit()

    csv_to_table = {
        'categories.csv': ('categories', ['id','category_id','name_slug','name_zh','name_en','track','direction','description_zh','description_en']),
        'subcategories.csv': ('subcategories', ['id','category_id','name_slug','name_zh','name_en']),
        'videos.csv': ('videos', ['id','subcategory_id','category_id','platform','platform_id','title_zh','title_en','description_zh','description_en','thumbnail_url','aspect_ratio','tags','status','track','direction','submitted_date','submitter_name']),
        'news.csv': ('news', ['id','title_zh','title_en','content_zh','content_en','summary_zh','summary_en','date','image_url','status','region','district']),
        'lifetips.csv': ('lifetips', ['id','title_zh','title_en','content_zh','content_en','summary_zh','summary_en','date','image_url','status','region']),
        'comments.csv': ('comments', ['id','video_id','author','content','date','status']),
        'submissions.csv': ('submissions', ['id','platform','platform_url','title_zh','title_en','category_id','subcategory_id','submitter_name','submitter_email','description_zh','direction','status','submitted_date']),
        'contacts.csv': ('contacts', ['id','name','email','subject','message','date','status']),
    }

    # Reference tables (categories / subcategories) are the static source of
    # truth in CSV — always sync any missing rows from CSV so new sub-categories
    # (e.g. s065-s073) appear on a persisted live DB after deploy, not just on a
    # fresh one.
    #
    # LIVE-EDITABLE tables (videos / submissions / comments / contacts) get a
    # one-way CSV->DB backfill: INSERT OR IGNORE by id so repo-committed rows
    # (e.g. v073+ uploaded before a deploy) are re-added to a persisted live DB
    # that already has rows, WITHOUT overwriting live admin edits / live-only
    # rows. This fixes the 2026-08-15 bug where a Render deploy wiped v073-v076
    # (init_db skipped non-empty tables and never re-seeded them).
    #
    # news / lifetips keep the count==0 guard: they are daily-fetched and the
    # live table is authoritative (a stale local CSV must never clobber the
    # live articles a cron just wrote).
    SYNC_TABLES = {
        'categories': 'insert_or_replace',
        'subcategories': 'insert_or_replace',
        'videos': 'insert_ignore',
        'submissions': 'insert_ignore',
        'comments': 'insert_ignore',
        'contacts': 'insert_ignore',
    }
    for csv_file, (table_name, fields) in csv_to_table.items():
        mode = SYNC_TABLES.get(table_name, 'count0_only')
        if mode == 'count0_only':
            count = db.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
            if count > 0:
                continue
        csv_path = os.path.join(DATA_DIR, csv_file)
        if not os.path.exists(csv_path):
            continue
        csv_ids = set()
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                csv_ids.add(str(row.get(fields[0], '')).strip())
                values = {k: row.get(k, '') for k in fields}
                placeholders = ', '.join(['?' for _ in fields])
                columns = ', '.join(fields)
                verb = 'INSERT OR REPLACE' if mode == 'insert_or_replace' else 'INSERT OR IGNORE'
                db.execute(f"{verb} INTO {table_name} ({columns}) VALUES ({placeholders})",
                           [values[k] for k in fields])
        # Reference tables are CSV-authoritative: DB rows removed from the CSV
        # (e.g. deleted s007 餐飲與酒類, merged into s031 2026-08-21) must be
        # pruned on every start, or a persisted live DB keeps serving the stale
        # sub/nav page + sitemap URL forever. NEVER applied to live-editable
        # tables (videos/submissions/...) — those are merge-add only.
        if mode == 'insert_or_replace':
            db_id = fields[0]
            if csv_ids:
                placeholders = ','.join(['?' for _ in csv_ids])
                db.execute(f"DELETE FROM {table_name} WHERE {db_id} NOT IN ({placeholders})",
                           list(csv_ids))
    # Seed crawled_videos from JSONL if empty (survives Render ephemeral storage)
    seed_path = os.path.join(DATA_DIR, 'seed_crawled_videos.jsonl')
    if os.path.exists(seed_path):
        crawl_count = db.execute("SELECT COUNT(*) FROM crawled_videos").fetchone()[0]
        if crawl_count == 0:
            imported = 0
            _seed_ids = set()
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
                        # Stable, content-derived id (crc32 of platform_id) so the
                        # same video always gets the same rowid on every re-seed,
                        # independent of file order or prior deletes. This keeps
                        # /video/cv_<id> URLs stable across Render re-deploys.
                        pkey = str(platform_id).encode('utf-8', 'ignore')
                        id_int = zlib.crc32(pkey)
                        while id_int in _seed_ids:
                            id_int = (id_int + 1) & 0xFFFFFFFF
                        _seed_ids.add(id_int)
                        db.execute(
                            """INSERT OR IGNORE INTO crawled_videos
                            (id, platform, platform_id, sub_category, district, title, url,
                             thumbnail_url, author_name, author_url, description,
                             view_count, like_count, comment_count, duration_sec,
                             published_at, score, updated_at, district_confirmed, sport_tag)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                            (id_int, platform, platform_id,
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
                             1 if item.get('district_confirmed') else 0,
                             str(item.get('sport_tag', '')).strip()))
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


def log_upload(entry):
    """Append-only, never-rewritten record of every user upload. Written at the
    FIRST possible point in the submit/admin-add flows so the raw source (URL,
    title, form fields, ip, timestamp) is preserved even if the main csv/db
    later gets mangled or wiped by a Render deploy. This file is pulled by the
    /admin/backup dump and merged into the local git repo by the frequent
    thingerz-daily-backup cron, so an upload is never lost.
    """
    try:
        path = os.path.join(DATA_DIR, 'uploads_log.jsonl')
        entry.setdefault('logged_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        entry.setdefault('remote_addr', request.remote_addr or '')
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass  # logging must never break an upload


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


# Convert YouTube's relative upload-time strings ("8 日前", "5 個月前", "1 年前",
# "13 小時前", "11 個月前曾經串流") into a sortable "days ago" float, so crawled
# videos can be ordered newest-first. Empty/unknown -> very old (sorts last).
_AGO_RE = re.compile(r'(\d+)\s*(分鐘|小時|日|星期|個月|年)前')
_AGO_MULT = {'分鐘': 1 / 1440.0, '小時': 1 / 24.0, '日': 1.0,
             '星期': 7.0, '個月': 30.0, '年': 365.0}


def _published_ago_days(s):
    if not s:
        return float('inf')
    m = _AGO_RE.search(str(s))
    if m:
        return int(m.group(1)) * _AGO_MULT[m.group(2)]
    # Absolute ISO/datetime upload timestamps (freshly curated rows write
    # published_at=now-ISO, not YouTube's relative "8 日前" string). Parse them so
    # batch-curated videos sort by real publish date, not dumped last at inf.
    try:
        t = str(s).strip()
        parsed = None
        if 'T' in t:
            parsed = datetime.fromisoformat(t.replace('Z', '+00:00'))
        else:
            # bare date like 2026-08-21
            from datetime import date
            parsed = datetime.combine(date.fromisoformat(t[:10]), datetime.min.time())
        if parsed.tzinfo is not None:
            from datetime import datetime as _dt, timezone
            now = _dt.now(timezone.utc)
            diff = now - parsed
            return max(0.0, diff.total_seconds() / 86400.0)
        else:
            from datetime import datetime as _dt, timezone
            diff = _dt.now(timezone.utc).replace(tzinfo=None) - parsed
            return max(0.0, diff.total_seconds() / 86400.0)
    except Exception:
        return float('inf')


def get_videos(subcategory_id=None, category_id=None, track=None, direction=None, status='approved', district=None, limit=None):
    videos = read_csv('videos.csv')
    result = [v for v in videos if v.get('status', '') == status]

    # Merge crawled_videos (limited to avoid slow loads)
    try:
        db = get_db()
        crawl_rows = []
        if district:
            # District pages need ALL confirmed rows for the district, not just
            # the top-10-per-sub slice — otherwise most district content is
            # invisible (e.g. 大埔 608 confirmed but only 5 surfaced).
            crawl_rows.extend(db.execute(
                "SELECT * FROM crawled_videos WHERE district_confirmed=1 AND "
                "district LIKE ? ORDER BY view_count DESC LIMIT 600",
                ('%' + district + '%',)).fetchall())
        else:
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
            elif sub_num == 62: cat_id = 'cat002'  # 音響設備及教學
            elif sub_num == 63: cat_id = 'cat001'  # 汽車維修及裝置
            elif sub_num == 64: cat_id = 'cat005'  # 燒賣腸粉關注組
            elif sub_num == 65: cat_id = 'cat002'  # 身心靈提升
            elif sub_num == 66: cat_id = 'cat003'  # 手錶設計及維修
            elif sub_num == 67: cat_id = 'cat003'  # 動漫及動畫
            elif sub_num == 68: cat_id = 'cat008'  # 玩具(四驅車,陀螺)
            elif sub_num == 69: cat_id = 'cat006'  # 生活小配件
            elif sub_num == 70: cat_id = 'cat002'  # 體育運動教學
            elif sub_num == 71: cat_id = 'cat004'  # ASMR音效
            elif sub_num == 72: cat_id = 'cat002'  # 唱歌教學
            elif sub_num == 73: cat_id = 'cat002'  # 攝影教學
            elif sub_num == 74: cat_id = 'cat007'  # 簡單醫美
            elif sub_num == 75: cat_id = 'cat004'  # 空間/打卡場地
            elif sub_num == 76: cat_id = 'cat003'  # Roblox Studio 遊戲製作
            elif sub_num == 77: cat_id = 'cat002'  # 程式編程教學
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
                'tags': ' | '.join(x for x in [cr['district'] or '', (cr['sport_tag'] if 'sport_tag' in cr.keys() else '') or ''] if x),
                'district_confirmed': bool(cr['district_confirmed']),
                'status': 'approved',
                'track': trk,
                'direction': trk,
                'author_name': cr['author_name'] or '',
                'view_count': cr['view_count'] or 0,
                'duration_sec': cr['duration_sec'] or 0,
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
            elif sub_num == 62: cat_id = 'cat002'  # 音響設備及教學
            elif sub_num == 63: cat_id = 'cat001'  # 汽車維修及裝置
            elif sub_num == 64: cat_id = 'cat005'  # 燒賣腸粉關注組
            elif sub_num == 65: cat_id = 'cat002'  # 身心靈提升
            elif sub_num == 66: cat_id = 'cat003'  # 手錶設計及維修
            elif sub_num == 67: cat_id = 'cat003'  # 動漫及動畫
            elif sub_num == 68: cat_id = 'cat008'  # 玩具(四驅車,陀螺)
            elif sub_num == 69: cat_id = 'cat006'  # 生活小配件
            elif sub_num == 70: cat_id = 'cat002'  # 體育運動教學
            elif sub_num == 71: cat_id = 'cat004'  # ASMR音效
            elif sub_num == 72: cat_id = 'cat002'  # 唱歌教學
            elif sub_num == 73: cat_id = 'cat002'  # 攝影教學
            elif sub_num == 74: cat_id = 'cat007'  # 簡單醫美
            elif sub_num == 75: cat_id = 'cat004'  # 空間/打卡場地
            elif sub_num == 76: cat_id = 'cat003'  # Roblox Studio 遊戲製作
            elif sub_num == 77: cat_id = 'cat002'  # 程式編程教學
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
                    'tags': ' | '.join(x for x in [cr['district'] or '', (cr['sport_tag'] if 'sport_tag' in cr.keys() else '') or ''] if x),
                    'district_confirmed': bool(cr['district_confirmed']),
                    'status': 'approved',
                    'track': trk,
                    'direction': trk,
                    'author_name': cr['author_name'] or '',
                    'view_count': cr['view_count'] or 0,
                    'duration_sec': cr['duration_sec'] or 0,
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
                  and (district in (v.get('tags') or '')
                       or district in (v.get('title_zh') or '')
                       or district in (v.get('description_zh') or ''))]
    # Ordering (user directive): USER-UPLOADED content first (videos.csv — includes IG
    # submissions), newest first by submitted date; then crawled videos by publish
    # recency (newest first via relative published_at). So a freshly uploaded IG reel
    # shows at the very front of its sub-category, not buried after all crawled rows.
    curated = [v for v in result if not str(v.get('id', '')).startswith('cv_')]
    crawled = [v for v in result if str(v.get('id', '')).startswith('cv_')]
    curated.sort(key=lambda v: str(v.get('submitted_date', '')), reverse=True)
    crawled.sort(key=lambda v: _published_ago_days(str(v.get('submitted_date', ''))))
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
                elif sub_num == 62: cat_id = 'cat002'
                elif sub_num == 63: cat_id = 'cat001'
                elif sub_num == 64: cat_id = 'cat005'
                elif sub_num == 65: cat_id = 'cat002'  # 身心靈提升
                elif sub_num == 66: cat_id = 'cat003'  # 手錶設計及維修
                elif sub_num == 67: cat_id = 'cat003'  # 動漫及動畫
                elif sub_num == 68: cat_id = 'cat008'  # 玩具(四驅車,陀螺)
                elif sub_num == 69: cat_id = 'cat006'  # 生活小配件
                elif sub_num == 70: cat_id = 'cat002'  # 體育運動教學
                elif sub_num == 71: cat_id = 'cat004'  # ASMR音效
                elif sub_num == 72: cat_id = 'cat002'  # 唱歌教學
                elif sub_num == 73: cat_id = 'cat002'  # 攝影教學
                elif sub_num == 74: cat_id = 'cat007'  # 簡單醫美
                elif sub_num == 75: cat_id = 'cat004'  # 空間/打卡場地
                elif sub_num == 76: cat_id = 'cat003'  # Roblox Studio 遊戲製作
                elif sub_num == 77: cat_id = 'cat002'  # 程式編程教學
                else: cat_id = 'cat001'
                trk = 'fun' if cat_id in ('cat003','cat004','cat005','cat007') else 'learning'
                return {
                    'id': video_id, 'subcategory_id': sc, 'category_id': cat_id,
                    'platform': r['platform'], 'platform_id': r['platform_id'],
                    'title_zh': r['title'] or '', 'title_en': '',
                    'description_zh': r['description'] or '', 'description_en': '',
                    'thumbnail_url': r['thumbnail_url'] or '',
                    'aspect_ratio': '16:9', 'tags': ' | '.join(x for x in [r['district'] or '', (r['sport_tag'] if 'sport_tag' in r.keys() else '') or ''] if x),
                    'district_confirmed': bool(r['district_confirmed']),
                    'status': 'approved', 'track': trk, 'direction': trk,
                    'author_name': r['author_name'] or '',
                    'view_count': r['view_count'] or 0,
                    'duration_sec': r['duration_sec'] or 0,
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
            if n['id'] == news_id and n.get('status') == 'published' and n.get('region', 'hk') != 'foreign':
                return n
        return None
    result = [n for n in news_list if n['status'] == 'published' and n.get('region', 'hk') != 'foreign']
    result.sort(key=lambda n: n.get('date', ''), reverse=True)
    return result


def get_lifetips(tip_id=None):
    rows = read_csv('lifetips.csv')
    for r in rows:
        vid = extract_youtube_id(str(r.get('content_zh', '') or '') + str(r.get('image_url', '') or ''))
        r['video_id'] = vid if vid else ''
        r['video_url'] = f"https://www.youtube.com/watch?v={vid}" if vid else ''
    if tip_id:
        for r in rows:
            if r['id'] == tip_id and r.get('status') == 'published' and r.get('region', 'hk') != 'foreign':
                return r
        return None
    result = [r for r in rows if r.get('status') == 'published' and r.get('region', 'hk') != 'foreign']
    result.sort(key=lambda r: r.get('date', ''), reverse=True)
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

    def add(path, priority=0.5, changefreq='weekly', lastmod=None, video=None):
        entry = {'loc': base + path, 'priority': priority,
                 'changefreq': changefreq, 'lastmod': lastmod, 'video': video}
        urls.append(entry)

    def iso_date(s):
        """Normalize a date string to YYYY-MM-DD if it looks like a date."""
        if not s:
            return None
        m = re.match(r'(\d{4})-(\d{2})-(\d{2})', str(s))
        return m.group(0) if m else None

    def video_meta(v, platform_key='platform', id_key='platform_id',
                   title_key='title_zh', desc_key='description_zh',
                   thumb_key='thumbnail_url', **kw):
        """Build video:video extension dict when the platform has a player URL."""
        plat = v.get(platform_key, '')
        pid = v.get(id_key, '')
        if plat != 'youtube' or not pid:
            return None
        player = f'https://www.youtube.com/embed/{pid}'
        return {
            'thumbnail_loc': v.get(thumb_key, ''),
            'title': (v.get(title_key, '') or '')[:100],
            'description': (v.get(desc_key, '') or '')[:2000],
            'player_loc': player,
        }

    # Static pages
    add('/', priority=1.0, changefreq='daily')
    add('/about', priority=0.4)
    add('/news', priority=0.8, changefreq='daily')
    add('/life-tips', priority=0.8, changefreq='daily')
    add('/track/fun', priority=0.6)
    add('/track/learning', priority=0.6)

    # 18-district GEO landing pages
    for dslug in geo.DISTRICT_SLUGS:
        add(f'/location/{dslug}', priority=0.7, changefreq='weekly')

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
        rows = db.execute("SELECT id, platform, platform_id, title, description, thumbnail_url, updated_at FROM crawled_videos WHERE district_confirmed=1 LIMIT 2000").fetchall()
        for r in rows:
            video_ids.add('cv_' + str(r['id']))
            add(f"/video/cv_{r['id']}", priority=0.4,
                lastmod=iso_date(r['updated_at']),
                video=video_meta(dict(r), platform_key='platform',
                                 id_key='platform_id', title_key='title',
                                 desc_key='description'))
        db.close()
    except Exception:
        pass

    # Manually approved videos (skip cv_* — already added from crawled_videos above)
    for v in get_videos(limit=10000):
        vid = v.get('id')
        if not vid or v.get('status') != 'approved':
            continue
        if str(vid).startswith('cv_') and vid in video_ids:
            continue
        add(f'/video/{vid}', priority=0.4,
            lastmod=iso_date(v.get('submitted_date')),
            video=video_meta(v))

    # News articles
    news_list = get_news() or []
    for n in news_list:
        if n.get('id') and n.get('status') == 'published':
            add(f'/news/{n["id"]}', priority=0.7, changefreq='monthly',
                lastmod=iso_date(n.get('date')))

    # Life-tips articles
    tips = get_lifetips() or []
    for t in tips:
        if t.get('id') and t.get('status') == 'published':
            add(f'/life-tips/{t["id"]}', priority=0.6, changefreq='monthly',
                lastmod=iso_date(t.get('date')))

    # Build XML
    urlset = Element('urlset')
    urlset.set('xmlns', 'http://www.sitemaps.org/schemas/sitemap/0.9')
    urlset.set('xmlns:video', 'http://www.google.com/schemas/sitemap-video/1.1')
    for e in urls:
        u = SubElement(urlset, 'url')
        SubElement(u, 'loc').text = e['loc']
        if e['lastmod']:
            SubElement(u, 'lastmod').text = e['lastmod']
        SubElement(u, 'changefreq').text = e['changefreq']
        SubElement(u, 'priority').text = str(e['priority'])
        if e['video']:
            v = SubElement(u, 'video:video')
            thumb = e['video'].get('thumbnail_loc') or ''
            if thumb:
                SubElement(v, 'video:thumbnail_loc').text = thumb
            SubElement(v, 'video:title').text = e['video']['title']
            SubElement(v, 'video:description').text = e['video']['description']
            SubElement(v, 'video:player_loc').text = e['video']['player_loc']
    xml_str = minidom.parseString(tostring(urlset)).toprettyxml(indent='  ')
    return Response(xml_str, mimetype='application/xml')


@app.route('/' + INDEXNOW_KEY + '.txt')
def indexnow_key():
    """IndexNow host-verification key file (must live at /{key}.txt)."""
    return Response(INDEXNOW_KEY + '\n', mimetype='text/plain')


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
    # cover /p/, /reel/, /reels/ (new share format), /share/ short codes, and
    # any trailing /path/?query so a full shared link always yields the code.
    m = re.search(r'instagram\.com/(?:p|reel|reels|share)/([a-zA-Z0-9_-]+)', url)
    if m:
        return m.group(1)
    # fallback: last non-empty path segment (strips / and ?query)
    seg = url.strip().rstrip('/').split('/')[-1].split('?')[0]
    return seg

def extract_tiktok_id(url):
    if not url:
        return ''
    match = re.search(r'tiktok\.com/@[\w.-]+/video/(\d+)', url)
    return match.group(1) if match else url.strip().split('/')[-1].split('?')[0]


def extract_douyin_id(url):
    """Extract a Douyin video ID from douyin.com / iesdouyin / v.douyin links.
    Falls back to the URL last segment (stripped of query + trailing slash)."""
    if not url:
        return ''
    url = url.strip()
    m = re.search(r'douyin\.com/(?:video|note)/([\w-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'iesdouyin\.com/share/(?:video|note)/([\w-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'v\.douyin\.com/([\w-]+)', url)
    if m:
        return m.group(1)
    return url.split('/')[-1].split('?')[0]


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


def extract_threads_id(url):
    """Extract the full @user/post/ID path from a Threads URL.

    Threads embeds require the username folder (@user/post/ID), unlike IG/TikTok.
    We return the path itself so it can be plugged straight into the {id} slot of
    the embed/watch base (https://www.threads.net/{id}).
    Examples:
      https://www.threads.net/@foo/post/AbC123        -> @foo/post/AbC123
      https://www.threads.net/@foo/post/AbC123/embed  -> @foo/post/AbC123
      https://www.threads.net/t/AbC123                -> t/AbC123
      https://www.threads.com/share/BAQF5WMX1X/       -> BAQF5WMX1X  (trailing slash OK)
    """
    if not url:
        return ''
    m = re.search(r'threads\.(?:net|com)/(@[\w.]+/post/[\w.-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'threads\.(?:net|com)/(t/[\w.-]+)', url)
    if m:
        return m.group(1)
    m = re.search(r'threads\.(?:net|com)/share/([\w.-]+)', url)
    if m:
        return m.group(1)
    # last path segment, robust to trailing slash / query
    return url.rstrip('/').split('/')[-1].split('?')[0]


def get_platform_thumb(platform, platform_id, api_url=''):
    """Get thumbnail URL for any platform."""
    if platform == 'youtube':
        return f"https://img.youtube.com/vi/{platform_id}/hqdefault.jpg"
    elif platform == 'instagram':
        # Served through our own /cover proxy: Instagram's /media/ URLs are
        # hotlink-blocked in browsers (login wall) and CDN signatures expire.
        return f"https://thingerz.com/cover/instagram/{platform_id}"
    elif platform == 'threads':
        # Threads has no server-side cover endpoint (embed is JS + signed URLs).
        # Cover is captured to data/covers/threads_<postid>.jpg by the local
        # Playwright script (thingerz-marketing/scripts/grab_threads_covers.py)
        # and served same-origin here. Key = the Threads post/short-code ID
        # (last path segment), NOT the full @user/post/… path.
        tid = platform_id.rstrip('/').split('/')[-1].split('?')[0]
        tid = re.sub(r'[^A-Za-z0-9_.-]', '_', tid) or 'x'
        return f"https://thingerz.com/cover/threads/{tid}"
    elif platform == 'bilibili':
        return api_url or f"https://picsum.photos/seed/bili_{platform_id}/400/225"
    elif platform == 'xiaohongshu':
        return api_url or f"https://picsum.photos/seed/xhs_{platform_id}/300/400"
    else:
        return api_url or f"https://picsum.photos/seed/{platform_id}/400/711"


def _ig_cover_bytes(platform_id):
    """Fetch an Instagram cover WITHOUT login, best-effort:
    1. p/<id>/media/?size=m (post/reel poster = IG's first-frame thumb)
    2. embed page display_url (full-res media)
    3. embed page profile_pic_url (author avatar — last-resort cover)
    Returns image bytes or None."""
    ua = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                        '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'}
    try:
        req = urllib.request.Request(f'https://www.instagram.com/p/{platform_id}/media/?size=m', headers=ua)
        data = urllib.request.urlopen(req, timeout=15).read()
        if data[:3] == b'\xff\xd8\xff':
            return data
    except Exception:
        pass
    try:
        html = urllib.request.urlopen(
            urllib.request.Request(f'https://www.instagram.com/p/{platform_id}/embed/captioned/', headers=ua),
            timeout=15).read().decode('utf-8', 'ignore').replace('\\', '')
        m = re.search(r'"display_url":"(https:[^"]+)"', html) or \
            re.search(r'"profile_pic_url":"(https:[^"]+)"', html)
        if m:
            url = m.group(1)
            data = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=15).read()
            if data[:3] == b'\xff\xd8\xff':
                return data
    except Exception:
        pass
    return None


@app.route('/cover/instagram/<platform_id>')
def ig_cover_proxy(platform_id):
    """Stable same-origin cover for IG posts/reels. Fetches once from Instagram
    (no login), caches bytes locally, then serves forever — immune to
    hotlink-blocking and CDN signature expiry. Re-caches lazily after a
    redeploy wipes the ephemeral disk."""
    safe = re.sub(r'[^a-zA-Z0-9_-]', '', platform_id) or 'x'
    cache_dir = os.path.join(DATA_DIR, 'covers')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        pass
    path = os.path.join(cache_dir, f'{safe}.jpg')
    if not os.path.exists(path):
        data = _ig_cover_bytes(safe)
        if not data:
            return Response('', 404)
        try:
            with open(path, 'wb') as f:
                f.write(data)
        except OSError:
            return Response(data, mimetype='image/jpeg')
    return send_file(path, mimetype='image/jpeg', max_age=86400)


@app.route('/cover/threads/<key>')
def threads_cover_proxy(key):
    """Serve a Threads cover. Tries a locally-captured file first
    (data/covers/threads_<key>.jpg, written by grab_threads_covers.py); if
    missing, lazily fetches the post's server-side og:image (works for video
    poster frames, no browser) and caches it. On total failure, redirects to a
    stable picsum placeholder so cards NEVER render a broken-image icon.
    Re-caches lazily after a redeploy wipes the ephemeral disk."""
    safe = re.sub(r'[^A-Za-z0-9_.-]', '', key) or 'x'
    cache_dir = os.path.join(DATA_DIR, 'covers')
    try:
        os.makedirs(cache_dir, exist_ok=True)
    except OSError:
        pass
    path = os.path.join(cache_dir, f'threads_{safe}.jpg')
    if not os.path.exists(path):
        data = _threads_cover_bytes(safe)
        if not data:
            # placeholder so the card never shows a broken-image icon
            return redirect(f'https://picsum.photos/seed/th_{safe}/400/300')
        try:
            with open(path, 'wb') as f:
                f.write(data)
        except OSError:
            return Response(data, mimetype='image/jpeg')
    return send_file(path, mimetype='image/jpeg', max_age=86400)


def _threads_cover_bytes(key):
    """Fetch a Threads post cover WITHOUT login or a browser, best-effort.
    Threads serves the canonical post page (note: NO trailing slash — one
    returns a JS shell without og:image) containing the CDN og:image meta
    (the first frame for videos). We resolve it and fetch the (signed, but
    currently valid) CDN bytes. Returns JPEG bytes or None."""
    ua = {'User-Agent': 'Mozilla/5.0'}
    key = (key or '').rstrip('/')
    if not key:
        return None
    cands = []
    if '/' in key:
        cands.append(f'https://www.threads.net/{key}')
    cands.append(f'https://www.threads.net/share/{key}')
    for url in cands:
        try:
            html = urllib.request.urlopen(urllib.request.Request(url, headers=ua), timeout=15) \
                       .read().decode('utf-8', 'ignore')
        except Exception:
            continue
        m = re.search(r'property="og:image"[^>]*content="(https:[^"]+)"', html) or \
            re.search(r'content="(https:[^"]+)"[^>]*property="og:image"', html)
        if not m:
            continue
        img_url = m.group(1).replace('&amp;', '&')
        try:
            data = urllib.request.urlopen(urllib.request.Request(
                img_url, headers={'User-Agent': ua['User-Agent'],
                                  'Referer': 'https://www.threads.net/'}), timeout=20).read()
        except Exception:
            continue
        if data[:3] == b'\xff\xd8\xff':
            return data
    return None


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
    elif sub_num == 62: return 'cat002'   # 音響設備及教學
    elif sub_num == 63: return 'cat001'   # 汽車維修及裝置
    elif sub_num == 64: return 'cat005'   # 燒賣腸粉關注組
    elif sub_num == 65: return 'cat002'   # 身心靈提升
    elif sub_num == 66: return 'cat003'   # 手錶設計及維修
    elif sub_num == 67: return 'cat003'   # 動漫及動畫
    elif sub_num == 68: return 'cat008'   # 玩具(四驅車,陀螺)
    elif sub_num == 69: return 'cat006'   # 生活小配件
    elif sub_num == 70: return 'cat002'  # 體育運動教學
    elif sub_num == 71: return 'cat004'  # ASMR音效
    elif sub_num == 72: return 'cat002'  # 唱歌教學
    elif sub_num == 73: return 'cat002'  # 攝影教學
    elif sub_num == 74: return 'cat007'  # 簡單醫美
    elif sub_num == 75: return 'cat004'  # 空間/打卡場地
    elif sub_num == 76: return 'cat003'  # Roblox Studio 遊戲製作
    elif sub_num == 77: return 'cat002'  # 程式編程教學
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
            'tags': ' | '.join(x for x in [cr['district'] or '', (cr['sport_tag'] if 'sport_tag' in cr.keys() else '') or ''] if x), 'district_confirmed': bool(cr['district_confirmed']),
            'status': 'approved', 'track': trk, 'direction': trk,
            'author_name': cr['author_name'] or '',
            'view_count': cr['view_count'] or 0,
            'duration_sec': cr['duration_sec'] or 0,
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
    latest_lifetips = get_lifetips()[:3]
    return render_template('index.html', fun_categories=fun_categories, learning_categories=learning_categories, featured_videos=featured_videos, latest_news=latest_news, latest_lifetips=latest_lifetips, platform_config=PLATFORM_CONFIG)


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
    return jsonify({'version': '1.2', 'api_key_set': bool(API_KEY), 'db_ok': True})


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
        # Legacy numeric ids (cat001..008) -> 301 to canonical slug URL
        legacy = get_category(slug)
        if legacy and legacy.get('name_slug'):
            return redirect(url_for('category_page', slug=legacy['name_slug']), code=301)
        abort(404)
    subcategories = get_subcategories(category['category_id'])
    videos = get_videos(category_id=category['category_id'])
    district = request.args.get('district', '').strip()
    if district:
        videos = [v for v in videos if v.get('district_confirmed', True) and (district in (v.get('tags') or '') or district in (v.get('title_zh') or '') or district in (v.get('description_zh') or ''))]
    return render_template('category.html', category=category, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG, selected_district=district)


@app.route('/subcategory/<subcategory_id>')
def subcategory_page(subcategory_id):
    # Merged-out subs: s007 餐飲與酒類 folded into s031 飲食與品味 (2026-08-21).
    # 301 so old bookmarks + search-indexed URLs land on the replacement page
    # instead of 404 (SEO-friendly, keeps link equity).
    MERGED_SUBS = {'s007': 's031'}
    if subcategory_id in MERGED_SUBS:
        return redirect(url_for('subcategory_page', subcategory_id=MERGED_SUBS[subcategory_id]), code=301)
    sub = get_subcategory(subcategory_id)
    if not sub:
        abort(404)
    category = get_category(sub['category_id'])
    subcategories = get_subcategories(sub['category_id'])
    videos = get_videos(subcategory_id=subcategory_id)
    district = request.args.get('district', '').strip()
    if district:
        videos = [v for v in videos if v.get('district_confirmed', True) and (district in (v.get('tags') or '') or district in (v.get('title_zh') or '') or district in (v.get('description_zh') or ''))]
    return render_template('subcategory.html', category=category, sub=sub, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG, selected_district=district)


@app.route('/video/<video_id>')
def video_detail(video_id):
    video = get_video(video_id)
    if not video:
        abort(404)
    increment_view(video_id)
    category = get_category(video['category_id'])
    sub = get_subcategory(video['subcategory_id'])
    comments = get_comments(video_id)
    related = get_related_videos(video)
    platform = PLATFORM_CONFIG.get(video.get('platform', 'youtube'), PLATFORM_CONFIG['youtube'])
    views = get_view_counts().get(video_id, 0)
    # derive the primary district(s) this video is tagged with (for 探索同區 CTA)
    v_district = None
    _tok = set()
    for raw in (video.get('tags') or '').split('|'):
        for t in raw.split('、'):
            if t.strip():
                _tok.add(t.strip())
    for d in getattr(geo, 'DISTRICTS', []) or []:
        if d.get('name_zh') in _tok:
            v_district = d
            break
    return render_template('video_detail.html', video=video, category=category, sub=sub, comments=comments, related_videos=related, platform=platform, platform_config=PLATFORM_CONFIG, views=views, video_district=v_district)


@app.route('/search')
def search():
    q = request.args.get('q', '').strip()
    if not q:
        return redirect(url_for('index'))
    all_videos = get_videos()
    results = [v for v in all_videos if q.lower() in (v.get('title_zh') or '').lower() or q.lower() in (v.get('title_en') or '').lower() or q.lower() in (v.get('tags') or '').lower() or q.lower() in (v.get('description_zh') or '').lower()]
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
        district = '、'.join(x for x in request.form.getlist('district') if x)  # 可選多個 18區（、隔開）
        block_reason = None
        if contains_blocked(title_zh) or contains_blocked(desc_zh):
            block_reason = "含有不當用語"
        elif screening:
            block_reason = screening.screen_upload(title_zh, desc_zh)
        if block_reason:
            return render_template('submit.html', categories=categories, districts=HK_DISTRICTS,
                                   platform_config=PLATFORM_CONFIG, success=False, blocked=True,
                                   block_reason=block_reason)
        # Resolve the platform id up-front so we can dedupe (and so the rate cap
        # isn't consumed by a repeat submission of an already-listed video).
        platform = request.form.get('platform', 'youtube')
        url = request.form.get('platform_url', '')
        if platform == 'youtube':
            platform_id = extract_youtube_id(url)
        elif platform == 'instagram':
            platform_id = extract_instagram_id(url)
        elif platform == 'threads':
            platform_id = extract_threads_id(url)
        elif platform == 'tiktok':
            platform_id = extract_tiktok_id(url)
        elif platform == 'douyin':
            platform_id = extract_douyin_id(url)
        elif platform == 'xiaohongshu':
            platform_id = extract_xiaohongshu_id(url)
        elif platform == 'bilibili':
            platform_id = extract_bilibili_id(url)
        else:
            platform_id = url.split('/')[-1].split('?')[0]
        if not platform_id:
            return render_template('submit.html', categories=categories, districts=HK_DISTRICTS,
                                   platform_config=PLATFORM_CONFIG, invalid=True, platform=platform)
        # Dedupe: same platform+id already in videos.csv → don't create a second
        # v-row, tell the submitter it's already listed and link the existing page.
        if platform_id:
            existing = [v for v in read_csv('videos.csv')
                        if v.get('platform') == platform and v.get('platform_id') == platform_id]
            if existing:
                vid = existing[0]
                dup_link = url_for('video_detail', video_id=vid.get('id', ''))
                return render_template('submit.html', categories=categories, districts=HK_DISTRICTS,
                                       platform_config=PLATFORM_CONFIG, success=False,
                                       already_exists=True, dup_link=dup_link, dup_title=vid.get('title_zh', ''))
        # Per-IP daily upload cap: reject without processing once an IP hits the
        # daily ceiling (durable SQLite counter, survives restarts).
        up_day = datetime.now().strftime('%Y-%m-%d')
        up_ip = _ip_hash(_client_ip())
        if _upload_count(up_ip, up_day) >= MAX_UPLOADS_PER_DAY:
            return render_template('submit.html', categories=categories, districts=HK_DISTRICTS,
                                   platform_config=PLATFORM_CONFIG, success=False, rate_limited=True)
        _inc_upload(up_ip, up_day)
        # Category verification: if the submitter's chosen sub-category clearly
        # does NOT match the content (confident match to a DIFFERENT category),
        # don't auto-post it in a wrong category — route to the admin review
        # queue so it can be moved to the right category.
        needs_review = False
        if screening and subcategory_id:
            matched = screening.match_subcategory(title_zh, desc_zh,
                                                  request.form.get('submitter_name', ''))
            if matched and matched != subcategory_id:
                needs_review = True
        if needs_review:
            pending_sub = {
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
                'status': 'pending',
                'submitted_date': datetime.now().strftime('%Y-%m-%d'),
                'district': district
            }
            pending_fieldnames = ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date', 'district']
            append_csv('submissions.csv', pending_sub, pending_fieldnames)
            log_upload({'event': 'submit_pending', 'id': pending_sub['id'],
                        'platform': pending_sub['platform'],
                        'platform_url': pending_sub['platform_url'],
                        'title_zh': title_zh, 'description_zh': desc_zh,
                        'subcategory_id': subcategory_id,
                        'district': district,
                        'submitter_name': pending_sub['submitter_name'],
                        'status': 'pending'})
            return render_template('submit.html', categories=categories, districts=HK_DISTRICTS,
                                   platform_config=PLATFORM_CONFIG, success=False, pending_review=True)
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
        # Auto-add to videos (platform/platform_id already resolved & deduped above)
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
            'submitted_date': datetime.now().strftime('%Y-%m-%d'),
            'submitter_name': submission['submitter_name']
        })
        vfieldnames = ['id','subcategory_id','category_id','platform','platform_id','title_zh','title_en','description_zh','description_en','thumbnail_url','aspect_ratio','tags','status','track','direction','submitted_date','submitter_name']
        write_csv('videos.csv', vids, vfieldnames)
        log_upload({'event': 'submit_approved', 'id': vids[-1]['id'],
                    'platform': platform, 'platform_url': url,
                    'platform_id': platform_id,
                    'title_zh': title_zh, 'description_zh': desc_zh,
                    'subcategory_id': subcategory_id, 'category_id': category_id,
                    'district': district,
                    'submitter_name': submission['submitter_name'],
                    'status': 'approved'})
        return render_template('submit.html', categories=categories, districts=HK_DISTRICTS, platform_config=PLATFORM_CONFIG, success=True,
                               new_video_id=vids[-1]['id'],
                               # Full absolute URL (not just /video/cv_xxx) so the
                               # WhatsApp/Telegram/IG/Threads share buttons carry a
                               # clickable link instead of a bare cv id.
                               new_video_url='https://' + CANONICAL_HOST + url_for('video_detail', video_id=vids[-1]['id']),
                               new_video_title=title_zh)
    return render_template('submit.html', categories=categories, districts=HK_DISTRICTS, platform_config=PLATFORM_CONFIG, success=False, blocked=False)


@app.route('/news')
def news_list():
    items = get_news()
    district = (request.args.get('district', '') or '').strip()
    if district:
        items = [n for n in items if n.get('district', '') == district]
    return render_template('news_list.html', news_items=items,
                           districts=geo.DISTRICTS, selected_district=district)


@app.route('/news/<news_id>')
def news_detail(news_id):
    item = get_news(news_id)
    if not item:
        return redirect(url_for('news_list'))
    return render_template('news_detail.html', news_item=item, all_news=get_news())


@app.route('/life-tips')
def lifetips_list():
    return render_template('lifetips_list.html', tip_items=get_lifetips())


@app.route('/life-tips/<tip_id>')
def lifetips_detail(tip_id):
    it = get_lifetips(tip_id)
    if not it:
        return redirect(url_for('lifetips_list'))
    return render_template('lifetips_detail.html', tip=it, all_tips=get_lifetips())


@app.route('/location/<slug>')
def location_page(slug):
    """GEO district landing pages (18 districts). Each page: H1/H2, 2-sentence
    intro, conversational FAQ, district-confirmed videos and Service JSON-LD.
    Optional ?svc=<subcategory_id|teaching> narrows the 區內影片 list to
    teaching/service sub-categories (music, magic, sports coaching, ...) so
    users can find a tutor/coach per district without a new top-level category."""
    TEACHING_SUBS = {
        's009', 's010', 's011', 's012', 's013', 's014', 's023', 's024', 's026',
        's029', 's030', 's058', 's059', 's062', 's070',
    }
    d = geo.DISTRICTS_BY_SLUG.get(slug)
    if not d:
        abort(404)
    vids = get_videos(district=d['name_zh']) or []
    # broaden: any curated video whose title/desc/tags mention the district name
    district = d['name_zh']
    extra = [v for v in get_videos(limit=300)
             if v.get('district_confirmed', True)
             and district in (v.get('tags', '') or '')
             and v not in vids]
    seen = {v['id'] for v in vids}
    for v in extra:
        if v['id'] not in seen:
            vids.append(v)
    svc = (request.args.get('svc', '') or '').strip()
    # chips: teaching/service sub-categories that actually have content in this district
    svc_chips = []
    sub_names = {s['id']: s['name_zh'] for s in get_subcategories()}
    have = {v.get('subcategory_id') for v in vids}
    for sid in sorted(TEACHING_SUBS):
        if sid in have:
            svc_chips.append({'id': sid, 'name_zh': sub_names.get(sid, sid)})
    if svc == 'teaching':
        vids = [v for v in vids if (v.get('subcategory_id') or '') in TEACHING_SUBS]
    elif svc.startswith('s') and len(svc) == 4 and svc[1:].isdigit():
        vids = [v for v in vids if (v.get('subcategory_id') or '') == svc]
    # 本區熱門分類: sub-categories actually present in this district's videos (top 6)
    _cnt = Counter((v.get('subcategory_id') or '') for v in vids)
    hot_subs = [{'id': sid, 'name_zh': sub_names.get(sid, sid), 'n': n}
                for sid, n in _cnt.most_common(6) if sid]
    # 本區精選: top 3 by view count, computed BEFORE svc filtering so it's stable
    featured = sorted(vids, key=lambda v: v.get('view_count') or 0, reverse=True)[:3]
    # 本區好去處: district-tagged 好去處 news (already published + non-foreign + date-sorted)
    district_news = [n for n in (get_news() or []) if n.get('district') == d['name_zh']][:3]
    return render_template('location.html', district=d, videos=vids,
                           all_districts=[x for x in geo.DISTRICTS],
                           svc_chips=svc_chips, selected_svc=svc,
                           hot_subs=hot_subs, featured_videos=featured,
                           district_news=district_news)


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


@app.route('/api/video-preview', methods=['GET'])
def api_video_preview():
    """Lightweight submit-page helper: given a platform + URL, resolve the
    platform id and fetch a thumbnail so the submit wizard can show a live
    preview. Read-only, no DB writes. Silently returns ok=False on failure so
    the front-end just prompts the user to continue with the correct link."""
    url = (request.args.get('url') or '').strip()
    platform = (request.args.get('platform') or 'youtube').strip()
    if not url:
        return jsonify({'ok': False, 'error': 'missing url'}), 400
    if platform == 'youtube':
        pid = extract_youtube_id(url)
    elif platform == 'instagram':
        pid = extract_instagram_id(url)
    elif platform == 'threads':
        pid = extract_threads_id(url)
    elif platform == 'tiktok':
        pid = extract_tiktok_id(url)
    elif platform == 'douyin':
        pid = extract_douyin_id(url)
    elif platform == 'xiaohongshu':
        pid = extract_xiaohongshu_id(url)
    elif platform == 'bilibili':
        pid = extract_bilibili_id(url)
    else:
        pid = url.rstrip('/').split('/')[-1].split('?')[0]
    if not pid:
        return jsonify({'ok': False, 'error': 'unrecognized_link'}), 200
    thumb = ''
    try:
        thumb = get_platform_thumb(platform, pid) or ''
    except Exception:
        thumb = ''
    # Best-effort title via YouTube oEmbed (auto-filled into the 中文標題 field by the
    # wizard so the submitter edits instead of retypes). Non-YouTube / fetch failure -> ''.
    title = ''
    if platform == 'youtube' and pid:
        try:
            o = json.load(urllib.request.urlopen(
                'https://www.youtube.com/oembed?url=' + urllib.parse.quote(f'https://www.youtube.com/watch?v={pid}') + '&format=json',
                timeout=4))
            title = (o.get('title') or '')[:100]
        except Exception:
            title = ''
    return jsonify({'ok': True, 'platform': platform, 'platform_id': pid,
                    'thumbnail_url': thumb, 'title': title})


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
        ip = _client_ip()
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
            r['count'] = str(int(r.get('count') or 0) + 1)
            r['clicks'] = str(int(r.get('clicks') or 0) + 1)
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
        vc_map[r['video_id']] = {'views': int(r.get('count') or 0), 'clicks': int(r.get('clicks') or 0)}
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
    elif platform == 'threads':
        platform_id = extract_threads_id(platform_id_raw) or platform_id_raw
    elif platform == 'tiktok':
        platform_id = extract_tiktok_id(platform_id_raw) or platform_id_raw
    elif platform == 'douyin':
        platform_id = extract_douyin_id(platform_id_raw) or platform_id_raw
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
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date', 'submitter_name']
    write_csv('videos.csv', vids, fieldnames)
    log_upload({'event': 'admin_add', 'id': vid['id'],
                'platform': platform, 'platform_id': platform_id,
                'title_zh': vid['title_zh'], 'subcategory_id': vid['subcategory_id'],
                'category_id': vid['category_id'], 'status': vid['status']})
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
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date', 'submitter_name']
    write_csv('videos.csv', vids, fieldnames)
    return redirect(url_for('admin_videos'))


@app.route('/admin/videos/delete/<video_id>', methods=['POST'])
@admin_required
def admin_video_delete(video_id):
    vids = [v for v in read_csv('videos.csv') if v['id'] != video_id]
    fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date', 'submitter_name']
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
            # allow the reviewer to correct the category at approval time
            new_sub = (request.form.get('subcategory_id') or '').strip()
            if new_sub and new_sub != s.get('subcategory_id'):
                s['subcategory_id'] = new_sub
                sb = get_subcategory(new_sub)
                s['category_id'] = sb['category_id'] if sb else s.get('category_id', '')
            break
    write_csv('submissions.csv', subs, ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date', 'district'])
    if submission:
        platform = submission.get('platform', 'youtube')
        url = submission.get('platform_url', '')
        if platform == 'youtube':
            platform_id = extract_youtube_id(url)
        elif platform == 'instagram':
            platform_id = extract_instagram_id(url)
        elif platform == 'threads':
            platform_id = extract_threads_id(url)
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
            'submitted_date': datetime.now().strftime('%Y-%m-%d'),
            'submitter_name': submission.get('submitter_name', '')
        })
        fieldnames = ['id', 'subcategory_id', 'category_id', 'platform', 'platform_id', 'title_zh', 'title_en', 'description_zh', 'description_en', 'thumbnail_url', 'aspect_ratio', 'tags', 'status', 'track', 'direction', 'submitted_date', 'submitter_name']
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
            'district': request.form.get('district', ''),
        })
        write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region', 'district'])
        return redirect(url_for('admin_news'))
    _news_items = read_csv('news.csv')
    _news_items.sort(key=lambda x: (x.get('date', ''), x.get('id', '')), reverse=True)
    return render_template('admin/news.html', news_items=_news_items, districts=geo.DISTRICTS)


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
            n['district'] = request.form.get('district', n.get('district', ''))
            break
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region', 'district'])
    return redirect(url_for('admin_news'))


@app.route('/admin/news/delete/<news_id>', methods=['POST'])
@admin_required
def admin_news_delete(news_id):
    news_list = [n for n in read_csv('news.csv') if n['id'] != news_id]
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region', 'district'])
    return redirect(url_for('admin_news'))


# --- Admin 生活小知識 (life-tips) — mirrors 好去處 (news) admin ---
_LIFETIPS_FIELDNAMES = ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region']


@app.route('/admin/lifetips', methods=['GET', 'POST'])
@admin_required
def admin_lifetips():
    if request.method == 'POST':
        tips = read_csv('lifetips.csv')
        max_num = max(int(t['id'].replace('t', '')) for t in tips) if tips else 0
        tips.append({
            'id': f"t{max_num + 1:03d}",
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
        write_csv('lifetips.csv', tips, _LIFETIPS_FIELDNAMES)
        return redirect(url_for('admin_lifetips'))
    _tip_items = read_csv('lifetips.csv')
    _tip_items.sort(key=lambda x: (x.get('date', ''), x.get('id', '')), reverse=True)
    return render_template('admin/lifetips.html', tip_items=_tip_items)


@app.route('/admin/lifetips/edit/<tip_id>', methods=['POST'])
@admin_required
def admin_lifetips_edit(tip_id):
    tips = read_csv('lifetips.csv')
    for t in tips:
        if t['id'] == tip_id:
            t['title_zh'] = request.form.get('title_zh', t.get('title_zh', ''))
            t['title_en'] = request.form.get('title_en', t.get('title_en', ''))
            t['content_zh'] = request.form.get('content_zh', t.get('content_zh', ''))
            t['content_en'] = request.form.get('content_en', t.get('content_en', ''))
            t['summary_zh'] = request.form.get('summary_zh', t.get('summary_zh', ''))
            t['summary_en'] = request.form.get('summary_en', t.get('summary_en', ''))
            t['date'] = request.form.get('date', t.get('date', ''))
            t['image_url'] = request.form.get('image_url', t.get('image_url', ''))
            t['status'] = request.form.get('status', t.get('status', 'published'))
            t['region'] = request.form.get('region', t.get('region', 'hk'))
            break
    write_csv('lifetips.csv', tips, _LIFETIPS_FIELDNAMES)
    return redirect(url_for('admin_lifetips'))


@app.route('/admin/lifetips/delete/<tip_id>', methods=['POST'])
@admin_required
def admin_lifetips_delete(tip_id):
    tips = [t for t in read_csv('lifetips.csv') if t['id'] != tip_id]
    write_csv('lifetips.csv', tips, _LIFETIPS_FIELDNAMES)
    return redirect(url_for('admin_lifetips'))


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
    # Also capture the append-only uploads log (raw source every upload) so it
    # rides along with the backup dump into the daily git sync.
    UL = os.path.join(DATA_DIR, 'uploads_log.jsonl')
    if os.path.exists(UL):
        try:
            with open(UL, encoding='utf-8') as f:
                all_data['uploads_log.jsonl'] = [json.loads(l) for l in f if l.strip()]
        except Exception:
            all_data['uploads_log.jsonl'] = []
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
        # Only restore real CSV tables. Skipping non-table keys (e.g.
        # uploads_log.jsonl) prevents write_csv -> DELETE FROM <no-table>
        # from crashing mid-restore AND wiping already-restored tables.
        if not filename.endswith('.csv'):
            continue
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
                'district': '',
            })
            existing_titles.add(title)
            fetched += 1
        write_csv('news.csv', existing, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status', 'region', 'district'])
    except Exception as e:
        return f'<p>獲取失敗：{e}</p><a href="{url_for("admin_news")}">返回</a>', 500
    return redirect(url_for('admin_news'))


# ==================== SECURITY HARDENING (CSRF / rate-limit) ====================

CANONICAL_HOST = os.environ.get('CANONICAL_HOST', 'thingerz.com')


@app.before_request
def canonical_host():
    """301 any non-canonical host (e.g. thingerz.onrender.com) to thingerz.com
    so Google/Bing consolidate all signals on one domain."""
    h = (request.host or '').lower()
    if h and h != CANONICAL_HOST and not (h.startswith('localhost') or h.startswith('127.')):
        return redirect('https://' + CANONICAL_HOST + request.full_path, code=301)

_RL_BUCKETS = {}  # rate-limit buckets: key -> [timestamps]


def _rate_ok(key, limit, window_sec):
    now = time.time()
    dq = _RL_BUCKETS.setdefault(key, [])
    while dq and dq[0] < now - window_sec:
        dq.pop(0)
    dq.append(now)
    return len(dq) <= limit


def _client_ip():
    # Respect proxy chain (Render/Cloudflare) — first untrusted hop is the client
    xff = request.headers.get('X-Forwarded-For', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.remote_addr or '?'


# Per-IP DAILY upload cap: one IP may upload at most this many videos per day.
# Durable (SQLite) so it survives Render restarts, unlike the 60s in-memory window.
MAX_UPLOADS_PER_DAY = 20

# Global per-IP request ceiling (ALL methods, ALL endpoints) — defense-in-depth
# against single-source floods / scraping. DELIBERATELY HIGH so legit shared-NAT
# users (one carrier IP, many people) are not caught; only trips on a sustained
# near-flood from one source. Does NOT stop distributed (multi-IP) DDoS — that
# is Cloudflare's job (hide origin IP + L3/L4/7 mitigation). Tunable via env.
GLOBAL_REQ_PER_MIN = int(os.environ.get('GLOBAL_REQ_PER_MIN', '1200'))  # 20 req/sec sustained


def _ip_hash(ip):
    import hashlib
    return hashlib.sha256((ip or '?').encode('utf-8')).hexdigest()[:16]


def _upload_count(ip_hash, day):
    try:
        db = get_db()
        r = db.execute("SELECT cnt FROM upload_limits WHERE ip_hash=? AND day=?",
                       (ip_hash, day)).fetchone()
        db.close()
        return r['cnt'] if r else 0
    except Exception:
        return 0


def _inc_upload(ip_hash, day):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO upload_limits(ip_hash, day, cnt) VALUES(?,?,1) "
            "ON CONFLICT(ip_hash, day) DO UPDATE SET cnt=cnt+1",
            (ip_hash, day))
        db.commit()
        db.close()
    except Exception:
        pass  # a counter failure must never break an upload


def _get_csrf():
    tok = session.get('_csrf')
    if not tok:
        tok = secrets.token_urlsafe(32)
        session['_csrf'] = tok
    return tok


def _csrf_ok(token):
    return bool(token) and secrets.compare_digest(token, str(session.get('_csrf') or ''))


def _rl_label():
    p = request.path
    if p.rstrip('/') == '/submit':
        return 'submit'
    if p.rstrip('/') == '/contact':
        return 'contact'
    if '/comment' in p:
        return 'comment'
    if p == '/api/content':
        return 'api_content'
    return None


@app.before_request
def _security_checks():
    # --- Global per-IP request ceiling (all methods) — defense-in-depth vs
    #     single-source floods / aggressive scraping. High, env-tunable threshold. ---
    gip = _client_ip()
    if not _rate_ok(f'rl:{gip}:global', GLOBAL_REQ_PER_MIN, 60):
        return jsonify({'status': 'error', 'message': 'Too many requests'}), 429

    # --- Rate limiting (per-IP, per-endpoint) — DDoS / spam guard ---
    if request.method == 'POST':
        lab = _rl_label()
        ip = _client_ip()
        if lab == 'api_content':
            if not _rate_ok(f'rl:{ip}:api', 120, 60):
                return jsonify({'status': 'error', 'message': 'Too many requests'}), 429
        elif lab in ('submit', 'contact', 'comment'):
            if not _rate_ok(f'rl:{ip}:{lab}', 10, 60):
                return jsonify({'status': 'error', 'message': 'Too many requests, please slow down'}), 429

    # --- CSRF on all unsafe methods; skip key-authenticated API + login ---
    if request.method in ('POST', 'PUT', 'PATCH', 'DELETE') \
            and request.path not in ('/api/content', '/admin'):
        token = request.form.get('csrf_token') or request.headers.get('X-CSRF-Token', '')
        if not _csrf_ok(token):
            return jsonify({'status': 'error', 'message': 'CSRF validation failed'}), 403


@app.context_processor
def inject_globals():
    return {
        'categories': get_categories(),
        'platform_config': PLATFORM_CONFIG,
        'directions': DIRECTIONS,
        'now': datetime.now(),
        'get_backup_status': get_backup_status,
        'csrf_token': _get_csrf,
        'districts': geo.DISTRICTS,
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
                 published_at, score, updated_at, sport_tag)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                 updated_at,
                 str(item.get('sport_tag', '')).strip()))
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
def add_security_headers(response):
    # Security headers — XSS/clickjacking/sniffing/mixed-content hardening
    response.headers.setdefault('X-Content-Type-Options', 'nosniff')
    response.headers.setdefault('X-Frame-Options', 'DENY')
    response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
    response.headers.setdefault('Permissions-Policy',
                                'camera=(), microphone=(), geolocation=()')
    response.headers.setdefault(
        'Content-Security-Policy',
        "default-src 'self'; script-src 'self' 'unsafe-inline' https://www.googletagmanager.com; "
        "style-src 'self' 'unsafe-inline'; img-src * data: blob:; media-src *; font-src *; "
        "frame-src * blob: data:; connect-src 'self' https://www.googletagmanager.com https://www.google-analytics.com; "
        "frame-ancestors 'none';")
    if request.is_secure:
        response.headers.setdefault('Strict-Transport-Security',
                                    'max-age=31536000; includeSubDomains')
    ct = response.headers.get('Content-Type', '')
    if ct and 'text/html' in ct:
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


@app.errorhandler(500)
def internal_error(e):
    # Generic message — do NOT leak stack traces to clients
    return ('<h1>500 Internal Server Error</h1>'
            '<p>Something went wrong. Please try again later.</p>'), 500


@app.errorhandler(413)
def too_large(e):
    return ('<h1>413 Payload Too Large</h1>'
            '<p>The request is too large.</p>'), 413


@app.errorhandler(403)
def forbidden(e):
    return ('<h1>403 Forbidden</h1>'
            '<p>Request rejected by security checks.</p>'), 403


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