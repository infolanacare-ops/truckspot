#!/usr/bin/env python3
"""
TruckSpot — Bulk import parkingów TIR z OpenStreetMap (Overpass API)
Pobiera wszystkie parkingi z tagami hgv=yes/designated dla krajów EU.

Użycie:
  python scripts/import_osm_parkings.py
  python scripts/import_osm_parkings.py --countries PL,DE,FR

Efekt: data/parkings.json (zastępuje/uzupełnia istniejący plik)
"""

import json, time, math, argparse, sys, os, re
import urllib.request, urllib.error

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(DATA_DIR, "parkings.json")

COUNTRIES = [
    "PL","DE","FR","CZ","AT","HU","RO","SK","NL","BE",
    "IT","ES","CH","HR","SI","BG","RS","LT","LV","EE",
    "FI","SE","DK","NO","PT","GR","UA","BY","LU","IE",
]

# Bounding boxy krajów (S, W, N, E)
COUNTRY_BBOX = {
    "PL": (49.0, 14.1, 54.9, 24.2),
    "DE": (47.3, 5.9,  51.2, 15.0),   # DE south+west
    "DE2": (51.2, 5.9, 55.1, 15.0),   # DE north+east
    "FR": (41.3, -5.2, 51.1, 9.6),
    "CZ": (48.5, 12.1, 51.1, 18.9),
    "AT": (46.4, 9.5,  49.0, 17.2),
    "HU": (45.7, 16.1, 48.6, 22.9),
    "RO": (43.6, 20.2, 48.3, 29.7),
    "SK": (47.7, 16.8, 49.6, 22.6),
    "NL": (50.7, 3.4,  53.6, 7.2),
    "BE": (49.5, 2.5,  51.5, 6.4),
    "IT": (36.6, 6.6,  47.1, 18.5),
    "ES": (36.0, -9.3, 43.8, 3.3),
    "CH": (45.8, 5.9,  47.8, 10.5),
    "HR": (42.4, 13.5, 46.6, 19.5),
    "SI": (45.4, 13.4, 46.9, 16.6),
    "BG": (41.2, 22.4, 44.2, 28.6),
    "RS": (42.2, 18.8, 46.2, 23.0),
    "LT": (53.9, 20.9, 56.5, 26.8),
    "LV": (55.7, 20.9, 57.8, 28.2),
    "EE": (57.5, 21.8, 59.7, 28.2),
    "FI": (59.8, 19.1, 70.1, 31.6),
    "SE": (55.3, 11.0, 69.1, 24.2),
    "DK": (54.6, 8.1,  57.8, 15.2),
    "NO": (57.9, 4.5,  71.2, 31.1),
    "PT": (36.9, -9.5, 42.2, -6.2),
    "GR": (34.8, 19.4, 41.8, 28.3),
    "UA": (44.4, 22.1, 52.4, 40.2),
    "BY": (51.2, 23.2, 53.9, 32.8),
    "LU": (49.4, 5.7,  50.2, 6.5),
    "IE": (51.4, -10.5,55.4, -6.0),
}

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

def overpass_query(bbox, mode="tir"):
    s, w, n, e = bbox
    bbox_str = f"{s},{w},{n},{e}"

    if mode == "tir":
        query = f"""
[out:json][timeout:120];
(
  node["amenity"="parking"]["hgv"~"yes|designated|trucks"]({bbox_str});
  way["amenity"="parking"]["hgv"~"yes|designated|trucks"]({bbox_str});
  node["amenity"="parking_space"]["hgv"~"yes|designated"]({bbox_str});
  node["highway"="rest_area"]["hgv"~"yes|designated"]({bbox_str});
  way["highway"="rest_area"]["hgv"~"yes|designated"]({bbox_str});
  node["highway"="services"]["hgv"~"yes|designated"]({bbox_str});
  way["highway"="services"]["hgv"~"yes|designated"]({bbox_str});
  node["amenity"="truckers"]({bbox_str});
  node["truck"="yes"]["amenity"="parking"]({bbox_str});
);
out center tags;
"""
    else:
        query = f"""
[out:json][timeout:120];
(
  node["amenity"="parking"]["motorhome"~"yes|designated"]({bbox_str});
  way["amenity"="parking"]["motorhome"~"yes|designated"]({bbox_str});
  node["tourism"="caravan_site"]({bbox_str});
  way["tourism"="caravan_site"]({bbox_str});
  node["tourism"="camp_site"]({bbox_str});
  way["tourism"="camp_site"]({bbox_str});
);
out center tags;
"""
    return query.strip()

def fetch_overpass(query, retries=3):
    data = ("data=" + urllib.parse.quote(query)).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(
                OVERPASS_URL,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded",
                         "User-Agent": "TruckSpot/1.0 (truckspot app)"}
            )
            with urllib.request.urlopen(req, timeout=130) as r:
                return json.loads(r.read().decode())
        except Exception as ex:
            print(f"    ! Attempt {attempt+1} failed: {ex}")
            if attempt < retries - 1:
                time.sleep(5 * (attempt + 1))
    return None

