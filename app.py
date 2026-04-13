#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, secrets, requests as _requests
from flask import Flask, render_template, request, jsonify, send_from_directory

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", secrets.token_hex(32))

DATA_DIR       = os.path.join(os.path.dirname(__file__), "data")
PARKINGS_PATH  = os.path.join(DATA_DIR, "parkings.json")

os.makedirs(DATA_DIR, exist_ok=True)

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


if __name__ == "__main__":
    app.run(debug=True, port=5002)
