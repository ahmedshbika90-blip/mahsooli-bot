# Methodology Note — Mahala CHIRPS Rainfall Score

**Deliverable:** CHIRPS rainfall lookup table for the Mahala AOI (Gedaref, Sudan).
**Prepared:** 2026-06-05.
**Data downloaded:** 2026-06-04.

## Data provenance

- **Source:** CHIRPS v2.0 `africa_monthly` precipitation, Climate Hazards Center,
  UC Santa Barbara (https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs).
- **Variable / units:** monthly precipitation (mm); the deliverable uses the
  **June–September seasonal total (mm)**.
- **Spatial resolution / CRS:** 0.05° grid, EPSG:4326 (lon/lat WGS84). The Mahala
  boundary is in the same CRS, so no reprojection is performed.
- **Period:** 2014–2024 inclusive. These start/end years were client-approved,
  even though the PDF wording says "10-year".

## Processing summary

1. Download CHIRPS Africa monthly rasters for months 06–09, 2014–2024 (44 files).
2. Close the open `Mahala.geojson` boundary into a polygon.
3. Clip each monthly raster to the polygon (a cell enters a seasonal total only
   where **all four** in-season months have data).
4. Sum Jun–Sep per year (11 seasonal-total rasters), then average per grid cell
   across the years (a cell is averaged only where **all 11 years** are present).
5. Apply the Mahsooli rubric and emit the grid lookup table.

**Scoring rubric (average mm → score):** `≥350 → 10`, `250–349 → 7`,
`150–249 → 4`, `<150 → 1`.

## Results

- **Grid cells retained:** **52** valid 0.05° cells inside the AOI.
- **Average seasonal rainfall:** **645.8–842.2 mm** across the AOI.
- **Data gaps:** none (every cell has all 4 months × 11 years).

## Documented decisions & anomalies

- **Period — 11 inclusive years used.** 2014–2024 inclusive is 11 years; this
  matches the client-approved start/end dates. Changing `START_YEAR`/`END_YEAR`
  in `.env` and re-running regenerates the table for any other approved period.
- **Zero score variance — every cell scores 10.** All AOI averages are ≥ 350 mm, so
  the V5 rainfall score is **10 for all 52 cells** and does not differentiate
  farmers within this AOI. **Recommendation:** raise with Mahsooli whether the
  rubric thresholds or the AOI need revisiting so the rainfall variable can
  discriminate risk.
- **Boundary source.** The pipeline uses the GeoJSON provided by the client.
  The source boundary was an open line; it was closed into a polygon by extending
  its terminal segments to their intersection (recorded in the output GeoJSON as
  `closure_method: extended_first_last_segments`).
- **Full-Africa download retained.** Step 0 downloads the full Africa monthly raster
  and then clips, rather than requesting a Gedaref bounding-box subset. Kept as-is so
  output stays byte-identical to this validated run; a bbox subset is recorded as an
  optional future optimisation (see README) and, if adopted, must reproduce the same
  lookup table.

## Reproducibility

Pinned dependencies (`numpy==2.4.6`, `rasterio==1.5.0`, Python 3.12) and a fixed
`.env` make the run reproducible: `python run_pipeline.py` regenerates the average
raster and lookup CSV; `python tools/snap_score.py` verifies GPS→score on the
configured farmer file (`SNAP_FARMERS_CSV`, default `data/farmers/farmers.csv`).
