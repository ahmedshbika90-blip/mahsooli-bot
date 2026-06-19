# Mahala CHIRPS Rainfall Pipeline

Builds a grid-keyed rainfall **score lookup table** for the Mahala area of interest
(AOI) in Gedaref, Sudan, from CHIRPS v2.0 satellite rainfall data. The output is a
CSV mapping each 0.05° grid cell to its average June–September rainfall (2014–2024)
and a Mahsooli **1–10 rainfall score**, importable directly into Google Sheets.

## Pipeline

```
chirps/0_download.py        Download + unzip CHIRPS v2.0 Africa monthly rasters (Jun–Sep, 2014–2024)
        │
chirps/1_close_boundary.py  Close the open Mahala.geojson line into a polygon
        │
chirps/2_clip.py            Clip each monthly raster to the Mahala polygon
        │
chirps/3_average.py         Sum Jun–Sep per year → average across years → score lookup CSV
```

Each step is **idempotent**: re-running skips files that already exist, so an
interrupted run can simply be restarted.

## Repository layout

Scripts are grouped by purpose; `config.py` is the single source of truth for all
paths and constants, imported by every script.

```
config.py                 Central config (paths, period, scoring rubric, NDVI thresholds)
run_pipeline.py           Runner for the CHIRPS chain (chirps/0 → 3)
ndvi_run_pipeline.py      Runner for the NDVI chain (ndvi/farmers → baseline → current)

chirps/                   CHIRPS rainfall pipeline (the numbered steps above)
ndvi/                     NDVI crop-health monitoring (Earth Engine + Sheets)
tools/                    Standalone helpers, run manually after the pipeline:
                            snap_score.py            GPS → grid cell → score
                            google_sheets_lookup.py  build the VLOOKUP workbook
                            pilot_launch_check.py    farmer sign-off gate
```

## Run it from GitHub (no laptop needed)

Each Engagement-1 deliverable has its own one-click workflow under the repo's
**Actions** tab — no local setup required. Pick the workflow, click **Run workflow**,
and collect the result from the run's **Artifacts** (it is also committed back into the
repo). One-time credential setup is in
[`docs/SETUP_CREDENTIALS.md`](docs/SETUP_CREDENTIALS.md).

| Workflow | What it does | Inputs | Output |
|---|---|---|---|
| **E1.1 - CHIRPS Rainfall Lookup Table** | Full rebuild: download → clip → average → lookup CSV → VLOOKUP workbook | `start_year`/`end_year` (blank = 2014–2024) | Lookup CSV + `.xlsx` (committed back + run artifact). Heavy/rare (~30–60 min); run only when the year range changes. |
| **E1.2 - NDVI Crop-Health Monitor** | Sentinel-2 NDVI vs baseline → alerts | `run_date` (blank = today) | Rows in the `NDVI_Log` Google Sheet + cached baseline. Also runs automatically on the in-season schedule. |
| **E1.3 - Pilot Launch Check** | Sign-off gate: scores all configured farmers, cross-checks each | `limit` (optional), `farmers_csv` | Sign-off package (XLSX + CSV + `.txt`). A **red run = sign-off blocked** (a mismatch or missing requested row was found). |

Run **E1.1 once before E1.3** — E1.3 reuses E1.1's committed lookup CSV. Only E1.2
requires credentials (Earth Engine + Sheets); E1.1's Sheet upload is optional and E1.3
needs none.

### Setting this repo up in your own GitHub account (from the ZIP)

If you received this project as a ZIP and created your **own** GitHub repository from
it, the Actions won't appear until the repo is set up the way below. You do **not** need
to rename any branch — the workflows commit their results back to whatever branch they
run on (`git push origin HEAD:$GITHUB_REF_NAME`), so a default branch named **`main` is
fine**; it does not have to be `develop`.

1. **Commit the whole project — including the hidden `.github/workflows/` folder — to
   the repo's default branch.** On github.com, open the default branch and confirm you
   can see `.github/workflows/` with the three `.yml` files (E1.1/E1.2/E1.3). If the
   Actions tab is empty, this hidden folder almost certainly got dropped when the ZIP
   was extracted/uploaded, or it landed on a non-default branch — `workflow_dispatch`
   buttons and the schedule only appear when the workflow files are on the **default
   branch**.
