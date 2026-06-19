"""
Central configuration for the Mahala CHIRPS rainfall pipeline.

This module is the single source of truth for every path and constant used by the
pipeline scripts (chirps/0_download -> chirps/1_close_boundary -> chirps/2_clip -> chirps/3_average).

Configuration is read from a `.env` file in the repository root (if present) with
sensible defaults, so the pipeline runs on any operating system with zero edits:

  - DATA_ROOT empty / unset  -> ./data next to this file (OS-agnostic default)
  - DATA_ROOT set            -> that absolute or relative path is used instead

There is no external dependency: the `.env` file is parsed with a tiny built-in
parser, and only `numpy` and `rasterio` are needed by the scripts themselves.
"""

import os
from pathlib import Path


# -----------------------------------------------------------------------------
# .env loading (minimal, dependency-free)
# -----------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent


def load_dotenv(env_path: Path) -> None:
    """
    Loads KEY=VALUE pairs from a .env file into os.environ.

    Supported syntax:
      - Blank lines and lines starting with '#' are ignored.
      - An optional `export ` prefix on the key is allowed.
      - Quoted values ("..." or '...') keep their interior verbatim, including
        spaces and '#'.
      - Unquoted values may carry a trailing inline comment (` #...`), which is
        stripped.

    Existing environment variables are NOT overwritten, so a value exported in
    the shell wins over the file.
    """
    if not env_path.exists():
        return

    with open(env_path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("export "):
                key = key[len("export "):].strip()

            value = value.strip()
            if len(value) >= 2 and value[0] in ("'", '"') and value[-1] == value[0]:
                # Quoted value: keep the interior exactly as written.
                value = value[1:-1]
            else:
                # Unquoted value: drop a trailing inline comment if present.
                for sep in (" #", "\t#"):
                    idx = value.find(sep)
                    if idx != -1:
                        value = value[:idx]
                value = value.strip()

            if key and key not in os.environ:
                os.environ[key] = value


load_dotenv(REPO_ROOT / ".env")


def _get(name: str, default: str) -> str:
    value = os.environ.get(name, "").strip()
    return value if value else default


def _get_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if not value:
        return default
    return value in ("1", "true", "yes", "on")


def _get_path(name: str, default: str = "") -> Path | None:
    raw_value = _get(name, default)
    if not raw_value:
        return None

    path = Path(raw_value).expanduser()
    if not path.is_absolute():
        path = (REPO_ROOT / path).resolve()
    return path


# -----------------------------------------------------------------------------
# Paths
# -----------------------------------------------------------------------------

# Where all generated data lives. Empty DATA_ROOT -> ./data next to this file.
_data_root_raw = _get("DATA_ROOT", "")
DATA_ROOT = Path(_data_root_raw).expanduser() if _data_root_raw else REPO_ROOT / "data"
if not DATA_ROOT.is_absolute():
    DATA_ROOT = (REPO_ROOT / DATA_ROOT).resolve()

# Boundary input file (relative to repo root unless an absolute path is given).
_boundary_raw = _get("BOUNDARY_GEOJSON", "Mahala.geojson")
INPUT_GEOJSON = Path(_boundary_raw).expanduser()
if not INPUT_GEOJSON.is_absolute():
    INPUT_GEOJSON = REPO_ROOT / INPUT_GEOJSON

# Pipeline stage folders.
BOUNDARY_DIR = DATA_ROOT / "00_boundary"
RAW_DIR = DATA_ROOT / "01_raw_africa_monthly"
CLIP_DIR = DATA_ROOT / "02_clip"
SEASONAL_DIR = DATA_ROOT / "03_seasonal_totals"
AVERAGE_DIR = DATA_ROOT / "04_average"
TABLE_DIR = DATA_ROOT / "05_tables"

# Closed boundary produced by step 1 and consumed by step 2.
CLOSED_GEOJSON = BOUNDARY_DIR / "Mahala_closed.geojson"

# Canonical farmer GPS coordinates for the CHIRPS snap/score helpers
# (tools/snap_score.py and tools/pilot_launch_check.py). This is the single place to
# swap farm coordinates in production: point SNAP_FARMERS_CSV at any CSV with lat/lon
# and an id column (farmer_id, mahsooli_id or id) and re-run snap_score (and
# google_sheets_lookup for a
# fresh workbook). Distinct from the NDVI registry (NDVI_FARMERS_CSV) below, which
# has a stricter schema. See load_farmers() below. The default is the tracked demo
# file docs/sample_farmers.csv so CI (which only has git-tracked files after
# checkout) runs out of the box; point it at data/farmers/farmers.csv (git-ignored,
# PII) in .env for production.
SNAP_FARMERS_CSV = _get_path("SNAP_FARMERS_CSV", "docs/sample_farmers.csv")


# -----------------------------------------------------------------------------
# Download / period / season
# -----------------------------------------------------------------------------

BASE_URL = _get(
    "BASE_URL",
    "https://data.chc.ucsb.edu/products/CHIRPS-2.0/africa_monthly/tifs",
)

# Filename product prefix, e.g. "chirps-v2.0" -> chirps-v2.0.<year>.<MM>.tif(.gz).
PRODUCT_PREFIX = _get("PRODUCT_PREFIX", "chirps-v2.0")

# Download behaviour.
DOWNLOAD_RETRIES = int(_get("DOWNLOAD_RETRIES", "3"))
DOWNLOAD_TIMEOUT = int(_get("DOWNLOAD_TIMEOUT", "120"))

START_YEAR = int(_get("START_YEAR", "2014"))
END_YEAR = int(_get("END_YEAR", "2024"))
YEARS = range(START_YEAR, END_YEAR + 1)

# Season months as a comma list, e.g. "6,7,8,9".
SEASON_MONTHS = [int(m) for m in _get("SEASON_MONTHS", "6,7,8,9").split(",") if m.strip()]

# Keep the .tif.gz archive after a successful unzip (matches the original run).
KEEP_GZ = _get_bool("KEEP_GZ", True)

# Month number -> (raw download subfolder, lowercase suffix used in clipped names).
MONTH_NAMES = {
    1: ("01_January", "january"),
    2: ("02_February", "february"),
    3: ("03_March", "march"),
    4: ("04_April", "april"),
    5: ("05_May", "may"),
    6: ("06_June", "june"),
    7: ("07_July", "july"),
    8: ("08_August", "august"),
    9: ("09_September", "september"),
    10: ("10_October", "october"),
    11: ("11_November", "november"),
    12: ("12_December", "december"),
}

# Only the months that are actually in season, in chronological order.
MONTHS = {m: MONTH_NAMES[m] for m in SEASON_MONTHS}


# -----------------------------------------------------------------------------
# Raster / scoring constants
# -----------------------------------------------------------------------------

NODATA = float(_get("NODATA", "-9999.0"))

# CHIRPS grid cell size in degrees. Cell centres fall at .x25 / .x75 and are the
# basis for the grid_key used to join farmer coordinates to the lookup table.
CELL_SIZE = float(_get("CELL_SIZE", "0.05"))


def make_grid_key(lat: float, lon: float) -> str:
    """Grid key used in the lookup table, e.g. '13.475_35.975'."""
    return f"{lat:.3f}_{lon:.3f}"


def snap_to_grid_center(lat: float, lon: float, cell: float = None):
    """
    Snaps an arbitrary lat/lon to the centre of its CHIRPS grid cell.

    Centres sit at multiples of `cell` offset by half a cell (e.g. 13.475 for a
    0.05 deg grid), matching the centres written into the lookup table.
    """
    import math

    if cell is None:
        cell = CELL_SIZE
    center_lat = (math.floor(lat / cell) + 0.5) * cell
    center_lon = (math.floor(lon / cell) + 0.5) * cell
    return center_lat, center_lon


# Id column names accepted by load_farmers(), tried in this order.
FARMER_ID_COLUMNS = ("farmer_id", "mahsooli_id", "id")


def load_farmers(path=None) -> list:
    """
    Reads farmer GPS coordinates into normalized records: {"id", "lat", "lon"}.

    Accepts any CSV that has lat/lon plus one id column named farmer_id,
    mahsooli_id or id (first found wins), so the same loader works for both the
    bundled demo file and a real farmer registry. Extra columns (e.g. radius_m)
    are ignored. Rows with a missing/unparseable lat or lon are skipped with a
    warning rather than aborting the run.
    """
    import csv

    if path is None:
        path = SNAP_FARMERS_CSV
    path = Path(path)

    farmers = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        id_col = next((c for c in FARMER_ID_COLUMNS if c in fieldnames), None)
        if "lat" not in fieldnames or "lon" not in fieldnames:
            raise ValueError(
                f"{path} must have 'lat' and 'lon' columns (found: {fieldnames})."
            )
        for row in reader:
            try:
                lat = float(row["lat"])
                lon = float(row["lon"])
            except (KeyError, TypeError, ValueError):
                print(f"SKIP - malformed farmer row: {row}")
                continue
            farmer_id = (row.get(id_col, "") if id_col else "").strip()
            farmers.append({"id": farmer_id, "lat": lat, "lon": lon})
    return farmers

# Mahsooli rainfall risk rubric: (minimum mm inclusive, score). Highest first.
SCORE_THRESHOLDS = [
    (350.0, 10),
    (250.0, 7),
    (150.0, 4),
    (0.0, 1),
]


def score_from_rainfall(avg_mm: float) -> int:
    """Maps an average seasonal rainfall (mm) to the Mahsooli 1-10 score."""
    for threshold, score in SCORE_THRESHOLDS:
        if avg_mm >= threshold:
            return score
    return 1


# -----------------------------------------------------------------------------
# Sentinel-2 NDVI crop-health monitoring (Google Earth Engine)
# -----------------------------------------------------------------------------
# This is a separate, self-contained sub-pipeline (ndvi/farmers -> ndvi/baseline ->
# ndvi/current), run by ndvi_run_pipeline.py. It does not touch the CHIRPS chain
# above. Like the rest of this file, every setting has a working default and is
# overridable via .env, so nothing is hardcoded in the ndvi/*.py scripts.

# Folders (under DATA_ROOT, alongside the CHIRPS stage folders).
NDVI_DIR = DATA_ROOT / "ndvi"
FARMERS_DIR = DATA_ROOT / "farmers"

# Input farmer plots for the NDVI pipeline (strict schema: mahsooli_id, lat, lon,
# optional radius_m - distinct from the permissive SNAP_FARMERS_CSV above). A
# relative path is resolved against the repo root. The default is the tracked demo
# file docs/sample_ndvi_farmers.csv, so CI (which only has git-tracked files after
# checkout) runs out of the box; set NDVI_FARMERS_CSV=data/farmers/farmers.csv in
# .env to point at the real, local-only registry.
NDVI_FARMERS_CSV = _get_path("NDVI_FARMERS_CSV", "docs/sample_ndvi_farmers.csv")

# Normalised farmer manifest written by ndvi/farmers and read by ndvi/baseline + ndvi/current.
FARMERS_NORMALIZED_CSV = NDVI_DIR / "farmers_normalized.csv"

# LEGACY single-baseline file (pre sector-baseline methodology). No longer
# written or read; kept only so the pipeline can warn that an old copy on disk
# is obsolete and safe to delete.
NDVI_BASELINE_CSV = NDVI_DIR / "baseline.csv"

# --- Baseline-donor plot registry (sector baselines) ---
# The client-supplied plots used ONLY to extract the sector baseline curves
# (these farmers are not the ones being financed). Tracked in git with phone
# numbers stripped; strict schema parsed by ndvi/registry.py: plot_id,
# farmer_name, sector, locality, village, geometry_type (polygon|point),
# geometry_wkt, lat, lon, area_feddan, radius_m, seasons (';'-separated cotton
# planting years), notes.
NDVI_PLOTS_REGISTRY = _get_path("NDVI_PLOTS_REGISTRY", "data/farmers/baseline_plots.csv")

# Normalised plot manifest written by ndvi/registry (JSON because polygon
# rings don't fit a flat CSV) and read by ndvi/baseline + ndvi/current.
PLOTS_NORMALIZED_JSON = NDVI_DIR / "plots_normalized.json"

# One feddan in square metres (Egyptian/Sudanese feddan).
FEDDAN_M2 = float(_get("FEDDAN_M2", "4200"))


def radius_from_feddan(area_feddan: float) -> float:
    """Radius (m) of a circle with the same area as `area_feddan` feddan."""
    import math

    return math.sqrt(area_feddan * FEDDAN_M2 / math.pi)


# Baseline artifacts written by ndvi/baseline (all three are committed):
#   plot_seasons: one NDVI curve per (plot, cotton season)  - traceability
#   plots:        one curve per plot (mean over its seasons) - traceability
#   sector:       one curve per sector (mean over plots)     - what current.py reads
NDVI_BASELINE_PLOT_SEASONS_CSV = NDVI_DIR / "baseline_plot_seasons.csv"
NDVI_BASELINE_PLOTS_CSV = NDVI_DIR / "baseline_plots.csv"
NDVI_BASELINE_SECTOR_CSV = NDVI_DIR / "baseline_sector.csv"

# --- Google Earth Engine ---
# EE is now project-scoped: ee.Initialize(creds, project=EE_PROJECT_ID). The
# service account needs roles/serviceusage.serviceUsageConsumer + the Earth
# Engine "Writer" role, and the project must be registered for Earth Engine.
EE_PROJECT_ID = _get("EE_PROJECT_ID", "")

# Service-account key as raw JSON content (CI/GitHub Secrets - no file on disk).
# When set, it wins over the file path so a deployed run authenticates headlessly.
GEE_SERVICE_ACCOUNT_INFO = _get("GEE_SERVICE_ACCOUNT_INFO", "")

# Local fallback: path to a service-account JSON key file. The same service
# account can serve both Earth Engine and the Sheets export.
GEE_SERVICE_ACCOUNT_JSON = _get_path("GEE_SERVICE_ACCOUNT_JSON")

# --- Google Cloud Storage credentials (NDVI run archive) ---
# The archive bucket lives in the same Cloud project as Earth Engine, so GCS
# reuses the EE service account by default. Set these only to use a separate key.
GCS_SERVICE_ACCOUNT_INFO = _get("GCS_SERVICE_ACCOUNT_INFO", "")  # key JSON content (CI)
GCS_SERVICE_ACCOUNT_JSON = _get_path("GCS_SERVICE_ACCOUNT_JSON")  # key file path (local)

# --- Sentinel-2 / NDVI ---
S2_COLLECTION = _get("S2_COLLECTION", "COPERNICUS/S2_SR_HARMONIZED")
NDVI_NIR_BAND = _get("NDVI_NIR_BAND", "B8")
NDVI_RED_BAND = _get("NDVI_RED_BAND", "B4")
NDVI_SCALE_M = int(_get("NDVI_SCALE_M", "10"))
# Default circular plot radius in metres around each farmer point.
FARMER_RADIUS_M = float(_get("FARMER_RADIUS_M", "100"))

# --- Cloud masking ---
# "scl" (default, satisfies the PRD) drops the SCL classes listed below.
# "cloudscore" uses Google's Cloud Score+ (better over arid bright soil).
CLOUD_MASK_METHOD = _get("CLOUD_MASK_METHOD", "scl").strip().lower()
# SCL classes to DROP: 3 cloud-shadow, 8 cloud-medium, 9 cloud-high, 10 cirrus, 11 snow.
SCL_DROP_CLASSES = [
    int(x) for x in _get("SCL_DROP_CLASSES", "3,8,9,10,11").split(",") if x.strip()
]
CLOUD_SCORE_PLUS_COLLECTION = _get(
    "CLOUD_SCORE_PLUS_COLLECTION", "GOOGLE/CLOUD_SCORE_PLUS/V1/S2_HARMONIZED"
)
CLOUD_SCORE_PLUS_BAND = _get("CLOUD_SCORE_PLUS_BAND", "cs_cdf")
CLOUD_SCORE_PLUS_MIN = float(_get("CLOUD_SCORE_PLUS_MIN", "0.60"))

# --- Baseline (season-aware, sector-grouped) ---
# Each donor plot contributes only its listed cotton seasons (the client's
# `seasons` column = years cotton was planted; other years were other crops).
# One season Y = SEASON_START (Jun 1 of Y) through SEASON_END (Mar 31 of Y+1),
# covering the full Sudan cotton cycle incl. harvest spillover. Weeks are keyed
# RELATIVE to the season start (absolute date offsets, so leap years and the
# Dec->Jan boundary need no special casing - the old DOY week 53 is retired).
SEASON_START_MONTH = int(_get("SEASON_START_MONTH", "6"))
SEASON_START_DAY = int(_get("SEASON_START_DAY", "1"))
SEASON_END_MONTH = int(_get("SEASON_END_MONTH", "3"))
SEASON_END_DAY = int(_get("SEASON_END_DAY", "31"))
# Seasons before this year are skipped: Sentinel-2 L2A (SR) over Sudan only
# exists from ~Dec 2018, so e.g. listed cotton seasons 2013/2015/2017 have no
# usable imagery. Skips are recorded in the manifest and run log.
MIN_SEASON_YEAR = int(_get("MIN_SEASON_YEAR", "2019"))
# Width in days of each season-week bin.
NDVI_WEEK_DAYS = int(_get("NDVI_WEEK_DAYS", "7"))


def _season_length_days() -> int:
    """
    Longest possible season length in days for the configured window,
    leap-aware (checked over reference years with and without a leap Feb).
    Jun 1 -> Mar 31 gives 304-305 days.
    """
    from datetime import date as _date

    longest = 0
    for ref_year in (2023, 2024):  # season 2023 spans leap Feb 2024; 2024 doesn't
        start = _date(ref_year, SEASON_START_MONTH, SEASON_START_DAY)
        end_year = ref_year if SEASON_END_MONTH >= SEASON_START_MONTH else ref_year + 1
        end = _date(end_year, SEASON_END_MONTH, SEASON_END_DAY)
        longest = max(longest, (end - start).days + 1)
    return longest


# Derived from the configured window (44 for the default Jun 1 -> Mar 31 with
# 7-day bins; week 44 is a short stub clipped at the season end).
NDVI_SEASON_WEEKS = -(-_season_length_days() // NDVI_WEEK_DAYS)  # ceil
# Minimum cloud-free observations for a baseline (plot, season, week) cell to be trusted.
BASELINE_MIN_COUNT = int(_get("BASELINE_MIN_COUNT", "3"))

# Sectors with separate baselines: Sudan's rainfed and irrigated farming
# perform differently, so each gets its own NDVI curve.
NDVI_SECTORS = ("rainfed", "irrigated")
# Sector assumed for monitored farmers whose registry has no sector column.
# Validated at load: a typo here would otherwise silently miss every sector
# baseline lookup and suppress all alerts.
NDVI_DEFAULT_SECTOR = _get("NDVI_DEFAULT_SECTOR", "rainfed").strip().lower()
if NDVI_DEFAULT_SECTOR not in NDVI_SECTORS:
    raise ValueError(
        f"NDVI_DEFAULT_SECTOR={NDVI_DEFAULT_SECTOR!r} is not one of {NDVI_SECTORS}; "
        f"fix it in .env"
    )

# Whether the 10-day cycle ALSO monitors the financed-farmer registry
# (NDVI_FARMERS_CSV -> farmers_normalized.csv) in addition to the donor plots.
# Off by default so an out-of-the-box run (CI, demo registry) stays donor-only and
# the retired M001-M010 demo points never silently reappear in the log. Production
# opts in via the repo variables NDVI_MONITOR_FARMERS=true + NDVI_FARMERS_CSV=<real>.
NDVI_MONITOR_FARMERS = _get_bool("NDVI_MONITOR_FARMERS", False)

# Earth Engine call behaviour (mirrors DOWNLOAD_RETRIES/DOWNLOAD_TIMEOUT for CHIRPS).
# Transient EE failures (quota, 429/503, backend timeouts) are retried this many
# times with exponential backoff starting at EE_RETRY_BASE_DELAY seconds.
EE_RETRIES = int(_get("EE_RETRIES", "3"))
EE_RETRY_BASE_DELAY = float(_get("EE_RETRY_BASE_DELAY", "5"))

# --- Current pull ---
# How many days back from the run date the current composite window spans.
NDVI_CURRENT_WINDOW_DAYS = int(_get("NDVI_CURRENT_WINDOW_DAYS", "10"))
# Minimum cloud-free observations required before a current reading is trusted.
# Below this, the plot is reported "No data" rather than risking a cloud-driven
# false alert (mirrors BASELINE_MIN_COUNT for the baseline). Set to 1 to restore
# the previous behaviour of only catching fully-cloudy (obs == 0) windows.
NDVI_CURRENT_MIN_COUNT = int(_get("NDVI_CURRENT_MIN_COUNT", "2"))

# --- Alert rule (all config-driven) ---
# Fire only when ALL hold: deviation% < ALERT_PCT, baseline >= VEG_FLOOR, and the
# absolute drop (baseline - ndvi) >= ABS_DROP_FLOOR. The floors suppress noisy
# false alarms at the low NDVI typical of arid bare soil in Gedaref.
NDVI_DEVIATION_ALERT_PCT = float(_get("NDVI_DEVIATION_ALERT_PCT", "-20"))
NDVI_VEG_FLOOR = float(_get("NDVI_VEG_FLOOR", "0.2"))
NDVI_ABS_DROP_FLOOR = float(_get("NDVI_ABS_DROP_FLOOR", "0.05"))

# --- Output Google Sheet (raw Sheets API v4) ---
# A human-created spreadsheet, shared (Editor) with the service-account email.
# Service accounts have no Drive storage, so they cannot create/own a Sheet -
# they only write into one shared with them. ndvi/current writes by this ID.
NDVI_SHEET_ID = _get("NDVI_SHEET_ID", "")
NDVI_SHEET_TAB = _get("NDVI_SHEET_TAB", "NDVI_Log")
# Off by default so a plain run never touches the network (mirrors NDVI_GCS_ARCHIVE).
NDVI_SHEET_PUSH = _get_bool("NDVI_SHEET_PUSH", False)

# --- Area-of-interest bounding boxes for flagging stray farmer GPS ---
# One box per sector (the donor plots span Gala'a Al Nahal at ~12.8 deg N up to
# Alfashaga at ~14.0 deg N for rainfed, and New Halfa at ~15.1 deg N for
# irrigated). The check stays warn-not-block: out-of-AOI plots are flagged for
# manual review, never dropped. The legacy single-box AOI_LAT_*/AOI_LON_* vars
# are kept as the fallback union bounds (and for .env back-compat).
AOI_LAT_MIN = float(_get("AOI_LAT_MIN", "12.6"))
AOI_LAT_MAX = float(_get("AOI_LAT_MAX", "15.4"))
AOI_LON_MIN = float(_get("AOI_LON_MIN", "34.5"))
AOI_LON_MAX = float(_get("AOI_LON_MAX", "36.6"))

AOI_BOXES = {
    "rainfed": (
        float(_get("AOI_RAINFED_LAT_MIN", "12.6")),
        float(_get("AOI_RAINFED_LAT_MAX", "14.2")),
        float(_get("AOI_RAINFED_LON_MIN", "34.5")),
        float(_get("AOI_RAINFED_LON_MAX", "36.6")),
    ),
    "irrigated": (
        float(_get("AOI_IRRIGATED_LAT_MIN", "14.9")),
        float(_get("AOI_IRRIGATED_LAT_MAX", "15.4")),
        float(_get("AOI_IRRIGATED_LON_MIN", "35.4")),
        float(_get("AOI_IRRIGATED_LON_MAX", "36.0")),
    ),
}

# --- Imagery exports (raw clipped Sentinel-2, NDVI raster, RGB quicklook) ---
# Generated per plot by ndvi/exports.py: automatically each monitoring cycle
# (when NDVI_EXPORT_ENABLED) and on demand via the CLI. Bands default to the
# four 10 m native bands so nothing is silently resampled.
NDVI_EXPORT_ENABLED = _get_bool("NDVI_EXPORT_ENABLED", True)
# When export is enabled, a missing raw-imagery artifact is an acceptance problem:
# the run must tell the PM/client why the raw files were not produced instead of
# silently going green with only the numeric CSV.
NDVI_REQUIRE_EXPORTS = _get_bool("NDVI_REQUIRE_EXPORTS", True)
# Also export imagery for the baseline DONOR plots (one set per usable season)
# so the raw Sentinel-2 / NDVI rasters behind each sector baseline are archived
# alongside the numeric CSVs - not just the monitored farmers' cycle imagery.
# Set false on a quota-constrained run to build the baseline CSVs only.
NDVI_BASELINE_EXPORT_IMAGERY = _get_bool("NDVI_BASELINE_EXPORT_IMAGERY", True)
NDVI_EXPORT_BANDS = [
    b.strip() for b in _get("NDVI_EXPORT_BANDS", "B2,B3,B4,B8").split(",") if b.strip()
]
# Padding (m) added around a plot's bounding box so imagery shows context.
NDVI_EXPORT_BBOX_BUFFER_M = float(_get("NDVI_EXPORT_BBOX_BUFFER_M", "100"))
# Hard guard below Earth Engine's ~50 MB synchronous-download cap.
NDVI_EXPORT_MAX_BYTES = int(_get("NDVI_EXPORT_MAX_BYTES", str(45 * 1024 * 1024)))
# Reflectance stretch for the RGB PNG (S2 SR DN ~0-10000; 0-3000 reads naturally).
NDVI_EXPORT_RGB_MAX = float(_get("NDVI_EXPORT_RGB_MAX", "3000"))
# Longest side (px) of the PNG quicklooks.
NDVI_EXPORT_PNG_DIM = int(_get("NDVI_EXPORT_PNG_DIM", "1024"))
# Red -> yellow -> green palette for the NDVI quicklook (-0.2 .. 0.8).
NDVI_EXPORT_NDVI_PALETTE = _get(
    "NDVI_EXPORT_NDVI_PALETTE",
    "9e1f1f,d9722d,e8c95c,d6e85c,8fce5a,4d9e3f,1d6b2e",
)
NDVI_EXPORT_NDVI_MIN = float(_get("NDVI_EXPORT_NDVI_MIN", "-0.2"))
NDVI_EXPORT_NDVI_MAX = float(_get("NDVI_EXPORT_NDVI_MAX", "0.8"))

# --- Google Cloud Storage run archive (traceability) ---
# When enabled, each baseline/cycle run mirrors its local run folder
# (data/ndvi/runs/<date>_<kind>/: imagery + table copies + run_log.json) to
# gs://GCS_BUCKET/GCS_ARCHIVE_PREFIX/<folder name>/ so any result can be traced
# back to its inputs, config and errors. Off by default so a plain run never
# touches the network (mirrors NDVI_SHEET_PUSH). Re-uploads are idempotent:
# objects of unchanged size are skipped unless GCS_OVERWRITE=true.
# Master switch: archive EVERY epic's deliverables (E1.1 CHIRPS, E1.2 NDVI,
# E1.3 pilot check) to GCS, classified date-first as gs://GCS_BUCKET/<date>/<epic>/.
# NDVI_GCS_ARCHIVE is kept as a back-compat alias that still enables E1.2 on its own.
GCS_ARCHIVE = _get_bool("GCS_ARCHIVE", False)
NDVI_GCS_ARCHIVE = _get_bool("NDVI_GCS_ARCHIVE", False)
# True when the E1.2 NDVI steps should archive (either switch turns it on).
NDVI_ARCHIVE_ENABLED = GCS_ARCHIVE or NDVI_GCS_ARCHIVE
GCS_BUCKET = _get("GCS_BUCKET", "")
# Optional top-level folder inside the bucket (empty = bucket root). Use it only
# when the bucket is shared with unrelated data; the date-first scheme lives under it.
GCS_DATA_PREFIX = _get("GCS_DATA_PREFIX", "")
# Legacy prefix from the E1.2-only archive; superseded by the date-first scheme.
GCS_ARCHIVE_PREFIX = _get("GCS_ARCHIVE_PREFIX", "E1.2_runs")
GCS_OVERWRITE = _get_bool("GCS_OVERWRITE", False)
# Dedicated, browsable folder holding only the NDVI GeoTIFFs (baseline + current),
# separate from the full E1.2_runs/ run archive, so clients can find them directly:
# gs://GCS_BUCKET/NDVI_TIFF_PREFIX/<baseline|current>/<date>/. Mirrored by the same
# NDVI_GCS_ARCHIVE switch that drives archive_run_dir_to_gcs().
NDVI_TIFF_PREFIX = _get("NDVI_TIFF_PREFIX", "ndvi")
NDVI_RUNS_DIR = NDVI_DIR / "runs"


def ndvi_deviation_pct(ndvi: float, baseline: float) -> float:
    """Percent deviation of current NDVI from the baseline: (ndvi-baseline)/baseline*100."""
    if not baseline:
        return 0.0
    return (ndvi - baseline) / baseline * 100.0


def ndvi_is_alert(ndvi: float, baseline: float) -> bool:
    """
    The NDVI alert rule. All three conditions must hold:
      - deviation%               <  NDVI_DEVIATION_ALERT_PCT  (e.g. dropped > 20%)
      - baseline                 >= NDVI_VEG_FLOOR            (real vegetation present)
      - (baseline - ndvi)        >= NDVI_ABS_DROP_FLOOR       (drop is materially large)
    The two floors keep arid bare-soil noise from raising false "crop stress" alerts.
    """
    return (
        ndvi_deviation_pct(ndvi, baseline) < NDVI_DEVIATION_ALERT_PCT
        and baseline >= NDVI_VEG_FLOOR
        and (baseline - ndvi) >= NDVI_ABS_DROP_FLOOR
    )


def is_in_aoi(lat: float, lon: float, sector: str = None) -> bool:
    """
    True if a coordinate falls inside the AOI.

    With a known sector, tests that sector's box; with sector=None, tests the
    union of all sector boxes plus the legacy fallback box (so callers that
    predate sectors keep working).
    """
    if sector in AOI_BOXES:
        lat_min, lat_max, lon_min, lon_max = AOI_BOXES[sector]
        return (lat_min <= lat <= lat_max) and (lon_min <= lon <= lon_max)
    for lat_min, lat_max, lon_min, lon_max in AOI_BOXES.values():
        if (lat_min <= lat <= lat_max) and (lon_min <= lon <= lon_max):
            return True
    return (AOI_LAT_MIN <= lat <= AOI_LAT_MAX) and (AOI_LON_MIN <= lon <= AOI_LON_MAX)


# -----------------------------------------------------------------------------
# PROJ database fix (must run before importing rasterio)
# -----------------------------------------------------------------------------

def configure_proj_database() -> None:
    """
    Points PROJ_LIB / PROJ_DATA at the rasterio/conda PROJ database.

    This avoids the common conflict where another tool (e.g. a system PostgreSQL /
    PostGIS install) injects an old proj.db into the environment, producing:

        proj.db contains DATABASE.LAYOUT.VERSION.MINOR = 2 whereas a number >= 6 is expected

    Must be called BEFORE `import rasterio`. If no valid PROJ database is found,
    any pre-existing (and possibly broken) PROJ path is removed so rasterio can
    fall back to its bundled data.
    """
    import sys

    candidates = []

    conda_prefix = os.environ.get("CONDA_PREFIX")
    if conda_prefix:
        candidates.append(Path(conda_prefix) / "Library" / "share" / "proj")
        candidates.append(Path(conda_prefix) / "share" / "proj")

    for entry in sys.path:
        p = Path(entry)
        candidates.append(p / "rasterio" / "proj_data")
        candidates.append(p / "pyproj" / "proj_dir" / "share" / "proj")

    selected = None
    for candidate in candidates:
        if (candidate / "proj.db").exists():
            selected = candidate
            break

    if selected:
        os.environ["PROJ_LIB"] = str(selected)
        os.environ["PROJ_DATA"] = str(selected)
        print(f"Using PROJ database: {selected}")
    else:
        old_proj = os.environ.get("PROJ_LIB") or os.environ.get("PROJ_DATA")
        if old_proj:
            print(f"Removing existing PROJ path: {old_proj}")
        os.environ.pop("PROJ_LIB", None)
        os.environ.pop("PROJ_DATA", None)
