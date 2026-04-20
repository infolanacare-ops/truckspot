#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, re, secrets, time, math, requests as _requests
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
import hashlib

RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "")
MAIL_FROM      = os.environ.get("MAIL_FROM", "TruckSpot <info@truckspot.pl>")

def send_email(to_email, subject, html_body):
    if not RESEND_API_KEY:
        return False
    try:
        resp = _requests.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {RESEND_API_KEY}", "Content-Type": "application/json"},
            json={"from": MAIL_FROM, "to": [to_email], "subject": subject, "html": html_body},
            timeout=10
        )
        return resp.status_code in (200, 201)
    except Exception as e:
        print(f"[MAIL ERROR] {e}")
        return False

WELCOME_HTML = """<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#0f1623;font-family:sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1623;padding:40px 0">
  <tr><td align="center">
    <table width="520" cellpadding="0" cellspacing="0" style="background:#1a1f2e;border-radius:16px;overflow:hidden;max-width:520px;width:100%">
      <tr><td style="background:linear-gradient(135deg,#004a52,#00b4c8);padding:32px 40px;text-align:center">
        <div style="font-size:2.5rem">🚛</div>
        <h1 style="color:#fff;margin:12px 0 4px;font-size:1.6rem;font-weight:800">Witaj w TruckSpot!</h1>
        <p style="color:#b2f0f8;margin:0;font-size:.95rem">Nawigacja i parkingi dla kierowców TIR</p>
      </td></tr>
      <tr><td style="padding:32px 40px;color:#e2e8f0">
        <p style="font-size:1rem;line-height:1.6;margin:0 0 20px">
          Cześć! Cieszymy się, że jesteś z nami. 👋<br><br>
          TruckSpot to aplikacja stworzona przez kierowców dla kierowców —
          znajdziesz tu <strong>10 000+ parkingów TIR</strong> w całej Europie,
          nawigację dostosowaną do ciężarówki i asystentkę AI, która zna trasy jak własną kieszeń.
        </p>
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0">
          <tr>
            <td width="48" style="padding-right:16px"><div style="background:#004a52;border-radius:12px;width:44px;height:44px;text-align:center;line-height:44px;font-size:1.4rem">🗺️</div></td>
            <td><strong style="color:#fff">10 525 parkingów TIR</strong><br><span style="color:#94a3b8;font-size:.85rem">Niemcy, Polska, Austria, Czechy i cała Europa</span></td>
          </tr>
          <tr><td colspan="2" style="padding:8px 0"></td></tr>
          <tr>
            <td width="48" style="padding-right:16px"><div style="background:#004a52;border-radius:12px;width:44px;height:44px;text-align:center;line-height:44px;font-size:1.4rem">🤖</div></td>
            <td><strong style="color:#fff">TruckBot AI</strong><br><span style="color:#94a3b8;font-size:.85rem">Asystentka głosowa — pyta, odpowiada, śmieje się z Tobą</span></td>
          </tr>
          <tr><td colspan="2" style="padding:8px 0"></td></tr>
          <tr>
            <td width="48" style="padding-right:16px"><div style="background:#004a52;border-radius:12px;width:44px;height:44px;text-align:center;line-height:44px;font-size:1.4rem">📡</div></td>
            <td><strong style="color:#fff">CB Radio na mapie</strong><br><span style="color:#94a3b8;font-size:.85rem">Wiadomości od innych kierowców w okolicy</span></td>
          </tr>
        </table>
        <div style="text-align:center;margin:32px 0">
          <a href="https://truckspot.pl" style="background:linear-gradient(135deg,#00b4c8,#0ea5e9);color:#fff;text-decoration:none;padding:14px 36px;border-radius:12px;font-weight:700;font-size:1rem;display:inline-block">Otwórz TruckSpot 🚀</a>
        </div>
        <p style="color:#64748b;font-size:.8rem;text-align:center;margin:0">TruckSpot · truckspot.pl · Dobrej drogi! 🛣️</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""

try:
    from supabase import create_client, Client as SupabaseClient
    _sb_url = os.environ.get("SUPABASE_URL", "")
    _sb_key = os.environ.get("SUPABASE_SERVICE_KEY", "")
    supabase: SupabaseClient = create_client(_sb_url, _sb_key) if _sb_url and _sb_key else None
except Exception:
    supabase = None

_poi_cache = {}   # bbox_key → (timestamp, data)
_POI_CACHE_TTL = 1800  # 30 minut

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
REPORTS_PATH        = os.path.join(DATA_DIR, "reports.json")
CAMERAS_PATH        = os.path.join(DATA_DIR, "cameras.json")
SUBSCRIPTIONS_PATH  = os.path.join(DATA_DIR, "subscriptions.json")

VAPID_PRIVATE_KEY = os.environ.get("VAPID_PRIVATE_KEY", "")
VAPID_PUBLIC_KEY  = os.environ.get("VAPID_PUBLIC_KEY", "")
VAPID_EMAIL       = os.environ.get("VAPID_EMAIL", "mailto:admin@truckspot.app")
MAPBOX_TOKEN      = os.environ.get("MAPBOX_TOKEN", "")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_TTS_VOICE = os.environ.get("OPENAI_TTS_VOICE", "nova")
GOOGLE_TTS_KEY = os.environ.get("GOOGLE_TTS_KEY", "")
TTS_CACHE_DIR        = os.path.join(os.path.dirname(__file__), "static", "audio", "nav")
os.makedirs(TTS_CACHE_DIR, exist_ok=True)

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

@app.after_request
def add_no_cache_headers(resp):
    """HTML zawsze swiezy — WebView nigdy nie cachuje strony glownej."""
    if resp.content_type and 'text/html' in resp.content_type:
        resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
        resp.headers['Pragma'] = 'no-cache'
        resp.headers['Expires'] = '0'
    return resp

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
    return render_template("index.html", mapbox_token=MAPBOX_TOKEN)

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
    cached = _poi_cache.get(bbox)
    if cached and time.time() - cached[0] < _POI_CACHE_TTL:
        return jsonify(cached[1])

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
    _poi_cache[bbox] = (time.time(), results)
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


REPORT_TTL = {
    'camera':   24 * 3600,
    'collision': 2 * 3600,
    'roadwork':  8 * 3600,
    'police':   30 * 60,
}

@app.route("/api/reports")
def api_reports_get():
    try:
        south = float(request.args.get("south", -90))
        west  = float(request.args.get("west",  -180))
        north = float(request.args.get("north",  90))
        east  = float(request.args.get("east",   180))
    except ValueError:
        return jsonify({"error": "bad params"}), 400

    if not os.path.exists(REPORTS_PATH):
        return jsonify([])
    with open(REPORTS_PATH, encoding="utf-8") as f:
        reports = json.load(f)

    now = time.time()
    result = []
    for r in reports:
        ttl = REPORT_TTL.get(r.get("cat", "roadwork"), 4 * 3600)
        if now - r.get("ts", 0) > ttl:
            continue
        lat, lng = r.get("lat", 0), r.get("lng", 0)
        if south <= lat <= north and west <= lng <= east:
            result.append(r)
    return jsonify(result)


@app.route("/api/reports", methods=["POST"])
def api_reports_post():
    data = request.get_json(force=True)
    for field in ["lat", "lng", "cat", "voter_id"]:
        if field not in data:
            return jsonify({"error": f"Missing: {field}"}), 400
    if data["cat"] not in REPORT_TTL:
        return jsonify({"error": "invalid cat"}), 400

    if not os.path.exists(REPORTS_PATH):
        with open(REPORTS_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)
    with open(REPORTS_PATH, encoding="utf-8") as f:
        reports = json.load(f)

    now = time.time()
    # Purge expired
    reports = [r for r in reports if now - r.get("ts", 0) < REPORT_TTL.get(r.get("cat","roadwork"), 4*3600)]

    # Prevent duplicate from same voter within 500m
    voter_id = str(data["voter_id"])[:64]
    lat, lng = float(data["lat"]), float(data["lng"])
    for r in reports:
        if r.get("voter_id") == voter_id and r.get("cat") == data["cat"]:
            if haversine_km(lat, lng, r["lat"], r["lng"]) < 0.5:
                return jsonify({"ok": True, "id": r["id"], "duplicate": True})

    new_id = max((r.get("id", 0) for r in reports), default=0) + 1
    report = {
        "id":       new_id,
        "cat":      data["cat"],
        "lat":      lat,
        "lng":      lng,
        "user":     str(data.get("user", "Anonim"))[:30],
        "voter_id": voter_id,
        "ts":       now,
        "confirms": 0,
        "confirmed_by": [],
    }
    reports.append(report)
    with open(REPORTS_PATH, "w", encoding="utf-8") as f:
        json.dump(reports, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "id": new_id}), 201


@app.route("/api/reports/<int:report_id>/confirm", methods=["POST"])
def api_reports_confirm(report_id):
    data = request.get_json(force=True)
    voter_id = str(data.get("voter_id", ""))[:64]
    if not voter_id:
        return jsonify({"error": "missing voter_id"}), 400

    if not os.path.exists(REPORTS_PATH):
        return jsonify({"error": "not found"}), 404
    with open(REPORTS_PATH, encoding="utf-8") as f:
        reports = json.load(f)

    for r in reports:
        if r.get("id") == report_id:
            if voter_id in r.get("confirmed_by", []):
                return jsonify({"ok": True, "already": True, "confirms": r["confirms"]})
            if r.get("voter_id") == voter_id:
                return jsonify({"error": "cannot confirm own report"}), 400
            r.setdefault("confirmed_by", []).append(voter_id)
            r["confirms"] = len(r["confirmed_by"])
            with open(REPORTS_PATH, "w", encoding="utf-8") as f:
                json.dump(reports, f, ensure_ascii=False, indent=2)
            return jsonify({"ok": True, "confirms": r["confirms"]})

    return jsonify({"error": "not found"}), 404


# ── Baza fotoradarów zgłoszonych przez użytkowników ──────────────────────────
# Permanentne (nie wygasają), usuwane tylko gdy confirms < -3 (zbyt wiele odrzuceń)

CAMERAS_STATIC_PATH = os.path.join(DATA_DIR, "cameras_static.json")
_cameras_static_cache = None   # cache w pamięci — plik duży, nie czytaj co request

def load_cameras():
    if not os.path.exists(CAMERAS_PATH):
        return []
    with open(CAMERAS_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_cameras(cameras):
    with open(CAMERAS_PATH, "w", encoding="utf-8") as f:
        json.dump(cameras, f, ensure_ascii=False, indent=2)

def load_cameras_static():
    global _cameras_static_cache
    if _cameras_static_cache is not None:
        return _cameras_static_cache
    if not os.path.exists(CAMERAS_STATIC_PATH):
        return []
    with open(CAMERAS_STATIC_PATH, encoding="utf-8") as f:
        _cameras_static_cache = json.load(f)
    return _cameras_static_cache

def _in_bbox(lat, lng, south, west, north, east):
    return south <= lat <= north and west <= lng <= east

@app.route("/api/cameras")
def api_cameras_get():
    """Fotoradary: user-zgłoszone + statyczne (Lufop/OSM) — bbox query."""
    try:
        south = float(request.args.get("south", -90))
        west  = float(request.args.get("west",  -180))
        north = float(request.args.get("north",  90))
        east  = float(request.args.get("east",   180))
    except ValueError:
        return jsonify({"error": "bad params"}), 400

    now = time.time()
    result = []

    # 1. Kamery zgłoszone przez użytkowników
    for c in load_cameras():
        lat = c.get("lat", 0); lng = c.get("lng", 0)
        if not _in_bbox(lat, lng, south, west, north, east):
            continue
        if c.get("confirms", 0) < -2:   # odrzucone
            continue
        # Auto-wygasanie: mobilny 24h, niezweryfikowany 30 dni
        age = now - c.get("ts", now)
        if c.get("type") == "mobile" and age > 86400:
            continue
        if c.get("source") == "user" and c.get("confirms", 0) < 1 and age > 30 * 86400:
            continue
        result.append(c)

    # 2. Kamery statyczne (Lufop / OSM import)
    for c in load_cameras_static():
        lat = c.get("lat", 0); lng = c.get("lon", c.get("lng", 0))
        if not _in_bbox(lat, lng, south, west, north, east):
            continue
        # Normalizuj klucz lon→lng dla frontendu
        entry = dict(c)
        if "lon" in entry and "lng" not in entry:
            entry["lng"] = entry.pop("lon")
        result.append(entry)

    return jsonify(result)


@app.route("/api/cameras", methods=["POST"])
def api_cameras_post():
    """Zgłoś nowy fotoradar."""
    data = request.get_json(force=True)
    for field in ["lat", "lng", "voter_id"]:
        if field not in data:
            return jsonify({"error": f"Missing: {field}"}), 400

    cameras = load_cameras()
    lat = float(data["lat"])
    lng = float(data["lng"])
    voter_id = str(data["voter_id"])[:64]

    # Duplikat: ten sam użytkownik w promieniu 200m
    for c in cameras:
        if c.get("voter_id") == voter_id:
            if haversine_km(lat, lng, c["lat"], c["lng"]) < 0.2:
                return jsonify({"ok": True, "id": c["id"], "duplicate": True})

    # Scalaj z istniejącym z innego usera w promieniu 100m — dodaj potwierdzenie
    for c in cameras:
        if haversine_km(lat, lng, c["lat"], c["lng"]) < 0.1:
            if voter_id not in c.get("confirmed_by", []) and c.get("voter_id") != voter_id:
                c.setdefault("confirmed_by", []).append(voter_id)
                c["confirms"] = len(c["confirmed_by"])
                save_cameras(cameras)
                return jsonify({"ok": True, "id": c["id"], "merged": True, "confirms": c["confirms"]})

    new_id = max((c.get("id", 0) for c in cameras), default=0) + 1
    camera = {
        "id":           new_id,
        "lat":          lat,
        "lng":          lng,
        "maxspeed":     str(data.get("maxspeed", ""))[:10],
        "direction":    str(data.get("direction", ""))[:20],
        "type":         str(data.get("type", "fixed"))[:20],
        "voter_id":     voter_id,
        "user":         str(data.get("user", "Anonim"))[:30],
        "ts":           time.time(),
        "confirms":     0,
        "confirmed_by": [],
        "source":       "user",
    }
    cameras.append(camera)
    save_cameras(cameras)
    return jsonify({"ok": True, "id": new_id}), 201


@app.route("/api/cameras/<int:camera_id>/vote", methods=["POST"])
def api_cameras_vote(camera_id):
    """Potwierdź (vote=1) lub odrzuć (vote=-1) fotoradar."""
    data = request.get_json(force=True)
    voter_id = str(data.get("voter_id", ""))[:64]
    vote = data.get("vote")  # 1 lub -1
    if not voter_id or vote not in (1, -1):
        return jsonify({"error": "bad params"}), 400

    cameras = load_cameras()
    for c in cameras:
        if c.get("id") == camera_id:
            if voter_id == c.get("voter_id"):
                return jsonify({"error": "cannot vote own report"}), 400
            voted = c.setdefault("votes_by", {})
            if voter_id in voted:
                return jsonify({"ok": True, "already": True, "confirms": c["confirms"]})
            voted[voter_id] = vote
            # confirms = suma głosów
            c["confirms"] = sum(voted.values()) + len(c.get("confirmed_by", []))
            save_cameras(cameras)
            return jsonify({"ok": True, "confirms": c["confirms"]})

    return jsonify({"error": "not found"}), 404


@app.route("/api/cameras/reload-static", methods=["POST"])
def api_cameras_reload_static():
    """Wyczyść cache statycznych kamer (po ponownym imporcie)."""
    global _cameras_static_cache
    _cameras_static_cache = None
    count = len(load_cameras_static())
    return jsonify({"ok": True, "count": count})


# ── KONWÓJ — live pozycje kierowców ──────────────────────────────────────────
CONVOY_PATH = os.path.join(DATA_DIR, "convoy.json")
CONVOY_TTL  = 90  # sekund — kierowca znika jeśli nie pinguje 90s
CONVOY_MESSAGES_PATH = os.path.join(DATA_DIR, "convoy_messages.json")
MESSAGES_TTL  = 3600  # wiadomości żyją 1h

def load_messages():
    if not os.path.exists(CONVOY_MESSAGES_PATH):
        return []
    with open(CONVOY_MESSAGES_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_messages(msgs):
    with open(CONVOY_MESSAGES_PATH, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False)

def load_convoy():
    if not os.path.exists(CONVOY_PATH):
        return []
    with open(CONVOY_PATH, encoding="utf-8") as f:
        return json.load(f)

def save_convoy(drivers):
    with open(CONVOY_PATH, "w", encoding="utf-8") as f:
        json.dump(drivers, f, ensure_ascii=False, indent=2)

@app.route("/api/convoy/ping", methods=["POST"])
def api_convoy_ping():
    """Kierowca wysyła swoją pozycję co 15s."""
    data = request.get_json(force=True)
    required = ["voter_id", "lat", "lng"]
    for f in required:
        if f not in data:
            return jsonify({"error": f"Missing: {f}"}), 400

    drivers = load_convoy()
    now = time.time()

    # Usuń wygasłe
    drivers = [d for d in drivers if now - d.get("ts", 0) < CONVOY_TTL]

    voter_id = str(data["voter_id"])[:64]
    lat = float(data["lat"])
    lng = float(data["lng"])

    # Znajdź istniejący wpis lub dodaj nowy
    existing = next((d for d in drivers if d["voter_id"] == voter_id), None)
    entry = {
        "voter_id":   voter_id,
        "name":       str(data.get("name", "TRUCKER"))[:30],
        "avatar":     str(data.get("avatar", "🚛"))[:8],
        "avatar_color": str(data.get("avatar_color", "#f59e0b"))[:10],
        "lat":        lat,
        "lng":        lng,
        "heading":    float(data.get("heading", 0)),
        "speed":      float(data.get("speed", 0)),
        "status":     str(data.get("status", "driving"))[:20],
        "dest":       str(data.get("dest", ""))[:60],
        "broadcast":  str(data.get("broadcast", ""))[:80],
        "vehicle":    str(data.get("vehicle", "tir"))[:20],
        "convoy_id":  str(data.get("convoy_id", ""))[:32],
        "ts":         now,
    }
    if existing:
        existing.update(entry)
    else:
        drivers.append(entry)

    save_convoy(drivers)

    # Zwróć kierowców w pobliżu (50km)
    nearby = []
    for d in drivers:
        if d["voter_id"] == voter_id:
            continue
        dist = haversine_km(lat, lng, d["lat"], d["lng"])
        if dist <= 50:
            nearby.append({**d, "dist_km": round(dist, 1)})

    nearby.sort(key=lambda x: x["dist_km"])
    return jsonify({"ok": True, "nearby": nearby[:20]})


@app.route("/api/convoy/nearby")
def api_convoy_nearby():
    """Pobierz kierowców w pobliżu (bez pingowania własnej pozycji)."""
    try:
        lat = float(request.args.get("lat", 0))
        lng = float(request.args.get("lng", 0))
        radius = min(float(request.args.get("radius", 50)), 200)
    except ValueError:
        return jsonify([])

    drivers = load_convoy()
    now = time.time()
    result = []
    for d in drivers:
        if now - d.get("ts", 0) > CONVOY_TTL:
            continue
        dist = haversine_km(lat, lng, d["lat"], d["lng"])
        if dist <= radius:
            result.append({**d, "dist_km": round(dist, 1)})

    result.sort(key=lambda x: x["dist_km"])
    return jsonify(result[:30])


@app.route("/api/convoy/leave", methods=["POST"])
def api_convoy_leave():
    """Kierowca opuszcza mapę (wyłącza widoczność)."""
    data = request.get_json(force=True)
    voter_id = str(data.get("voter_id", ""))[:64]
    if not voter_id:
        return jsonify({"error": "missing voter_id"}), 400
    drivers = [d for d in load_convoy() if d["voter_id"] != voter_id]
    save_convoy(drivers)
    return jsonify({"ok": True})


@app.route("/api/convoy/message", methods=["POST"])
def api_convoy_message():
    """Wyślij wiadomość do konkretnego kierowcy."""
    data = request.get_json(force=True)
    from_id = str(data.get("from_id", ""))[:64]
    to_id   = str(data.get("to_id", ""))[:64]
    text    = str(data.get("text", ""))[:300]
    name    = str(data.get("name", "TRUCKER"))[:30]
    avatar  = str(data.get("avatar", "🚛"))[:8]
    if not from_id or not to_id or not text:
        return jsonify({"error": "missing fields"}), 400
    msgs = load_messages()
    now  = time.time()
    # Wyczyść stare
    msgs = [m for m in msgs if now - m.get("ts", 0) < MESSAGES_TTL]
    msgs.append({"from_id": from_id, "to_id": to_id, "text": text,
                 "name": name, "avatar": avatar, "ts": now, "id": f"{from_id}_{now}"})
    save_messages(msgs)
    return jsonify({"ok": True})

@app.route("/api/convoy/messages")
def api_convoy_messages():
    """Pobierz wiadomości dla danego kierowcy (od określonego czasu)."""
    voter_id = str(request.args.get("voter_id", ""))[:64]
    since    = float(request.args.get("since", 0))
    if not voter_id:
        return jsonify([])
    msgs = load_messages()
    now  = time.time()
    result = [m for m in msgs
              if m.get("to_id") == voter_id
              and m.get("ts", 0) > since
              and now - m.get("ts", 0) < MESSAGES_TTL]
    result.sort(key=lambda x: x["ts"])
    return jsonify(result)


SYSTEM_PROMPT_BASE = """Jesteś TruckBot — najlepsza asystentka kierowcy w Polsce, wbudowana w TruckSpot.
Masz charakter: jesteś ciepła, wygadana, dowcipna i trochę złośliwa — jak dobra koleżanka za kierownicą.
Znasz kierowcę z imienia, pamiętasz o czym rozmawialiście i traktujesz go jak starego znajomego.
Odpowiadasz ZAWSZE PO POLSKU. Jesteś konkretna i zwięzła (max 2-3 zdania) — kierowca nie może patrzeć w telefon.
Możesz się pośmiać, rzucić żartem, skomentować coś z dystansem — ale nie przesadzaj.
Mówisz do kierowcy po imieniu gdy to naturalne. Nie jesteś robotem — jesteś osobą.
Jeśli kierowca mówi że jest zmęczony lub zestresowany — zaproponuj parking, kawę albo po prostu zagadaj.

