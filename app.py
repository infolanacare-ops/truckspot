#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, secrets, time, math, requests as _requests
from flask import Flask, render_template, request, jsonify, send_from_directory

try:
    from pywebpush import webpush, WebPushException
    PUSH_AVAILABLE = True
except ImportError:
    PUSH_AVAILABLE = False

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATA_DIR        = os.path.join(os.path.dirname(__file__), "data")
PARKINGS_PATH   = os.path.join(DATA_DIR, "parkings.json")
SPOTS_PATH      = os.path.join(DATA_DIR, "spots.json")
MARKETS_PATH    = os.path.join(DATA_DIR, "markets.json")
SCENIC_PATH     = os.path.join(DATA_DIR, "scenic.json")
COMMENTS_PATH   = os.path.join(DATA_DIR, "comments.json")
OCCUPANCY_PATH  = os.path.join(DATA_DIR, "occupancy.json")
MESSAGES_PATH       = os.path.join(DATA_DIR, "messages.json")
SUBSCRIPTIONS_PATH  = os.path.join(DATA_DIR, "subscriptions.json")

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_EMAIL       = os.environ.get("VAPID_EMAIL", "mailto:admin@truckspot.app")

PUSH_ALERT_RADIUS_KM = 20  # promień alertów

CAT_LABELS_PL = {
    'police':   '🚔 Policja w pobliżu!',
    'accident': '🚨 Wypadek na drodze!',
    'traffic':  '🚦 Korek na trasie!',
    'roadwork': '🚧 Roboty drogowe!',
    'weather':  '⛈️ Ostrzeżenie pogodowe!',
    'fuel':     '⛽ Info o paliwie',
    'help':     '🆘 Potrzebna pomoc!',
    'info':     'ℹ️ Info od kierowcy',
}

def haversine_km(lat1, lng1, lat2, lng2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng/2)**2
    return R * 2 * math.asin(math.sqrt(max(0, a)))

