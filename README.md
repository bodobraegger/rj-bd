# ☆ rj-bd ☆

A minimal, fast website displaying Rio de Janeiro and Niterói beach water quality data from INEA.

☆☆☆☆☆

## Overview

Beach water quality monitoring for Rio's coastline. Updated daily via automated parsing of INEA (Instituto Estadual do Ambiente) PDF bulletins and INEA's public Power BI dashboard.

## Features

* ☆ Interactive map with color-coded beach status markers
* ☆ Sortable beach list (favorites, status)
* ☆ Clickable legend filters to show/hide beach categories
* ☆ Mobile-responsive design with grid layout
* ☆ Sub-50KB bundle size (vanilla JavaScript, no frameworks)
* ☆ Offline support via service worker

## How It Works

### Data Pipeline

1. ☆ **Daily update** (`.github/workflows/update-data.yml`, 22:00 UTC / 19:00 Rio, or manual trigger):
   - `scripts/download_bulletins.sh` probes INEA for the newest bulletin PDFs (last 14 days)
   - `scripts/fetch_powerbi.py` queries INEA's public Power BI dashboard
   - `scripts/parse_inea_bulletin.py` merges all sources per beach (newest data wins) on top of the previous `data/beachData.json`, so a beach never loses its last known status when a source is unavailable
   - `scripts/test_parsing.py` validates the result; the workflow commits it only when it changed and passes validation
2. ☆ **Deploy** (`.github/workflows/deploy.yml`): every push to `main` (and every data update) stamps the service worker cache version and publishes to GitHub Pages

See [docs/inea-data-sources.md](docs/inea-data-sources.md) for the INEA sources and reverse-engineered APIs.

### Status Classifications

- **Própria** (Suitable for bathing) - Green
- **Imprópria** (Not suitable) - Red
- **Atenção** (Mixed monitoring points) - Yellow
- **Desconhecido** (Unknown) - Gray (hidden by default)

A beach with several monitoring points is *Atenção* when the points disagree.

## Project Structure

```
.
├── index.html                      # App shell + PWA meta
├── css/styles.css                  # All styling
├── js/
│   ├── app.js                      # Core logic and UI (vanilla JS)
│   └── sw.js                       # Service worker (offline cache)
├── data/
│   ├── beachData.json              # Generated beach data (bot-committed daily)
│   └── manifest.json               # PWA manifest
├── scripts/
│   ├── download_bulletins.sh       # INEA bulletin PDF discovery/download
│   ├── fetch_powerbi.py            # INEA Power BI dashboard fetcher
│   ├── parse_inea_bulletin.py      # Parser + source merger
│   ├── test_parsing.py             # Data validation (run in CI)
│   └── test_bulletins.sh           # Local end-to-end smoke test
├── docs/inea-data-sources.md       # INEA source/API documentation
└── .github/workflows/
    ├── update-data.yml             # Daily data update
    └── deploy.yml                  # GitHub Pages deployment
```

## Deployment

### GitHub Pages Setup

1. **Enable Pages**: Repository Settings → Pages → Source: GitHub Actions
2. **Automatic**: data updates run daily; every push to `main` deploys
3. **Manual trigger**: Actions tab → "Update Beach Data" → Run workflow

### Data Freshness

The site header shows the date of the newest data (`lastUpdate`). Each beach also carries its own `lastUpdate`; when a source stops publishing, the beach keeps its last known status and date instead of disappearing.

## Local Development

```bash
python3 -m http.server          # serve the app at localhost:8000
./scripts/test_bulletins.sh    # full pipeline smoke test (needs poppler-utils)
```

## Data Format

### data/beachData.json

```json
{
  "lastUpdate": "2026-07-02T00:00:00",
  "source": "INEA - Instituto Estadual do Ambiente",
  "bulletin": "Boletim de Balneabilidade das Praias",
  "beaches": [
    {
      "id": 5,
      "name": "Copacabana",
      "lat": -22.9702,
      "lng": -43.1815,
      "status": "attention",
      "city": "Rio de Janeiro",
      "zone": "Zona Sul",
      "lastUpdate": "2026-06-30T00:00:00",
      "monitoringPoints": [
        { "code": "CP04", "location": "Em frente à Rua República do Peru", "status": "proper" }
      ],
      "properCount": 3,
      "improperCount": 1
    }
  ]
}
```

### Beach Coverage

23 Rio de Janeiro beaches (Zona Sul, Zona Oeste, Baía de Guanabara) and 14 Niterói beaches. The authoritative list lives in `scripts/parse_inea_bulletin.py` (`RJ_BEACHES` / `NITEROI_BEACHES`); the tests derive their expectations from it.

## Known Limitations

- **Source volatility**: INEA replaced the per-zone Rio PDF bulletin with a statewide bulletin whose data pages are images (June 2026); see docs/inea-data-sources.md
- **Manual coordinates**: beach lat/lng hardcoded (Power BI provides per-point coordinates that could replace them)
- **No historical data**: only the latest status is shown, though the daily data commits build a history in git

## Roadmap

- [ ] Integrate weather API (OpenWeatherMap or INMET)
- [ ] When an actual water quality api becomes available, switch over, see https://github.com/orgs/prefeitura-rio/repositories
- [ ] Add historical trend graphs (the daily data commits are the dataset)

## Contributing

1. Fork repository
2. Create feature branch
3. Test locally (`./scripts/test_bulletins.sh`)
4. Submit pull request

## License

MIT

## Resources

- INEA Balneability: https://www.inea.rj.gov.br/balneabilidade/
- Leaflet.js: https://leafletjs.com/
