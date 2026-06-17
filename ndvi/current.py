"""
NDVI step 2 - Current-cycle NDVI, anomaly alert, Sheets export, imagery, archive.

For the latest monitoring window, pulls the cloud-masked Sentinel-2 NDVI for
each monitored plot (the baseline-donor plots from ndvi/registry.py; financed
farmers join via NDVI_MONITOR_FARMERS once registered), compares it to the
plot's SECTOR baseline for the matching season-week, flags plots whose NDVI
has dropped materially below normal, and writes the result to a local CSV and
(optionally) the Mahsooli Google Sheet. When imagery export is enabled it also
saves each plot's raw clipped Sentinel-2 / NDVI GeoTIFFs + RGB / NDVI PNGs for
the window, and the whole dated run folder can be mirrored to Google Drive.

Alert rule (config.ndvi_is_alert): fire only when the NDVI is >20% below the
sector baseline AND the baseline shows real vegetation (>= NDVI_VEG_FLOOR) AND
the absolute drop is material (>= NDVI_ABS_DROP_FLOOR). The floors suppress
false alarms at the low NDVI typical of arid bare soil. A plot with fewer than
NDVI_CURRENT_MIN_COUNT cloud-free images this window is reported as "No data"
- never a false alert. Runs dated Apr 1 - May 31 fall between cotton seasons:
every plot is flagged "Off-season" and no Earth Engine quota is spent.

The 7 Google Sheets columns are UNCHANGED from the original handover (a
non-technical user keeps reading the same table):
    Mahsooli ID | Date | NDVI value | Baseline value | Deviation % | Alert flag | Window
Sector context lives in a separate Sector_Baseline tab (rewritten on each
push), so the live NDVI_Log header is never touched.

Idempotent: the local dated CSV is skipped if present (use --force); the Sheet
is upserted by (Mahsooli ID, Date) so re-runs never duplicate a cycle.

Usage:
    python ndvi/current.py [--date YYYY-MM-DD] [--push] [--force]
                           [--no-export] [--archive]

Output:
    data/ndvi/ndvi_log_<date>.csv          (always)
    data/ndvi/runs/<date>_cycle/           (imagery + CSV copy + run_log.json)
    Google Sheet NDVI_Log + Sector_Baseline tabs  (with --push / NDVI_SHEET_PUSH)
    Drive mirror of the run folder         (with --archive / NDVI_DRIVE_ARCHIVE)
"""

import argparse
import csv
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
import baseline_io
import ee_auth
import seasons
from registry import load_normalized_plots
from runlog import RunLog, run_dir_for
from pipeline_utils import PipelineError, run_main, write_csv_atomic

STEP = "current"

SHEET_HEADER = [
    "Mahsooli ID", "Date", "NDVI value", "Baseline value",
    "Deviation %", "Alert flag", "Window",
]

SECTOR_BASELINE_TAB = "Sector_Baseline"
SECTOR_BASELINE_HEADER = [
    "Sector", "Week", "Week dates", "Baseline NDVI", "Plots", "Confidence",
]

# Alert-flag values (kept short but interpretable; explained in the PM guide).
FLAG_ALERT = "Yes"
FLAG_OK = "No"
FLAG_NO_DATA = "No data"
FLAG_NO_COVERAGE = "No coverage"
FLAG_OFF_SEASON = "Off-season"


def parse_args():
    parser = argparse.ArgumentParser(description="Compute current NDVI + alerts.")
    parser.add_argument(
        "--date",
        default=None,
        help="Run date YYYY-MM-DD (default: today). The window ends on this date.",
    )
    parser.add_argument(
        "--push",
        action="store_true",
        help="Also upsert the results into the configured Google Sheet.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite today's local CSV if it already exists.",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Skip the per-plot imagery exports even if NDVI_EXPORT_ENABLED.",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Mirror the run folder to Google Drive "
             "(also enabled by NDVI_DRIVE_ARCHIVE=true).",
    )
    return parser.parse_args()


