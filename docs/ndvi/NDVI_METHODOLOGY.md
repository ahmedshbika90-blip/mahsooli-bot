# NDVI Monitoring — Methodology Note

This note documents how the Sentinel-2 NDVI crop-health pipeline works, the choices
made for the Sudan context, and its known limitations. It is the technical
companion to the plain-English `NDVI_PM_GUIDE.md`.

## What it produces

For each monitored plot, on a 7–10 day cycle through the cotton season (June –
March), the pipeline measures how green/healthy the crop is (NDVI) from
Sentinel-2 satellite imagery, compares it to the **sector baseline** (rainfed or
irrigated "normal" for that week of the season), and raises a field-visit alert
when the crop is materially below normal. Results land in the `NDVI_Log` tab of
the Mahsooli Google Sheet (7 columns) and a local CSV; each run also saves the
per-plot **raw clipped Sentinel-2 imagery, NDVI raster (GeoTIFF) and RGB / NDVI
quicklooks (PNG)** plus a structured run log, optionally mirrored to a dated
Google Drive folder for traceability.

## Data source

- **Imagery:** `COPERNICUS/S2_SR_HARMONIZED` (Sentinel-2 Level-2A surface
  reflectance, harmonized so the multi-year series is internally consistent).
- **Index:** NDVI = (B8 − B4) / (B8 + B4), via `normalizedDifference(['B8','B4'])`,
  sampled at 10 m. NDVI is scale-invariant, so no reflectance rescaling is needed.
