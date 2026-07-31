"""Push full_export.json data to Thingerz API in batches.
Usage: python push_to_thingerz.py full_export.json
"""
import requests, json, sys, time

API_URL = "https://thingerz.onrender.com/api/content"
API_KEY = "thingerz_crawler_2026"
BATCH_SIZE = 500

def main():
    if len(sys.argv) < 2:
        print("Usage: python push_to_thingerz.py full_export.json")
        sys.exit(1)
    
    with open(sys.argv[1], 'r', encoding='utf-8') as f:
        raw = json.load(f)
    
    # Detect payload format
    items = raw if isinstance(raw, list) else raw.get('content', raw.get('data', []))
    total = len(items)
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
            sent += res.get('received', len(batch))
            dups += res.get('duplicates_skipped', 0)
            errs += res.get('errors', 0)
            pct = min(100, int((i + BATCH_SIZE) / total * 100))
            print(f"  [{pct}%] Batch {i//BATCH_SIZE+1}: received={res.get('received')}, dup={res.get('duplicates_skipped')}, err={res.get('errors')}")
        except Exception as e:
            print(f"  ERROR batch {i//BATCH_SIZE+1}: {e}")
            time.sleep(3)
        time.sleep(0.5)
    
    print(f"\nDone. Sent={sent}, Duplicates={dups}, Errors={errs}")

if __name__ == '__main__':
    main()
