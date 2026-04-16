#!/usr/bin/env python3
"""
TruckSpot — import statycznych fotoradarów dla Europy
Źródła:
  1. Lufop.net  — CC BY-SA 4.0, darmowy CSV dla 25+ krajów EU
  2. Open-GATSO-POI (GitHub) — backup dla Francji i krajów słabiej pokrytych
  3. Overpass API (OSM) — fallback dla krajów bez pliku Lufop

Użycie:
  python scripts/import_cameras.py
  python scripts/import_cameras.py --countries PL,DE,FR,CZ,HU,RO,AT,NL,BE,SK,IT,ES
  python scripts/import_cameras.py --source osm   # tylko Overpass

Efekt: data/cameras_static.json  (tablica obiektów kompatybilna z /api/cameras)
"""

import json, csv, io, time, math, argparse, sys, os
import urllib.request, urllib.error

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
OUT_FILE = os.path.join(DATA_DIR, "cameras_static.json")

# Główne kraje TIR w Europie — slug Lufop + kod ISO
TIR_COUNTRIES = {
    "PL": "poland",
    "DE": "germany",
    "FR": "france",
    "CZ": "czech-republic",
    "AT": "austria",
    "HU": "hungary",
    "RO": "romania",
    "SK": "slovakia",
    "NL": "netherlands",
    "BE": "belgium",
    "IT": "italy",
    "ES": "spain",
    "PT": "portugal",
    "CH": "switzerland",
    "SE": "sweden",
    "DK": "denmark",
    "NO": "norway",
    "FI": "finland",
    "BG": "bulgaria",
    "HR": "croatia",
    "SI": "slovenia",
    "RS": "serbia",
    "TR": "turkey",
    "UA": "ukraine",
}

LUFOP_CSV_URL = "https://speed-camera-map.lufop.net/{slug}/download/csv/"
OPEN_GATSO_URL = "https://github.com/1e1/Open-GATSO-POI/releases/latest/download/speed_cameras_{iso}.csv"
OVERPASS_URL   = "https://overpass-api.de/api/interpreter"

HEADERS = {"User-Agent": "TruckSpot-CameraImport/1.0 (truck navigation app)"}


def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))


def fetch_url(url, timeout=30):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")


def parse_lufop_csv(text, iso):
    """
    Format Lufop: lon,lat,name,[speed],[type],[azimuth],[city],[country]
    """
    cameras = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        try:
            if len(row) < 2:
                continue
            lon = float(row[0].strip())
            lat = float(row[1].strip())
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                continue
            name    = row[2].strip() if len(row) > 2 else ""
            speed   = ""
            cam_type = "fixed"
            # Wyciągnij prędkość z nazwy np. "Speed cam@80" lub "80"
            if "@" in name:
                parts = name.split("@", 1)
                name  = parts[0].strip()
                speed = parts[1].strip()
            elif len(row) > 3 and row[3].strip().isdigit():
                speed = row[3].strip()
            # Typ kamery
            if len(row) > 4:
                t = row[4].strip().lower()
                if "mobile" in t or "mobil" in t:
                    cam_type = "mobile"
                elif "average" in t or "section" in t or "odcink" in t:
                    cam_type = "average"
            cameras.append({
                "lat": lat, "lon": lon,
                "maxspeed": speed,
                "type": cam_type,
                "country": iso,
                "source": "lufop",
                "name": name[:60],
            })
        except (ValueError, IndexError):
            continue
    return cameras


def parse_opengatso_csv(text, iso):
    """
    Format Open-GATSO: lat,lon,name,speed[,type,azimuth]
    """
    cameras = []
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        try:
            if len(row) < 2:
                continue
            # Próbuj obie kolejności (lat/lon i lon/lat)
            try:
                lat = float(row[0].strip())
                lon = float(row[1].strip())
            except ValueError:
                continue
            if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                # Zamień jeśli to lon/lat
                lat, lon = lon, lat
                if not (-90 <= lat <= 90 and -180 <= lon <= 180):
                    continue
            speed = row[3].strip() if len(row) > 3 else ""
            cameras.append({
                "lat": lat, "lon": lon,
                "maxspeed": speed,
                "type": "fixed",
                "country": iso,
                "source": "opengatso",
                "name": row[2].strip()[:60] if len(row) > 2 else "",
            })
        except (ValueError, IndexError):
            continue
    return cameras


