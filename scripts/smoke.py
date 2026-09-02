#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Thingerz canonical smoke test.

Runs key routes through the Flask test client + search-tokenizer unit checks.
This is the repo's verification entry point (no pytest/lint/build exists):
    .venv/bin/python scripts/smoke.py
Exit 0 = all pass, 1 = any failure. Data-driven assertions are kept loose on
purpose (the local data/thingerz.db may be a subset of live); we assert status
codes + presence of stable page markers, not exact counts.

Ad-hoc verification pattern: after ANY template/app change, run this; the
changed-path behaviour checks still live in `hermes-verify-*` temp scripts.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import app  # noqa: E402

failures = []


def ck(name, cond, extra=""):
    print(("PASS" if cond else "FAIL"), name, extra)
    if not cond:
        failures.append(name)


def main():
    c = app.app.test_client()
    geo = app.geo

    # ---- key public routes render ----
    routes_200 = ["/", "/news", "/life-tips", "/submit", "/search?q=婚禮",
                  "/category/commercial", "/subcategory/s002",
                  "/subcategory/s078", "/subcategory/s079",
                  "/topics", "/topic/hk-small-shops"]
    for r in routes_200:
        ck(f"200 {r}", c.get(r).status_code == 200, str(c.get(r).status_code))
    # empty /search redirects to home by design
    ck("/search (empty q) -> 302", c.get("/search").status_code == 302)

    # ---- all 18 /location pages ----
    bad = [s for s in (d["slug"] for d in geo.DISTRICTS)
           if c.get("/location/" + s).status_code != 200]
    ck("18 /location 200", not bad, str(bad))

    # ---- a real video detail page (id discovered from homepage) ----
    home = c.get("/").get_data(as_text=True)
    m = re.search(r"/video/(cv_[a-z0-9]+)", home)
    ck("video detail 200", bool(m) and c.get("/video/" + m.group(1)).status_code == 200,
       m.group(1) if m else "no video on home")

    # ---- search: compound long-tails must be non-zero (fixed 2026-08-25) ----
    def nres(q):
        h = c.get("/search?q=" + q).get_data(as_text=True)
        mm = re.search(r"找到 (\d+) 個結果", h)
        return int(mm.group(1)) if mm else -1

    for q in ("觀塘美食", "婚禮攝影", "香港品牌", "親子活動", "觀塘健身",
              "屯門學bass", "深水埗cafe", "中西區補習"):
        n = nres(q)
        ck(f'search "{q}" non-zero', n > 0, str(n))

    # ---- search tokenizer units ----
    ck("tok 觀塘美食", app._search_tokens("觀塘美食") == ["觀塘", "美食"])
    ck("tok 屯門學bass", app._search_tokens("屯門學bass") == ["屯門", "學", "bass"])
    big = app._token_expand(["婚禮攝影"])
    ck("bigram expand", "婚禮" in big and "攝影" in big)

    # ---- home hero: search form + 3 entries + map view present ----
    body = home.split("</style>", 1)[1]
    ck("home hero search", 'class="hero-search"' in body)
    ck("home 3 entries", body.count('class="hero-entry"') == 3)
    ck("home map view 18 cells", len(re.findall(r'class="map-district"', body)) == 18)
    ck("home hot chips 5", body.count('class="hot-chip"') == 5)

    # ---- blank-template guard: no Jinja/500 artifacts ----
    for label, page in (("home", home),):
        ck(f"{label} no Traceback", "Traceback" not in page and "Internal Server Error" not in page)

    print("\nRESULT:", "ALL_PASS" if not failures else "FAILS: " + ", ".join(failures))
    sys.exit(0 if not failures else 1)


if __name__ == "__main__":
    main()