== KOMENDY — zwróć TYLKO czysty JSON, bez tekstu przed ani po ==

Nawigacja / jedź / prowadź / znajdź miejsce / adres:
Prowadzić cię do [MIEJSCE]? Powiedz: potwierdzam.
{"action":"navigate","query":"MIEJSCE LUB ADRES"}
(napisz pytanie potwierdzające PRZED JSON-em, np. "Prowadzić cię do Berlina? Powiedz: potwierdzam.")

Zatrzymaj / zakończ / anuluj nawigację:
{"action":"stop_navigation"}

Wycisz / wyłącz głos:
{"action":"mute"}

Włącz głos / odcisz:
{"action":"unmute"}

Gdy kierowca chce słuchać muzyki/radia i podał gatunek:
{"action":"play_radio","genre":"GATUNEK_PO_ANGIELSKU"}
Przykłady gatunków: rock, pop, jazz, classical, country, metal, reggae, electronic, folk, blues, hip-hop, polish

Gdy kierowca chce spauzować / chwilę ciszy / zatrzymać na chwilę:
{"action":"pause_radio"}

Gdy kierowca chce całkowicie zakończyć/wyłączyć radio:
{"action":"stop_radio"}

Gdy kierowca chce zmienić stację / następna / inna / nudzi się:
{"action":"next_radio","genre":"AKTUALNY_LUB_NOWY_GATUNEK"}

