# GPS → grid → score in Google Sheets

This is the spreadsheet workflow that turns a farmer's GPS coordinate into a
rainfall score using the lookup table from the pipeline
(`data/05_tables/Mahala_CHIRPS_grid_lookup_*.csv`).

`tools/snap_score.py` is the runnable reference implementation of exactly this logic —
run it to verify the formulas below on the sample farmers.

> **Local vs. Google Sheets:** the deliverable only requires a two-column lookup
> *importable into Google Sheets* — the local CSV/`.xlsx` already satisfy that.
> Publishing a live Sheet (`tools/google_sheets_lookup.py --upload-google-drive`) is an
> optional convenience; there is no requirement to upload every CSV to Drive.

## 1. Import the lookup table

`File → Import → Upload` the lookup CSV into a tab named **`lookup`**. It is UTF-8,
comma-delimited, so it imports without reformatting. Key columns:

- `grid_key` (column **A**) — e.g. `13.475_35.975`
- `score_1_10` (the last column)

## 2. Snap a coordinate to its grid key

CHIRPS cells are 0.05° wide with centres at `.x25` / `.x75`. With the farmer's
latitude in `A2` and longitude in `B2`, the cell-centre key is:

```
=TEXT((FLOOR(A2/0.05)+0.5)*0.05,"0.000") & "_" & TEXT((FLOOR(B2/0.05)+0.5)*0.05,"0.000")
```

Example: `13.470, 35.980` → `13.475_35.975`.

## 3. Look up the score (with an out-of-AOI fallback)

Put the key from step 2 in `C2`, then:

```
=IFNA(
   INDEX(lookup!$A:$Z, MATCH(C2, lookup!$A:$A, 0), MATCH("score_1_10", lookup!$1:$1, 0)),
   "Outside coverage area - no score (escalate for manual review)"
 )
```

`INDEX/MATCH` finds the `score_1_10` column by **name**, so it keeps working even
though the table is wide (per-year columns sit between `grid_key` and the score).
`IFNA` turns a missing key (coordinate outside the Mahala AOI) into a plain-English
message instead of `#N/A`.

A one-cell `VLOOKUP` alternative (if you first build a 2-column `grid_key,score`
helper range named `lookup2`):

```
=IFNA(VLOOKUP(C2, lookup2!$A:$B, 2, FALSE), "Outside coverage area - escalate")
```

## 4. Verify (≥5 sample farmers)

`docs/sample_farmers.csv` (the default `SNAP_FARMERS_CSV`) has 6 coordinates (5 inside
the AOI, 1 outside). Run:

```bash
python tools/snap_score.py
```

Expected: `F001`–`F005` each return a score of **10**; `F006` (13.000, 35.000) is
flagged as outside the coverage area. The same six rows pasted into the sheet with
the formulas above must produce identical results — no `#N/A`.

To score real farmers, set `SNAP_FARMERS_CSV` in `.env` to your own CSV (any file with
`lat`, `lon` and an id column named `farmer_id`, `mahsooli_id` or `id`) and re-run
`python tools/snap_score.py` — the pipeline (steps 0–3) does not need to re-run.
