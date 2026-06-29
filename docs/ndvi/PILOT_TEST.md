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
Sheet even if `.env` enables the push. The baseline build makes ~53 Earth
Engine calls and takes several minutes.

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

Expected totals: manifest = 11 plots (9 in AOI, 2 outside), 2 skipped;
`data_pilot/ndvi/baseline.csv` = 11 × 53 = 583 rows; no `*.part` file left
behind anywhere.

Weather caveat: PILOT09's buckets depend on actual cloud cover. The checklist
asks for the right *bucket*, not exact counts. If a dry spell leaves no cloudy
window, force the No-data path once with `NDVI_CURRENT_MIN_COUNT=99` added to
the run command.

## What to verify in the output

1. `WARN [farmers]` lines for row 12 and PILOT13; `WARN ... outside the Gedaref AOI`
   for PILOT07/PILOT08; final farmers line says `Valid plots: 11  Skipped: 2  Outside AOI: 2`.
2. Baseline ends with the `BASELINE RUN SUMMARY` block and a `RUN-SUMMARY [baseline] ...`
   line where `cells=583 complete=yes` and the three buckets (full_conf / low_conf /
   no_imagery) sum to 583.
3. Current ends with `RUN-SUMMARY [current] ... no_coverage=2` and per-plot lines
   matching the table above.

## Failure drills (each must produce its specific message, not a traceback)

All inside the pilot env (`NDVI_FARMERS_CSV=... DATA_ROOT=data_pilot`):

| Drill | How | Must see (and `echo $?`) |
|---|---|---|
| Interrupted build | `python ndvi/baseline.py --refresh`, Ctrl-C mid-run | `INTERRUPTED [baseline] - no partial output was finalized` (130); at most a `.part` file; previous `baseline.csv` untouched; re-run completes |
| Truncated legacy file | `head -200 data_pilot/ndvi/baseline.csv > t && mv t data_pilot/ndvi/baseline.csv` | `python ndvi/current.py` → `ERROR [current] baseline-incomplete: ... run: python ndvi/baseline.py --refresh` (6); `python ndvi/baseline.py` → `WARN [baseline] ... incomplete ... rebuilding`, then rebuilds |
| EE auth failure | `EE_PROJECT_ID=does-not-exist python ndvi/baseline.py --refresh` | `ERROR [...] ee-auth: ...` (4), no retries spent |
| EE transient failure | `EE_RETRIES=2 EE_RETRY_BASE_DELAY=1 python ndvi/baseline.py --refresh`, cut the network after week 1 | `RETRY [...]` lines, then `ERROR [baseline] ee-transient: ... failed after 2 attempts` (5); `.part` removed, `baseline.csv` unchanged |
| Zero valid input | point `NDVI_FARMERS_CSV` at a header-only CSV | `ERROR [farmers] invalid-input: 0 valid farmer rows ...` (2) |
| Missing prerequisite | `rm data_pilot/ndvi/farmers_normalized.csv && python ndvi/baseline.py` | `ERROR [farmers] missing-prereq: ... run this first: python ndvi/farmers.py` (3) |

## Regression on real data (before merging)

Run the pipeline plainly (no overrides): the committed 530-row baseline must
pass validation against the committed 10-farmer manifest and print
`SKIP - baseline already exists and is complete`, and the dated log must keep
the same 7 columns as `data/ndvi/ndvi_log_2026-06-08.csv`.
