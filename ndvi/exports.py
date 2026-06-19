"""
NDVI imagery exports - per-plot raw clipped Sentinel-2, NDVI raster, RGB image.

For one plot and one date window this produces four artifacts (the client's
"see the data" deliverable):

    <plot>_<start>_<end>_s2.tif     raw clipped Sentinel-2 (NDVI_EXPORT_BANDS,
                                    10 m native, cloud-masked median composite)
    <plot>_<start>_<end>_ndvi.tif   NDVI raster (float)
    <plot>_<start>_<end>_rgb.png    true-colour quicklook (B4/B3/B2)
    <plot>_<start>_<end>_ndvi.png   NDVI quicklook (red->green palette)

Used two ways:
  - automatically each monitoring cycle (ndvi/current.py calls
    export_plot_imagery() for every plot over the cycle window), and
  - on demand via this CLI for any plot + season or date range, e.g.:

        python ndvi/exports.py --plot BP008 --season 2024
        python ndvi/exports.py --all-plots --start 2025-08-01 --end 2025-08-15
        python ndvi/exports.py --plot BP003 --season 2023 --upload

Implementation notes:
  - Synchronous ee.Image.getDownloadURL / getThumbURL + local download. The
    plots are tiny (largest ~2x2 km -> well under Earth Engine's ~50 MB
    synchronous cap; a pre-flight estimate enforces NDVI_EXPORT_MAX_BYTES).
    ee.batch.Export.toDrive was rejected: it exports to the SERVICE ACCOUNT's
    Drive (which no human can browse) and is asynchronous.
  - format='GEO_TIFF' is passed explicitly - the getDownloadURL default is a
    ZIP of per-band files.
  - Downloads go through download_atomic (`.part` + rename) with EE_RETRIES,
    matching the pipeline's no-truncated-files discipline.
  - A window with zero cloud-free images returns no artifacts (recorded by
    the caller / run log as "no imagery") - never an error.

Output (CLI): data/ndvi/runs/<today>_export/imagery/ + run_log.json
              (--upload mirrors the run folder to Google Cloud Storage)
"""

import argparse
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
import ee_auth
import seasons
from registry import load_normalized_plots
from runlog import RunLog, run_dir_for
from pipeline_utils import PipelineError, download_atomic, retry_call, run_main

STEP = "exports"


def _bbox_meters(plot):
    """Approximate (width_m, height_m) of the plot's export bounding box."""
    if plot.get("geometry_type") == "polygon":
        lons = [p[0] for p in plot["coordinates"]]
        lats = [p[1] for p in plot["coordinates"]]
        lat0 = sum(lats) / len(lats)
        width = (max(lons) - min(lons)) * 111_320.0 * math.cos(math.radians(lat0))
        height = (max(lats) - min(lats)) * 110_540.0
    else:
        width = height = 2.0 * float(plot["radius_m"])
    pad = 2.0 * config.NDVI_EXPORT_BBOX_BUFFER_M
    return width + pad, height + pad


def check_export_size(plot):
    """
    Pre-flight guard against Earth Engine's ~50 MB synchronous download cap.
    Estimates the raw multiband GeoTIFF (the largest artifact).
    """
    width_m, height_m = _bbox_meters(plot)
    pixels = (width_m / config.NDVI_SCALE_M) * (height_m / config.NDVI_SCALE_M)
    est_bytes = int(pixels * len(config.NDVI_EXPORT_BANDS) * 2)  # uint16
    if est_bytes > config.NDVI_EXPORT_MAX_BYTES:
        raise PipelineError(
            STEP, "export-too-large",
            f"{plot.get('plot_id') or plot.get('mahsooli_id')}: estimated "
            f"{est_bytes / 1e6:.0f} MB exceeds NDVI_EXPORT_MAX_BYTES "
            f"({config.NDVI_EXPORT_MAX_BYTES / 1e6:.0f} MB)",
            "reduce NDVI_EXPORT_BANDS, raise NDVI_SCALE_M for exports, or "
            "raise NDVI_EXPORT_MAX_BYTES", exit_code=2,
        )
    return est_bytes


def export_region(ee, plot):
    """Plot geometry bounds padded by NDVI_EXPORT_BBOX_BUFFER_M (context)."""
    return (ee_auth.plot_geometry(ee, plot)
            .bounds()
            .buffer(config.NDVI_EXPORT_BBOX_BUFFER_M)
            .bounds())