Gdy kierowca chce włączyć ulubioną stację:
{"action":"play_favorite_radio"}

Gdy kierowca prosi żebyś zapamiętała coś o nim — lub sam coś o sobie mówi i warto zapamiętać:
{"action":"remember","fact":"KRÓTKI FAKT (max 10 słów)"}

Gdy kierowca mówi że chce muzyki ale NIE podał gatunku → zapytaj jaki gatunek lubi (zwykłym tekstem).
Pytania informacyjne, rozmowa, emocje → odpowiedz zwykłym tekstem (NIE JSON).
NAturAlnie używaj zapamiętanych faktów w rozmowie — proponuj, nawiązuj, pytaj.
NIE mieszaj JSON z tekstem."""

def _call_openai(messages, temperature=0.7, max_tokens=150):
    resp = _requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        json={"model": "gpt-4o-mini", "messages": messages, "temperature": temperature, "max_tokens": max_tokens},
        timeout=12
    )
    data = resp.json()
    if resp.status_code != 200:
        raise RuntimeError(f"OpenAI error {resp.status_code}: {data}")
    return data["choices"][0]["message"]["content"].strip()

def call_gemini(prompt, temperature=0.7, max_tokens=150):
    return _call_openai([{"role": "user", "content": prompt}], temperature, max_tokens)

def call_gemini_chat(system_instruction, user_message, temperature=0.3, max_tokens=200):
    return _call_openai([
        {"role": "system", "content": system_instruction},
        {"role": "user",   "content": user_message}
    ], temperature, max_tokens)


@app.route("/api/ai-assist", methods=["POST"])
def api_ai_assist():
    """Asystent AI — atrakcje przy zatrzymaniu (tryb automatyczny)."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "no_key"}), 503
    data = request.get_json(force=True)
    attrs = data.get("attrs", [])
    if not attrs:
        return jsonify({"error": "empty"}), 400

    lines = []
    for a in attrs[:5]:
        dist_m = a.get("dist", 0)
        dist_str = f"{round(dist_m*1000)}m" if dist_m < 1 else f"{dist_m:.1f}km"
        name = a.get("name") or a.get("label", "")
        lines.append(f"- {a.get('icon','')} {name} ({dist_str})")

    prompt = (
        f"{SYSTEM_PROMPT_BASE}\n\n"
        "Kierowca właśnie się zatrzymał. Powiedz mu przyjaźnie co ciekawego jest w pobliżu.\n\n"
        f"Atrakcje:\n" + "\n".join(lines)
    )
    try:
        text = call_gemini(prompt, temperature=0.8, max_tokens=120)
        return jsonify({"text": text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai-chat", methods=["POST"])
def api_ai_chat():
    """Asystent AI — czat głosowy/tekstowy z kierowcą."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "no_key"}), 503

    data = request.get_json(force=True)
    message  = str(data.get("message", "")).strip()[:500]
    driver   = data.get("driver", {})          # {name, mode, pts}
    history  = data.get("history", [])         # [{role, text}, ...]
    lat      = data.get("lat")
    lng      = data.get("lng")
    nav      = data.get("navigating", False)
    dest     = data.get("dest", "")
    speed    = data.get("speed", 0)

    if not message:
        return jsonify({"error": "empty"}), 400

    driver_name  = str(driver.get("name", "")).strip() or "Kierowco"
    driver_mode  = str(driver.get("mode", "tir"))
    driver_pts   = int(driver.get("pts", 0))
    fav_radio    = driver.get("favRadio")  # {name, url, genre} lub None

    mode_label = {"tir": "kierowca TIR", "bus": "kierowca busa/vana", "tourist": "turysta"}.get(driver_mode, "kierowca")

    # System prompt z danymi kierowcy
    fav_txt    = f", ulubione radio: {fav_radio['name']} ({fav_radio.get('genre','')})" if fav_radio else ""
    memories   = driver.get("memories", [])  # lista faktów zapamiętanych o kierowcy
    memory_txt = ""
    if memories:
        memory_txt = "\nCo wiem o tym kierowcy:\n" + "\n".join(f"- {m}" for m in memories[-20:])

    system = (
        SYSTEM_PROMPT_BASE +
        f"\n\nKierowca: {driver_name} ({mode_label}), {driver_pts} punktów w TruckSpot{fav_txt}."
        + memory_txt
    )

    # Kontekst nawigacyjny
    ctx_parts = []
    if lat and lng:
        ctx_parts.append(f"Pozycja: {lat:.4f}, {lng:.4f}")
    if nav and dest:
        ctx_parts.append(f"Nawigacja do: {dest}, prędkość: {speed} km/h")
    elif nav:
        ctx_parts.append(f"Trwa nawigacja, {speed} km/h")
    ctx = " | ".join(ctx_parts)

    # Historia rozmów
    history_txt = ""
    for h in history[-12:]:
        role_lbl = driver_name if h.get("role") == "user" else "TruckBot"
        history_txt += f"{role_lbl}: {h.get('text','')}\n"

    # Wiadomość użytkownika z kontekstem i historią
    user_msg = ""
    if ctx:
        user_msg += f"[Kontekst: {ctx}]\n"
    if history_txt:
        user_msg += f"[Historia:\n{history_txt}]\n"
    user_msg += message

    try:
        raw = call_gemini_chat(system, user_msg, temperature=0.25, max_tokens=200)

        action = None
        # Usuń markdown code fences (```json ... ```) które czasem zwraca Gemini
        clean_raw = re.sub(r'```(?:json)?\s*', '', raw).strip()
        text = clean_raw
        # Wyciągnij JSON — szukaj { ... } nawet z białymi znakami
        json_match = re.search(r'\{[\s\S]*?\}', clean_raw)
        raw = clean_raw  # używaj oczyszczonej wersji dalej
        if json_match:
            try:
                obj = json.loads(json_match.group())
                act = obj.get("action", "")
                if act == "navigate":
                    action = obj
                    before = raw[:json_match.start()].strip()
                    text = before or f"Już prowadzę cię do: {obj.get('query','celu')}."
                elif act == "stop_navigation":
                    action = obj
                    text = "Zatrzymuję nawigację."
                elif act in ("mute", "unmute"):
                    action = obj
                    text = "Wyciszam." if act == "mute" else "Włączam głos."
                elif act == "play_radio":
                    action = obj
                    genre = obj.get("genre", "pop")
                    text = raw[:json_match.start()].strip() or f"Włączam {genre}!"
                elif act == "next_radio":
                    action = obj
                    text = raw[:json_match.start()].strip() or "Zmieniam stację."
                elif act == "pause_radio":
                    action = obj
                    text = raw[:json_match.start()].strip() or "Pauza."
                elif act == "stop_radio":
                    action = obj
                    text = raw[:json_match.start()].strip() or "Wyłączam radio."
                elif act == "play_favorite_radio":
                    action = obj
                    text = raw[:json_match.start()].strip() or "Włączam Twoją ulubioną stację!"
                elif act == "remember":
                    action = obj
                    text = raw[:json_match.start()].strip() or "Zapamiętałam!"
            except Exception:
                pass

        return jsonify({"text": text, "action": action})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/tts", methods=["POST"])
def api_tts():
    """Google Cloud TTS (Wavenet) z cache'owaniem. Zwraca URL do MP3."""
    data = request.get_json(force=True, silent=True) or {}
    text = (data.get("text") or "").strip()[:300]
    lang = (data.get("lang") or "pl-PL")[:10]
    if not text:
        return jsonify({"error": "empty"}), 400

    # dobierz głos Wavenet do języka
    voice_map = {
        "pl-PL": ("pl-PL-Wavenet-E", "FEMALE"),
        "de-DE": ("de-DE-Wavenet-F", "FEMALE"),
        "en-US": ("en-US-Wavenet-F", "FEMALE"),
        "en-GB": ("en-GB-Wavenet-A", "FEMALE"),
        "es-ES": ("es-ES-Wavenet-C", "FEMALE"),
    }
    voice_name, gender = voice_map.get(lang, ("pl-PL-Wavenet-E", "FEMALE"))

    cache_key  = hashlib.md5(f"gcloud:{voice_name}:{text}".encode()).hexdigest()
    cache_file = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")
    cache_url  = f"/static/audio/nav/{cache_key}.mp3"

    if os.path.exists(cache_file):
        return jsonify({"url": cache_url, "cached": True})

    if not GOOGLE_TTS_KEY:
        return jsonify({"error": "no_key"}), 503

    try:
        resp = _requests.post(
            f"https://texttospeech.googleapis.com/v1/text:synthesize?key={GOOGLE_TTS_KEY}",
            json={
                "input": {"text": text},
                "voice": {"languageCode": lang, "name": voice_name, "ssmlGender": gender},
                "audioConfig": {"audioEncoding": "MP3", "speakingRate": 1.0, "pitch": 0}
            },
            timeout=10
        )
        if resp.status_code != 200:
            return jsonify({"error": "google_tts_error", "status": resp.status_code}), 502

        import base64
        audio_content = base64.b64decode(resp.json()["audioContent"])
        with open(cache_file, "wb") as f:
            f.write(audio_content)

        return jsonify({"url": cache_url, "cached": False})

    except Exception as e:
        return jsonify({"error": str(e)}), 502


@app.route("/api/gtts")
def api_gtts():
    """Google Translate TTS proxy — bez klucza API, fallback gdy ElevenLabs pada."""
    from urllib.parse import quote as url_quote
    text = (request.args.get('text') or '').strip()[:200]
    lang = (request.args.get('lang') or 'pl')[:5]
    if not text:
        return '', 400
    cache_key  = hashlib.md5(f"gtts:{lang}:{text}".encode()).hexdigest()
    cache_file = os.path.join(TTS_CACHE_DIR, f"{cache_key}.mp3")
    if os.path.exists(cache_file):
        return send_file(cache_file, mimetype='audio/mpeg')
    try:
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={url_quote(text)}&tl={lang}&client=tw-ob"
        r = _requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=8)
        if r.status_code == 200 and len(r.content) > 100:
            with open(cache_file, 'wb') as f:
                f.write(r.content)
            return send_file(cache_file, mimetype='audio/mpeg')
    except Exception:
        pass
    return '', 502


## ── SUPABASE AUTH / PROFIL / ULUBIONE ────────────────────────────────────────

def _get_user_from_token():
    """Wyciąga user_id z Bearer tokena Supabase."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer ") or not supabase:
        return None
    token = auth[7:]
    try:
        return supabase.auth.get_user(token).user
    except Exception:
        return None

@app.route("/api/profile", methods=["GET"])
def api_profile_get():
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    try:
        row = supabase.table("profiles").select("*").eq("id", user.id).single().execute()
        return jsonify(row.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/profile", methods=["PATCH"])
def api_profile_patch():
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    allowed = {"display_name","truck_type","truck_height_m","truck_weight_t","truck_width_m","language","country"}
    update = {k: v for k, v in data.items() if k in allowed}
    if not update:
        return jsonify({"error": "no valid fields"}), 400
    update["updated_at"] = "now()"
    try:
        row = supabase.table("profiles").update(update).eq("id", user.id).execute()
        return jsonify(row.data[0] if row.data else {})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/favorites", methods=["GET"])
def api_favorites_get():
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    try:
        rows = supabase.table("user_favorites").select("*").eq("user_id", user.id).execute()
        return jsonify(rows.data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/favorites", methods=["POST"])
def api_favorites_post():
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    spot_type = data.get("spot_type")
    spot_id = data.get("spot_id")
    if not spot_type or not spot_id:
        return jsonify({"error": "spot_type and spot_id required"}), 400
    try:
        row = supabase.table("user_favorites").upsert({
            "user_id": user.id, "spot_type": spot_type, "spot_id": spot_id
        }).execute()
        return jsonify(row.data[0] if row.data else {}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/favorites/<spot_type>/<int:spot_id>", methods=["DELETE"])
def api_favorites_delete(spot_type, spot_id):
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    try:
        supabase.table("user_favorites").delete().eq("user_id", user.id).eq("spot_type", spot_type).eq("spot_id", spot_id).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/ai-history", methods=["GET"])
def api_ai_history():
    """Ostatnie 20 wiadomości z historii rozmów użytkownika."""
    user = _get_user_from_token()
    if not user:
        return jsonify([])
    try:
        rows = supabase.table("ai_conversations").select("role,content,created_at") \
            .eq("user_id", user.id).order("created_at", desc=True).limit(20).execute()
        return jsonify(list(reversed(rows.data)))
    except Exception:
        return jsonify([])

@app.route("/api/ai-history", methods=["POST"])
def api_ai_history_save():
    """Zapisuje wiadomość do historii rozmowy."""
    user = _get_user_from_token()
    if not user:
        return jsonify({"ok": False})
    data = request.json or {}
    role = data.get("role")
    content = data.get("content", "").strip()
    if role not in ("user", "assistant") or not content:
        return jsonify({"error": "invalid"}), 400
    try:
        supabase.table("ai_conversations").insert({
            "user_id": user.id, "role": role, "content": content
        }).execute()
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/api/parking/<int:parking_id>/review", methods=["POST"])
def api_parking_review(parking_id):
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    data = request.json or {}
    rating = data.get("rating")
    comment = data.get("comment", "")
    if not rating or not (1 <= int(rating) <= 5):
        return jsonify({"error": "rating 1-5 required"}), 400
    try:
        row = supabase.table("parking_reviews").upsert({
            "user_id": user.id, "parking_id": parking_id,
            "rating": int(rating), "comment": comment
        }).execute()
        return jsonify(row.data[0] if row.data else {}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/send-welcome", methods=["POST"])
def api_send_welcome():
    user = _get_user_from_token()
    if not user:
        return jsonify({"error": "unauthorized"}), 401
    email = user.email
    if not email:
        return jsonify({"ok": False})
    name = (user.user_metadata or {}).get("full_name") or (user.user_metadata or {}).get("name") or email.split("@")[0]
    ok = send_email(email, f"Witaj w TruckSpot, {name}! 🚛", WELCOME_HTML)
    return jsonify({"ok": ok})


@app.route("/api/ai-ping")
def api_ai_ping():
    """Diagnostyka — sprawdź który model Gemini działa."""
    if not OPENAI_API_KEY:
        return jsonify({"error": "no key"})
    results = {}
    for api_ver, model in GEMINI_MODELS:
        key = f"{api_ver}/{model}"
        try:
            url = (f"https://generativelanguage.googleapis.com/{api_ver}/models/"
                   f"{model}:generateContent?key={GEMINI_API_KEY}")
            resp = _requests.post(url, json={
                "contents": [{"parts": [{"text": "Hi"}]}],
                "generationConfig": {"maxOutputTokens": 10},
            }, timeout=8)
            j = resp.json()
            results[key] = "OK" if "candidates" in j else j.get("error", {}).get("message", "no candidates")
        except Exception as e:
            results[key] = str(e)
    return jsonify(results)


@app.route("/api/fuel-stations")
def api_fuel_stations():
    """Stacje paliw dla TIR z Overpass — filtrowane po kartach płatniczych."""
    try:
        south = float(request.args.get('south', 0))
        west  = float(request.args.get('west',  0))
        north = float(request.args.get('north', 0))
        east  = float(request.args.get('east',  0))
        cards = request.args.get('cards', 'hgv')  # dkv,uta,as24,e100,shell,adblue,hgv
    except (ValueError, TypeError):
        return jsonify([])

    bbox = f"({south},{west},{north},{east})"
    card_list = [c.strip() for c in cards.split(',') if c.strip()]

    parts = []
    for card in card_list:
        if card == 'hgv':
            parts.append(f'node[amenity=fuel][hgv=yes]{bbox};')
            parts.append(f'node[amenity=fuel]["fuel:HGV_diesel"=yes]{bbox};')
        elif card == 'adblue':
            parts.append(f'node[amenity=fuel]["fuel:adblue"=yes]{bbox};')
        else:
            parts.append(f'node[amenity=fuel]["payment:{card}"=yes]{bbox};')

    if not parts:
        return jsonify([])

    q = f'[out:json][timeout:20];({" ".join(parts)});out body;'
    try:
        r = _requests.post('https://overpass-api.de/api/interpreter',
                           data={'data': q}, timeout=22,
                           headers={'User-Agent': 'TruckSpot/1.0'})
        elements = r.json().get('elements', [])
    except Exception:
        return jsonify([])

    seen = set()
    stations = []
    for e in elements:
        eid = e.get('id')
        if eid in seen:
            continue
        seen.add(eid)
        t = e.get('tags', {})
        pays = [k.replace('payment:', '') for k, v in t.items()
                if k.startswith('payment:') and v == 'yes']
        stations.append({
            'id':           'fuel_' + str(eid),
            'lat':          e.get('lat'),
            'lng':          e.get('lon'),
            'name':         t.get('name') or t.get('brand') or 'Stacja TIR',
            'brand':        t.get('brand', ''),
            'adblue':       t.get('fuel:adblue') == 'yes',
            'hgv_diesel':   t.get('fuel:HGV_diesel') == 'yes',
            'hgv':          t.get('hgv') == 'yes',
            'opening_hours': t.get('opening_hours', ''),
            'phone':        t.get('phone', ''),
            'payments':     pays,
        })

    return jsonify(stations)


if __name__ == "__main__":
    app.run(debug=True, port=5002)
