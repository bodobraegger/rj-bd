# Balneabilidade Rio

A minimal, fast website displaying Rio de Janeiro beach water quality data from INEA bulletins.

## Overview

Real-time beach water quality monitoring for Rio's coastline. Updated weekly via automated parsing of INEA (Instituto Estadual do Ambiente) PDF bulletins.


## Features

* ☆ Interactive map with color-coded beach status markers
* ☆ Sortable beach list (favorites, alphabetical, status)
* ☆ Clickable legend filters to show/hide beach categories
* ☆ Mobile-responsive design with grid layout
* ☆ Sub-50KB bundle size (vanilla JavaScript, no frameworks)

## How It Works

### Data Pipeline

1. ☆ **Automated Updates**: GitHub Actions runs on:
   - Every push to `main` branch
   - Every Monday at 6 AM UTC (scheduled)
   - Manual workflow trigger
2. ☆ **PDF Download**: Fetches latest INEA bulletin from `inea.rj.gov.br`
3. ☆ **Parsing**: Python script extracts beach status using `pdftotext`
4. ☆ **JSON Generation**: Outputs `beachData.json` with 25 Rio beaches
5. ☆ **Deployment**: Publishes to GitHub Pages automatically

### Data Source

INEA publishes weekly "Boletim de Balneabilidade" PDFs with beach water quality classifications:
- **Própria** (Suitable for bathing) - Green
- **Imprópria** (Not suitable) - Red
- **Atenção** (Warning) - Yellow
- **Desconhecido** (Unknown) - Gray (hidden by default)

Bulletins available at: `https://www.inea.rj.gov.br/rio-de-janeiro/`

## Project Structure

```
.
├── index.html                  # Main application (HTML + inline CSS)
├── app.js                      # Core logic and UI (vanilla JS)
├── beachData.json              # Generated beach status data
├── parse_inea_bulletin.py      # PDF parser script
├── .github/
│   └── workflows/
│       └── update-data.yml     # Weekly automation workflow
└── README.md
```

## Deployment

### GitHub Pages Setup

1. **Enable Pages**: Repository Settings → Pages → Source: GitHub Actions
2. **Push to GitHub**: Workflow runs automatically on Monday mornings
3. **Manual Trigger**: Actions tab → "Update Beach Data and Deploy" → Run workflow

### What Gets Deployed

- `index.html`, `app.js`, `beachData.json`
- PDF downloads are **ephemeral** (not committed to git)
- Keeps repository clean (<1MB)

### Data Freshness

The site displays the bulletin date from the `lastUpdate` field in `beachData.json`. When the bulletin is from today, it shows "Hoje" (Today). Otherwise, it shows the actual date or "X dias atrás" (X days ago).

If INEA hasn't published a new bulletin, the workflow will reuse the existing data (no update).

## Technical Details

### Map Behavior

- **Desktop**: Sidebar on right, full-height map
- **Mobile**: Map on top (45vh), scrollable grid below (55vh)
- **Bounds**: Restricted to Rio de Janeiro area
- **Auto-fit**: Centers on visible beaches (excluding hidden statuses)
- **Resize**: Recalculates map dimensions on viewport change

## Data Format

### beachData.json

```json
{
  "lastUpdate": "2026-03-04T00:00:00",
  "source": "INEA - Instituto Estadual do Ambiente",
  "bulletin": "Boletim de Balneabilidade das Praias",
  "beaches": [
    {
      "id": 1,
      "name": "Copacabana",
      "lat": -22.9711,
      "lng": -43.1822,
      "status": "proper",
      "zone": "Zona Sul",
      "lastUpdate": "2026-03-09T10:00:00"
    }
  ]
}
```

### Beach Coverage

25 beaches across Rio's coastline:
- Zona Oeste: Barra de Guaratiba, Prainha, Grumari, Recreio, Barra da Tijuca, etc.
- Zona Sul: Leblon, Ipanema, Arpoador, Copacabana, Leme, etc.
- Baía de Guanabara: Flamengo, Botafogo, Urca, etc.

### Styling

All CSS is inline in `index.html`. Current design: minimal Swiss aesthetic inspired by US Graphics.

## Known Limitations

- **PDF Dependency**: INEA must publish bulletins in consistent format
- **Manual Coordinates**: Beach lat/lng hardcoded (INEA doesn't provide)
- **No Historical Data**: Only shows latest bulletin
- **Weather Alerts**: Currently disabled
## Roadmap

- [ ] Integrate weather API (OpenWeatherMap or INMET)
- [ ] When an actual water quality api becomes available, switch over, see https://github.com/orgs/prefeitura-rio/repositories
- [ ] Add historical trend graphs
- [ ] Service worker for offline support

## Contributing

1. Fork repository
2. Create feature branch
3. Test locally
4. Submit pull request

## License

MIT

## Resources

- INEA Balneability: https://www.inea.rj.gov.br/rio-de-janeiro/
- Leaflet.js: https://leafletjs.com/
