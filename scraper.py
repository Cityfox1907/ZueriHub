#!/usr/bin/env python3
"""
ZüriHub Scraper v2 – Vollständige Datenbank
============================================
Gastro: ≥40 Bewertungen | Handwerk: ≥20 Bewertungen
Alle Sternebewertungen 1–5 werden erfasst.

Setup:
  pip install requests
  export GOOGLE_PLACES_API_KEY="dein-key"
  python scraper.py
"""

import os, json, time, math, requests
from datetime import datetime

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "AIzaSyB1djuoI4by6_R_FZRuLfSY3Yp2H6m2bcA")
OUTPUT_DIR = "data"

# Kanton Zürich Bounding Box
ZH = {"sw_lat": 47.1594, "sw_lng": 8.3570, "ne_lat": 47.6946, "ne_lng": 8.9844}

# Raster: 2.5km für maximale Abdeckung
GRID_KM = 2.5
RADIUS_M = 2200

# ─── Mindestbewertungen pro Kategorie ────────────────────────────────────
MIN_REVIEWS = {"gastro": 40, "handwerker": 20}

# ─── Suchkategorien (erweitert) ──────────────────────────────────────────
CATEGORIES = {
    "gastro": {
        "display": "Gastronomie",
        "searches": [
            {"q": "Restaurant Zürich", "type": "restaurant"},
            {"q": "Bar Pub Zürich", "type": "bar"},
            {"q": "Café Cafeteria Zürich", "type": "cafe"},
            {"q": "Takeaway Imbiss Zürich", "type": "meal_takeaway"},
            {"q": "Bäckerei Konditorei Zürich", "type": "bakery"},
            {"q": "Hotel Zürich", "type": "lodging"},
            {"q": "Brauerei Biergarten Zürich", "type": "restaurant"},
            {"q": "Sushi Japanisch Zürich", "type": "restaurant"},
            {"q": "Pizza Italienisch Zürich", "type": "restaurant"},
            {"q": "Thai Asiatisch Zürich", "type": "restaurant"},
            {"q": "Burger Fast Food Zürich", "type": "restaurant"},
            {"q": "Kebab Döner Zürich", "type": "meal_takeaway"},
            {"q": "Eisdiele Glacé Zürich", "type": "restaurant"},
            {"q": "Weinbar Vinothek Zürich", "type": "bar"},
            {"q": "Nachtclub Lounge Zürich", "type": "night_club"},
            {"q": "Catering Partyservice Zürich", "type": "meal_delivery"},
        ],
    },
    "handwerker": {
        "display": "Bau & Handwerk",
        "searches": [
            {"q": "Elektriker Elektroinstallateur Zürich", "type": "electrician"},
            {"q": "Sanitär Sanitärinstallateur Zürich", "type": "plumber"},
            {"q": "Maler Malergeschäft Zürich", "type": "painter"},
            {"q": "Gipser Verputzer Stuckateur Zürich", "type": "general_contractor"},
            {"q": "Schreiner Schreinerei Zürich", "type": "general_contractor"},
            {"q": "Bodenleger Parkett Laminat Zürich", "type": "general_contractor"},
            {"q": "Dachdecker Spengler Bedachung Zürich", "type": "roofing_contractor"},
            {"q": "Schlosser Metallbau Zürich", "type": "locksmith"},
            {"q": "Heizung Lüftung Klima Zürich", "type": "general_contractor"},
            {"q": "Gartenbau Landschaftsgärtner Zürich", "type": "general_contractor"},
            {"q": "Zimmermann Holzbau Zürich", "type": "general_contractor"},
            {"q": "Plattenleger Fliesenleger Zürich", "type": "general_contractor"},
            {"q": "Umzugsfirma Transport Zürich", "type": "moving_company"},
            {"q": "Reinigung Gebäudereinigung Zürich", "type": "general_contractor"},
            {"q": "Maurer Baufirma Zürich", "type": "general_contractor"},
            {"q": "Storenbau Sonnenschutz Zürich", "type": "general_contractor"},
            {"q": "Küchenbau Küchenmontage Zürich", "type": "general_contractor"},
            {"q": "Glaser Glaserei Zürich", "type": "general_contractor"},
        ],
    },
}

