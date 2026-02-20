#!/usr/bin/env python3
"""
Google Places API Scraper – Kanton Zürich Hub
==============================================
Scannt den gesamten Kanton Zürich nach Gastronomie- und Handwerksbetrieben,
filtert nach Mindestbewertungen und exportiert strukturierte JSON-Dateien.

Voraussetzungen:
  pip install requests

Konfiguration:
  Setze deinen API-Key als Umgebungsvariable:
    export GOOGLE_PLACES_API_KEY="dein-key-hier"

  Oder trage ihn direkt in die Variable API_KEY ein.

Benötigte APIs im Google Cloud Projekt:
  - Places API (New)
  - Maps JavaScript API (für Frontend)
"""

import os
import json
import time
import math
import requests
from datetime import datetime

# ─── Konfiguration ──────────────────────────────────────────────────────────

API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "DEIN_API_KEY_HIER")

MIN_REVIEWS = 100  # Mindestanzahl Bewertungen
OUTPUT_DIR = "data"

# Kanton Zürich – Bounding Box (SW → NE)
ZH_BOUNDS = {
    "sw_lat": 47.1594,
    "sw_lng": 8.3570,
    "ne_lat": 47.6946,
    "ne_lng": 8.9844,
}

# Rasterauflösung: ~3km Schritte für lückenlose Abdeckung
GRID_STEP_KM = 3.0
SEARCH_RADIUS_M = 2500  # Suchradius pro Gitterpunkt

# ─── Suchkategorien ─────────────────────────────────────────────────────────

CATEGORIES = {
    "gastro": {
        "display": "Gastronomie",
        "searches": [
            {"query": "Restaurant", "type": "restaurant"},
            {"query": "Bar", "type": "bar"},
            {"query": "Café Cafeteria", "type": "cafe"},
            {"query": "Takeaway Imbiss", "type": "meal_takeaway"},
            {"query": "Bäckerei Konditorei", "type": "bakery"},
        ],
    },
    "handwerker": {
        "display": "Handwerker",
        "searches": [
            {"query": "Elektriker Elektroinstallateur Zürich", "type": "electrician"},
            {"query": "Gipser Verputzer Zürich", "type": "general_contractor"},
            {"query": "Maler Malergeschäft Zürich", "type": "painter"},
            {"query": "Bodenleger Parkett Zürich", "type": "general_contractor"},
            {"query": "Schreiner Schreinerei Zürich", "type": "general_contractor"},
            {"query": "Sanitär Sanitärinstallateur Zürich", "type": "plumber"},
            {"query": "Dachdecker Spengler Zürich", "type": "roofing_contractor"},
            {"query": "Schlosser Metallbau Zürich", "type": "locksmith"},
            {"query": "Heizung Lüftung Klima Zürich", "type": "general_contractor"},
            {"query": "Gartenbau Landschaftsgärtner Zürich", "type": "general_contractor"},
        ],
    },
}

# Branchenzuordnung für Handwerker (Keyword-basiert)
TRADE_KEYWORDS = {
    "Elektriker": ["elektr", "electric", "elektro"],
    "Gipser": ["gips", "verputz", "stuck"],
    "Maler": ["maler", "malerei", "anstrich", "paint"],
    "Bodenleger": ["boden", "parkett", "laminat", "floor"],
    "Schreiner": ["schrein", "carpent", "holz", "möbel", "tischler"],
    "Sanitär": ["sanitär", "sanitar", "plumb", "rohrleitun"],
    "Dachdecker": ["dach", "spengler", "roof", "bedachung"],
    "Schlosser": ["schloss", "metall", "locksmith", "stahl"],
    "Heizung/Klima": ["heiz", "lüftung", "klima", "hvac", "wärme"],
    "Gartenbau": ["garten", "landschaft", "garden", "grün", "pflanz"],
}

# Gastro-Branchenzuordnung
GASTRO_KEYWORDS = {
    "Restaurant": ["restaurant", "ristorante", "gasth", "wirtschaft", "beiz"],
    "Bar": ["bar", "lounge", "pub", "club", "cocktail"],
    "Café": ["café", "cafe", "coffee", "kaffee", "cafeteria"],
    "Takeaway": ["takeaway", "take away", "imbiss", "kebab", "pizza", "sushi", "thai", "döner"],
    "Bäckerei": ["bäcker", "konditor", "bakery", "brot", "pâtisserie", "confiserie"],
}


# ─── Hilfsfunktionen ────────────────────────────────────────────────────────