def _download(make_url, path, describe):
    """Build the URL and download it atomically, both inside the retry loop."""
    def attempt():
        return download_atomic(make_url(), path, timeout=config.DOWNLOAD_TIMEOUT)

    return retry_call(
        attempt,
        attempts=config.EE_RETRIES,
        base_delay=config.EE_RETRY_BASE_DELAY,
        describe=describe,
    )


def export_plot_imagery(ee, plot, start_date, end_date, out_dir: Path):
    """
    Export the four artifacts for one plot over [start_date, end_date]
    (inclusive). Returns a list of artifact dicts; empty when the window has
    zero cloud-free images.
    """
    pid = ee_auth.plot_id_of(plot)
    check_export_size(plot)
    region = export_region(ee, plot)

    collection = ee_auth.masked_s2_collection(
        ee, region, start_date, end_date + timedelta(days=1)
    )
    n_images = ee_auth.getinfo_with_retry(
        collection.size(), STEP, f"{pid} image count"
    )
    if not n_images:
        return []

    composite = collection.median()
    ndvi = composite.normalizedDifference(
        [config.NDVI_NIR_BAND, config.NDVI_RED_BAND]
    ).rename("NDVI").toFloat()

    out_dir.mkdir(parents=True, exist_ok=True)
    stem = f"{pid}_{start_date.isoformat()}_{end_date.isoformat()}"
    artifacts = []

    def add(path, kind, n_bytes):
        artifacts.append({"file": path, "kind": kind, "bytes": n_bytes,
                          "images_in_window": n_images})

    # Raw clipped multiband GeoTIFF (explicit GEO_TIFF: the default is a ZIP).
    raw = composite.select(config.NDVI_EXPORT_BANDS).toUint16()
    path = out_dir / f"{stem}_s2.tif"
    n = _download(
        lambda: raw.getDownloadURL({
            "region": region, "scale": config.NDVI_SCALE_M, "format": "GEO_TIFF",
        }),
        path, f"{pid} raw GeoTIFF",
    )
    add(path, "raw-geotiff", n)

    # NDVI GeoTIFF.
    path = out_dir / f"{stem}_ndvi.tif"
    n = _download(
        lambda: ndvi.getDownloadURL({
            "region": region, "scale": config.NDVI_SCALE_M, "format": "GEO_TIFF",
        }),
        path, f"{pid} NDVI GeoTIFF",
    )
    add(path, "ndvi-geotiff", n)

    # RGB quicklook PNG (reflectance stretched 0..NDVI_EXPORT_RGB_MAX).
    rgb_vis = composite.visualize(
        bands=["B4", "B3", "B2"], min=0, max=config.NDVI_EXPORT_RGB_MAX
    )
    path = out_dir / f"{stem}_rgb.png"
    n = _download(
        lambda: rgb_vis.getThumbURL({
            "region": region, "dimensions": config.NDVI_EXPORT_PNG_DIM,
            "format": "png",
        }),
        path, f"{pid} RGB PNG",
    )
    add(path, "rgb-png", n)

    # NDVI quicklook PNG.
    ndvi_vis = ndvi.visualize(
        min=config.NDVI_EXPORT_NDVI_MIN, max=config.NDVI_EXPORT_NDVI_MAX,
        palette=[c.strip() for c in config.NDVI_EXPORT_NDVI_PALETTE.split(",")],
    )
    path = out_dir / f"{stem}_ndvi.png"
    n = _download(
        lambda: ndvi_vis.getThumbURL({
            "region": region, "dimensions": config.NDVI_EXPORT_PNG_DIM,
            "format": "png",
        }),
        path, f"{pid} NDVI PNG",
    )
    add(path, "ndvi-png", n)

    return artifacts


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export per-plot raw/NDVI GeoTIFFs + RGB/NDVI PNGs.")
    parser.add_argument("--plot", action="append", default=None, metavar="PLOT_ID",
                        help="Plot id from the registry (repeatable).")
    parser.add_argument("--all-plots", action="store_true",
                        help="Export every plot in the registry.")
    parser.add_argument("--season", type=int, default=None, metavar="YEAR",
                        help="Export the whole cotton season YEAR "
                             "(Jun 1 -> Mar 31 of YEAR+1).")
    parser.add_argument("--start", default=None, help="Window start YYYY-MM-DD.")
    parser.add_argument("--end", default=None, help="Window end YYYY-MM-DD (inclusive).")
    parser.add_argument("--out", default=None,
                        help="Output folder (default: data/ndvi/runs/<today>_export).")
    parser.add_argument("--upload", action="store_true",
                        help="Mirror the run folder to Google Cloud Storage when done.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print the export plan and exit (no Earth Engine).")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    if args.season is not None:
        if args.start or args.end:
            raise PipelineError(STEP, "invalid-input",
                                "--season and --start/--end are mutually exclusive",
                                "pick one way to define the window", exit_code=2)
        start = seasons.season_start(args.season)
        end = min(seasons.season_end(args.season), date.today())
    elif args.start and args.end:
        start, end = date.fromisoformat(args.start), date.fromisoformat(args.end)
    else:
        raise PipelineError(STEP, "invalid-input",
                            "no window given",
                            "pass --season YEAR or both --start and --end",
                            exit_code=2)
    if start > end:
        raise PipelineError(STEP, "invalid-input", f"start {start} is after end {end}",
                            "swap the dates", exit_code=2)

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
    elif not args.all_plots:
        raise PipelineError(STEP, "invalid-input", "no plots selected",
                            "pass --plot PLOT_ID (repeatable) or --all-plots",
                            exit_code=2)

    run_dir = Path(args.out) if args.out else run_dir_for(date.today(), "export")
    out_dir = run_dir / "imagery"

    print("=" * 90)
    print("NDVI imagery export - raw clipped S2 + NDVI GeoTIFF, RGB + NDVI PNG")
    print("=" * 90)
    print(f"Window: {start} to {end} (inclusive)")
    print(f"Plots:  {', '.join(p['plot_id'] for p in plots)}")
    print(f"Bands:  {','.join(config.NDVI_EXPORT_BANDS)} at {config.NDVI_SCALE_M} m")
    print(f"Output: {out_dir}")
    print("=" * 90)

    if args.dry_run:
        print()
        print("DRY RUN - no Earth Engine calls will be made")
        for p in plots:
            est = check_export_size(p)
            print(f"  {p['plot_id']}: 4 file(s), raw GeoTIFF est. "
                  f"{est / 1e6:.1f} MB")
        return 0

    run_log = RunLog(STEP, "export", date.today())
    run_log.set_param("window", f"{start} to {end}")
    run_log.set_param("plots", [p["plot_id"] for p in plots])

    ee = ee_auth.initialize_earth_engine(STEP)
    print(f"Earth Engine initialised (project: {config.EE_PROJECT_ID})")
    print()

    n_files = 0
    failures = 0
    for p in plots:
        pid = p["plot_id"]
        try:
            artifacts = export_plot_imagery(ee, p, start, end, out_dir)
            if not artifacts:
                print(f"  {pid:<12} no cloud-free imagery in this window")
                run_log.plot_status(pid, imagery="none (no cloud-free images)")
                continue
            for a in artifacts:
                run_log.artifact(a["file"], a["kind"], plot_id=pid,
                                 bytes=a["bytes"])
            run_log.plot_status(pid, imagery=[a["kind"] for a in artifacts],
                                images_in_window=artifacts[0]["images_in_window"])
            total_mb = sum(a["bytes"] for a in artifacts) / 1e6
            print(f"  {pid:<12} {len(artifacts)} file(s), {total_mb:.1f} MB, "
                  f"{artifacts[0]['images_in_window']} image(s) in window")
            n_files += len(artifacts)
        except PipelineError:
            raise
        except Exception as e:  # noqa: BLE001 - record + continue with next plot
            failures += 1
            run_log.error(f"export failed for {pid}: {e}")
            run_log.plot_status(pid, imagery_error=str(e))
            print(f"  WARN [{STEP}] export failed for {pid}: {e}")

    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_log.write(run_dir)
    print()
    print(f"RUN-SUMMARY [{STEP}] plots={len(plots)} files={n_files} "
          f"failures={failures} window={start}_{end}")
    print(f"Run log: {log_path}")

    if args.upload or config.NDVI_GCS_ARCHIVE:
        from gcs import archive_run_dir_to_gcs  # repo root; deps needed only on use

        archive_run_dir_to_gcs(run_dir, STEP)

    # Any failed plot makes the CLI exit nonzero: a 7-of-8-plots-failed export
    # must not read as success to automation (details are in the run log).
    return 1 if failures else 0


if __name__ == "__main__":
    run_main(main, STEP)
