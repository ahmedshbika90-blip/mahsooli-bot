"""
NDVI step 1 - Build the sector NDVI baselines from donor plots (Earth Engine).

For each baseline-donor plot (ndvi/registry.py), extracts the weekly NDVI
curve of every usable cotton season it lists, then averages in two stages:

    per (plot, season, week)  ->  per (plot, week)  ->  per (SECTOR, week)
         traceability             mean over seasons      mean over plot curves

The two-stage averaging keeps a plot with many seasons (e.g. Bahaa's 4) from
dominating the sector curve. One season = Jun 1 (year Y) -> Mar 31 (Y+1),
binned into 44 weeks keyed relative to the season start (ndvi/seasons.py).
The rainfed and irrigated sectors get separate curves because they perform
differently; the sector curve is what ndvi/current.py compares monitored
plots against (financed farmers will not have their own history - that is the
whole reason the donor plots exist).

Design notes:
  - Seasons before MIN_SEASON_YEAR (default 2019) were already skipped by the
    registry step (no Sentinel-2 SR over Sudan) and are recorded in the run log.
  - A week with no cloud-free imagery yields an empty NDVI cell (obs_count=0)
    - legitimately empty, never an error, excluded from the means.
  - An observation-count trust gate marks thin cells: a (plot, season, week)
    below BASELINE_MIN_COUNT is untrusted; plot- and sector-level rows where
    NO contributing cell is trusted are marked low_confidence, and current.py
    will not alert on them.
  - All three CSVs are written via `.part` + atomic rename after a
    completeness check, so an interrupted run can never leave a truncated
    baseline under a final name. Earth Engine calls are retried (EE_RETRIES).

Idempotent: skips when all three outputs exist AND validate as complete
against the current plot manifest. Use --refresh to force a rebuild.

Usage:
    python ndvi/baseline.py [--refresh] [--dry-run] [--archive] [--plot BP008]

    --dry-run   print the execution plan (plots, seasons, EE call count) and
                exit before any Earth Engine call - no credentials needed.
    --plot ID   smoke-test mode: build only the given plot(s), writing
                *.smoke.csv files that the current step never reads.
    --archive   mirror the run folder to Google Drive even if
                NDVI_DRIVE_ARCHIVE is false.

Outputs: data/ndvi/baseline_plot_seasons.csv  (plot_id, sector, season, week, ...)
         data/ndvi/baseline_plots.csv         (plot_id, sector, week, ...)
         data/ndvi/baseline_sector.csv        (sector, week, ...) <- current.py reads this
         data/ndvi/runs/<date>_baseline/      (table copies + run_log.json)
"""

import argparse
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
import baseline_io
import ee_auth
import seasons
from registry import load_normalized_plots
from runlog import RunLog, run_dir_for
from pipeline_utils import CsvPartWriter, PipelineError, run_main

STEP = "baseline"


def export_baseline_imagery(ee, plots, run_dir, run_log, run_date):
    """
    Supplementary: archive the raw Sentinel-2 / NDVI imagery BEHIND each sector
    baseline by exporting one artifact set per (donor plot, usable season) into
    run_dir/imagery - so the Drive archive holds the imagery, not only the
    numeric CSVs. The baseline CSVs are already finalized when this runs, so any
    export failure here is recorded and skipped: it never fails the run. Gated by
    NDVI_BASELINE_EXPORT_IMAGERY; the imagery/ folder is mirrored to Drive by the
    same archive_run_dir() that uploads the tables.
    """
    from exports import export_plot_imagery  # lazy: pulls EE-only export deps

    out_dir = run_dir / "imagery"
    n_files = failures = 0
    print()
    print("Baseline imagery (raw clipped S2 + NDVI per donor plot/season):")
    for p in plots:
        pid = p["plot_id"]
        for year in p["seasons"]:
            start = seasons.season_start(year)
            end = min(seasons.season_end(year), run_date)
            label = f"{pid} {year}"
            try:
                artifacts = export_plot_imagery(ee, p, start, end, out_dir)
                if not artifacts:
                    print(f"  {label:<16} no cloud-free imagery in window")
                    continue
                for a in artifacts:
                    run_log.artifact(a["file"], a["kind"], plot_id=pid,
                                     season=year, bytes=a["bytes"])
                n_files += len(artifacts)
                total_mb = sum(a["bytes"] for a in artifacts) / 1e6
                print(f"  {label:<16} {len(artifacts)} file(s), {total_mb:.1f} MB")
            except Exception as e:  # noqa: BLE001 - supplementary; CSVs already final
                failures += 1
                run_log.error(f"baseline imagery failed for {label}: {e}")
                run_log.plot_status(pid, imagery_error=str(e))
                print(f"  WARN [{STEP}] imagery export failed for {label}: {e}")
    print(f"  Baseline imagery: {n_files} file(s), {failures} failure(s)")