def km_to_lat(km):
    """Konvertiert km in Breitengrad-Differenz."""
    return km / 111.0

def km_to_lng(km, lat):
    """Konvertiert km in Längengrad-Differenz bei gegebenem Breitengrad."""
    return km / (111.0 * math.cos(math.radians(lat)))

def generate_grid():
    """Erzeugt ein Raster von Mittelpunkten über den Kanton Zürich."""
    points = []
    lat = ZH_BOUNDS["sw_lat"]
    while lat <= ZH_BOUNDS["ne_lat"]:
        lng = ZH_BOUNDS["sw_lng"]
        while lng <= ZH_BOUNDS["ne_lng"]:
            points.append((lat, lng))
            lng += km_to_lng(GRID_STEP_KM, lat)
        lat += km_to_lat(GRID_STEP_KM)
    print(f"  Raster: {len(points)} Gitterpunkte generiert")
    return points

def classify_trade(name, types_list):
    """Ordnet einen Handwerksbetrieb einer Branche zu."""
    name_lower = name.lower()
    for trade, keywords in TRADE_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return trade
    return "Sonstige"

def classify_gastro(name, types_list):
    """Ordnet einen Gastrobetrieb einer Unterkategorie zu."""
    name_lower = name.lower()
    # Google Types zuerst prüfen
    type_map = {
        "restaurant": "Restaurant",
        "bar": "Bar",
        "cafe": "Café",
        "meal_takeaway": "Takeaway",
        "bakery": "Bäckerei",
    }
    for gtype, label in type_map.items():
        if gtype in types_list:
            return label
    # Fallback: Keyword-Match
    for category, keywords in GASTRO_KEYWORDS.items():
        for kw in keywords:
            if kw in name_lower:
                return category
    return "Restaurant"  # Default


# ─── API-Abfragen ───────────────────────────────────────────────────────────