- **Platform:** Google Earth Engine (server-side compute), accessed from Python with
  a service account. `getInfo()` returns results synchronously — fine for the
  ~10–100 plot scale (well under Earth Engine's 5000-element client limit).

## Plot geometries

The baseline-donor registry (`data/farmers/baseline_plots.csv`, parsed by
`ndvi/registry.py`) supports two geometry types:

- **Polygons** — the client-surveyed plot boundaries (WKT, lon/lat). Rings are
  validated for closure, ≥3 distinct vertices and self-intersection (warn, never
  silently "fixed"), and the planar area is cross-checked against the stated
  feddan (warn when off by >50% — catches transposed coordinates).
- **Points** — buffered by a radius derived from the stated area:
  `radius = sqrt(area_feddan × 4200 m² / π)` (e.g. 850 feddan → 1 066 m). DMS
  coordinates (e.g. `13°59'45"N`) are converted automatically.

Monitored financed farmers (later, via `NDVI_MONITOR_FARMERS`) stay point +
`radius_m` circles with an optional `sector` column.

## Cloud masking

Two methods, switchable via `CLOUD_MASK_METHOD`:

- **`scl` (default, per the PRD):** drops Scene Classification Layer classes
  3 (cloud shadow), 8 (cloud medium), 9 (cloud high), 10 (cirrus), 11 (snow).
- **`cloudscore` (recommended upgrade for Sudan):** Google's Cloud Score+
  (`cs_cdf ≥ 0.60`). SCL is known to over-mask bright bare soil in arid regions,
  dropping otherwise-valid pixels; Cloud Score+ handles clouds and shadows in one
  continuous score and performs better over bright surfaces. Both are supported so
  the PRD requirement is met while a better option is one config flag away.

## Baseline (the "normal") — sector methodology

The plots being financed will not have their own usable history, so the baseline
comes from **donor plots**: a client-curated collection of plots that grew cotton
in known years (no single farmer has enough history for a good average — this
spreads the curve over many plots and seasons). Two separate baselines are kept,
because Sudan's **rainfed** and **irrigated** sectors perform differently.

- **Season window:** one cotton season Y runs **Jun 1 (Y) → Mar 31 (Y+1)**
  (sowing through harvest spillover), binned into **44 seven-day weeks keyed
  relative to Jun 1** — absolute date offsets, so curves from different years
  align week-for-week, leap Februaries need no special casing, and the old
  calendar DOY week-53 problem is retired. Week 44 is a short 3–4 day stub.
- **Season selection:** each plot contributes **only its listed cotton seasons**
  (the registry `seasons` column = years cotton was planted; other years were
  other crops and would poison the curve). Seasons before `MIN_SEASON_YEAR`
  (2019 — Sentinel-2 SR over Sudan only exists from ~Dec 2018) and unfinished
  seasons are skipped, with the reason recorded in the manifest and run log
  (e.g. Bahaa Eldeen Daood's 2013/2015/2017 seasons).
- **Two-stage averaging:**
  1. `baseline_plot_seasons.csv` — one curve per (plot, season): traceability.
  2. `baseline_plots.csv` — per plot: mean over its seasons-with-data.
  3. `baseline_sector.csv` — per sector: mean over the plot curves. Averaging
     plots (not raw seasons) keeps a many-season plot from dominating.
- **Trust gate:** a (plot, season, week) cell below `BASELINE_MIN_COUNT`
  (default 3) cloud-free observations is untrusted; plot- and sector-level rows
  where no contributing cell is trusted are marked **low confidence**, and the
  alert logic will not fire on them. The live comparison applies the same
  discipline via `NDVI_CURRENT_MIN_COUNT` (default 2).
- The baseline is built once and validated-then-skipped on later runs;
  `python ndvi/baseline.py --refresh` rebuilds. `--dry-run` prints the full
  execution plan (plots, seasons, EE call count) without credentials;
  `--plot BP008` smoke-tests one plot into `*.smoke.csv` files.

## Alert rule

`deviation % = (current NDVI − sector baseline for this season-week) / baseline × 100`.
A plot is flagged **"Yes" (field visit required)** only when **all three** hold:

1. deviation % < `NDVI_DEVIATION_ALERT_PCT` (default −20%), and
2. baseline ≥ `NDVI_VEG_FLOOR` (default 0.20 — real vegetation present), and
3. absolute drop (baseline − current) ≥ `NDVI_ABS_DROP_FLOOR` (default 0.05).

A pure 20%-relative rule is unstable at the low NDVI typical of arid bare soil
(e.g. a 20% drop on a baseline of 0.15 is ~0.03 NDVI — within noise). The two floors
suppress those false alarms while keeping the PRD's 20%-below-baseline behaviour for
genuinely vegetated plots. All thresholds are config-driven.

## Output

Local CSV (`data/ndvi/ndvi_log_<date>.csv`) and the Google Sheet `NDVI_Log` tab share
the same 7 columns (unchanged from the original handover):

`Mahsooli ID | Date | NDVI value | Baseline value | Deviation % | Alert flag | Window`

Alert flag values: **Yes** (field visit), **No** (healthy / not anomalous), **No data**
(fewer than `NDVI_CURRENT_MIN_COUNT` cloud-free images this window — never a false
alert), **No coverage** (GPS outside the sector AOI — manual review), and
**Off-season** (run dated Apr 1 – May 31, between cotton seasons — no Earth Engine
quota is spent). The Sheet is upserted by (Mahsooli ID, Date), so re-runs never
duplicate a cycle. A separate **`Sector_Baseline` tab** (rewritten on each push)
shows the per-sector weekly curve being compared against, with week date ranges
and confidence. Service accounts cannot create/own Sheets, so the workbook is
human-created and shared (Editor) with the service-account email.

## Imagery exports (raw clipped data, NDVI, RGB)

Per plot and window, `ndvi/exports.py` saves four artifacts: the raw clipped
Sentinel-2 composite (`NDVI_EXPORT_BANDS`, default B2/B3/B4/B8 — the 10 m native
bands — as a cloud-masked median, GeoTIFF), the NDVI raster (GeoTIFF, float),
and RGB + NDVI PNG quicklooks. Generated automatically each monitoring cycle
(`NDVI_EXPORT_ENABLED`) and on demand:

```
python ndvi/exports.py --plot BP008 --season 2024
python ndvi/exports.py --all-plots --start 2025-08-01 --end 2025-08-15
```

Implementation: synchronous `getDownloadURL(format='GEO_TIFF')` / `getThumbURL`
with atomic downloads and retries. The plots are tiny (largest ~2×2 km ≈ 0.4 MB
raw), far below Earth Engine's ~50 MB synchronous cap; a pre-flight estimate
enforces `NDVI_EXPORT_MAX_BYTES`. `ee.batch.Export.toDrive` was rejected because
it exports to the *service account's* own Drive (not browsable by humans) and is
asynchronous.

The **baseline build** reuses the same exporter for the **donor plots**: with
`NDVI_BASELINE_EXPORT_IMAGERY` (default on) it writes one artifact set per
(donor plot, usable season) into `data/ndvi/runs/<date>_baseline/imagery/`, so the
raw rasters behind each sector baseline are archived next to the CSVs — not only
the per-plot-season-week NDVI numbers in `baseline_plot_seasons.csv`. Imagery is
supplementary: the baseline CSVs are finalized first, and any export failure is
recorded in the run log and skipped, never failing the build.

## Run archive (traceability)

Every baseline / cycle / export run writes a dated local folder
`data/ndvi/runs/<date>_<kind>/` containing the imagery, copies of the tables and
a `run_log.json` (parameters, whitelisted config snapshot, per-plot statuses,
skipped seasons, artifacts, errors — never credentials). With
`NDVI_DRIVE_ARCHIVE=true` (or `--archive`) the folder is mirrored to
`GOOGLE_DRIVE_FOLDER / E1.2_runs / <date>_<kind>` so any number in the Sheet can
be traced back to the exact inputs and settings that produced it. Re-archiving
updates files in place (no duplicates). Note: a service account can only write
into a **Shared Drive** folder (no personal Drive storage); the OAuth-user flow
works for a normal "My Drive" folder.

## Known limitations / things to surface, not hide

- **Cloudy growing season:** June–September is the rainy season, so clear pixels are
  scarcest exactly when monitoring matters most. The 10-day window, the
  `NDVI_CURRENT_MIN_COUNT` gate and the "No data" flag prevent false anomalies.
- **Irrigated sector is not yet active.** The client's coordinates file is
  rainfed-only; the single irrigated donor (New Halfa, 2024, 10 feddan) yields no
  usable weekly cells, so `baseline_sector.csv` has an **empty** irrigated curve.
  A monitored irrigated farmer therefore gets no comparison until real irrigated
  donor plots are collected — flag this to the client rather than treating
  irrigated monitoring as live.
- **Single-season rainfed plots** (Musaab, Alem Eldeen): inter-annual variance is
  not averaged out for their contribution; mitigated by averaging across plots.
- **Phenology mixing:** Gala'a Al Nahal (~12.8°N) and Gallabat (~13.4°N) may green
  up weeks apart; a single rainfed curve blurs onset. Per-plot curves are retained
  (`baseline_plots.csv`), so a per-locality split is a config change later.
- **Donor plots vs financed plots:** donors are 150–1000 feddan field aggregates;
  financed farmers will be ~100 m circles. Absolute NDVI levels can differ
  systematically, so the −20% rule may need tuning after one observed season.
- **Stated vs measured areas:** the registry validator measures some polygons well
  below their stated feddan (BP003 ~351 vs 900, BP005 ~498 vs 1000, BP006 ~62 vs
  500) — flagged to the client; the polygon (not the stated area) is what's used.
- **GPS outside the AOI:** flagged "No coverage" for manual review rather than crashing.
- **Earth Engine quota:** a full baseline build is ~220 `reduceRegions` calls
  (5 distinct seasons × 44 weeks); cycles add 1 call + 4 small downloads per plot.
  If the plot count grows into the thousands, switch to batch `Export` tasks.