2. **Enable Actions:** **Settings → Actions → General → Actions permissions →** *Allow
   all actions and reusable workflows*. (No need to change the "Workflow permissions"
   radio — each workflow already requests `contents: write` itself.)
3. **Add Secrets & Variables** (**Settings → Secrets and variables → Actions**), using
   *your own* Google service account, Sheet, and bucket:
   - Secret: `GEE_SERVICE_ACCOUNT_INFO` — the full service-account key JSON (required for E1.2).
   - Variables: `EE_PROJECT_ID`, `NDVI_SHEET_ID` (required for E1.2); optionally
     `GCS_BUCKET`, `GCS_ARCHIVE=true`, `NDVI_GCS_ARCHIVE=true` to archive each run to
     Google Cloud Storage. Full walkthrough to create these:
     [`docs/SETUP_CREDENTIALS.md`](docs/SETUP_CREDENTIALS.md).
4. **Run them:** open the **Actions** tab — E1.1, E1.2, E1.3 appear in the left sidebar.
   Pick one → **Run workflow**. E1.2 also runs automatically on the 1st/11th/21st
   in-season, on the default branch.
5. **Private repo:** add teammates as **collaborators with Write access** (Settings →
   Collaborators) so they can see and run the Actions.

## Quick start

**Recommended — with [uv](https://docs.astral.sh/uv/)** (one command installs the
right Python + all dependencies from the lockfile):

```bash
uv sync                          # creates .venv and installs pinned deps from uv.lock
uv run python run_pipeline.py    # run the whole pipeline
```

Don't have uv? Install it once: `curl -LsSf https://astral.sh/uv/install.sh | sh`
(macOS/Linux) or `brew install uv`. On Windows:
`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.

**Alternative — with pip:**

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run_pipeline.py
```

Configuration is optional — defaults work out of the box. To customise, copy
`.env.example` to `.env` and edit it (`cp .env.example .env`).

To run a single step instead (prefix with `uv run` if you use uv):

```bash
uv run python chirps/0_download.py       # or: python chirps/0_download.py  (pip/venv)
uv run python chirps/1_close_boundary.py
uv run python chirps/2_clip.py
uv run python chirps/3_average.py
```

### Score a farmer (GPS → score)

Once the lookup table exists, map any farmer GPS coordinate to its rainfall score:

```bash
uv run python tools/snap_score.py                # uses config.SNAP_FARMERS_CSV (default: data/farmers/farmers.csv)
uv run python tools/snap_score.py my_farmers.csv # one-off override on the command line
```

**Swapping farm coordinates** (the common production change): point `SNAP_FARMERS_CSV`
in `.env` at your CSV and re-run `python tools/snap_score.py` — nothing else changes.
(The NDVI pipeline reads a separate `NDVI_FARMERS_CSV`; see its section below.)
The CSV needs `lat`, `lon` and an id column named `farmer_id`, `mahsooli_id` or
`id` (extra columns such as `radius_m` are ignored), so both the bundled demo file
and a real farmer registry work unchanged. Because steps 4 (and 5) read only the
step-3 lookup CSV plus these coordinates, the expensive pipeline (steps 0–3) does
**not** need to re-run.

It snaps each coordinate to its 0.05° grid cell, looks up the score, flags
out-of-AOI coordinates with a plain-English message, and writes
`data/05_tables/farmer_scores.csv`. The equivalent **Google Sheets** snapping +
`VLOOKUP`/`INDEX-MATCH` formulas are in
[`docs/lookup_in_google_sheets.md`](docs/lookup_in_google_sheets.md).

### Create the demo workbook

`tools/google_sheets_lookup.py` builds a dated workbook,
`data/05_tables/Mahsooli_CHIRPS_v2_RainfallLookup_Gedaref_2014-2024_processed_<date>.xlsx`,
a 3-sheet lookup/VLOOKUP demo (`score_lookup`, `farmers_demo`, `methodology`;
`openpyxl` required):

```bash
python tools/google_sheets_lookup.py
```