def load_subscriptions():
    if not os.path.exists(SUBSCRIPTIONS_PATH):
        return []
    with open(SUBSCRIPTIONS_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_subscriptions(subs):
    with open(SUBSCRIPTIONS_PATH, "w", encoding="utf-8") as f:
        json.dump(subs, f, ensure_ascii=False, indent=2)

def send_push_nearby(lat, lng, cat, text, radius_km=PUSH_ALERT_RADIUS_KM):
    if not PUSH_AVAILABLE or not VAPID_PRIVATE_KEY or not VAPID_PUBLIC_KEY:
        return 0
    subs = load_subscriptions()
    title = CAT_LABELS_PL.get(cat, 'ℹ️ Alert TruckSpot')
    payload = json.dumps({
        'title': title,
        'body':  text[:120],
        'icon':  '/static/icon-192.png',
        'badge': '/static/favicon-32.png',
        'data':  {'lat': lat, 'lng': lng, 'cat': cat},
        'tag':   f'cb-{cat}',
    })
    dead, sent = [], 0
    for sub in subs:
        slat, slng = sub.get('lat'), sub.get('lng')
        if slat is None or slng is None:
            continue
        if haversine_km(lat, lng, slat, slng) > radius_km:
            continue
        try:
            webpush(
                subscription_info=sub['subscription'],
                data=payload,
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={'sub': VAPID_EMAIL},
            )
            sent += 1
        except WebPushException as ex:
            if ex.response and ex.response.status_code in (404, 410):
                dead.append(sub['id'])
    # usuń wygasłe subskrypcje
    if dead:
        save_subscriptions([s for s in subs if s.get('id') not in dead])
    return sent

# ── Autobahn GmbH cache (in-memory, TTL=10 min) ──────────────────────────────
_AUTOBAHN_CACHE = {}          # road_id -> (timestamp, data)
_AUTOBAHN_TTL   = 600         # seconds
_AUTOBAHN_ROADS = [
    "A1","A2","A3","A4","A5","A6","A7","A8","A9",
    "A10","A13","A14","A17","A19","A20","A24","A27","A28","A29","A30",
    "A31","A33","A38","A39","A40","A42","A43","A44","A45","A46",
    "A57","A59","A61","A63","A65","A66","A67","A70","A71","A72","A73",
    "A93","A94","A95","A96","A98","A99",
]

os.makedirs(DATA_DIR, exist_ok=True)
if not os.path.exists(SPOTS_PATH):
    with open(SPOTS_PATH, "w", encoding="utf-8") as _f:
        import json as _j; _j.dump([], _f)

def load_parkings():
    if not os.path.exists(PARKINGS_PATH):
        return []
    with open(PARKINGS_PATH, encoding="utf-8") as f:
        return json.load(f)

@app.route("/sw.js")
def service_worker():
    resp = send_from_directory('static', 'sw.js')
    resp.headers['Service-Worker-Allowed'] = '/'
    resp.headers['Cache-Control'] = 'no-cache'
    return resp

@app.route("/static/manifest.json")
def manifest():
    resp = send_from_directory('static', 'manifest.json')
    resp.headers['Content-Type'] = 'application/manifest+json'
    resp.headers['Cache-Control'] = 'public, max-age=86400'
    return resp

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/parkings")
def api_parkings():
    parkings = load_parkings()
    mode     = request.args.get("mode", "")   # tir / camper / tourist
    country  = request.args.get("country", "")

    result = []
    for p in parkings:
        if mode and mode not in p.get("type", []):
            continue
        if country and p.get("country", "") != country:
            continue
        result.append(p)

    return jsonify(result)

@app.route("/api/parking/<int:parking_id>")
def api_parking_detail(parking_id):
    parkings = load_parkings()
    for p in parkings:
        if p["id"] == parking_id:
            return jsonify(p)
    return jsonify({"error": "Not found"}), 404

@app.route("/api/spots", methods=["GET"])
def api_spots_get():
    if not os.path.exists(SPOTS_PATH):
        return jsonify([])
    with open(SPOTS_PATH, encoding="utf-8") as f:
        return jsonify(json.load(f))

@app.route("/api/spots", methods=["POST"])
def api_spots_post():
    data = request.get_json(force=True)
    required = ["name","lat","lng","cat","stars"]
    for field in required:
        if field not in data:
            return jsonify({"error": f"Missing: {field}"}), 400

    with open(SPOTS_PATH, encoding="utf-8") as f:
        spots = json.load(f)

    new_id = max((s.get("id",0) for s in spots), default=0) + 1
    spot = {
        "id":    new_id,
        "name":  str(data["name"])[:100],
        "lat":   float(data["lat"]),
        "lng":   float(data["lng"]),
        "cat":   str(data["cat"])[:30],
        "desc":  str(data.get("desc",""))[:500],
        "stars": int(data["stars"]),
        "added": data.get("added",""),
    }
    spots.append(spot)
    with open(SPOTS_PATH, "w", encoding="utf-8") as f:
        json.dump(spots, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": new_id}), 201

@app.route("/api/route-pois")
def api_route_pois():
    """POI wzdłuż trasy: stacje, MOP, restauracje, autohof — Overpass API."""
    try:
        south = float(request.args.get("south", 47))
        west  = float(request.args.get("west",  8))
        north = float(request.args.get("north", 55))
        east  = float(request.args.get("east",  22))
    except ValueError:
        return jsonify({"error": "bad params"}), 400

    if (north - south) > 10 or (east - west) > 14:
        return jsonify([])

    bbox = f"{south},{west},{north},{east}"
    query = f"""
    [out:json][timeout:20];
    (
      node["amenity"="fuel"]({bbox});
      node["amenity"="fuel"]["hgv"="yes"]({bbox});
      node["highway"="rest_area"]({bbox});
      node["highway"="services"]({bbox});
      node["amenity"="parking"]["hgv"="yes"]({bbox});
      node["amenity"="parking"]["hgv"="designated"]({bbox});
      node["amenity"="restaurant"]({bbox});
      node["shop"="truck"]({bbox});
      node["amenity"="truck_wash"]({bbox});
      node["amenity"="shower"]({bbox});
    );
    out 120;
    """
    try:
        resp = _requests.post("https://overpass-api.de/api/interpreter",
                              data=query.strip(), timeout=22)
        elements = resp.json().get("elements", [])
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    POI_ICON = {
        "fuel":        "⛽", "rest_area":   "🅿️", "services": "🛣️",
        "parking":     "🅿️", "restaurant":  "🍽️", "truck_wash": "🚿",
        "shower":      "🚿", "truck":       "🔧",
    }
    results = []
    for el in elements:
        tags = el.get("tags", {})
        amenity = tags.get("amenity") or tags.get("highway") or tags.get("shop") or "poi"
        icon = POI_ICON.get(amenity, "📍")
        # Better label for fuel+hgv
        if amenity == "fuel" and tags.get("hgv") in ("yes","designated"):
            icon = "⛽🚛"
        name = tags.get("name") or tags.get("operator") or tags.get("brand") or amenity.replace("_"," ").title()
        results.append({
            "id":   f"poi_{el['id']}",
            "lat":  el.get("lat", 0),
            "lng":  el.get("lon", 0),
            "name": name,
            "type": amenity,
            "icon": icon,
            "hgv":  tags.get("hgv","") in ("yes","designated"),
        })
    return jsonify(results)


@app.route("/api/autobahn-parkings")
def api_autobahn_parkings():
    """Pobiera parkingi TIR z oficjalnego API Autobahn GmbH (rząd DE, bezpłatne)."""
    south = request.args.get("south", type=float, default=47.0)
    west  = request.args.get("west",  type=float, default=5.8)
    north = request.args.get("north", type=float, default=55.1)
    east  = request.args.get("east",  type=float, default=15.1)

    now = time.time()
    results = []
    for road in _AUTOBAHN_ROADS:
        # Serve from cache if fresh
        cached = _AUTOBAHN_CACHE.get(road)
        if cached and now - cached[0] < _AUTOBAHN_TTL:
            road_data = cached[1]
        else:
            try:
                r = _requests.get(
                    f"https://verkehr.autobahn.de/o/autobahn/{road}/services/parking_lorry",
                    timeout=8, headers={"Accept": "application/json"}
                )
                if r.status_code != 200:
                    continue
                rd = r.json()
                road_data = rd.get("parking_lorry", rd.get("parking", []))
                _AUTOBAHN_CACHE[road] = (now, road_data)
            except Exception:
                continue

        for p in road_data:
            try:
                lat = float(p["coordinate"]["lat"])
                lng = float(p["coordinate"]["long"])
            except (KeyError, ValueError, TypeError):
                continue
            # Bbox filter
            if not (south <= lat <= north and west <= lng <= east):
                continue

            # description is a list of strings
            raw_desc = p.get("description", [])
            desc_html = " · ".join(
                d if isinstance(d, str) else d.get("value","")
                for d in raw_desc if d
            )

            # Feature icons → amenities
            icons = [i.get("icon","") for i in p.get("lorryParkingFeatureIcons",[])]
            amenities = []
            icon_map = {
                "TOILETTEBLAU": "toilet", "RASTSTAETTEBLAU": "restaurant",
                "TANKSTELLEBLAU": "fuel",  "LKWWASCHEBLAU": "truck_wash",
                "WIFIBLAU": "wifi",        "DUSCHBLAU": "shower",
                "PARKPLATZLKWBLAU": "secured",
            }
            for icon in icons:
                if icon in icon_map:
                    amenities.append(icon_map[icon])

            results.append({
                "id":        f"ab_{road}_{p.get('identifier','')[:20]}",
                "name":      p.get("title", f"MOP {road}"),
                "subtitle":  p.get("subtitle",""),
                "lat":       lat,
                "lng":       lng,
                "country":   "DE",
                "road":      road,
                "type":      ["tir"],
                "amenities": amenities,
                "desc_html": desc_html[:400],
                "source":    "autobahn_de",
                "url":       f"https://www.autobahn.de/service/parken/",
            })

    return jsonify(results)


@app.route("/api/osm-parkings")
def api_osm_parkings():
    """Pobiera parkingi TIR/Camper z OpenStreetMap Overpass API dla widocznego obszaru mapy."""
    try:
        south = float(request.args.get("south", 47))
        west  = float(request.args.get("west",  8))
        north = float(request.args.get("north", 55))
        east  = float(request.args.get("east",  22))
        mode  = request.args.get("mode", "tir")
    except ValueError:
        return jsonify({"error": "bad params"}), 400

    # Ogranicz obszar żeby nie przeciążać Overpass
    if (north - south) > 8 or (east - west) > 12:
        return jsonify([])  # zbyt duży obszar — poczekaj na zoom

    bbox = f"{south},{west},{north},{east}"

    if mode == "tir":
        query = f"""
        [out:json][timeout:20];
        (
          node["amenity"="parking"]["hgv"="yes"]({bbox});
          node["amenity"="parking"]["hgv"="designated"]({bbox});
          node["highway"="rest_area"]["hgv"="yes"]({bbox});
          way["amenity"="parking"]["hgv"="yes"]({bbox});
        );
        out center 60;
        """
    elif mode == "camper":
        query = f"""
        [out:json][timeout:20];
        (
          node["tourism"="camp_site"]({bbox});
          node["amenity"="parking"]["motorhome"="yes"]({bbox});
          node["leisure"="slipway"]["motorhome"="yes"]({bbox});
        );
        out center 60;
        """
    else:  # tourist
        query = f"""
        [out:json][timeout:20];
        (
          node["tourism"="camp_site"]({bbox});
          node["tourism"="caravan_site"]({bbox});
          node["amenity"="parking"]["tourism"="yes"]({bbox});
        );
        out center 60;
        """

    try:
        resp = _requests.post(
            "https://overpass-api.de/api/interpreter",
            data=query.strip(), timeout=25
        )
        data = resp.json()
    except Exception as e:
        return jsonify({"error": str(e)}), 502

    results = []
    for el in data.get("elements", []):
        lat = el.get("lat") or (el.get("center", {}).get("lat"))
        lng = el.get("lon") or (el.get("center", {}).get("lon"))
        if not lat or not lng:
            continue
        tags = el.get("tags", {})
        name = tags.get("name") or tags.get("operator") or "Parking OSM"
        results.append({
            "id":       f"osm_{el['id']}",
            "name":     name,
            "lat":      lat,
            "lng":      lng,
            "type":     [mode],
            "country":  tags.get("addr:country", ""),
            "city":     tags.get("addr:city", tags.get("addr:town", "")),
            "address":  tags.get("addr:street", ""),
            "amenities": _parse_osm_amenities(tags),
            "price_eur": 0,
            "rating":    0,
            "spots_tir": int(tags.get("capacity:hgv", tags.get("capacity", 0)) or 0),
            "spots_camper": 0,
            "poi":       [],
            "source":    "osm",
            "osm_url":   f"https://www.openstreetmap.org/node/{el['id']}",
        })

    return jsonify(results)


def _parse_osm_amenities(tags):
    amenities = []
    if tags.get("shower") == "yes":        amenities.append("shower")
    if tags.get("toilets") == "yes":       amenities.append("toilet")
    if tags.get("restaurant"):             amenities.append("restaurant")
    if tags.get("wifi") == "yes":          amenities.append("wifi")
    if tags.get("electric_vehicle"):       amenities.append("electricity")
    if tags.get("hgv_wash") == "yes":      amenities.append("truck_wash")
    if tags.get("repair") == "yes":        amenities.append("repair")
    if tags.get("drinking_water")=="yes":  amenities.append("water")
    return amenities


@app.route("/api/comments")
def api_comments_get():
    parking_id = request.args.get("parking_id", "")
    if not os.path.exists(COMMENTS_PATH):
        return jsonify([])
    with open(COMMENTS_PATH, encoding="utf-8") as f:
        all_c = json.load(f)
    if parking_id:
        all_c = [c for c in all_c if str(c.get("parking_id")) == str(parking_id)]
    return jsonify(sorted(all_c, key=lambda x: x.get("date",""), reverse=True))

@app.route("/api/comments", methods=["POST"])
def api_comments_post():
    data = request.get_json(force=True)
    for field in ["parking_id","text","stars","user"]:
        if field not in data:
            return jsonify({"error": f"Missing: {field}"}), 400
    if not os.path.exists(COMMENTS_PATH):
        with open(COMMENTS_PATH,"w",encoding="utf-8") as f: json.dump([],f)
    with open(COMMENTS_PATH, encoding="utf-8") as f:
        comments = json.load(f)
    new_id = max((c.get("id",0) for c in comments), default=0) + 1
    comment = {
        "id":         new_id,
        "parking_id": str(data["parking_id"]),
        "user":       str(data["user"])[:30],
        "text":       str(data["text"])[:300],
        "stars":      max(1, min(5, int(data["stars"]))),
        "date":       data.get("date",""),
    }
    comments.append(comment)
    with open(COMMENTS_PATH,"w",encoding="utf-8") as f:
        json.dump(comments, f, ensure_ascii=False, indent=2)
    return jsonify({"ok":True,"id":new_id}), 201

OCC_TTL = 2 * 3600  # seconds

@app.route("/api/occupancy")
def api_occupancy_get():
    parking_id = request.args.get("parking_id", "")
    if not parking_id:
        return jsonify({"error": "missing parking_id"}), 400
    if not os.path.exists(OCCUPANCY_PATH):
        return jsonify({"free": 0, "busy": 0, "full": 0, "total": 0})
    with open(OCCUPANCY_PATH, encoding="utf-8") as f:
        all_votes = json.load(f)
    import time
    now = time.time()
    # Filter this parking, last 2h, deduplicate by ip (keep latest)
    relevant = [v for v in all_votes
                if str(v.get("parking_id")) == str(parking_id)
                and now - v.get("ts", 0) < OCC_TTL]
    # Deduplicate by voter_id (keep latest per voter)
    by_voter = {}
    for v in sorted(relevant, key=lambda x: x.get("ts", 0)):
        by_voter[v.get("voter_id", v.get("ts"))] = v["level"]
    cnt = {"free": 0, "busy": 0, "full": 0}
    for level in by_voter.values():
        if level in cnt:
            cnt[level] += 1
    cnt["total"] = cnt["free"] + cnt["busy"] + cnt["full"]
    return jsonify(cnt)

@app.route("/api/occupancy", methods=["POST"])
def api_occupancy_post():
    import time
    data = request.get_json(force=True)
    if not data.get("parking_id") or data.get("level") not in ("free", "busy", "full"):
        return jsonify({"error": "bad params"}), 400
    if not os.path.exists(OCCUPANCY_PATH):
        with open(OCCUPANCY_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(OCCUPANCY_PATH, encoding="utf-8") as f:
        votes = json.load(f)
    now = time.time()
    # Purge old votes (>2h) to keep file small
    votes = [v for v in votes if now - v.get("ts", 0) < OCC_TTL]
    # voter_id from client (random uuid stored in localStorage)
    voter_id = str(data.get("voter_id", request.remote_addr))[:64]
    votes.append({
        "parking_id": str(data["parking_id"]),
        "level":      data["level"],
        "voter_id":   voter_id,
        "ts":         now,
    })
    with open(OCCUPANCY_PATH, "w", encoding="utf-8") as f:
        json.dump(votes, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


MSG_TTL = 24 * 3600  # 24h

@app.route("/api/messages")
def api_messages_get():
    try:
        south = float(request.args.get("south", -90))
        west  = float(request.args.get("west",  -180))
        north = float(request.args.get("north",  90))
        east  = float(request.args.get("east",   180))
    except ValueError:
        return jsonify({"error": "bad params"}), 400

    if not os.path.exists(MESSAGES_PATH):
        return jsonify([])
    with open(MESSAGES_PATH, encoding="utf-8") as f:
        msgs = json.load(f)

    now = time.time()
    result = []
    for m in msgs:
        if now - m.get("ts", 0) > MSG_TTL:
            continue
        lat, lng = m.get("lat", 0), m.get("lng", 0)
        if south <= lat <= north and west <= lng <= east:
            result.append(m)
    return jsonify(sorted(result, key=lambda x: x.get("ts", 0), reverse=True))


@app.route("/api/messages", methods=["POST"])
def api_messages_post():
    data = request.get_json(force=True)
    for field in ["lat", "lng", "text", "cat"]:
        if field not in data:
            return jsonify({"error": f"Missing: {field}"}), 400

    if not os.path.exists(MESSAGES_PATH):
        with open(MESSAGES_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(MESSAGES_PATH, encoding="utf-8") as f:
        msgs = json.load(f)

    # Purge expired
    now = time.time()
    msgs = [m for m in msgs if now - m.get("ts", 0) < MSG_TTL]

    new_id = max((m.get("id", 0) for m in msgs), default=0) + 1
    msg = {
        "id":     new_id,
        "lat":    float(data["lat"]),
        "lng":    float(data["lng"]),
        "text":   str(data["text"])[:200],
        "cat":    str(data["cat"])[:20],
        "color":  str(data.get("color", "#3b82f6"))[:10],
        "emoji":  str(data.get("emoji", "🚛"))[:4],
        "ts":     now,
        "likes":  0,
        "dislikes": 0,
    }
    msgs.append(msg)
    with open(MESSAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=2)

    # Push do użytkowników w pobliżu (tylko alerty wysokiej ważności)
    if msg["cat"] in ("police", "accident", "help", "roadwork", "weather"):
        try:
            send_push_nearby(msg["lat"], msg["lng"], msg["cat"], msg["text"])
        except Exception:
            pass

    return jsonify({"ok": True, "id": new_id}), 201


@app.route("/api/messages/<int:msg_id>/react", methods=["POST"])
def api_messages_react(msg_id):
    data = request.get_json(force=True)
    reaction = data.get("reaction")  # "like" or "dislike"
    if reaction not in ("like", "dislike"):
        return jsonify({"error": "bad reaction"}), 400
    if not os.path.exists(MESSAGES_PATH):
        return jsonify({"error": "not found"}), 404
    with open(MESSAGES_PATH, encoding="utf-8") as f:
        msgs = json.load(f)
    for m in msgs:
        if m.get("id") == msg_id:
            if reaction == "like":
                m["likes"] = m.get("likes", 0) + 1
            else:
                m["dislikes"] = m.get("dislikes", 0) + 1
            break
    else:
        return jsonify({"error": "not found"}), 404
    with open(MESSAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True})


@app.route("/api/markets")
def api_markets():
    """Zwraca targi/flohmarkt z bazy danych."""
    if not os.path.exists(MARKETS_PATH):
        return jsonify([])
    with open(MARKETS_PATH, encoding="utf-8") as f:
        markets = json.load(f)
    country = request.args.get("country", "")
    state   = request.args.get("state", "")
    if country:
        markets = [m for m in markets if m.get("country", "DE") == country]
    if state:
        markets = [m for m in markets if m.get("state", "") == state]
    return jsonify(markets)


@app.route("/api/scenic")
def api_scenic():
    """Zwraca punkty widokowe / piękne widoki."""
    if not os.path.exists(SCENIC_PATH):
        return jsonify([])
    with open(SCENIC_PATH, encoding="utf-8") as f:
        scenic = json.load(f)
    country = request.args.get("country", "")
    stype   = request.args.get("type", "")
    if country:
        scenic = [s for s in scenic if s.get("country", "") == country]
    if stype:
        scenic = [s for s in scenic if s.get("type", "") == stype]
    return jsonify(scenic)


@app.route("/api/vapid-public-key")
def api_vapid_public_key():
    return jsonify({"key": VAPID_PUBLIC_KEY})

@app.route("/api/push/subscribe", methods=["POST"])
def api_push_subscribe():
    data = request.get_json(force=True)
    if not data.get("subscription"):
        return jsonify({"error": "missing subscription"}), 400
    subs = load_subscriptions()
    sub_id = data.get("id") or secrets.token_hex(8)
    # aktualizuj jeśli istnieje, dodaj jeśli nowe
    existing = next((s for s in subs if s.get("id") == sub_id), None)
    entry = {
        "id":           sub_id,
        "subscription": data["subscription"],
        "lat":          data.get("lat"),
        "lng":          data.get("lng"),
        "ts":           time.time(),
    }
    if existing:
        existing.update(entry)
    else:
        subs.append(entry)
    save_subscriptions(subs)
    return jsonify({"ok": True, "id": sub_id})

@app.route("/api/push/update-position", methods=["POST"])
def api_push_update_position():
    data = request.get_json(force=True)
    sub_id = data.get("id")
    lat, lng = data.get("lat"), data.get("lng")
    if not sub_id or lat is None or lng is None:
        return jsonify({"error": "missing fields"}), 400
    subs = load_subscriptions()
    for s in subs:
        if s.get("id") == sub_id:
            s["lat"], s["lng"], s["ts"] = lat, lng, time.time()
            break
    save_subscriptions(subs)
    return jsonify({"ok": True})

@app.route("/api/push/unsubscribe", methods=["POST"])
def api_push_unsubscribe():
    data = request.get_json(force=True)
    sub_id = data.get("id")
    if not sub_id:
        return jsonify({"error": "missing id"}), 400
    subs = [s for s in load_subscriptions() if s.get("id") != sub_id]
    save_subscriptions(subs)
    return jsonify({"ok": True})


if __name__ == "__main__":
    app.run(debug=True, port=5002)
