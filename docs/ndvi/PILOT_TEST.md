# E1.2 Pilot Test — real plots, every error path

A manual, pre-merge test of the NDVI pipeline's error handling using
`docs/pilot_test_plots.csv` (13 rows → 11 valid plots). Each plot is placed to
exercise one path — normal data, no clear imagery, low confidence,
out-of-coverage, invalid input — and the checklist below says exactly which
message each one must produce. Nothing here touches the committed
`data/ndvi/` outputs: everything is written under an isolated, git-ignored
`data_pilot/` root.

## How to run

```bash
NDVI_FARMERS_CSV=docs/pilot_test_plots.csv DATA_ROOT=data_pilot NDVI_SHEET_PUSH=false python ndvi_run_pipeline.py
```

Shell environment variables override `.env`, so no config edits are needed.
`NDVI_SHEET_PUSH=false` keeps the PILOT test rows out of the production Google
Sheet even if `.env` enables the push. The sector-baseline build uses the donor
plot registry and makes one reduceRegions call per usable season/week; with the
current committed registry that is 5 seasons × 44 weeks = 220 Earth Engine calls.

## Plot checklist

| Plot | Location (lat, lon, r) | Why it's there | Expected result |
|---|---|---|---|
| PILOT01 | 13.470, 35.980, 100 m | known-good Gedaref cell (mirrors M001) | normal data; full-confidence baseline; flag `No` (or `Yes` if genuinely stressed) |
| PILOT02 | 13.462, 36.031, 100 m | second known-good cell | normal data |
| PILOT03 | 14.200, 35.200, 100 m | north-central AOI, different area | normal data |
| PILOT04 | 14.750, 34.800, 200 m | north-west AOI, larger plot | normal data |
| PILOT05 | 13.418, 35.933, 50 m | tiny plot (few 10 m pixels) | normal data; exercises small-geometry reduce |
| PILOT06 | 13.000, 34.500, 100 m | exactly on the AOI corner | `in_aoi=yes` in the manifest (bounds are inclusive) — boundary regression |
| PILOT07 | 12.990, 35.900, 100 m | just outside the AOI (lat 12.99) | `WARN [farmers] ... outside the Gedaref AOI`; baseline rows still built; current flag `No coverage` |
| PILOT08 | 12.100, 33.500, 100 m | far outside (mirrors M010) | `No coverage` |
| PILOT09 | 13.050, 36.450, 150 m | SE corner toward the Ethiopian highlands — cloudiest area in the Jun–Sep wet season | wet-season weeks land in the LOW CONFIDENCE / NO CLOUD-FREE IMAGERY summary buckets; an in-season current run likely flags `No data` with "too few cloud-free images this window (n/2)" — NOT a generic failure |
| PILOT10 | 14.950, 36.480, 100 m | near the NE corner, distinct Sentinel-2 tile | normal data |
| PILOT11 | 13.444, 35.884, 250 m | large plot | normal data |
| (row 12) | 13.500, 35.500 — no id | invalid input: missing mahsooli_id | `WARN [farmers] invalid-row: missing mahsooli_id`, skipped |
| PILOT13 | 99.000, 35.500 | invalid input: impossible latitude | `WARN [farmers] invalid-row: lat/lon out of range`, skipped |

Expected farmer manifest totals: 11 valid farmer rows (9 in AOI, 2 outside), 2
skipped. Baseline outputs are the sector-methodology files:
`baseline_plot_seasons.csv`, `baseline_plots.csv`, and `baseline_sector.csv`;
no `*.part` file should be left behind anywhere.

Weather caveat: PILOT09's buckets depend on actual cloud cover. The checklist
asks for the right *bucket*, not exact counts. If a dry spell leaves no cloudy
window, force the No-data path once with `NDVI_CURRENT_MIN_COUNT=99` added to
the run command.

## What to verify in the output

1. `WARN [farmers]` lines for row 12 and PILOT13; `WARN ... outside the Gedaref AOI`
   for PILOT07/PILOT08; final farmers line says `Valid plots: 11  Skipped: 2  Outside AOI: 2`.
2. Baseline ends with the `BASELINE RUN SUMMARY` block and a `RUN-SUMMARY [baseline] ...`
   line showing the donor plot count, season count, 44-week sector curves, and
   `complete=yes`.
3. Current ends with `RUN-SUMMARY [current] ... no_coverage=2` and per-plot lines
   matching the table above.

## Failure drills (each must produce its specific message, not a traceback)

All inside the pilot env (`NDVI_FARMERS_CSV=... DATA_ROOT=data_pilot`):

| Drill | How | Must see (and `echo $?`) |
|---|---|---|
| Interrupted build | `python ndvi/baseline.py --refresh`, Ctrl-C mid-run | `INTERRUPTED [baseline] - no partial output was finalized` (130); at most a `.part` file; previous baseline CSVs untouched; re-run completes |
| Truncated sector file | truncate `data_pilot/ndvi/baseline_sector.csv` | `python ndvi/current.py` → `ERROR [current] baseline-incomplete/baseline-corrupt: ... run: python ndvi/baseline.py --refresh` (6); `python ndvi/baseline.py` rebuilds |
| EE auth failure | `EE_PROJECT_ID=does-not-exist python ndvi/baseline.py --refresh` | `ERROR [...] ee-auth: ...` (4), no retries spent |
| EE transient failure | `EE_RETRIES=2 EE_RETRY_BASE_DELAY=1 python ndvi/baseline.py --refresh`, cut the network after week 1 | `RETRY [...]` lines, then `ERROR [baseline] ee-transient: ... failed after 2 attempts` (5); partial files removed and previous baseline outputs untouched |
| Zero valid input | point `NDVI_FARMERS_CSV` at a header-only CSV | `ERROR [farmers] invalid-input: 0 valid farmer rows ...` (2) |
| Missing prerequisite | `rm data_pilot/ndvi/farmers_normalized.csv && python ndvi/baseline.py` | `ERROR [farmers] missing-prereq: ... run this first: python ndvi/farmers.py` (3) |
| Required imagery export failure | force an export error with `NDVI_REQUIRE_EXPORTS=true` | `ERROR [baseline|current] imagery-export: ...` (9); the message names the plot/window and the run log has details |

## Regression on real data (before merging)

Run the pipeline plainly (no overrides): the committed sector baseline must pass
validation, the financed-farmer manifest from `data/farmers/farmers.csv` must join
the monitored set, and the dated log must keep the same 7 columns as the existing
`data/ndvi/ndvi_log_*.csv` files.