The workbook is written locally and committed back by the E1.1 workflow (and
uploaded as a run artifact). Its `farmers_demo` tab uses the configured
`SNAP_FARMERS_CSV` rows so the VLOOKUP proof matches the provided farmer file.
Open the `.xlsx` directly, or import it into Google Sheets manually if a live
spreadsheet is wanted — the VLOOKUP recalculates on open.

## NDVI crop-health monitoring (Sentinel-2 + Google Earth Engine)

A **separate** sub-pipeline that monitors crop health for the registered plots
through the cotton season (Jun 1 → Mar 31). It pulls cloud-masked Sentinel-2 NDVI
from Google Earth Engine, compares each reading to its **sector baseline** (separate
rainfed / irrigated "normal" curves, built from the client's baseline-donor plots and
only their listed cotton seasons), raises a field-visit alert when a plot is
materially below normal, writes a 7-column `NDVI_Log` tab (+ a `Sector_Baseline` tab)
into the Mahsooli Google Sheet, saves per-plot raw clipped Sentinel-2 / NDVI GeoTIFFs
and RGB / NDVI quicklooks, and can mirror each dated run folder (imagery + tables +
run log) to Google Cloud Storage for traceability. It is intentionally **not** part of
`run_pipeline.py` (the CHIRPS chain) — it has its own runner and needs Earth Engine /
Sheets credentials.

```
ndvi/registry.py   Load + validate donor plots (config.NDVI_PLOTS_REGISTRY)   [local]
        │          (polygons or area-derived circles, sectors, cotton seasons)
ndvi/baseline.py   Build per-(plot, season, week) → plot → SECTOR baselines   [Earth Engine
        │          + raw S2/NDVI imagery per donor plot & season → GCS          + optional GCS]
ndvi/current.py    Current NDVI → deviation vs sector norm → alert → CSV +    [Earth Engine + Sheets
                   Sheet + imagery export + GCS archive                        + optional GCS]
```

**Donor-plot registry** (`config.NDVI_PLOTS_REGISTRY`, default
`data/farmers/baseline_plots.csv`) — one row per baseline donor plot. Columns:
`plot_id, farmer_name, sector, locality, village, geometry_type, geometry_wkt,
lat, lon, area_feddan, radius_m, seasons, notes`. `sector` is `rainfed` or
`irrigated`; `seasons` is the `;`/`,`-separated list of years cotton was planted
(other years grew other crops and are ignored); polygons use `geometry_wkt`,
points use `lat`/`lon` (+ `radius_m`, derived from `area_feddan` if blank). Donor
plots are **not** the financed farmers — they exist only to derive each sector's
"normal" curve. The full schema is in the `ndvi/registry.py` docstring.

**What each run archives** — everything under `data/ndvi/` is regenerated by a run and
**git-ignored**; the deliverable is the Google Sheet + the GCS run archive (mirrored when
`NDVI_GCS_ARCHIVE=true` or `--archive`), not the repo. The only tracked input is the donor
registry `data/farmers/baseline_plots.csv`.

```
data/ndvi/baseline_plot_seasons.csv   per (plot, season, week) NDVI + obs_count  (regenerated, ignored)
data/ndvi/baseline_plots.csv          per (plot, week), mean over seasons         (regenerated, ignored)
data/ndvi/baseline_sector.csv         per (sector, week)  ← current.py reads this (regenerated, ignored)
data/ndvi/runs/<date>_baseline/       the three CSVs + run_log.json + imagery/    (ignored — large)
        └── imagery/<plot>_<start>_<end>_{s2,ndvi}.tif + _{rgb,ndvi}.png
data/ndvi/runs/<date>_cycle/          alert CSV + run_log.json + imagery/         (ignored — large)
```

The baseline archive carries both the **numeric inputs** to the averaging
(`baseline_plot_seasons.csv` holds per-plot-season-week NDVI + observation counts)
and, behind them, the **raw clipped Sentinel-2 / NDVI rasters** per donor plot and
season (toggle `NDVI_BASELINE_EXPORT_IMAGERY`, default on). So a sector baseline can
be traced back numerically *and* visually.

**One date-first GCS archive for every epic.** The master switch `GCS_ARCHIVE`
(with `GCS_BUCKET`) archives the deliverables of *all three* epics to a single
bucket, classified by the day they were produced — so "what did we produce on this
date" is one folder:

```
gs://<GCS_BUCKET>/<YYYY-MM-DD>/e1.1-chirps/    lookup CSVs + average & seasonal rasters + boundary
gs://<GCS_BUCKET>/<YYYY-MM-DD>/e1.2-baseline/  baseline CSVs + imagery (incl. baseline NDVI)
gs://<GCS_BUCKET>/<YYYY-MM-DD>/e1.2-cycle/     cycle alert log + imagery + run log
gs://<GCS_BUCKET>/<YYYY-MM-DD>/e1.3-pilot/     pilot sign-off xlsx / csv / txt
```

Large re-downloadable intermediates (raw monthly CHIRPS, clips) are intentionally
skipped. `NDVI_GCS_ARCHIVE` stays as a back-compat alias that enables E1.2 on its own.

**Finding the NDVI rasters quickly.** On top of the run archive above, the NDVI
GeoTIFFs are *also* mirrored into a dedicated, browsable folder so the client never
has to dig through run folders:

```
gs://<GCS_BUCKET>/ndvi/baseline/<date>/<plot>_<start>_<end>_ndvi.tif   ← baseline NDVI
gs://<GCS_BUCKET>/ndvi/current/<date>/<plot>_<start>_<end>_ndvi.tif    ← each cycle's NDVI
```

The folder name is `NDVI_TIFF_PREFIX` (default `ndvi`).

