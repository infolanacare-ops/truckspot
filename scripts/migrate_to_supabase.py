"""
Migracja danych z JSON → Supabase PostgreSQL
Uruchom: python scripts/migrate_to_supabase.py
"""
import json, os, sys, time
import urllib.request, urllib.error

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://sabeurtjyasiwozekguh.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "resolution=merge-duplicates"
}

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

def post_batch(table, rows):
    url = f"{SUPABASE_URL}/rest/v1/{table}"
    body = json.dumps(rows).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status
    except urllib.error.HTTPError as e:
        print(f"  ERROR {e.code}: {e.read().decode()[:200]}")
        return e.code

def migrate(table, filepath, transform=None, batch=500):
    print(f"\n→ Migruję {table} z {os.path.basename(filepath)}...")
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = list(data.values())[0] if data else []
    if not isinstance(data, list):
        data = [data]
    if transform:
        data = [transform(r) for r in data]

    total = len(data)
    print(f"  Łącznie: {total} rekordów")
    ok = 0
    for i in range(0, total, batch):
        chunk = data[i:i+batch]
        status = post_batch(table, chunk)
        if status in (200, 201):
            ok += len(chunk)
            print(f"  [{ok}/{total}] ✓")
        else:
            print(f"  [{i}/{total}] ✗ status={status}")
        time.sleep(0.2)
    print(f"  Gotowe: {ok}/{total}")

def fix_parking(r):
    return {
        "id": r["id"],
        "name": r.get("name", ""),
        "lat": r.get("lat"),
        "lng": r.get("lng"),
        "type": r.get("type", []),
        "country": r.get("country"),
        "city": r.get("city"),
        "address": r.get("address"),
        "spots_tir": r.get("spots_tir", 0) or 0,
        "spots_camper": r.get("spots_camper", 0) or 0,
        "amenities": r.get("amenities", []),
        "price_eur": r.get("price_eur", 0) or 0,
        "rating": r.get("rating"),
        "status": r.get("status", "open"),
        "poi": r.get("poi", []),
    }

def fix_market(r):
    return {
        "id": r["id"],
        "name": r.get("name"),
        "city": r.get("city"),
        "state": r.get("state"),
        "region": r.get("region"),
        "address": r.get("address"),
        "lat": r.get("lat"),
        "lng": r.get("lng"),
        "type": r.get("type"),
        "schedule": r.get("schedule"),
        "recurring": bool(r.get("recurring", False)),
        "recurring_day": r.get("recurring_day"),
        "dates": r.get("dates"),
        "time_from": r.get("time_from"),
        "time_to": r.get("time_to"),
        "website": r.get("website"),
        "description": r.get("description"),
        "indoor": bool(r.get("indoor", False)),
        "free_entry": bool(r.get("free_entry", True)),
        "parking": bool(r.get("parking", False)),
        "country": r.get("country"),
    }

def fix_scenic(r):
    return {
        "id": r["id"],
        "name": r.get("name"),
        "country": r.get("country"),
        "region": r.get("region"),
        "lat": r.get("lat"),
        "lng": r.get("lng"),
        "type": r.get("type"),
        "description": r.get("description"),
        "elevation": r.get("elevation"),
        "best_season": r.get("best_season"),
        "parking": bool(r.get("parking", False)),
        "free_entry": bool(r.get("free_entry", True)),
        "website": r.get("website"),
    }

if __name__ == "__main__":
    migrate("parkings",    os.path.join(DATA_DIR, "parkings.json"),  fix_parking, batch=200)
    migrate("markets",     os.path.join(DATA_DIR, "markets.json"),   fix_market)
    migrate("scenic_spots",os.path.join(DATA_DIR, "scenic.json"),    fix_scenic)
    print("\n✅ Migracja zakończona!")
