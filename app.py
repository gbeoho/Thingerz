import csv
import os
import re
import uuid
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, jsonify, session

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SECRET_KEY'] = os.urandom(24).hex()
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
os.makedirs(DATA_DIR, exist_ok=True)

ADMIN_PASSWORD = 'Gabriel00!'
FOUL_WORDS = ['fuck', 'shit', 'damn', 'ass', 'bitch', 'dick', 'piss', 'crap', 'bastard', 'slut', 'whore', '屌', '鳩', '柒', '撚', '閪', '屄', '𨳒', '仆街', '冚家鏟', '傻閪', 'on9', 'on99', 'diu', 'pkm', 'hihi', 'clsm', 'cls', 'mlg']

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
}

DIRECTIONS = {
    'fun': {'name_zh': 'Fun 頻道', 'name_en': 'Fun', 'color': 'fun'},
    'learning': {'name_zh': 'Learning 頻道', 'name_en': 'Learning', 'color': 'learning'},
    'business': {'name_zh': '商業配對', 'name_en': 'Business Matching', 'color': 'business'},
    'skills_exchange': {'name_zh': '技能互換', 'name_en': 'Skills Exchange', 'color': 'skills'},
}


def filter_profanity(text):
    result = text
    for word in FOUL_WORDS:
        result = result.replace(word, '*' * len(word))
    return result


def read_csv(filename):
    filepath = os.path.join(DATA_DIR, filename)
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        return list(reader)


def write_csv(filename, rows, fieldnames):
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(filename, row, fieldnames):
    filepath = os.path.join(DATA_DIR, filename)
    file_exists = os.path.exists(filepath)
    with open(filepath, 'a', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)


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


def get_videos(subcategory_id=None, category_id=None, track=None, direction=None, status='approved', limit=None):
    videos = read_csv('videos.csv')
    result = [v for v in videos if v.get('status', '') == status]
    if subcategory_id:
        result = [v for v in result if v['subcategory_id'] == subcategory_id]
    if category_id:
        result = [v for v in result if v['category_id'] == category_id]
    if track:
        result = [v for v in result if v.get('track', '') == track]
    if direction:
        result = [v for v in result if v.get('direction', '') == direction]
    result.sort(key=lambda v: v.get('submitted_date', ''), reverse=True)
    if limit:
        result = result[:limit]
    return result


def get_video(video_id):
    for v in read_csv('videos.csv'):
        if v['id'] == video_id:
            return v
    return None


def get_comments(video_id):
    comments = [c for c in read_csv('comments.csv') if c['video_id'] == video_id and c['status'] == 'approved']
    comments.sort(key=lambda c: c.get('date', ''), reverse=True)
    return comments


def get_news(news_id=None):
    news_list = read_csv('news.csv')
    if news_id:
        for n in news_list:
            if n['id'] == news_id:
                return n
        return None
    return [n for n in news_list if n['status'] == 'published']


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
    vc = read_csv('view_counts.csv')
    return {r['video_id']: int(r.get('count', 0)) for r in vc}


def increment_view(video_id):
    vc = read_csv('view_counts.csv')
    found = False
    for r in vc:
        if r['video_id'] == video_id:
            r['count'] = str(int(r.get('count', 0)) + 1)
            found = True
            break
    if not found:
        vc.append({'video_id': video_id, 'count': '1'})
    write_csv('view_counts.csv', vc, ['video_id', 'count'])


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


def generate_id(prefix):
    return f"{prefix}{uuid.uuid4().hex[:8]}"


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('admin_logged_in'):
            return redirect(url_for('admin_login'))
        return f(*args, **kwargs)
    return decorated


# ==================== PUBLIC ROUTES ====================

@app.route('/')
def index():
    categories = get_categories()
    fun_categories = [c for c in categories if c.get('track', '') == 'fun']
    learning_categories = [c for c in categories if c.get('track', '') == 'learning']
    featured_videos = get_videos(limit=6)
    latest_news = get_news()[:3]
    return render_template('index.html', fun_categories=fun_categories, learning_categories=learning_categories, featured_videos=featured_videos, latest_news=latest_news, platform_config=PLATFORM_CONFIG)


@app.route('/choose-logo')
def choose_logo():
    return render_template('choose_logo.html')


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
    return render_template('category.html', category=category, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG)


