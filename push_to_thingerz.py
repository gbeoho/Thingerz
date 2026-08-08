"""Push full_export.json data to Thingerz API in batches.
Usage: python push_to_thingerz.py full_export.json
"""
import requests, json, sys, time, os

API_URL = "https://thingerz.onrender.com/api/content"
import os as _os

def _load_api_key():
    try:
        with open("/opt/data/Thingerz/.env", encoding="utf-8") as _f:
            for _l in _f:
                if _l.strip().startswith("API_KEY="):
                    return _l.strip().split("=", 1)[1].strip()
    except FileNotFoundError:
        pass
    return _os.environ.get("API_KEY", "")

API_KEY = _load_api_key()
BATCH_SIZE = 500

def main():
    if len(sys.argv) < 2:
        print("Usage: python push_to_thingerz.py full_export.json")
        sys.exit(1)

    filepath = sys.argv[1]
    if not os.path.exists(filepath):
        print(f"ERROR: File not found: {filepath}")
        sys.exit(1)

    size_mb = os.path.getsize(filepath) / (1024 * 1024)
    print(f"File: {filepath} ({size_mb:.1f} MB)")

    with open(filepath, 'r', encoding='utf-8') as f:
        raw_text = f.read()
    
    if not raw_text.strip():
        print("ERROR: File is empty")
        sys.exit(1)

    # Try parsing as JSON
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}")
        print(f"First 200 chars: {raw_text[:200]}")
        sys.exit(1)

    # Handle various export formats
    if isinstance(raw, list):
        items = raw
    elif isinstance(raw, dict):
        items = raw.get('content') or raw.get('data') or raw.get('items') or []
        if not items and 'export_date' in raw:
            items = raw.get('results', [])
        if not items:
            for k, v in raw.items():
                if isinstance(v, list) and len(v) > 100:
                    items = v
                    break
    else:
        print(f"ERROR: Unexpected JSON type: {type(raw)}")
        sys.exit(1)

    total = len(items)
    if total == 0:
        print("ERROR: No items found in JSON")
        sys.exit(1)
    print(f"Total items: {total}")

    sent, dups, errs = 0, 0, 0
    for i in range(0, total, BATCH_SIZE):
        batch = items[i:i+BATCH_SIZE]
        try:
            r = requests.post(API_URL,
                json={"content": batch, "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")},
                headers={"X-API-Key": API_KEY, "Content-Type": "application/json"},
                timeout=120)
            res = r.json()
            received = res.get('received', len(batch))
            dups += res.get('duplicates_skipped', 0)
            errs += res.get('errors', 0)
            sent += received
            pct = min(100, int((i + BATCH_SIZE) / total * 100))
            print(f"  [{pct}%] Batch {i//BATCH_SIZE+1}: recv={received}, dup={res.get('duplicates_skipped')}, err={res.get('errors')}")
        except Exception as e:
            print(f"  ERROR batch {i//BATCH_SIZE+1}: {e}")
            time.sleep(3)
        time.sleep(0.5)

    print(f"\nDone. Sent={sent}, Duplicates={dups}, Errors={errs}")

if __name__ == '__main__':
    main()