def load_monitored_plots():
    """
    The plots monitored each cycle: the baseline-donor registry plots, plus
    the financed-farmer manifest when NDVI_MONITOR_FARMERS is enabled.

    Ids must be unique across BOTH sources: the EE join, the result dict and
    the Sheet upsert key are all id-based, so a collision would silently
    report one geometry's stats under two rows.
    """
    plots = load_normalized_plots()
    if config.NDVI_MONITOR_FARMERS:
        from farmers import load_normalized_farmers

        plots = plots + load_normalized_farmers()
    ids = [ee_auth.plot_id_of(p) for p in plots]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise PipelineError(
            STEP, "invalid-input",
            f"duplicate plot id(s) across the donor registry and the farmer "
            f"manifest: {dupes}",
            "make ids unique (donor plots use BPxxx; farmers use their own "
            "Mahsooli ids)", exit_code=2,
        )
    return plots


def pull_current_ndvi(ee, plots, window_start, window_end):
    """Return {plot_id: {'ndvi': float|None, 'obs': int}} for the window."""
    fc = ee_auth.build_plots_fc(ee, plots)
    # filterDate end is exclusive, so add a day to include window_end.
    collection = ee_auth.masked_ndvi_collection(
        ee, fc, window_start, window_end + timedelta(days=1)
    )
    # Guard the fully-clouded window: mean() of an empty collection is a
    # band-less image that reduceRegions refuses (same guard as baseline.py).
    composite = ee.Image(ee.Algorithms.If(
        collection.size().gt(0),
        collection.mean().addBands(collection.count().rename("obs")),
        ee.Image.constant(0).updateMask(ee.Image.constant(0)).rename("NDVI")
        .addBands(ee.Image.constant(0).rename("obs")),
    ))
    stats = ee_auth.getinfo_with_retry(
        composite.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=config.NDVI_SCALE_M,
            tileScale=4,
        ),
        STEP,
        f"current window {window_start} to {window_end} reduceRegions",
    )

    result = {}
    for feat in stats["features"]:
        props = feat["properties"]
        obs = props.get("obs")
        result[props.get("mahsooli_id", "")] = {
            "ndvi": props.get("NDVI"),
            "obs": int(round(obs)) if obs is not None else 0,
        }
    return result


def build_rows(plots, current, baseline_map, run_date, window_label, week):
    """
    Assemble the 7-column rows + a parallel plain-English summary.

    `week` is the season-week of the run date, or None when off-season (then
    every plot is flagged Off-season and `current`/`baseline_map` are unused).
    """
    date_str = run_date.isoformat()

    rows = []
    summaries = []
    for p in plots:
        pid = ee_auth.plot_id_of(p)
        sector = p["sector"]
        norm_label = f"the {sector} donor-plot norm"
        cur = current.get(pid, {"ndvi": None, "obs": 0})
        ndvi = cur["ndvi"]

        base = baseline_map.get((sector, week)) if week is not None else None
        if week is not None and base is None:
            # Unreachable once the baseline passed validation on load; if this
            # fires, the validation and this lookup have drifted apart.
            print(f"WARN [{STEP}] no baseline row for sector {sector} week {week} "
                  f"(validation should have caught this) - treating as thin baseline")
            base = {"ndvi": None, "low_conf": True}

        ndvi_str = ""
        base_str = "" if base is None or base["ndvi"] is None else f"{base['ndvi']:.4f}"
        dev_str = ""

        if week is None:
            flag = FLAG_OFF_SEASON
            summary = "between cotton seasons (Apr-May) - monitoring resumes Jun 1"
        elif not p["in_aoi"]:
            flag = FLAG_NO_COVERAGE
            summary = "outside AOI - manual review"
        elif ndvi is None or cur["obs"] < config.NDVI_CURRENT_MIN_COUNT:
            flag = FLAG_NO_DATA
            summary = (f"too few cloud-free images this window "
                       f"({cur['obs']}/{config.NDVI_CURRENT_MIN_COUNT})")
        else:
            ndvi_str = f"{ndvi:.4f}"
            if base["ndvi"] is None or base["low_conf"]:
                flag = FLAG_OK
                summary = "current reading OK; baseline too thin to judge anomaly"
            else:
                dev = config.ndvi_deviation_pct(ndvi, base["ndvi"])
                dev_str = f"{dev:.1f}"
                if config.ndvi_is_alert(ndvi, base["ndvi"]):
                    flag = FLAG_ALERT
                    summary = f"ALERT: {dev:.0f}% below {norm_label} - field visit"
                else:
                    flag = FLAG_OK
                    summary = f"healthy: {dev:.0f}% vs {norm_label}"

        rows.append([pid, date_str, ndvi_str, base_str, dev_str, flag, window_label])
        summaries.append((pid, flag, summary))

    return rows, summaries