def parse_args():
    parser = argparse.ArgumentParser(description="Build the sector NDVI baselines.")
    parser.add_argument("--refresh", action="store_true",
                        help="Rebuild even if the baseline files already exist.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the execution plan and exit (no Earth Engine).")
    parser.add_argument("--plot", action="append", default=None, metavar="PLOT_ID",
                        help="Smoke-test only this plot id (repeatable); writes "
                             "*.smoke.csv files instead of the real baseline.")
    parser.add_argument("--archive", action="store_true",
                        help="Mirror the run folder to Google Drive "
                             "(also enabled by NDVI_DRIVE_ARCHIVE=true).")
    return parser.parse_args()


def season_to_plots(plots):
    """{season_year: [plot, ...]} over each plot's usable seasons."""
    mapping = {}
    for p in plots:
        for year in p["seasons"]:
            mapping.setdefault(year, []).append(p)
    return mapping


def build_plot_season_curves(ee, plots, writer, built_utc):
    """
    The Earth Engine loop: one reduceRegions per (season, week), restricted to
    the plots that list that season. Streams rows into `writer` and returns
    (seen_keys, ps_rows).
    """
    seen = set()
    ps_rows = []
    unexpected = set()

    for season_year, season_plots in sorted(season_to_plots(plots).items()):
        fc = ee_auth.build_plots_fc(ee, season_plots)
        ids = {ee_auth.plot_id_of(p) for p in season_plots}
        sector_of = {ee_auth.plot_id_of(p): p["sector"] for p in season_plots}

        for week in range(1, baseline_io.n_weeks() + 1):
            start, end_exclusive = seasons.week_date_range(season_year, week)
            weekly = ee_auth.masked_ndvi_collection(
                ee, fc, start.isoformat(), end_exclusive.isoformat()
            )
            # A week with zero cloud-free images would make mean() a band-less
            # image and reduceRegions would refuse it; substitute a fully-masked
            # NDVI + constant-0 obs so empty weeks come back as obs_count=0.
            composite = ee.Image(ee.Algorithms.If(
                weekly.size().gt(0),
                weekly.mean().addBands(weekly.count().rename("obs")),
                ee.Image.constant(0).updateMask(ee.Image.constant(0))
                .rename("NDVI")
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
                f"season {season_year} week {week} reduceRegions",
            )

            week_rows = []
            for feat in stats["features"]:
                props = feat["properties"]
                plot_id = props.get("mahsooli_id", "")
                if plot_id not in ids:
                    unexpected.add(plot_id)
                    continue
                ndvi = props.get("NDVI")
                obs = props.get("obs")
                obs_count = int(round(obs)) if obs is not None else 0
                row = {
                    "plot_id": plot_id,
                    "sector": sector_of.get(plot_id, ""),
                    "season": season_year,
                    "week": week,
                    "ndvi": "" if ndvi is None else round(ndvi, 4),
                    "obs_count": obs_count,
                    "built_utc": built_utc,
                }
                week_rows.append(row)
                seen.add((plot_id, season_year, week))

            writer.write_rows(week_rows)
            ps_rows.extend(week_rows)

        print(f"  season {season_year}: {len(season_plots)} plot(s) x "
              f"{baseline_io.n_weeks()} weeks done")

    if unexpected:
        raise PipelineError(
            STEP, "output-incomplete",
            f"Earth Engine returned ids not in the plot manifest: "
            f"{sorted(unexpected)[:5]} - id join is broken, partial output discarded",
            "re-run after checking plots_normalized.json for duplicate/blank ids",
            exit_code=6,
        )
    return seen, ps_rows


def aggregate_plot_curves(ps_rows, plots, built_utc):
    """
    Stage 2: per-(plot, week) mean over that plot's seasons-with-data.

    A cell is trusted when its obs_count >= BASELINE_MIN_COUNT; the plot-week
    is low_confidence when no contributing season cell is trusted.
    """
    listed_count = {
        p["plot_id"]: len(p["seasons"]) + len(p["seasons_skipped"]) for p in plots
    }
    cells = {}  # (plot_id, week) -> list of (ndvi, obs_count)
    sector_by_plot = {p["plot_id"]: p["sector"] for p in plots}
    for r in ps_rows:
        if r["ndvi"] != "":
            cells.setdefault((r["plot_id"], r["week"]), []).append(
                (float(r["ndvi"]), r["obs_count"])
            )

    rows = []
    for p in plots:
        for week in range(1, baseline_io.n_weeks() + 1):
            values = cells.get((p["plot_id"], week), [])
            trusted = [v for v, obs in values if obs >= config.BASELINE_MIN_COUNT]
            rows.append({
                "plot_id": p["plot_id"],
                "sector": sector_by_plot[p["plot_id"]],
                "week": week,
                "baseline_ndvi": (
                    "" if not values
                    else round(sum(v for v, _ in values) / len(values), 4)
                ),
                "n_seasons_used": len(values),
                "n_seasons_listed": listed_count[p["plot_id"]],
                "obs_total": sum(obs for _, obs in values),
                "low_confidence": "no" if trusted else "yes",
                "built_utc": built_utc,
            })
    return rows


def aggregate_sector_curves(plot_rows, plots, built_utc):
    """
    Stage 3: per-(sector, week) mean over the plot curves - what current.py
    reads. Rows exist for every sector x week even when a sector has no data.
    """
    plots_in_sector = {
        sector: [p for p in plots if p["sector"] == sector and p["seasons"]]
        for sector in config.NDVI_SECTORS
    }
    by_key = {}  # (sector, week) -> list of plot rows with data
    for r in plot_rows:
        if r["baseline_ndvi"] != "":
            by_key.setdefault((r["sector"], r["week"]), []).append(r)

    rows = []
    for sector in config.NDVI_SECTORS:
        for week in range(1, baseline_io.n_weeks() + 1):
            contributing = by_key.get((sector, week), [])
            trusted = [r for r in contributing if r["low_confidence"] == "no"]
            rows.append({
                "sector": sector,
                "week": week,
                "baseline_ndvi": (
                    "" if not contributing
                    else round(
                        sum(float(r["baseline_ndvi"]) for r in contributing)
                        / len(contributing), 4)
                ),
                "n_plots": len(plots_in_sector[sector]),
                "n_plot_weeks_with_data": len(contributing),
                "low_confidence": "no" if trusted else "yes",
                "built_utc": built_utc,
            })
    return rows


def check_completeness(seen, plots):
    """Refuse to finalize unless every (plot, season, week) cell came back."""
    expected = baseline_io.expected_plot_season_keys(plots)
    missing = expected - seen
    if missing:
        sample = ", ".join(f"{pid} {y} wk{w}" for pid, y, w in sorted(missing)[:5])
        raise PipelineError(
            STEP, "output-incomplete",
            f"{len(missing)} of {len(expected)} (plot, season, week) cells "
            f"missing from the Earth Engine results (e.g. {sample}) - partial "
            f"output discarded",
            "re-run python ndvi/baseline.py; if it persists, check the plot "
            "geometries of the listed ids", exit_code=6,
        )


def print_plan(plots, out_paths):
    """--dry-run: everything the build WOULD do, with zero EE calls."""
    mapping = season_to_plots(plots)
    n_calls = len(mapping) * baseline_io.n_weeks()
    print()
    print("DRY RUN - no Earth Engine calls will be made")
    for p in plots:
        skipped = ", ".join(f"{y} ({reason.split('(')[0].strip()})"
                            for y, reason in p["seasons_skipped"]) or "-"
        print(f"  {p['plot_id']} [{p['sector']:<9}] {p['geometry_type']:<7} "
              f"seasons used: {p['seasons'] or '-'}   skipped: {skipped}")
    for season_year in sorted(mapping):
        start = seasons.season_start(season_year)
        end = seasons.season_end(season_year)
        print(f"  season {season_year}: {start} -> {end}, "
              f"{len(mapping[season_year])} plot(s)")
    print(f"  Earth Engine calls: {len(mapping)} season(s) x "
          f"{baseline_io.n_weeks()} weeks = {n_calls} reduceRegions")
    for path in out_paths:
        print(f"  would write: {path}")


def print_summary(sector_rows, plots, plot_season_path):
    in_aoi = sum(1 for p in plots if p["in_aoi"])
    print()
    print("=" * 90)
    print("BASELINE RUN SUMMARY (sector methodology)")
    print(f"  Donor plots: {len(plots)} (in AOI: {in_aoi}, outside: "
          f"{len(plots) - in_aoi})   Season weeks: {baseline_io.n_weeks()}")
    parts = []
    for sector in config.NDVI_SECTORS:
        rows = [r for r in sector_rows if r["sector"] == sector]
        with_data = [r for r in rows if r["baseline_ndvi"] != ""]
        low = [r for r in with_data if r["low_confidence"] == "yes"]
        n_plots = rows[0]["n_plots"] if rows else 0
        print(f"  {sector:<10}: {n_plots} plot(s); {len(with_data)}/{len(rows)} "
              f"weeks with data, {len(low)} of those low-confidence")
        parts.append(f"{sector}_weeks={len(with_data)}")
    skipped = [(p["plot_id"], y) for p in plots for y, _ in p["seasons_skipped"]]
    if skipped:
        print(f"  Skipped seasons (recorded in run log): "
              f"{', '.join(f'{pid} {y}' for pid, y in skipped)}")
    print(f"  Traceability curves: {plot_season_path}")
    print(f"RUN-SUMMARY [{STEP}] plots={len(plots)} "
          f"seasons={len(season_to_plots(plots))} weeks={baseline_io.n_weeks()} "
          f"{' '.join(parts)} complete=yes")
    print("=" * 90)


def main() -> int:
    args = parse_args()

    out_ps = config.NDVI_BASELINE_PLOT_SEASONS_CSV
    out_plots = config.NDVI_BASELINE_PLOTS_CSV
    out_sector = config.NDVI_BASELINE_SECTOR_CSV

    print("=" * 90)
    print("NDVI step 1 - build sector NDVI baselines from donor plots (Earth Engine)")
    print("=" * 90)
    print(f"Season window:  Jun 1 -> Mar 31 (Y+1), {baseline_io.n_weeks()} weeks, "
          f"seasons >= {config.MIN_SEASON_YEAR}")
    print(f"Collection:     {config.S2_COLLECTION}")
    print(f"Cloud mask:     {config.CLOUD_MASK_METHOD}")
    print(f"Sector output:  {out_sector}")
    print("=" * 90)

    baseline_io.warn_if_legacy_baseline(STEP)

    plots = load_normalized_plots()
    if args.plot:
        wanted = set(args.plot)
        unknown = wanted - {p["plot_id"] for p in plots}
        if unknown:
            raise PipelineError(
                STEP, "invalid-input", f"unknown --plot id(s): {sorted(unknown)}",
                "ids must exist in plots_normalized.json (python ndvi/registry.py)",
                exit_code=2,
            )
        plots = [p for p in plots if p["plot_id"] in wanted]
        out_ps = out_ps.with_name(out_ps.stem + ".smoke.csv")
        out_plots = out_plots.with_name(out_plots.stem + ".smoke.csv")
        out_sector = out_sector.with_name(out_sector.stem + ".smoke.csv")
        print(f"SMOKE MODE - only {sorted(wanted)}; writing *.smoke.csv files "
              f"(current.py never reads these)")
    print(f"Plots: {len(plots)}")

    no_season_plots = [p["plot_id"] for p in plots if not p["seasons"]]
    if no_season_plots:
        print(f"WARN [{STEP}] plots with no usable seasons (contribute nothing): "
              f"{no_season_plots}")

    if args.dry_run:
        print_plan(plots, [out_ps, out_plots, out_sector])
        return 0

    if not args.plot and not args.refresh:
        problems = baseline_io.validate_baseline_outputs(plots, STEP)
        if not problems:
            print(f"SKIP - baseline already exists and is complete: {out_sector}")
            print("       (use --refresh to rebuild)")
            if config.NDVI_DRIVE_ARCHIVE or args.archive:
                # Retry-the-upload-only path: archive the most recent baseline
                # run folder without re-spending any Earth Engine quota.
                existing = sorted(config.NDVI_RUNS_DIR.glob("*_baseline"))
                if existing:
                    from gdrive import archive_run_dir

                    archive_run_dir(existing[-1], STEP)
                else:
                    print(f"WARN [{STEP}] no run folder under "
                          f"{config.NDVI_RUNS_DIR} to archive - use --refresh")
            return 0
        if all(p.startswith("missing ") for p in problems):
            print(f"Building (first run: {'; '.join(problems)})")
        else:
            print(f"WARN [{STEP}] existing baseline failed validation - rebuilding "
                  f"({'; '.join(problems)})")

    run_date = date.today()
    run_log = RunLog(STEP, "baseline", run_date)
    run_log.set_param("plots", [p["plot_id"] for p in plots])
    run_log.set_param("smoke_mode", bool(args.plot))
    for p in plots:
        run_log.plot_status(p["plot_id"], sector=p["sector"],
                            geometry_type=p["geometry_type"],
                            seasons_used=p["seasons"], in_aoi=p["in_aoi"],
                            warnings=p["warnings"])
        for year, reason in p["seasons_skipped"]:
            run_log.skipped_season(p["plot_id"], year, reason)

    ee = ee_auth.initialize_earth_engine(STEP)
    print(f"Earth Engine initialised (project: {config.EE_PROJECT_ID})")
    print()

    built_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Rows stream into baseline_plot_seasons.csv.part; final names appear only
    # after the completeness check passes. Any failure discards the .part files.
    with CsvPartWriter(out_ps, fieldnames=baseline_io.PLOT_SEASON_FIELDS) as ps_writer:
        seen, ps_rows = build_plot_season_curves(ee, plots, ps_writer, built_utc)
        check_completeness(seen, plots)

        plot_rows = aggregate_plot_curves(ps_rows, plots, built_utc)
        sector_rows = aggregate_sector_curves(plot_rows, plots, built_utc)

        with CsvPartWriter(out_plots, fieldnames=baseline_io.PLOT_FIELDS) as w:
            w.write_rows(plot_rows)
        with CsvPartWriter(out_sector, fieldnames=baseline_io.SECTOR_FIELDS) as w:
            w.write_rows(sector_rows)
        ps_writer.finalize()

    for path, kind in ((out_ps, "plot-season curves"), (out_plots, "plot curves"),
                       (out_sector, "sector baseline")):
        run_log.artifact(path, kind)
        print(f"  Saved atomically: {path}")

    print_summary(sector_rows, plots, out_ps)

    # Dated run folder: table copies + run log; optionally mirrored to Drive.
    run_dir = run_dir_for(run_date, "baseline" if not args.plot else "baseline-smoke")
    run_dir.mkdir(parents=True, exist_ok=True)
    for path in (out_ps, out_plots, out_sector):
        shutil.copy2(path, run_dir / path.name)

    if config.NDVI_BASELINE_EXPORT_IMAGERY:
        export_baseline_imagery(ee, plots, run_dir, run_log, run_date)

    log_path = run_log.write(run_dir)
    print(f"  Run log: {log_path}")

    if config.NDVI_DRIVE_ARCHIVE or args.archive:
        from gdrive import archive_run_dir  # repo root; lazy: needs Drive deps

        archive_run_dir(run_dir, STEP)

    return 0


if __name__ == "__main__":
    run_main(main, STEP)
