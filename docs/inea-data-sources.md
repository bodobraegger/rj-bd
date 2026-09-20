# INEA data sources

Everything known about where INEA publishes beach water quality
("balneabilidade") data, including the reverse-engineered Power BI API and
the pin-map extraction for the statewide bulletin.
Last verified: 2026-09-05.

## Timeline / context

Until late June 2026, INEA published weekly per-region PDF bulletins with
text-extractable status tables. Around 2026-06-26 they switched to a single
consolidated statewide bulletin whose data pages are **map images with
colored pins** — nothing machine-readable. The last per-zone Rio PDF was
`Zona-sudoeste-e-Zona-sul-30-06-26.pdf`; Niterói PDFs were still being
published as of `Niterói-02-07-26.pdf`.

As of 2026-09-05 it has flipped back: INEA is again publishing per-city
PDFs (confirmed `Zona-sudoeste-e-Zona-sul-03-09-26.pdf`,
`Niteroi-03-09-26.pdf`), while the statewide bulletin link on
`/balneabilidade/` is gone — that page now redirects to a stub template
page with no PDF link, media, or mention of "praia"/"boletim" at all. The
last statewide PDF the link scraper can still find is the stale
2026-07-03 one referenced below. `download_bulletins.sh` treats a missing
statewide link as a warning, not a failure, so this is not fatal, just
another silent-drop case to expect.

The per-zone Rio bulletin (`Zona-sudoeste-e-Zona-sul`) came back on
2026-08-19 and has been weekly (Thursdays) since: 19-08, 27-08, 03-09,
10-09, 17-09. Niterói bulletins never stopped and sometimes get an extra
Monday issue (14-09). The `Zona-oeste-e-Zona-sul` name has never appeared
in 2026; the "Zona Oeste" beaches only come from Power BI. The statewide
bulletin link on INEA's page still points to the 2026-07-03 issue, so that
channel is dead for now.

This is why the pipeline merges multiple sources and keeps last-known-good
data per beach: any single INEA channel can (and does) silently stop.

## INEA geo-blocks every connection from outside Brazil

Confirmed 2026-09-20. A `check-host.net` HTTP check of a bulletin PDF from
40 nodes: only the Brazilian node (a datacenter IP) connected, all 39 others
in Europe, Asia and the Americas got "Connection timed out". A probe
workflow on `ubuntu-latest`, `ubuntu-24.04-arm`, `macos-latest` and
`windows-latest` runners got the same TCP timeout on `www.inea.rj.gov.br`.
Public fetch proxies fail too: Wayback `save` returns 500, `r.jina.ai` 422,
`api.codetabs.com` and `api.allorigins.win` 522 (their own upstream fetch
times out). The 2026-09-05 note that blamed cloud datacenter ranges was
wrong: the rule is by country, and a Brazilian datacenter IP passes.

Consequences:

- GitHub Actions can only refresh from the Power BI API, which INEA hosts
  on Microsoft infrastructure and which is reachable from anywhere.
- Every bulletin PDF must be fetched from a Brazilian IP. The pipeline
  therefore has two runners of the same script, `scripts/update_data.sh`:
  the daily GitHub Actions workflow (Power BI only in practice), and a
  systemd user timer on a machine in Brazil (`scripts/systemd/`, twice a
  day, `Persistent=true` so a missed slot runs at next boot). Both commit
  and push `data/beachData.json`; the merge-by-date logic makes the order
  irrelevant.

Options considered for a fetcher that does not depend on one laptop being
on, all untested, in order of preference:

1. **Always-free VM in São Paulo** (Oracle Cloud `sa-saopaulo-1` always-free
   tier, or an AWS/GCP free-tier instance in `sa-east-1` /
   `southamerica-east1`) running the same systemd timer. The check-host
   result shows a Brazilian datacenter IP is not blocked. Needs an account
   with a card on file.
2. **GitHub self-hosted runner** on that VM or on the laptop: keeps the
   workflow as the single entry point, but adds a runner daemon to keep
   updated for no gain over the timer.