def parse_amenities(tags):
    result = []
    mapping = {
        "fuel": ["fuel", "amenity=fuel"],
        "toilet": ["toilets", "toilet"],
        "shower": ["shower", "showers"],
        "restaurant": ["restaurant", "food"],
        "wifi": ["internet_access", "wifi"],
        "lighting": ["lit"],
        "monitored": ["surveillance", "monitored"],
        "secured": ["fee", "barrier"],
        "shop": ["shop"],
        "truck_wash": ["truck_wash", "carwash"],
    }
    for amenity, keys in mapping.items():
        for k in keys:
            if k in tags and tags[k] not in ("no", "0", "false"):
                result.append(amenity)
                break
    return list(set(result))

def get_lat_lng(el):
    if "center" in el:
        return el["center"]["lat"], el["center"]["lon"]
    return el.get("lat"), el.get("lon")

def parse_spots(tags):
    for key in ["capacity:hgv", "capacity:trucks", "capacity"]:
        v = tags.get(key)
        if v and str(v).isdigit():
            return int(v)
    return 0

def parse_price(tags):
    fee = tags.get("fee", "").lower()
    if fee in ("no", "0", "free"):
        return 0
    charge = tags.get("charge", "")
    m = re.search(r"(\d+\.?\d*)", charge)
    if m:
        return float(m.group(1))
    return 5  # default unknown = 5€

def make_parking(el, country, next_id, ptype="tir"):
    tags = el.get("tags", {})
    lat, lng = get_lat_lng(el)
    if not lat or not lng:
        return None

    name = (tags.get("name") or tags.get("name:en") or
            tags.get("operator") or
            ("Parking TIR" if ptype == "tir" else "Parking Camper"))

    city = (tags.get("addr:city") or tags.get("addr:town") or
            tags.get("addr:village") or "")
    address = tags.get("addr:street", "")
    if tags.get("addr:housenumber"):
        address += " " + tags["addr:housenumber"]

    amenities = parse_amenities(tags)
    spots = parse_spots(tags)
    price = parse_price(tags)

    ptype_list = [ptype]
    if ptype == "tir" and tags.get("motorhome") in ("yes", "designated"):
        ptype_list.append("camper")

    return {
        "id": next_id,
        "name": name.strip(),
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "type": ptype_list,
        "country": country,
        "city": city,
        "address": address.strip(),
        "spots_tir": spots if ptype == "tir" else 0,
        "spots_camper": spots if ptype == "camper" else 0,
        "amenities": amenities,
        "price_eur": price,
        "rating": 0,
        "status": "open",
        "source": "osm",
        "osm_id": el["id"],
        "poi": [],
    }

import urllib.parse

def import_country(country, existing_osm_ids, next_id, modes=("tir",)):
    bbox = COUNTRY_BBOX.get(country)
    if not bbox:
        print(f"  ! No bbox for {country}, skipping")
        return [], next_id

    results = []
    for mode in modes:
        print(f"  Querying OSM ({mode})...", end=" ", flush=True)
        q = overpass_query(bbox, mode)
        data = fetch_overpass(q)
        if not data:
            print("FAILED")
            continue

        elements = data.get("elements", [])
        added = 0
        for el in elements:
            osm_id = el.get("id")
            if osm_id in existing_osm_ids:
                continue
            p = make_parking(el, country, next_id, mode)
            if p:
                results.append(p)
                existing_osm_ids.add(osm_id)
                next_id += 1
                added += 1

        print(f"got {len(elements)} elements -> {added} new")
        time.sleep(2)  # be nice to Overpass

    return results, next_id

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--countries", default=",".join(COUNTRIES))
    parser.add_argument("--append", action="store_true", help="Append to existing (default: replace OSM entries)")
    args = parser.parse_args()

    raw_countries = [c.strip().upper() for c in args.countries.split(",")]
    # Expand DE -> DE + DE2
    target_countries = []
    for c in raw_countries:
        target_countries.append(c)
        if c == "DE":
            target_countries.append("DE2")

    # Load existing
    existing = []
    if os.path.exists(OUT_FILE):
        with open(OUT_FILE, encoding="utf-8") as f:
            existing = json.load(f)
        print(f"Loaded {len(existing)} existing parkings")

    # Keep manual entries + OSM entries for countries NOT being re-imported
    manual = [p for p in existing if not p.get("osm_id")]
    kept_osm = [p for p in existing if p.get("osm_id") and p.get("country") not in target_countries]
    print(f"Keeping {len(manual)} manual + {len(kept_osm)} OSM from other countries, re-importing {target_countries}...")

    existing_osm_ids = {p["osm_id"] for p in kept_osm if p.get("osm_id")}
    base = manual + kept_osm
    next_id = max((p["id"] for p in base), default=0) + 1
    all_new = []

    for country in target_countries:
        print(f"\n[{country}]")
        new, next_id = import_country(country, existing_osm_ids, next_id, modes=("tir",))
        all_new.extend(new)
        print(f"  -> {len(new)} parkings added for {country}")

    final = base + all_new
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)

    print(f"\nDone! Total: {len(final)} parkings ({len(manual)} manual + {len(all_new)} from OSM)")
    print(f"   Saved to {OUT_FILE}")

if __name__ == "__main__":
    main()
