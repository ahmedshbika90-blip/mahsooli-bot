"""
NDVI shared helper - reading and validating the baseline CSVs (no Earth Engine).

The sector-baseline methodology produces THREE artifacts (all written by
ndvi/baseline.py):

  baseline_plot_seasons.csv  one NDVI curve per (donor plot, cotton season) -
                             the traceability layer, kept forever
  baseline_plots.csv         one curve per plot (mean over its seasons)
  baseline_sector.csv        one curve per sector (mean over plot curves) -
                             the ONLY file ndvi/current.py consumes

Both producers and consumers go through this module so loading and validation
can never drift apart:

  - baseline.py uses validate_baseline_outputs() on its skip path, so a
    truncated or stale build is rebuilt instead of silently accepted.
  - current.py uses load_sector_baseline_validated(), so it refuses to run
    against an incomplete sector baseline (every sector x week cell must be
    present) with a clear rebuild instruction.

A complete sector baseline means one row for every (sector, week) in
config.NDVI_SECTORS x {1..n_weeks} - rows may have an empty NDVI (a sector or
week with no data is legitimate and marked low_confidence), but must exist.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
from pipeline_utils import PipelineError

PLOT_SEASON_FIELDS = [
    "plot_id", "sector", "season", "week", "ndvi", "obs_count", "built_utc"
]
PLOT_FIELDS = [
    "plot_id", "sector", "week", "baseline_ndvi", "n_seasons_used",
    "n_seasons_listed", "obs_total", "low_confidence", "built_utc"
]
SECTOR_FIELDS = [
    "sector", "week", "baseline_ndvi", "n_plots", "n_plot_weeks_with_data",
    "low_confidence", "built_utc"
]


def n_weeks() -> int:
    """Number of season-week bins (44 for 7-day bins over Jun 1 -> Mar 31)."""
    return config.NDVI_SEASON_WEEKS


def expected_plot_season_keys(plots):
    """Every (plot_id, season, week) cell a finished build must contain."""
    return {
        (p["plot_id"], season, w)
        for p in plots
        for season in p["seasons"]
        for w in range(1, n_weeks() + 1)
    }


def expected_sector_keys():
    """Every (sector, week) cell the sector baseline must contain."""
    return {
        (sector, w)
        for sector in config.NDVI_SECTORS
        for w in range(1, n_weeks() + 1)
    }


def _read_rows(path, fields, step, int_columns):
    """Parse a baseline CSV; raise a classified error on a corrupt file."""
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != fields:
            raise PipelineError(
                step, "baseline-corrupt",
                f"{path} has header {reader.fieldnames}, expected {fields}",
                "rebuild it: python ndvi/baseline.py --refresh", exit_code=6,
            )
        rows = []
        for i, row in enumerate(reader, start=2):
            try:
                for col in int_columns:
                    row[col] = int(row[col])
            except (KeyError, TypeError, ValueError) as e:
                raise PipelineError(
                    step, "baseline-corrupt",
                    f"{path} line {i} is unparseable ({e!r}): {row}",
                    "rebuild it: python ndvi/baseline.py --refresh", exit_code=6,
                ) from e
            rows.append(row)
    return rows


def read_plot_season_rows(path, step):
    return _read_rows(path, PLOT_SEASON_FIELDS, step, ("season", "week", "obs_count"))


def read_plot_rows(path, step):
    return _read_rows(path, PLOT_FIELDS, step,
                      ("week", "n_seasons_used", "n_seasons_listed", "obs_total"))


def read_sector_rows(path, step):
    return _read_rows(path, SECTOR_FIELDS, step,
                      ("week", "n_plots", "n_plot_weeks_with_data"))


def validate_baseline_outputs(plots, step):
    """
    Check the three existing baseline files against the current plot manifest.

    Returns a list of human-readable problems (empty = complete and current).
    Used by baseline.py's skip path: any problem -> rebuild.
    """
    problems = []

    for path in (config.NDVI_BASELINE_PLOT_SEASONS_CSV,
                 config.NDVI_BASELINE_PLOTS_CSV,
                 config.NDVI_BASELINE_SECTOR_CSV):
        if not path.exists():
            problems.append(f"missing {path.name}")
    if problems:
        return problems

    try:
        ps_rows = read_plot_season_rows(config.NDVI_BASELINE_PLOT_SEASONS_CSV, step)
        sector_rows = read_sector_rows(config.NDVI_BASELINE_SECTOR_CSV, step)
        plot_rows = read_plot_rows(config.NDVI_BASELINE_PLOTS_CSV, step)
    except PipelineError as e:
        return [f"{e.cause}: {e.detail}"]

    present_ps = {(r["plot_id"], r["season"], r["week"]) for r in ps_rows}
    expected_ps = expected_plot_season_keys(plots)
    missing_ps = expected_ps - present_ps
    if missing_ps:
        problems.append(
            f"{len(missing_ps)} (plot, season, week) cells missing from "
            f"{config.NDVI_BASELINE_PLOT_SEASONS_CSV.name}"
        )
    # Staleness in the OTHER direction matters just as much: rows from a plot
    # or season REMOVED from the registry are baked into the committed sector
    # means, so they must force a rebuild, not a shrug.
    extra_ps = {(pid, season) for pid, season, _ in present_ps} \
        - {(pid, season) for pid, season, _ in expected_ps}
    if extra_ps:
        problems.append(
            f"stale (plot, season) curves no longer in the registry: "
            f"{sorted(extra_ps)[:5]}"
        )

    manifest_ids = {p["plot_id"] for p in plots}
    plot_file_ids = {r["plot_id"] for r in plot_rows}
    if manifest_ids - plot_file_ids:
        problems.append(
            f"plots absent from {config.NDVI_BASELINE_PLOTS_CSV.name}: "
            f"{sorted(manifest_ids - plot_file_ids)}"
        )
    if plot_file_ids - manifest_ids:
        problems.append(
            f"stale plots no longer in the registry: "
            f"{sorted(plot_file_ids - manifest_ids)}"
        )

    missing_sector = expected_sector_keys() - {(r["sector"], r["week"])
                                               for r in sector_rows}
    if missing_sector:
        problems.append(
            f"{len(missing_sector)} (sector, week) cells missing from "
            f"{config.NDVI_BASELINE_SECTOR_CSV.name}"
        )
    return problems


def load_sector_baseline_validated(step):
    """
    Load {(sector, week): {'ndvi': float|None, 'low_conf': bool, 'n_plots': int}}
    after verifying the file exists and covers every sector x week cell.
    """
    path = config.NDVI_BASELINE_SECTOR_CSV
    if not path.exists():
        raise PipelineError(
            step, "missing-prereq", f"sector baseline not found: {path}",
            "run this first: python ndvi/baseline.py", exit_code=3,
        )

    rows = read_sector_rows(path, step)
    missing = expected_sector_keys() - {(r["sector"], r["week"]) for r in rows}
    if missing:
        sample = ", ".join(f"{s} wk{w}" for s, w in sorted(missing)[:5])
        raise PipelineError(
            step, "baseline-incomplete",
            f"{len(missing)} (sector, week) cells absent from {path} "
            f"(e.g. {sample}) - likely a truncated or stale build",
            "run: python ndvi/baseline.py --refresh", exit_code=6,
        )

    table = {}
    for row in rows:
        ndvi_raw = (row.get("baseline_ndvi") or "").strip()
        table[(row["sector"], row["week"])] = {
            "ndvi": float(ndvi_raw) if ndvi_raw else None,
            "low_conf": (row.get("low_confidence") or "").strip().lower() == "yes",
            "n_plots": row["n_plots"],
        }
    return table


def warn_if_legacy_baseline(step):
    """One-line courtesy warning when the pre-sector baseline.csv still exists."""
    legacy = config.NDVI_BASELINE_CSV
    if legacy.exists():
        print(
            f"WARN [{step}] {legacy} is from the retired per-plot DOY-week "
            f"methodology and is no longer read by any step - safe to delete "
            f"(the sector baseline lives in {config.NDVI_BASELINE_SECTOR_CSV.name})"
        )