3. **Cloudflare Worker proxy**: the domain is already on Cloudflare, but a
   Worker fetches from the colo that handled the request, so a call from a
   GitHub runner in the US would exit from a US colo and be blocked. Only a
   Worker cron trigger pinned to a Brazilian colo could work, and Cloudflare
   does not offer that pinning.
4. **Third-party mirrors**: `toemcasa.com.br` republishes per-beach statuses
   but from the Power BI dataset (it showed 2026-08-24 on 2026-09-20), and
   news sites only quote the weekend summary. Nothing publishes the PDFs.

## 1. Bulletin PDFs (primary while they last)

Uploaded to WordPress at predictable URLs, weekly-ish, no index page
(the wp-json media API does not list them, so URL probing is required):

```
https://www.inea.rj.gov.br/wp-content/uploads/{YYYY}/{MM}/{name}-{DD-MM-YY}.pdf
```

- Rio names: `Zona-sudoeste-e-Zona-sul` (paused late June to mid August 2026, weekly again since), `Zona-oeste-e-Zona-sul` (never seen, probed anyway)
- Niterói names: `Niterói` (URL-encoded `Niter%C3%B3i`), `Niteroi`
- INEA sometimes files a PDF under the *following* month's folder
  (e.g. the 30-06 bulletin lives in `2026/07/`), so probe both.
- `scripts/download_bulletins.sh` implements this probing.

## 1b. Statewide bulletin (current; image-based, parsed via pin detection)

```
https://www.inea.rj.gov.br/wp-content/uploads/2026/07/Site-Boletim-de-Balneabilidade-do-Estado-do-RJ_03.07.2026_v2.pdf
```

Weekly, linked from https://www.inea.rj.gov.br/balneabilidade/ (301s to
`/ar-agua-e-solo/balneabilidade-das-praias/`; follow redirects and grep the
`Boletim-de-Balneabilidade…pdf` href — `download_bulletins.sh` does this and
saves it as `statewide.pdf`, but only when no per-zone Rio bulletin was
found, because the file is 31 MB). From late June to mid August 2026 this
was the only source for Rio statuses; the linked issue has been stuck at
2026-07-03 since.

`pdftotext` yields only region headings; the per-beach data are JPEG map
images with green/red teardrop pins. `scripts/parse_statewide_bulletin.py`
extracts statuses anyway, with no dependencies beyond poppler-utils:

1. Locate relevant pages by their extractable headings
   (`Zona Sudoeste`, `Zona Sul`, `Niterói`; `Magé` shares Niterói's page).
2. `pdftoppm -r 150` renders each page to raw PPM (stdlib-parseable).
3. Pins are found by color thresholding (saturated pin green/red vs the
   pastel basemap) plus blob size/aspect filters; the teardrop's bottom tip
   is the anchor pixel. Legend pins are excluded by their white
   surroundings. Two maps per page are split at large vertical pin gaps.
4. Each map is registered against the official point coordinates
   (`data/monitoringPoints.json`, from the Power BI dataset) with an
   iterative-closest-point fit using greedy one-to-one matching — no OCR,
   no manual georeferencing.
5. Matches beyond a 50px residual are dropped; a map needing less than 60%
   coverage is rejected entirely, and the merge keeps last known statuses.

Validated against the 03-07 bulletin: 66/68 points matched (worst residual
7px); all 37 derived beach statuses agreed with the same measurement
cycle's text-parseable zone bulletins. Runs in ~3.5s.

Failure modes to expect: INEA changing pin colors/shapes (thresholds in
`classify_pixel`), reshuffling pages (heading detection survives that),
changing map extents (registration refits every run), or overlapping pins
occluding each other (occluded points are simply skipped that week).

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

Update 2026-09-05: the lag was gone; `fetch_powerbi.py` returned
collections up to 2026-08-24, ahead of the PDF bulletins at the time.

Update 2026-09-20: stale again. The newest collection is still 2026-08-24
while the PDFs are at 2026-09-17, so Power BI now lags four weeks. Keep the
merge-by-date logic: INEA has flipped source freshness three times this year.

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