@app.route('/subcategory/<subcategory_id>')
def subcategory_page(subcategory_id):
    sub = get_subcategory(subcategory_id)
    if not sub:
        return redirect(url_for('index'))
    category = get_category(sub['category_id'])
    subcategories = get_subcategories(sub['category_id'])
    videos = get_videos(subcategory_id=subcategory_id)
    return render_template('subcategory.html', category=category, sub=sub, subcategories=subcategories, videos=videos, platform_config=PLATFORM_CONFIG)


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
        submission = {
            'id': generate_id('sub_'),
            'platform': request.form.get('platform', 'youtube'),
            'platform_url': request.form.get('platform_url', ''),
            'title_zh': request.form.get('title_zh', ''),
            'title_en': request.form.get('title_en', ''),
            'category_id': category_id,
            'subcategory_id': subcategory_id,
            'submitter_name': request.form.get('submitter_name', ''),
            'submitter_email': request.form.get('submitter_email', ''),
            'description_zh': request.form.get('description_zh', ''),
            'direction': request.form.get('direction', ''),
            'status': 'pending',
            'submitted_date': datetime.now().strftime('%Y-%m-%d')
        }
        fieldnames = ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date']
        append_csv('submissions.csv', submission, fieldnames)
        return render_template('submit.html', categories=categories, platform_config=PLATFORM_CONFIG, success=True)
    return render_template('submit.html', categories=categories, platform_config=PLATFORM_CONFIG, success=False)


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
    content = filter_profanity(request.form.get('content', '').strip())
    author = filter_profanity(request.form.get('author', '').strip()) or '匿名用戶'
    if not content:
        return redirect(url_for('video_detail', video_id=video_id))
    append_csv('comments.csv', {
        'id': generate_id('cm_'), 'video_id': video_id, 'author': author,
        'content': content, 'date': datetime.now().strftime('%Y-%m-%d'), 'status': 'approved'
    }, ['id', 'video_id', 'author', 'content', 'date', 'status'])
    return redirect(url_for('video_detail', video_id=video_id))


@app.route('/api/subcategories/<category_id>')
def api_subcategories(category_id):
    return jsonify(get_subcategories(category_id))


# ==================== ADMIN ROUTES ====================

@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        if request.form.get('password') == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_dashboard'))
        return render_template('admin/login.html', error='密碼錯誤')
    return render_template('admin/login.html', error=None)


@app.route('/admin/logout')
def admin_logout():
    session.pop('admin_logged_in', None)
    return redirect(url_for('admin_login'))


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
        thumb = request.form.get('thumbnail_url', '') or f"https://img.youtube.com/vi/{platform_id}/hqdefault.jpg"
    elif platform == 'instagram':
        platform_id = extract_instagram_id(platform_id_raw) or platform_id_raw
        thumb = request.form.get('thumbnail_url', '') or f"https://picsum.photos/seed/{platform_id}/400/711"
    elif platform == 'tiktok':
        platform_id = extract_tiktok_id(platform_id_raw) or platform_id_raw
        thumb = request.form.get('thumbnail_url', '') or f"https://picsum.photos/seed/{platform_id}/400/711"
    else:
        platform_id = platform_id_raw
        thumb = request.form.get('thumbnail_url', '')
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
    write_csv('submissions.csv', subs, ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date'])
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
            'tags': '',
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
    write_csv('submissions.csv', subs, ['id', 'platform', 'platform_url', 'title_zh', 'title_en', 'category_id', 'subcategory_id', 'submitter_name', 'submitter_email', 'description_zh', 'direction', 'status', 'submitted_date'])
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
        })
        write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status'])
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
            break
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status'])
    return redirect(url_for('admin_news'))


@app.route('/admin/news/delete/<news_id>', methods=['POST'])
@admin_required
def admin_news_delete(news_id):
    news_list = [n for n in read_csv('news.csv') if n['id'] != news_id]
    write_csv('news.csv', news_list, ['id', 'title_zh', 'title_en', 'content_zh', 'content_en', 'summary_zh', 'summary_en', 'date', 'image_url', 'status'])
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


@app.context_processor
def inject_globals():
    return {
        'categories': get_categories(),
        'platform_config': PLATFORM_CONFIG,
        'directions': DIRECTIONS,
        'now': datetime.now()
    }


@app.after_request
def add_utf8_header(response):
    response.headers['Content-Type'] = 'text/html; charset=utf-8'
    return response


@app.errorhandler(500)
def internal_error(e):
    import traceback
    return f"<pre>500 Internal Server Error\n\n{traceback.format_exc()}</pre>", 500


if __name__ == '__main__':
    import sys
    port = int(os.environ.get('PORT', 5000))
    debug = '--debug' in sys.argv
    app.run(host='0.0.0.0', port=port, debug=debug)