def _week_dates_label(week: int) -> str:
    """Generic 'Jun 01 - Jun 07' label for a season-week (non-leap reference)."""
    start, end_exclusive = seasons.week_date_range(2025, week)
    end = end_exclusive - timedelta(days=1)
    return f"{start.strftime('%b %d')} - {end.strftime('%b %d')}"


def push_to_sheet(rows):
    """Upsert rows into the configured Sheet, keyed on (Mahsooli ID, Date)."""
    import sheets

    if not config.NDVI_SHEET_ID:
        # Defensive: main() already fails fast on this; keep it classified (not a
        # bare SystemExit) so any other caller still gets a finalizable error.
        raise PipelineError(
            STEP, "missing-prereq",
            "NDVI_SHEET_PUSH/--push is set but NDVI_SHEET_ID is empty",
            "set it to the spreadsheet ID of a Sheet shared (Editor) with the "
            "service-account email", exit_code=3,
        )

    service = sheets.build_sheets_service()
    tab = config.NDVI_SHEET_TAB
    sheets.ensure_tab_and_header(service, config.NDVI_SHEET_ID, tab, SHEET_HEADER)

    existing = sheets.read_existing_keys(service, config.NDVI_SHEET_ID, tab)
    new_rows = [r for r in rows if (str(r[0]).strip(), str(r[1]).strip()) not in existing]
    appended = sheets.append_rows(service, config.NDVI_SHEET_ID, tab, new_rows)
    return appended, len(rows) - appended, service


def push_sector_baseline_tab(service):
    """
    Rewrite the Sector_Baseline tab from baseline_sector.csv (clear + write -
    the table is a snapshot, not a log). Lives next to NDVI_Log so the PM can
    see what "normal" each sector is being compared against.
    """
    import sheets

    path = config.NDVI_BASELINE_SECTOR_CSV
    if not path.exists():
        print(f"WARN [{STEP}] {path} not found - Sector_Baseline tab not updated")
        return 0

    display = []
    for r in baseline_io.read_sector_rows(path, STEP):
        display.append([
            r["sector"],
            r["week"],
            _week_dates_label(r["week"]),
            r["baseline_ndvi"],
            r["n_plots"],
            "low confidence" if (r["low_confidence"] or "").lower() == "yes" else "ok",
        ])
    sheets.overwrite_tab(service, config.NDVI_SHEET_ID, SECTOR_BASELINE_TAB,
                         SECTOR_BASELINE_HEADER, display)
    return len(display)


