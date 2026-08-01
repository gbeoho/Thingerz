import os, json, sqlite3
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder='.', static_url_path='')
CORS(app)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'thingerz_crawler.db')

CATEGORY_NAMES = {
    's001': '市場研究與分析', 's002': '品牌推廣', 's003': '網上生意', 's004': '專業顧問',
    's005': '室內設計', 's006': '醫療服務', 's007': '餐飲與酒類', 's008': '活動與配對',
    's009': '技能教學', 's010': '表演教練', 's011': '音樂學習', 's012': '視覺創作課程',
    's013': '語言與翻譯', 's014': '心理／自我提升', 's015': '平面設計', 's016': '服飾設計',
    's017': '手作工藝', 's018': '配件設計', 's019': '攝影與影像', 's020': '印刷與工藝',
    's021': '藝術裝置', 's022': '繪畫與素描', 's023': '音樂演出', 's024': '舞蹈表演',
    's025': '戲劇與短劇', 's026': '魔術與奇技', 's027': '特技與雜耍', 's028': '互動娛樂',
    's029': '烘焙', 's030': '餐飲教學', 's031': '飲品與品味', 's032': '食物創作',
    's033': '香氛與感官', 's034': '園藝與種植', 's035': '飲食品牌', 's036': '婚禮策劃',
    's037': '婚禮設計', 's038': '婚禮造型', 's039': '婚禮甜點', 's040': '親子活動',
    's041': '日常生活美學', 's042': '節慶與禮品', 's043': '化妝', 's044': '護膚',
    's045': '造型與形象', 's046': '美感內容', 's047': '個人品牌形象', 's048': '美容服務',
    's049': '親子教育', 's050': '兒童活動', 's051': '社區組織', 's052': '公共參與',
    's053': '社交配對', 's054': '公眾講座',
}