# ─── Branchen-Klassifikation ─────────────────────────────────────────────
GASTRO_CLASSIFY = {
    "Restaurant": ["restaurant", "ristorante", "gasth", "wirtschaft", "beiz", "stube", "brasserie", "trattoria", "osteria", "bistro"],
    "Bar": ["bar", "lounge", "pub", "club", "cocktail", "nightclub", "nachtclub", "brewery", "brauerei"],
    "Café": ["café", "cafe", "coffee", "kaffee", "cafeteria", "tea room"],
    "Takeaway": ["takeaway", "take away", "imbiss", "kebab", "döner", "fast food", "food truck", "sushi bar", "poke"],
    "Bäckerei": ["bäcker", "konditor", "bakery", "brot", "pâtisserie", "confiserie", "patisserie", "glacé", "gelat"],
    "Hotel": ["hotel", "hostel", "gasth", "pension", "lodge", "resort", "motel", "b&b"],
}

HANDWERK_CLASSIFY = {
    "Elektriker": ["elektr", "electric", "elektro"],
    "Sanitär": ["sanitär", "sanitar", "plumb", "rohr"],
    "Maler": ["maler", "malerei", "anstrich", "paint", "farb"],
    "Gipser": ["gips", "verputz", "stuck", "stuckat"],
    "Schreiner": ["schrein", "carpent", "holz", "möbel", "tischler", "cabinet"],
    "Bodenleger": ["boden", "parkett", "laminat", "floor", "belag"],
    "Dachdecker": ["dach", "spengler", "roof", "bedachung", "flachdach"],
    "Schlosser": ["schloss", "metall", "locksmith", "stahl", "schmiede"],
    "Heizung/Klima": ["heiz", "lüftung", "klima", "hvac", "wärme", "kälte"],
    "Gartenbau": ["garten", "landschaft", "garden", "grün", "pflanz", "rasen"],
    "Zimmermann": ["zimmer", "holzbau", "gebälk", "dachstuhl", "tragwerk"],
    "Plattenleger": ["fliese", "platte", "keramik", "mosaik", "stein", "kachel"],
    "Umzug": ["umzug", "transport", "moving", "zügel", "räumung"],
    "Reinigung": ["reinig", "clean", "putz", "gebäuderein", "facility"],
    "Maurer": ["maurer", "mauer", "beton", "bau firm", "baufirma", "hochbau"],
    "Storenbau": ["store", "sonnen", "jalousie", "rolllad", "markise"],
    "Küchenbau": ["küche", "kitchen", "einbauküche"],
    "Glaser": ["glas", "verglas", "fenster"],
}


def km2lat(km): return km / 111.0
def km2lng(km, lat): return km / (111.0 * math.cos(math.radians(lat)))

def grid():
    pts = []
    la = ZH["sw_lat"]
    while la <= ZH["ne_lat"]:
        lo = ZH["sw_lng"]
        while lo <= ZH["ne_lng"]:
            pts.append((la, lo))
            lo += km2lng(GRID_KM, la)
        la += km2lat(GRID_KM)
    print(f"  Raster: {len(pts)} Punkte")
    return pts

def classify(name, types_list, cat):
    n = name.lower()
    table = GASTRO_CLASSIFY if cat == "gastro" else HANDWERK_CLASSIFY

    # Google types first (for gastro)
    if cat == "gastro":
        tmap = {"restaurant":"Restaurant","bar":"Bar","cafe":"Café","meal_takeaway":"Takeaway","bakery":"Bäckerei","lodging":"Hotel","night_club":"Bar"}
        for t, label in tmap.items():
            if t in types_list: return label

    for trade, kws in table.items():
        for kw in kws:
            if kw in n: return trade
    return "Restaurant" if cat == "gastro" else "Sonstige"


def search(lat, lng, query):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.userRatingCount,places.googleMapsUri,places.photos,places.types,places.businessStatus,places.websiteUri,places.nationalPhoneNumber",
    }
    body = {
        "textQuery": query,
        "locationBias": {"circle": {"center": {"latitude": lat, "longitude": lng}, "radius": float(RADIUS_M)}},
        "maxResultCount": 20,
        "languageCode": "de",
        "regionCode": "CH",
    }
    try:
        r = requests.post(url, json=body, headers=headers, timeout=30)
        if r.status_code == 200: return r.json().get("places", [])
        if r.status_code == 429: time.sleep(5); return []
        print(f"    Error {r.status_code}: {r.text[:150]}")
    except Exception as e:
        print(f"    Request error: {e}")
    return []