def main() -> int:
    args = parse_args()

    # Fail fast before any Earth Engine work: a push with no target Sheet is a
    # configuration error, not a run to start and abandon. (push_to_sheet's own
    # guard raises after compute - too late, and SystemExit there would even
    # bypass run-dir finalization since it is not an Exception.)
    if (args.push or config.NDVI_SHEET_PUSH) and not config.NDVI_SHEET_ID:
        raise PipelineError(
            STEP, "missing-prereq",
            "Sheet push is enabled (--push / NDVI_SHEET_PUSH) but NDVI_SHEET_ID is empty",
            "set NDVI_SHEET_ID to the spreadsheet ID of a Sheet shared (Editor) with "
            "the service-account email, or run without --push",
            exit_code=3,
        )

    run_date = date.fromisoformat(args.date) if args.date else date.today()
    window_start = run_date - timedelta(days=config.NDVI_CURRENT_WINDOW_DAYS)
    window_label = f"{window_start.isoformat()} to {run_date.isoformat()}"

    season_year = seasons.current_season_year(run_date)
    week = seasons.season_week(run_date, season_year) if season_year else None

    out_path = config.NDVI_DIR / f"ndvi_log_{run_date.isoformat()}.csv"

    print("=" * 90)
    print("NDVI step 2 - current NDVI, anomaly alerts, Google Sheets export")
    print("=" * 90)
    print(f"Run date:    {run_date.isoformat()}")
    print(f"Window:      {window_label} ({config.NDVI_CURRENT_WINDOW_DAYS} days)")
    if week is not None:
        wk_start, wk_end_excl = seasons.week_date_range(season_year, week)
        print(f"Season/week: {season_year} season, week {week} "
              f"({wk_start.isoformat()} to "
              f"{(wk_end_excl - timedelta(days=1)).isoformat()})")
    else:
        print("Season/week: OFF-SEASON (Apr-May) - plots will be flagged, no "
              "Earth Engine calls")
    print(f"Cloud mask:  {config.CLOUD_MASK_METHOD}")
    print(f"Output:      {out_path}")
    print("=" * 90)

    baseline_io.warn_if_legacy_baseline(STEP)

    if out_path.exists() and out_path.stat().st_size > 0 and not args.force:
        print(f"SKIP - log already exists: {out_path} (use --force to overwrite)")
        skip_compute = True
    else:
        skip_compute = False

    run_log = RunLog(STEP, "cycle", run_date)
    run_log.set_param("window", window_label)
    run_log.set_param("season_year", season_year)
    run_log.set_param("season_week", week)
    run_dir = run_dir_for(run_date, "cycle")
    ee = None

    if not skip_compute:
        plots = load_monitored_plots()
        run_log.set_param("plots", [ee_auth.plot_id_of(p) for p in plots])

        if week is not None:
            baseline_map = baseline_io.load_sector_baseline_validated(STEP)
            ee = ee_auth.initialize_earth_engine(STEP)
            print(f"Earth Engine initialised (project: {config.EE_PROJECT_ID})")
            print(f"Plots: {len(plots)}")
            print()
            current = pull_current_ndvi(ee, plots, window_start, run_date)
        else:
            baseline_map = {}
            current = {}
            print(f"Plots: {len(plots)} (all off-season)")
            print()

        rows, summaries = build_rows(plots, current, baseline_map, run_date,
                                     window_label, week)

        for pid, flag, summary in summaries:
            print(f"  {pid:<12} [{flag:<11}] {summary}")
            run_log.plot_status(pid, flag=flag, summary=summary)

        write_csv_atomic(out_path, fieldnames=None, rows=rows, header=SHEET_HEADER)
        run_log.artifact(out_path, "cycle log")

        flags = {FLAG_ALERT: 0, FLAG_OK: 0, FLAG_NO_DATA: 0,
                 FLAG_NO_COVERAGE: 0, FLAG_OFF_SEASON: 0}
        for r in rows:
            flags[r[5]] = flags.get(r[5], 0) + 1
        print()
        print(f"Rows: {len(rows)}   Flags: Alert={flags[FLAG_ALERT]}  OK={flags[FLAG_OK]}  "
              f"No data (clouds)={flags[FLAG_NO_DATA]}  "
              f"No coverage={flags[FLAG_NO_COVERAGE]}  "
              f"Off-season={flags[FLAG_OFF_SEASON]}")
        print(f"RUN-SUMMARY [{STEP}] date={run_date.isoformat()} plots={len(rows)} "
              f"week={week if week is not None else 'off-season'} "
              f"alert={flags[FLAG_ALERT]} ok={flags[FLAG_OK]} "
              f"no_data={flags[FLAG_NO_DATA]} no_coverage={flags[FLAG_NO_COVERAGE]} "
              f"off_season={flags[FLAG_OFF_SEASON]}")
        print(f"Saved atomically: {out_path}")
    else:
        # Re-load the existing CSV so --push still works on a skipped re-run.
        with open(out_path, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.reader(f)
            next(reader, None)
            rows = list(reader)

    # The local CSV above is already finalized; a Sheet failure must not stop
    # the run log / archive below, so it is recorded and re-raised at the end.
    push_failure = None
    push_enabled = args.push or config.NDVI_SHEET_PUSH
    if push_enabled:
        print()
        print(f"Pushing to Google Sheet: {config.NDVI_SHEET_ID} / {config.NDVI_SHEET_TAB}")
        try:
            appended, skipped, service = push_to_sheet(rows)
            print(f"  Appended {appended} new rows, skipped {skipped} already present.")
            n_baseline_rows = push_sector_baseline_tab(service)
            if n_baseline_rows:
                print(f"  Rewrote {SECTOR_BASELINE_TAB} tab ({n_baseline_rows} rows).")
        except Exception as e:  # noqa: BLE001 - record, finish the run, re-raise
            push_failure = e
            run_log.error(f"Sheet push failed: {e}")
            print(f"  WARN [{STEP}] Sheet push failed (local CSV is intact): {e}")

    # Per-plot imagery for this window (raw clipped + NDVI GeoTIFF, RGB + NDVI
    # PNG). Failures are recorded per plot, never fatal: the alert CSV/Sheet
    # above is already safe and must not be lost to an imagery hiccup.
    export_enabled = (config.NDVI_EXPORT_ENABLED and not args.no_export
                      and not skip_compute and week is not None)
    if export_enabled:
        import exports

        print()
        print(f"Exporting per-plot imagery to {run_dir / 'imagery'}")
        for p in plots:
            pid = ee_auth.plot_id_of(p)
            try:
                artifacts = exports.export_plot_imagery(
                    ee, p, window_start, run_date, run_dir / "imagery"
                )
                for a in artifacts:
                    run_log.artifact(a["file"], a["kind"], plot_id=pid)
                run_log.plot_status(pid, imagery=[a["kind"] for a in artifacts])
                print(f"  {pid:<12} {len(artifacts)} file(s)")
            except Exception as e:  # noqa: BLE001 - record + continue
                run_log.error(f"imagery export failed for {pid}: {e}")
                run_log.plot_status(pid, imagery_error=str(e))
                print(f"  WARN [{STEP}] imagery export failed for {pid}: {e}")

    # Dated run folder. A fresh run copies the CSV and writes the full run log.
    # A skip re-run (e.g. retrying a failed push or archive) must not clobber
    # the original run log, so it records itself as run_log_rerun.json - and
    # the Drive archive runs EITHER way, so the documented "re-run with
    # --archive to retry the upload only" actually works without --force.
    run_dir.mkdir(parents=True, exist_ok=True)
    if not skip_compute or not (run_dir / out_path.name).exists():
        shutil.copy2(out_path, run_dir / out_path.name)
    log_name = "run_log.json" if not skip_compute else "run_log_rerun.json"
    log_path = run_log.write(run_dir, name=log_name)
    print(f"Run log: {log_path}")

    if config.NDVI_DRIVE_ARCHIVE or args.archive:
        from gdrive import archive_run_dir  # repo root; deps needed only on use

        archive_run_dir(run_dir, STEP)

    if push_failure is not None:
        raise PipelineError(
            STEP, "sheet-push",
            f"Google Sheet push failed: {push_failure}",
            f"the local CSV ({out_path.name}) and {log_name} are intact; fix the "
            f"Sheets credentials/sharing and re-run with --push", exit_code=8,
        )

    print()
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    run_main(main, STEP)
