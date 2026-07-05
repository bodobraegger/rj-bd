# INEA data sources

Everything known about where INEA publishes beach water quality
("balneabilidade") data, including the reverse-engineered Power BI API.
Last verified: 2026-07-05.

## Timeline / context

Until late June 2026, INEA published weekly per-region PDF bulletins with
text-extractable status tables. Around 2026-06-26 they switched to a single
consolidated statewide bulletin whose data pages are **map images with
colored pins** — nothing machine-readable. The last per-zone Rio PDF was
`Zona-sudoeste-e-Zona-sul-30-06-26.pdf`; Niterói PDFs were still being
published as of `Niterói-02-07-26.pdf`.

This is why the pipeline merges multiple sources and keeps last-known-good
data per beach: any single INEA channel can (and does) silently stop.

## 1. Bulletin PDFs (primary while they last)

Uploaded to WordPress at predictable URLs, weekly-ish, no index page
(the wp-json media API does not list them, so URL probing is required):

```
https://www.inea.rj.gov.br/wp-content/uploads/{YYYY}/{MM}/{name}-{DD-MM-YY}.pdf
```

- Rio names: `Zona-sudoeste-e-Zona-sul`, `Zona-oeste-e-Zona-sul` (likely discontinued June 2026)
- Niterói names: `Niterói` (URL-encoded `Niter%C3%B3i`), `Niteroi`
- INEA sometimes files a PDF under the *following* month's folder
  (e.g. the 30-06 bulletin lives in `2026/07/`), so probe both.
- `scripts/download_bulletins.sh` implements this probing.

Statewide bulletin (current, NOT machine-readable, kept for reference):

```
https://www.inea.rj.gov.br/wp-content/uploads/2026/07/Site-Boletim-de-Balneabilidade-do-Estado-do-RJ_03.07.2026_v2.pdf
```

Linked from https://www.inea.rj.gov.br/balneabilidade/ ("boletim de
balneabilidade"). `pdftotext` yields only headings; the per-beach data are
JPEG map images with green/red pins. Extracting statuses would require pin
detection + georeferencing. Rejected.

## 2. Power BI dashboard (reverse-engineered public API)

INEA's site links a public "publish to web" Power BI report (page
"Balneabilidade de Praias"):

```
https://app.powerbi.com/view?r=eyJrIjoiNWI4MDFiMzEtNGY0OS00M2Y1LWE5MWYtZWNlNzQyYmUwMjkwIiwidCI6IjZkYjc3YWU3LWQwYTQtNDYxNi1iNzM4LTg4ODE4NTQxOWIzOSJ9
```

The `r=` parameter is base64 JSON: `{"k": "<resource key>", "t": "<tenant>"}`.
The resource key `5b801b31-4f49-43f5-a91f-ece742be0290` authorizes
unauthenticated API access.

### Endpoints

Base host: `https://wabi-brazil-south-api.analysis.windows.net`
(the `wabi-brazil-south-redirect` host in the embed HTML returns 403 for
direct API calls — use the `-api` host).

All requests need headers:

```
X-PowerBI-ResourceKey: 5b801b31-4f49-43f5-a91f-ece742be0290
ActivityId: <any uuid>
RequestId: <any uuid>
Content-Type: application/json;charset=UTF-8   (for POST)
```

- `GET /public/reports/{resourceKey}/modelsAndExploration?preferReadOnlySession=true`
  → model id (`5721923`), dataset id (`c9353be0-85cb-4f81-9b1e-ef5e121124f7`),
  report id (`642f871e-cbd8-42f4-9cd6-3536460d67c2`), all report pages/visuals.
- `POST /public/reports/conceptualschema` with `{"modelIds": [5721923]}`
  → full table/column schema.
- `POST /public/reports/querydata?synchronous=true` with a SemanticQuery
  → actual data. See `scripts/fetch_powerbi.py`.

### The balneabilidade table

Entity `fDISEQ_Balneabilidade_Praias` (~300 rows, one per monitoring point,
whole state). Useful columns:

| Column | Notes |
|---|---|
| `Ponto de Coleta` | point code, e.g. `AR000` (zero-padding differs from the PDFs' `AR00`) |
| `Código Ponto de Coleta` | long form, e.g. `02RJ01AC0001` |
| `Data da coleta` | epoch milliseconds |
| `Praia`, `Município`, `Localização` | names/description |
| `Classificação` | `Própria`, `Imprópria`, `Nº Amostragens Insuficiente`, `''` |
| `Latitude ` (trailing space!), `Longitude` | official per-point coordinates |
| also | enterococci/E. coli concentrations, `Choveu nas últimas 24h?`, `Blue Flag` |

### Response format (DSR)

`querydata` responses compress rows: `results[0].result.data.dsr.DS[0]`
holds `PH[0].DM0` (rows) and `ValueDicts` (string tables). Per row, bitmask
`R` marks columns repeated from the previous row, bitmask `Ø` marks nulls,
and `C` lists the remaining values in column order; dictionary-typed values
are indices into `ValueDicts`. Decoder: `decode_rows()` in
`scripts/fetch_powerbi.py`.

### Caveat: dataset lag

As of 2026-07-05 the model refreshes regularly (last refresh 2026-07-03) but
the newest `Data da coleta` was 2026-05-05 (Rio) / 2026-05-07 (Niterói) —
about two months behind the PDF bulletins, with statuses that contradict the
newer PDFs. The merge-by-date logic therefore prefers the PDFs while they
are fresher. If INEA fixes their pipeline, Power BI becomes the best source
automatically.

## 3. Dead ends (checked 2026-07-05)

- **ArcGIS "Balneabilidade" FeatureServer** (`services1.arcgis.com/BaEibxoJ7fXjdIEF`,
  owner `admin_govest`, the old "Partiu Praia" app): per-point coordinates
  but statuses frozen at 2017.
- **INEA's own ArcGIS org** (`inea.maps.arcgis.com`, GEOINEA): no
  balneabilidade layers at all.
- **Niterói SIGeo** (`sig.niteroi.rj.gov.br/.../NGP_SMARHS_BALNEABILIDADE_P_PTSDEBALNEABILIDADE_PUBLICO/FeatureServer`):
  live service with `tx_status`/`dt_dtatualizacao` per point, but last
  updated 2026-02-11 — staler than the Niterói PDFs.
- **INEA wp-json media API**: does not index the bulletin uploads, so PDF
  discovery must stay URL-probing based.
- **Raw historical data**: INEA mentions a raw bacteriological dataset since
  2005 (annual snapshots, not a live feed).