def fetch_overpass(iso, timeout=60):
    """Pobierz fotoradary dla kraju z OSM Overpass API."""
    query = f"""[out:json][timeout:{timeout}];
area["ISO3166-1"="{iso}"]->.c;
(
  node["highway"="speed_camera"](area.c);
  node["enforcement"="maxspeed"](area.c);
  node["enforcement"="speed"](area.c);
  node["camera:type"="speed"](area.c);
);
out;"""
    try:
        data_bytes = urllib.request.urlopen(
            urllib.request.Request(OVERPASS_URL, data=("data="+urllib.parse.quote(query)).encode(),
                                   headers=HEADERS, method="POST"),
            timeout=timeout+10
        ).read()
        data = json.loads(data_bytes)
        cameras = []
        for el in data.get("elements", []):
            if "lat" not in el or "lon" not in el:
                continue
            tags = el.get("tags", {})
            speed = tags.get("maxspeed", "")
            t = "fixed"
            if tags.get("camera:type") in ("mobile", "radar"):
                t = "mobile"
            cameras.append({
                "lat": el["lat"], "lon": el["lon"],
                "maxspeed": speed, "type": t,
                "country": iso, "source": "osm",
                "name": tags.get("name", ""),
            })
        return cameras
    except Exception as e:
        print(f"  Overpass błąd dla {iso}: {e}")
        return []


def deduplicate(cameras, radius_km=0.05):
    """Usuń duplikaty w promieniu radius_km."""
    result = []
    for cam in cameras:
        duplicate = False
        for existing in result:
            if haversine_km(cam["lat"], cam["lon"], existing["lat"], existing["lon"]) < radius_km:
                duplicate = True
                break
        if not duplicate:
            result.append(cam)
    return result


def main():
    import urllib.parse  # needed in fetch_overpass

    parser = argparse.ArgumentParser(description="Import fotoradarów dla TruckSpot")
    parser.add_argument("--countries", default=",".join(TIR_COUNTRIES.keys()),
                        help="Kody ISO krajów oddzielone przecinkiem (np. PL,DE,FR)")
    parser.add_argument("--source", choices=["lufop", "opengatso", "osm", "all"], default="all",
                        help="Źródło danych (domyślnie: all — próbuje kolejno)")
    args = parser.parse_args()

    countries = [c.strip().upper() for c in args.countries.split(",")]
    all_cameras = []

    for iso in countries:
        slug = TIR_COUNTRIES.get(iso)
        print(f"\n[{iso}] Pobieranie...", end=" ")
        cameras = []

        if args.source in ("lufop", "all") and slug:
            try:
                url = LUFOP_CSV_URL.format(slug=slug)
                text = fetch_url(url, timeout=20)
                cameras = parse_lufop_csv(text, iso)
                print(f"Lufop: {len(cameras)} kamer", end=" ")
            except Exception as e:
                print(f"Lufop błąd ({e})", end=" ")

        if not cameras and args.source in ("opengatso", "all"):
            try:
                url = OPEN_GATSO_URL.format(iso=iso.lower())
                text = fetch_url(url, timeout=20)
                cameras = parse_opengatso_csv(text, iso)
                print(f"OpenGATSO: {len(cameras)} kamer", end=" ")
            except Exception as e:
                print(f"OpenGATSO błąd ({e})", end=" ")

        if not cameras and args.source in ("osm", "all"):
            print("→ Overpass...", end=" ")
            cameras = fetch_overpass(iso, timeout=90)
            print(f"OSM: {len(cameras)} kamer", end=" ")
            time.sleep(2)  # rate limit Overpass

        cameras = deduplicate(cameras)
        print(f"→ po dedup: {len(cameras)}")
        all_cameras.extend(cameras)

    # Globalna deduplikacja
    print(f"\nŁącznie przed dedup: {len(all_cameras)}")
    all_cameras = deduplicate(all_cameras, radius_km=0.03)
    print(f"Łącznie po dedup: {len(all_cameras)}")

    # Dodaj ID i timestamp
    ts = time.time()
    for i, cam in enumerate(all_cameras):
        cam["id"]      = f"static_{i+1}"
        cam["ts"]      = ts
        cam["confirms"] = 0

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_cameras, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✅ Zapisano {len(all_cameras)} kamer → {OUT_FILE}")
    print(f"   Rozmiar pliku: {os.path.getsize(OUT_FILE) / 1024:.1f} KB")


if __name__ == "__main__":
    import urllib.parse
    main()