def photo_url(name, w=400):
    if not name: return None
    return f"https://places.googleapis.com/v1/{name}/media?maxWidthPx={w}&key={API_KEY}"

def process(place, cat):
    rc = place.get("userRatingCount", 0)
    if rc < MIN_REVIEWS[cat]: return None
    pid = place.get("id", "")
    name = place.get("displayName", {}).get("text", "?")
    addr = place.get("formattedAddress", "")
    loc = place.get("location", {})
    types = place.get("types", [])
    photos = [photo_url(p.get("name")) for p in place.get("photos", [])[:3] if p.get("name")]
    return {
        "id": pid, "name": name, "address": addr,
        "lat": loc.get("latitude", 0), "lng": loc.get("longitude", 0),
        "rating": place.get("rating", 0), "reviewCount": rc,
        "gmapsUrl": place.get("googleMapsUri", f"https://www.google.com/maps/place/?q=place_id:{pid}"),
        "website": place.get("websiteUri", ""), "phone": place.get("nationalPhoneNumber", ""),
        "photos": photos, "trade": classify(name, types, cat),
        "types": types, "hours": [], "businessStatus": place.get("businessStatus", "OPERATIONAL"),
    }


def scrape(cat):
    cfg = CATEGORIES[cat]
    print(f"\n{'='*50}\n  {cfg['display']} (min. {MIN_REVIEWS[cat]} Bewertungen)\n{'='*50}")
    pts = grid()
    all_p = {}
    reqs = 0
    for sd in cfg["searches"]:
        q = sd["q"]
        print(f"\n  → '{q}'")
        for i, (la, lo) in enumerate(pts):
            for p in search(la, lo, q):
                pp = process(p, cat)
                if pp and pp["id"] not in all_p:
                    all_p[pp["id"]] = pp
            reqs += 1
            if (i+1) % 25 == 0:
                print(f"    {i+1}/{len(pts)} – {len(all_p)} Betriebe")
            time.sleep(0.1)
    print(f"\n  Total: {len(all_p)} | Requests: {reqs}")
    return list(all_p.values())


def rankings(places):
    rk = {}
    for trade in set(p["trade"] for p in places):
        tp = [p for p in places if p["trade"] == trade]
        best = sorted(tp, key=lambda x: (x["rating"], x["reviewCount"]), reverse=True)
        worst = sorted(tp, key=lambda x: (x["rating"], -x["reviewCount"]))
        most = sorted(tp, key=lambda x: x["reviewCount"], reverse=True)
        rk[trade] = {
            "total": len(tp),
            "top_rated": [p["id"] for p in best[:10]],
            "worst_rated": [p["id"] for p in worst[:10]],
            "most_reviewed": [p["id"] for p in most[:10]],
        }
    return rk

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    ts = datetime.now().isoformat()
    for cat in CATEGORIES:
        places = scrape(cat)
        places.sort(key=lambda x: (x["rating"], x["reviewCount"]), reverse=True)
        out = {
            "metadata": {"generated": ts, "minReviews": MIN_REVIEWS[cat], "region": "Kanton Zürich", "category": cat, "totalResults": len(places)},
            "rankings": rankings(places),
            "places": places,
        }
        fp = os.path.join(OUTPUT_DIR, f"{cat}.json")
        with open(fp, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\n  → {fp} ({len(places)} Einträge)")
        trades = {}
        for p in places: trades[p["trade"]] = trades.get(p["trade"], 0) + 1
        for t, c in sorted(trades.items(), key=lambda x: -x[1]):
            print(f"    {t}: {c}")
    print(f"\n{'='*50}\n  Fertig. JSON-Dateien in ./{OUTPUT_DIR}/\n{'='*50}")

if __name__ == "__main__":
    if API_KEY == "DEIN_API_KEY_HIER":
        print("FEHLER: API-Key setzen!\n  export GOOGLE_PLACES_API_KEY='...'")
        exit(1)
    main()