CAT_GROUPS = {
    's001':'商業與專業服務','s002':'商業與專業服務','s003':'商業與專業服務','s004':'商業與專業服務',
    's005':'商業與專業服務','s006':'商業與專業服務','s007':'商業與專業服務','s008':'商業與專業服務',
    's009':'教學與培訓','s010':'教學與培訓','s011':'教學與培訓','s012':'教學與培訓',
    's013':'教學與培訓','s014':'教學與培訓',
    's015':'藝術與設計','s016':'藝術與設計','s017':'藝術與設計','s018':'藝術與設計',
    's019':'藝術與設計','s020':'藝術與設計','s021':'藝術與設計','s022':'藝術與設計',
    's023':'表演與娛樂','s024':'表演與娛樂','s025':'表演與娛樂','s026':'表演與娛樂',
    's027':'表演與娛樂','s028':'表演與娛樂',
    's029':'飲食與手作','s030':'飲食與手作','s031':'飲食與手作','s032':'飲食與手作',
    's033':'飲食與手作','s034':'飲食與手作','s035':'飲食與手作',
    's036':'婚禮與生活','s037':'婚禮與生活','s038':'婚禮與生活','s039':'婚禮與生活',
    's040':'婚禮與生活','s041':'婚禮與生活','s042':'婚禮與生活',
    's043':'美容與形象','s044':'美容與形象','s045':'美容與形象','s046':'美容與形象',
    's047':'美容與形象','s048':'美容與形象',
    's049':'親子與社區','s050':'親子與社區','s051':'親子與社區','s052':'親子與社區',
    's053':'親子與社區','s054':'親子與社區',
}


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    db = get_db()
    db.execute('''CREATE TABLE IF NOT EXISTS crawled_videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        platform TEXT NOT NULL, platform_id TEXT NOT NULL,
        sub_category TEXT, district TEXT, title TEXT, url TEXT,
        thumbnail_url TEXT, author_name TEXT, author_url TEXT,
        description TEXT, view_count INTEGER DEFAULT 0,
        like_count INTEGER DEFAULT 0, comment_count INTEGER DEFAULT 0,
        duration_sec INTEGER DEFAULT 0, published_at TEXT,
        score REAL DEFAULT 0, updated_at TEXT,
        UNIQUE(platform, platform_id))''')
    db.commit()

    # Load from JSON if DB is empty
    count = db.execute('SELECT COUNT(*) FROM crawled_videos').fetchone()[0]
    if count == 0:
        json_path = os.path.join(os.path.dirname(DB_PATH), 'thingerz_export.json')
        if os.path.exists(json_path):
            with open(json_path, 'r', encoding='utf-8') as f:
                raw = json.load(f)
            items = raw if isinstance(raw, list) else raw.get('content', raw.get('data', []))
            for item in items:
                try:
                    db.execute('''INSERT OR IGNORE INTO crawled_videos
                        (platform, platform_id, sub_category, district, title, url, thumbnail_url,
                         author_name, author_url, description, view_count, like_count, comment_count,
                         duration_sec, published_at, score, updated_at)
                        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (item.get('platform',''), str(item.get('platform_id','')),
                         item.get('sub_category',''), item.get('district',''),
                         item.get('title',''), item.get('url',''), item.get('thumbnail_url',''),
                         item.get('author_name',''), item.get('author_url',''),
                         str(item.get('description',''))[:500],
                         int(item.get('view_count') or 0), int(item.get('like_count') or 0),
                         int(item.get('comment_count') or 0), int(item.get('duration_sec') or 0),
                         item.get('published_at',''), float(item.get('score') or 0),
                         item.get('updated_at','')))
                except:
                    pass
            db.commit()
    db.close()


@app.route('/api/stats')
def api_stats():
    db = get_db()
    total = db.execute('SELECT COUNT(*) FROM crawled_videos').fetchone()[0]
    platforms = db.execute('SELECT platform, COUNT(*) as cnt FROM crawled_videos GROUP BY platform ORDER BY cnt DESC').fetchall()
    subcats = db.execute('SELECT sub_category, COUNT(*) as cnt FROM crawled_videos WHERE sub_category != "" GROUP BY sub_category ORDER BY cnt DESC').fetchall()
    districts = db.execute('SELECT district, COUNT(*) as cnt FROM crawled_videos WHERE district != "" GROUP BY district ORDER BY cnt DESC').fetchall()
    db.close()
    return jsonify({
        'total': total,
        'platforms': [{'platform': r['platform'], 'count': r['cnt']} for r in platforms],
        'sub_categories_covered': len(subcats),
        'districts_covered': len(districts),
    })


@app.route('/api/categories')
def api_categories():
    db = get_db()
    rows = db.execute('SELECT sub_category, COUNT(*) as cnt FROM crawled_videos WHERE sub_category != "" GROUP BY sub_category ORDER BY cnt DESC').fetchall()
    db.close()
    return jsonify([{
        'id': r['sub_category'],
        'name_zh': CATEGORY_NAMES.get(r['sub_category'], r['sub_category']),
        'group': CAT_GROUPS.get(r['sub_category'], ''),
        'count': r['cnt']
    } for r in rows])


@app.route('/api/districts')
def api_districts():
    db = get_db()
    rows = db.execute('SELECT district, COUNT(*) as cnt FROM crawled_videos WHERE district != "" GROUP BY district ORDER BY cnt DESC').fetchall()
    db.close()
    return jsonify([{'district': r['district'], 'count': r['cnt']} for r in rows])


@app.route('/api/items')
def api_items():
    db = get_db()
    platform = request.args.get('platform', '')
    district = request.args.get('district', '')
    category = request.args.get('category', '')
    q = request.args.get('q', '')
    limit = min(int(request.args.get('limit', 20) or 20), 200)
    offset = int(request.args.get('offset', 0) or 0)

    query = 'SELECT * FROM crawled_videos WHERE 1=1'
    params = []
    if platform:
        query += ' AND platform=?'
        params.append(platform)
    if district:
        query += ' AND district=?'
        params.append(district)
    if category:
        query += ' AND sub_category=?'
        params.append(category)
    if q:
        query += ' AND (title LIKE ? OR description LIKE ?)'
        params.extend([f'%{q}%', f'%{q}%'])
    query += ' ORDER BY view_count DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    items = [dict(r) for r in db.execute(query, params).fetchall()]
    total = db.execute('SELECT COUNT(*) FROM crawled_videos WHERE 1=1' + (query.split('WHERE')[1].split('ORDER')[0] if 'WHERE' in query else ''), 
                       params[:-2] if params else []).fetchone()[0] if params else db.execute('SELECT COUNT(*) FROM crawled_videos').fetchone()[0]
    db.close()
    return jsonify({'items': items, 'total': total, 'limit': limit, 'offset': offset})


@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
