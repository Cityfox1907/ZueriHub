# ZüriHub – Setup & Konfiguration

## Projektstruktur

```
zurich-hub/
├── index.html          ← Haupt-App (Frontend, direkt im Browser öffnen)
├── scraper.py          ← Backend-Skript (Datensammlung via Google Places API)
├── data/               ← Wird vom Scraper generiert
│   ├── gastro.json
│   ├── handwerker.json
│   └── metadata.json
└── README.md
```

---

## Schritt 1: Google Cloud Projekt einrichten

1. Gehe zu [Google Cloud Console](https://console.cloud.google.com/)
2. Erstelle ein neues Projekt (z.B. "ZüriHub")
3. Aktiviere folgende APIs:
   - **Places API (New)** – für den Scraper
   - **Maps JavaScript API** – für die Karten-Darstellung
4. Erstelle einen API-Key unter *APIs & Services → Credentials → Create Credentials → API Key*
5. Empfohlen: Beschränke den Key auf die zwei aktiven APIs und deine Domain

### Kostenhinweis
Die Places API (New) berechnet ca. **$0.032 pro Text Search Request**. Ein vollständiger Scan des Kanton Zürich (alle Kategorien, ~180 Rasterpunkte × 15 Suchbegriffe) erzeugt ca. **2'700 Requests ≈ $86**. Für einen ersten Test reicht ein reduziertes Raster (GRID_STEP_KM auf 8 setzen → ~300 Requests ≈ $10).

---

## Schritt 2: Backend / Datensammlung

### Voraussetzungen
- Python 3.8+
- `requests` Bibliothek

```bash
pip install requests
```

### API-Key setzen

```bash
export GOOGLE_PLACES_API_KEY="AIzaSy..."
```

Oder direkt in `scraper.py` Zeile 24 eintragen.

### Scraper starten

```bash
python scraper.py
```

Das Skript:
- Erzeugt ein Raster über den gesamten Kanton Zürich
- Scannt jede Kategorie (Gastro + Handwerker) an jedem Rasterpunkt
- Filtert automatisch alle Betriebe mit weniger als 100 Bewertungen
- Klassifiziert jeden Betrieb in eine Branche (Elektriker, Maler, Restaurant, Bar...)
- Generiert branchenspezifische Rankings (Top/Bottom/Most Reviewed)
- Speichert alles als JSON in `./data/`

### Parameter anpassen (optional)

In `scraper.py`:
| Variable | Standard | Beschreibung |
|---|---|---|
| `MIN_REVIEWS` | 100 | Mindestanzahl Bewertungen |
| `GRID_STEP_KM` | 3.0 | Rasterabstand in km (kleiner = gründlicher, teurer) |
| `SEARCH_RADIUS_M` | 2500 | Suchradius pro Punkt |

---

## Schritt 3: Frontend starten

### Option A: Direkt im Browser (Demo-Modus)

Öffne `index.html` direkt im Browser. Ohne JSON-Dateien im `data/`-Ordner startet automatisch ein **Demo-Modus** mit exemplarischen Zürcher Betrieben. Die Karte funktioniert nur mit gültigem Google Maps API-Key.

### Option B: Mit echten Daten (lokaler Server)

Da Browser aus Sicherheitsgründen keine lokalen JSON-Dateien per `fetch()` laden, brauchst du einen lokalen Server:

```bash
# Python
python -m http.server 8000

# oder Node.js
npx serve .

# oder PHP
php -S localhost:8000
```

Dann im Browser: `http://localhost:8000`

### Option C: GitHub Pages

1. Push das gesamte `zurich-hub/` Verzeichnis (inkl. `data/`-Ordner) in ein GitHub Repository
2. Aktiviere GitHub Pages unter *Settings → Pages → Source: main branch*
3. Die App ist dann unter `https://dein-username.github.io/zurich-hub/` erreichbar

### API-Key im Frontend setzen

In `index.html` Zeile 11:
```javascript
window.GMAPS_KEY = 'DEIN_GOOGLE_MAPS_API_KEY';
```

⚠️ **Wichtig**: Beschränke den Maps JavaScript API Key auf deine Domain(s) in der Google Cloud Console, damit er nicht missbraucht werden kann.

---

## Features-Übersicht

### Filterung
- **Multi-Select Branchen**: Klicke mehrere Branchen-Chips gleichzeitig an
- **Rating-Filter**: 5★ (≥4.8), 4+★ (≥4.0), 3+★ (≥3.0), <2★ (unter 2.0 – Warnung)
- Filter sind kombinierbar

### Sortierung
- Beste/Schlechteste Bewertung
- Meiste/Wenigste Bewertungen
- Alphabetisch

### Karte
- Farbcodierte Marker (Gold ≥4.5, Grün ≥3.5, Gelb ≥2.0, Rot <2.0)
- Bidirektionale Interaktion: Hover über Liste → Marker-Highlight, Hover über Marker → Liste-Highlight
- GMB-Visitenkarten-Popup mit Foto, Sternen, Adresse und direktem Google-Maps-Link

### Rankings
- Branchenspezifische Top-Listen über den 🏆-Button
- Automatisch generierte Ranglisten pro Branche
- Visuelle Hervorhebung (goldener Rand für Top, roter Rand für Warnung)

---

## Architektur-Entscheidungen

**Warum statische JSON statt Live-API-Calls?**
- Google Places API ist kostenpflichtig (~$0.03/Request)
- API-Keys dürfen nie im Frontend-Code exponiert werden
- Statische Daten ermöglichen blitzschnelle Filter/Sortierung ohne Netzwerk
- Daten können regelmässig per Cron-Job aktualisiert werden

**Warum Vanilla JS statt React/Vue?**
- Direkt lauffähig ohne Build-Pipeline
- Kein Node.js, npm oder Bundler nötig
- Optimal für GitHub Pages Hosting
- Volle Kontrolle über Performance

**Warum ein Raster-Scan?**
- Die Google Places API limitiert Ergebnisse auf 20 pro Request
- Ein engmaschiges Raster stellt sicher, dass auch Betriebe ausserhalb der Stadt Zürich erfasst werden
- Deduplizierung über Place-IDs verhindert Doppeleinträge

---

## Erweiterungsmöglichkeiten

- **Automatisierung**: Cron-Job der den Scraper wöchentlich ausführt und `data/` aktualisiert
- **Suche**: Volltextsuche über Betriebsnamen mit Fuse.js
- **Detail-Seiten**: Klick auf Betrieb öffnet erweiterte Ansicht mit allen Fotos, Öffnungszeiten, Telefon
- **Vergleichsmodus**: Zwei Betriebe nebeneinander vergleichen
- **Export**: CSV/PDF Export der gefilterten Listen
