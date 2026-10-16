#!/usr/bin/env python3
"""Stage 2: details for each prk (shard=i/n, budget=N). Bare details API, kill-safe jsonl."""
import json, os, sys, time, urllib.parse, argparse
from curl_cffi import requests as cr

ap = argparse.ArgumentParser()
ap.add_argument("--shard", default="0/1")
ap.add_argument("--budget", type=int, default=55)
ap.add_argument("--out", default="/storage/emulated/0/HERMES/projects/torob-wheel-harvest/_raw/details.jsonl")
ap.add_argument("--list", dest="lst", default="/storage/emulated/0/HERMES/projects/torob-wheel-harvest/_raw/list.json")
a = ap.parse_args()
si, sn = (int(x) for x in a.shard.split("/"))

items = json.load(open(a.lst, encoding="utf-8"))
prs = sorted(items)
mine = [p for i, p in enumerate(prs) if i % sn == si]
done = set()
if os.path.exists(a.out):
    for line in open(a.out, encoding="utf-8"):
        try:
            done.add(json.loads(line).get("prk"))
        except Exception:
            pass
todo = [p for p in mine if p not in done]
print("shard %s: %d assigned, %d done, %d to fetch (budget %d)" % (a.shard, len(mine), len(done), len(todo), a.budget))

s = cr.Session(impersonate="chrome")
H = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36",
     "Referer": "https://torob.com/", "Accept": "application/json"}
ok = wall = 0
f = open(a.out, "a", encoding="utf-8")
for prk in todo[: a.budget]:
    u = "https://api.torob.com/v4/base-product/details/?prk=" + prk
    try:
        r = s.get(u, headers=H, timeout=25)
    except Exception as e:
        print("  ERR", prk[:8], type(e).__name__)
        time.sleep(2)
        continue
    if r.status_code in (429, 490, 403):
        wall += 1
        print("  WALL %s (x%d) — stopping this shard" % (r.status_code, wall))
        if wall >= 2:
            break
        time.sleep(45)
        continue
    try:
        d = r.json()
    except Exception:
        print("  BADJSON", r.status_code, prk[:8])
        continue
    rec = {"prk": prk, "name": d.get("name1"), "name_en": d.get("name2"), "price": d.get("price"),
           "price_text": d.get("price_text"), "min_price": d.get("min_price"), "max_price": d.get("max_price"),
           "url": "https://torob.com/p/%s/" % prk,
           "web_url": d.get("web_client_absolute_url") or d.get("canonical_url") or "",
           "image": d.get("image_url") or "", "images": len(d.get("image_urls") or []),
           "rating": d.get("rating_count"), "shop_count": d.get("shop_count"),
           "seller_title": d.get("seller_title") or "", "availability": d.get("availability"),
           "category": d.get("torob_category") or "", "crumbs": d.get("breadcrumbs") or [],
           "key_specs": d.get("key_specs") or [], "struct_specs": d.get("structural_specs") or [],
           "seo": d.get("seo_description") or "", "variants": d.get("variants") or [],
           "sellers": (d.get("products_info") or {}).get("result", []) if isinstance(d.get("products_info"), dict) else [],
           "in_store": (d.get("products_in_store_info") or {}).get("result", []) if isinstance(d.get("products_in_store_info"), dict) else []}
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    f.flush()
    ok += 1
    if ok % 10 == 0:
        print("  %d ok | %s" % (ok, (rec.get("name") or "")[:50]))
    time.sleep(1.2)
f.close()
print("DONE shard %s: +%d saved, walls=%d -> %s" % (a.shard, ok, wall, a.out))