def search_nearby(lat, lng, query, place_type, radius=SEARCH_RADIUS_M):
    """
    Führt eine Nearby Search (Text Search) über die Places API durch.
    Nutzt die Places API (New) – Text Search Endpoint.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": API_KEY,
        "X-Goog-FieldMask": (
            "places.id,places.displayName,places.formattedAddress,"
            "places.location,places.rating,places.userRatingCount,"
            "places.googleMapsUri,places.photos,places.types,"
            "places.businessStatus,places.primaryType,"
            "places.websiteUri,places.nationalPhoneNumber,"
            "places.currentOpeningHours"
        ),
    }
    body = {
        "textQuery": query,
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": float(radius),
            }
        },
        "maxResultCount": 20,
        "languageCode": "de",
        "regionCode": "CH",
    }

    results = []
    try:
        resp = requests.post(url, json=body, headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("places", [])
        elif resp.status_code == 429:
            print("    Rate Limit – warte 5 Sekunden...")
            time.sleep(5)
        else:
            print(f"    API Error {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"    Request-Fehler: {e}")

    return results


def get_photo_url(photo_name, max_width=400):
    """Generiert eine Photo-URL aus der Places API (New) Photo Reference."""
    if not photo_name:
        return None
    return (
        f"https://places.googleapis.com/v1/{photo_name}/media"
        f"?maxWidthPx={max_width}&key={API_KEY}"
    )


def process_place(place, category_type):
    """Extrahiert und normalisiert einen Place-Eintrag."""
    rating_count = place.get("userRatingCount", 0)
    if rating_count < MIN_REVIEWS:
        return None

    place_id = place.get("id", "")
    name = place.get("displayName", {}).get("text", "Unbekannt")
    address = place.get("formattedAddress", "")
    location = place.get("location", {})
    lat = location.get("latitude", 0)
    lng = location.get("longitude", 0)
    rating = place.get("rating", 0)
    gmaps_url = place.get("googleMapsUri", f"https://www.google.com/maps/place/?q=place_id:{place_id}")
    types = place.get("types", [])
    website = place.get("websiteUri", "")
    phone = place.get("nationalPhoneNumber", "")

    # Fotos
    photos = place.get("photos", [])
    photo_urls = []
    for photo in photos[:3]:
        photo_name = photo.get("name", "")
        url = get_photo_url(photo_name)
        if url:
            photo_urls.append(url)

    # Branchenzuordnung
    if category_type == "gastro":
        trade = classify_gastro(name, types)
    else:
        trade = classify_trade(name, types)

    # Öffnungszeiten
    hours = place.get("currentOpeningHours", {})
    weekday_text = hours.get("weekdayDescriptions", [])

    return {
        "id": place_id,
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "rating": rating,
        "reviewCount": rating_count,
        "gmapsUrl": gmaps_url,
        "website": website,
        "phone": phone,
        "photos": photo_urls,
        "trade": trade,
        "types": types,
        "hours": weekday_text,
        "businessStatus": place.get("businessStatus", "OPERATIONAL"),
    }


# ─── Hauptlogik ─────────────────────────────────────────────────────────────

def scrape_category(category_key):
    """Scannt eine Hauptkategorie über das gesamte Zürich-Raster."""
    category = CATEGORIES[category_key]
    print(f"\n{'='*60}")
    print(f"  Kategorie: {category['display']}")
    print(f"{'='*60}")

    grid = generate_grid()
    all_places = {}  # place_id → place_data (Deduplizierung)
    request_count = 0

    for search_def in category["searches"]:
        query = search_def["query"]
        print(f"\n  Suche: '{query}'")

        for i, (lat, lng) in enumerate(grid):
            results = search_nearby(lat, lng, query, search_def["type"])
            request_count += 1

            for place in results:
                processed = process_place(place, category_key)
                if processed and processed["id"] not in all_places:
                    all_places[processed["id"]] = processed

            # Fortschritt
            if (i + 1) % 20 == 0:
                print(f"    Punkt {i+1}/{len(grid)} – {len(all_places)} Betriebe gefunden")

            # Rate Limiting: 0.1s zwischen Requests
            time.sleep(0.1)

    print(f"\n  Gesamt: {len(all_places)} Betriebe mit ≥{MIN_REVIEWS} Bewertungen")
    print(f"  API-Requests: {request_count}")
    return list(all_places.values())


def generate_rankings(places, category_key):
    """Erzeugt branchenspezifische Rankings."""
    rankings = {}
    trades = set(p["trade"] for p in places)

    for trade in trades:
        trade_places = [p for p in places if p["trade"] == trade]

        # Top 10 nach Bewertung (bei Gleichstand: mehr Reviews gewinnen)
        by_rating = sorted(
            trade_places,
            key=lambda x: (x["rating"], x["reviewCount"]),
            reverse=True,
        )[:10]

        # Bottom 10 (schlechteste Bewertungen)
        by_worst = sorted(
            trade_places,
            key=lambda x: (x["rating"], -x["reviewCount"]),
        )[:10]

        # Meiste Bewertungen
        by_reviews = sorted(
            trade_places,
            key=lambda x: x["reviewCount"],
            reverse=True,
        )[:10]

        rankings[trade] = {
            "total": len(trade_places),
            "top_rated": [p["id"] for p in by_rating],
            "worst_rated": [p["id"] for p in by_worst],
            "most_reviewed": [p["id"] for p in by_reviews],
        }

    return rankings


def main():
    """Hauptfunktion: Scannt, filtert, klassifiziert und exportiert."""
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    timestamp = datetime.now().isoformat()
    metadata = {
        "generated": timestamp,
        "minReviews": MIN_REVIEWS,
        "region": "Kanton Zürich",
        "bounds": ZH_BOUNDS,
    }

    for category_key in CATEGORIES:
        places = scrape_category(category_key)

        # Rankings generieren
        rankings = generate_rankings(places, category_key)

        # Sortiert nach Rating (absteigend) speichern
        places.sort(key=lambda x: (x["rating"], x["reviewCount"]), reverse=True)

        output = {
            "metadata": {**metadata, "category": category_key, "totalResults": len(places)},
            "rankings": rankings,
            "places": places,
        }

        filepath = os.path.join(OUTPUT_DIR, f"{category_key}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        print(f"\n  → Gespeichert: {filepath} ({len(places)} Einträge)")

        # Statistiken pro Branche
        trades = {}
        for p in places:
            t = p["trade"]
            trades[t] = trades.get(t, 0) + 1
        print("  Branchen-Verteilung:")
        for t, count in sorted(trades.items(), key=lambda x: -x[1]):
            print(f"    {t}: {count}")

    # Gemeinsame Metadaten
    meta_path = os.path.join(OUTPUT_DIR, "metadata.json")
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  Scraping abgeschlossen. Daten in ./{OUTPUT_DIR}/")
    print(f"{'='*60}")


if __name__ == "__main__":
    if API_KEY == "DEIN_API_KEY_HIER":
        print("FEHLER: Bitte API-Key setzen!")
        print("  export GOOGLE_PLACES_API_KEY='dein-key'")
        print("  oder direkt in scraper.py eintragen.")
        exit(1)
    main()
