# NDVI Crop Monitoring — One-Page Guide for the Product Manager

This pipeline checks every monitored plot from satellite every ~10 days during the
cotton season and tells you which fields look unhealthy and may need a visit. You
do not need any technical knowledge to run it or read the results.

## What it does (in plain words)

For each plot it measures how green the crop is from satellite images (ignoring
cloudy days) and compares that to how green a **normal cotton field in that sector
(rainfed or irrigated) usually is in that week of the season**. The "normal" curve
was built from the donor plots the team collected — fields that grew cotton in known
years — because the farmers we finance don't have enough history of their own. If a
field is much less green than normal, it raises an alert. Each run also saves the
satellite pictures themselves (true-colour and crop-greenness images plus the raw
clipped data) and a run log, so every number can be traced back later.

## How to run a monitoring cycle

1. Go to the project on GitHub → **Actions** tab → **"E1.2 - NDVI Crop-Health Monitor"**.
2. Click **"Run workflow"** (top right). Leave the date blank to use today, or type a
   date (YYYY-MM-DD) to re-check an earlier point in the season.
3. Click the green **"Run workflow"** button. It takes a few minutes.
4. When it finishes, open the **Mahsooli Google Sheet → `NDVI_Log` tab**. New rows for
   this cycle appear at the bottom.

It also runs automatically on the 1st, 11th, and 21st of each month during the
season (June through March — cotton is harvested into the new year). April and May
runs simply report "Off-season".

## How to read the results

Each row is one plot for one cycle, with these columns:

| Column | What it means |
|---|---|
| **Mahsooli ID** | The plot's ID. Donor baseline plots use `BP...`; registered farmer rows use their Mahsooli IDs. |
| **Date** | The day this reading was taken. |
| **NDVI value** | How green the field is now (higher = healthier; ~0.1 bare soil, ~0.6+ healthy crop). |
| **Baseline value** | How green a normal field in this sector is in this week of the season. |
| **Deviation %** | How far above/below normal the field is. Negative = below normal. |
| **Alert flag** | What to do (see below). |
| **Window** | The date range the satellite reading covers. |

**Alert flag values:**

- **Yes** → The crop is well below the sector's normal. **Schedule a field visit.**
- **No** → The crop looks normal/healthy. No action.
- **No data** → Clouds blocked enough of the satellite view this cycle that the reading
  can't be trusted. Not a problem with the crop — it usually clears up next cycle.
- **No coverage** → The plot's GPS is outside the monitored area. **Check the GPS** and
  flag it for manual review.
- **Off-season** → The run date falls in April–May, between cotton seasons. Nothing to
  monitor; cycles resume automatically from June 1.

The **`Sector_Baseline` tab** in the same Sheet shows the weekly "normal" curve for
each sector — what every reading is compared against. Rows marked *low confidence*
mean the satellite archive was too thin that week for the comparison to fire an alert.
**Note:** the irrigated curve currently comes from a single donor plot and season, so
treat irrigated alerts as advisory for now.

## Where the satellite pictures live

Every run saves, for each plot: a true-colour photo (`_rgb.png`), a crop-greenness
map (`_ndvi.png`), and the raw clipped satellite data (`_s2.tif`, `_ndvi.tif`) plus a
`run_log.json` describing the run. They are stored in a folder named after the run
date — in the GitHub Actions run's **Artifacts** ("ndvi-run"), and, when archiving
is enabled, in **Google Cloud Storage → `<GCS_BUCKET>` → `E1.2_runs` → `<date>_cycle`**. To get
pictures for any other plot or period, the technical contact runs e.g.
`python ndvi/exports.py --plot BP003 --season 2023`.

**Looking for just the baseline NDVI?** The NDVI greenness rasters are also collected
into one dedicated, easy-to-browse folder so you don't have to open each run folder:

- **Baseline NDVI:** `<GCS_BUCKET>` → `ndvi` → `baseline` → `<date>` — one
  `_ndvi.tif` per donor plot/season, the imagery behind the sector baseline.
- **Each cycle's NDVI:** `<GCS_BUCKET>` → `ndvi` → `current` → `<date>`.

The numeric baseline values per sector and week live alongside, in the run folder's
`baseline_sector.csv` (and the **Sector_Baseline** tab of the Google Sheet).

## When you see "Yes"

Treat it as a prompt to send someone to look at the field, or to call the farmer. The
satellite cannot tell you *why* the crop is stressed (drought, pests, late planting) —
only that it looks worse than the sector's normal. The field visit confirms the cause.

## Who to contact

- The reading didn't run or the Sheet didn't update → check the GitHub Actions run for a
  red ✗ and share it with the technical contact. The log always ends with a single line
  starting `ERROR [...]` that says what broke and what to do — share that line. Green
  runs end with a `RUN-SUMMARY` line counting, per cause, how many plots were healthy,
  alerted, cloud-blocked, outside coverage, or off-season.
- Adding or changing **donor plots** (the baseline) → `data/farmers/baseline_plots.csv`
  (one row per plot: sector, polygon or point, size in feddan, and the years cotton was
  planted). The next run validates it and rebuilds the baseline automatically.
- Registering **financed farmers** for monitoring → the CSV named by `NDVI_FARMERS_CSV`
  (columns: `mahsooli_id, lat, lon`, optional `radius_m`, optional `sector`) plus
  `NDVI_MONITOR_FARMERS=true`. Both are data changes, not code changes.