**Irrigated is not yet active.** The current registry has usable donor data only for
the **rainfed** sector (the client's coordinates file is rainfed-only). The irrigated
sector baseline is therefore empty, so a monitored irrigated farmer currently gets no
comparison — irrigated monitoring needs real irrigated donor plots first.

**Two operational notes:** an unknown `sector` is rejected/defaulted at load (a typo
cannot silently drop a plot or suppress its alerts), and removing a plot or season from
the registry is detected as stale and forces a baseline rebuild on the next run.

```bash
pip install earthengine-api google-api-python-client google-auth
python ndvi_run_pipeline.py        # runs steps 0 → 1 → 2 (stops on first failure)
# or single steps / utilities:
python ndvi/baseline.py --dry-run                 # print the build plan, no credentials needed
python ndvi/current.py --date 2025-08-15 --push   # re-check a date, write the Sheet
python ndvi/exports.py --plot BP008 --season 2024 # raw clipped + NDVI + RGB for any window
```

**Setup (one-time):** create a Google Cloud project, enable the Earth Engine + Sheets
APIs (+ Cloud Storage if you use the run archive), register the project for Earth
Engine, create a service account (roles
`roles/serviceusage.serviceUsageConsumer` + Earth Engine **Writer**) and download its
key JSON, then create the output Google Sheet and **share it (Editor) with the
service-account email** (service accounts cannot create their own Sheets). Locally set
`EE_PROJECT_ID`, `GEE_SERVICE_ACCOUNT_JSON` (key file path) and `NDVI_SHEET_ID` in
`.env`; on GitHub Actions the key JSON's **contents** go into the `GEE_SERVICE_ACCOUNT_INFO`
secret instead of a path. The full click-by-click walkthrough for both local and CI is in
**[`docs/SETUP_CREDENTIALS.md`](docs/SETUP_CREDENTIALS.md)**.

The alert rule, season window, minimum season year, cloud-mask method (`scl` default /
`cloudscore`), export bands, GCS archiving and all thresholds are config-driven —
see the `.env.example` "NDVI" block. Full
details are in [`docs/ndvi/NDVI_METHODOLOGY.md`](docs/ndvi/NDVI_METHODOLOGY.md); the
plain-English operator guide for the PM is
[`docs/ndvi/NDVI_PM_GUIDE.md`](docs/ndvi/NDVI_PM_GUIDE.md). The
[`.github/workflows/e1.2-ndvi-monitor.yml`](.github/workflows/e1.2-ndvi-monitor.yml) workflow adds
a manual "Run workflow" button plus a ~10-day in-season schedule. It pushes to the
`NDVI_Log` Sheet (`NDVI_SHEET_PUSH=true`) and runs on the in-season cron once its
GitHub Secrets/Variables are configured per
[`docs/SETUP_CREDENTIALS.md`](docs/SETUP_CREDENTIALS.md).

## Pilot Launch Check (farmer sign-off gate)

`tools/pilot_launch_check.py` is the sign-off gate run **before**
the first farmer approvals. It applies the rainfall lookup to all configured registered farmers
and writes a sign-off package — no Earth Engine, Sheets or network access needed, so it
runs offline straight from the committed step-3 lookup CSV.

```bash
python tools/pilot_launch_check.py                                            # all configured farmers
python tools/pilot_launch_check.py --farmers-csv path/to/registry.csv
python tools/pilot_launch_check.py --farmers-csv path/to/registry.csv --limit 10
python tools/pilot_launch_check.py --lookup-csv path/to/lookup.csv           # pin a specific lookup
```

Flags: `--farmers-csv` (default `SNAP_FARMERS_CSV`, i.e. `data/farmers/farmers.csv`),
`--lookup-csv` (default: newest `Mahala_CHIRPS_grid_lookup_*.csv` in `data/05_tables/`),
`--limit` (optional; omit to check all rows).

It writes three files into `data/pilot_check/`:

| File | Contents |
|------|----------|
| `E1.3_Pilot_Check_<date>.xlsx` | Per-farmer check sheet with a live VLOOKUP, the `score_lookup` tab, and a sign-off tab |
| `E1.3_Pilot_Check_<date>.csv` | The same check rows, flat |
| `E1.3_Signoff_Request_<date>.txt` | Plain-language sign-off request |

It deliberately reuses the **exact** snapping (`snap_to_grid_center` + grid-key
match, not nearest-neighbour) and **never silently scores a farmer outside the AOI** —
those are escalated for manual review while the sign-off stays valid for the in-AOI
farmers. Every scored farmer is cross-checked two independent ways (stored score vs.
`score_from_rainfall`); any score `MISMATCH` sets the status to **`BLOCKED`** and the run
exits non-zero, so a faulty lookup cannot be signed off.

## Configuration (`.env`)

All paths and parameters come from a single `.env` file in the repo root. Every
setting has a working default, so an unedited `.env` (or none at all) still runs.

| Variable          | Default                              | Meaning |
|-------------------|--------------------------------------|---------|
| `DATA_ROOT`       | *(blank)* → `./data`                 | Where all generated data is stored. Blank = the `data/` folder next to the scripts, so it works on any OS without edits. Set an absolute/relative path to store data elsewhere. |
| `BOUNDARY_GEOJSON`| `Mahala.geojson`                     | The AOI boundary input file. |
| `SNAP_FARMERS_CSV`| `data/farmers/farmers.csv`           | Farmer GPS registry read by `snap_score`, `google_sheets_lookup` and the pilot check. The common production change — point this at your CSV and re-run (no pipeline re-run needed). |
| `START_YEAR`      | `2014`                               | First year (inclusive). |
| `END_YEAR`        | `2024`                               | Last year (inclusive). |
| `SEASON_MONTHS`   | `6,7,8,9`                            | In-season months (6=June … 9=September). |
| `KEEP_GZ`         | `true`                               | Keep the `.tif.gz` after unzip. `false` deletes it to halve raw storage. |
| `BASE_URL`        | CHIRPS v2.0 africa_monthly archive   | Download source (rarely changed). |
| `PRODUCT_PREFIX`  | `chirps-v2.0`                        | Filename prefix: `<PREFIX>.<year>.<MM>.tif(.gz)`. |
| `DOWNLOAD_RETRIES`| `3`                                  | Download attempts per file before giving up. |
| `DOWNLOAD_TIMEOUT`| `120`                                | Per-request timeout (seconds). |
| `NODATA`          | `-9999.0`                            | NoData value written into clipped/derived rasters. |

The table above lists the core CHIRPS settings. The full **NDVI** block (`EE_*`,
`NDVI_*`, `GCS_*`, `S2_*`, `CLOUD_*`, `BASELINE_*`, `AOI_*`), including the optional
Google Cloud Storage run archive, is documented inline in
[`.env.example`](.env.example), which is the single source of truth for every setting.

**To change what the pipeline does, edit `.env` and re-run — no code changes needed.**

## Data layout

Everything generated lands under `DATA_ROOT` (default `data/`):

```
data/
├── 00_boundary/          Mahala_closed.geojson           (kept in git)
├── 01_raw_africa_monthly/<year>/<MM_Month>/*.tif(.gz)    (ignored — large)
├── 02_clip/<year>/chirps-v2.0.<year>.<MM>_<month>.tif    (ignored — intermediate)
├── 03_seasonal_totals/<year>/Mahala_CHIRPS_<season>_total_<year>.tif   (ignored)
├── 04_average/Mahala_CHIRPS_<season>_average_<start>_<end>_<n>years.tif (kept in git)
└── 05_tables/Mahala_CHIRPS_grid_lookup_<start>_<end>_<n>years.csv       (kept in git)
```

Raw and intermediate rasters (hundreds of MB) are git-ignored; the small final
deliverables — the closed boundary, the average raster, and the lookup CSV — are
committed (see `.gitignore`).

## Output: the lookup table

`data/05_tables/Mahala_CHIRPS_grid_lookup_2014_2024_11years.csv`, one row per valid
grid cell:

| Column | Meaning |
|--------|---------|
| `grid_key` | `lat_lon` key (3 decimals) for VLOOKUP in Google Sheets |
| `lat_center`, `lon_center` | Cell-centre coordinates |
| `jun_sep_total_<year>_mm` | Per-year June–September total (mm) |
| `avg_jun_sep_2014_2024_mm` | 11-year average (mm) |
| `score_1_10` | Mahsooli rainfall score |

**Scoring rubric** (average mm → score): `≥350 → 10`, `250–349 → 7`,
`150–249 → 4`, `<150 → 1`.

## Methodology notes

The full dated methodology note (data provenance, decisions, anomalies) is in
[`docs/METHODOLOGY.md`](docs/METHODOLOGY.md). Summary:

- **Source:** CHIRPS v2.0 `africa_monthly` (data.chc.ucsb.edu).
- **Resolution / CRS:** 0.05°, EPSG:4326 (lon/lat WGS84). The boundary is in the
  same CRS, so no reprojection is performed.
- **Period:** 2014–2024 = **11 inclusive years**. This is intentional: the client
  approved those start/end dates even though the PDF wording says "10-year".
- **AOI boundary:** the pipeline uses the client-provided GeoJSON, not a generated
  replacement boundary.
- **AOI result:** 52 valid grid cells; observed average 645.8–842.2 mm.
- **Known anomaly:** every cell scores **10** (all values ≥ 350 mm), so the V5
  rainfall score has **no variance** across this AOI — flag with Mahsooli whether
  the rubric or AOI needs revisiting to differentiate farmers.

## Possible future optimisation

Step 0 downloads the full Africa raster for each month (then clips). Downloading a
Gedaref bounding-box subset would cut storage/bandwidth. It is intentionally left
as-is so output stays byte-identical to the validated run; if adopted, verify the
lookup CSV is unchanged. (A `KEEP_GZ=false` option already exists to reduce raw
storage without affecting results.)

## Requirements

- **Python 3.12+** (pinned in `.python-version`; required by `rasterio==1.5.0`).
- `numpy==2.4.6`, `rasterio==1.5.0`; everything else uses the standard library.
  Versions are pinned in `pyproject.toml` and locked in `uv.lock` (used by `uv sync`);
  `requirements.txt` carries the same pins for the pip path.
- Optional NDVI dependencies: `earthengine-api`, `google-api-python-client`,
  `google-auth`, and `google-cloud-storage` (for the run archive) — install with
  `pip install ".[ndvi]"`. `openpyxl` (already pinned) builds the Excel workbook.
- `rasterio` wheels bundle **GDAL/PROJ**, so `pip install` works on macOS/Windows/Linux
  without a system GDAL. If another tool (e.g. a system PostgreSQL/PostGIS) injects an
  old `proj.db` and you hit a `proj.db ... VERSION.MINOR` error, `config.configure_proj_database()`
  auto-resolves it; using a clean virtualenv avoids it entirely.

## License

Proprietary. Licensing terms (copyright holder / client-ownership) are to be confirmed
with the client at handover.
