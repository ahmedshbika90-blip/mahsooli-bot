"""
NDVI step 0 - Load and validate farmer plots (local only, no network).

Reads the farmer registry CSV (mahsooli_id, lat, lon, optional radius_m), validates
each row, fills in the default plot radius, flags any coordinate outside the Gedaref
AOI, and writes a normalised manifest that the baseline / current steps consume.

This is the NDVI counterpart of chirps/1_close_boundary.py: a cheap local prep step
with no Earth Engine dependency, so the inputs can be checked before any quota is spent.

Usage:
    python ndvi/farmers.py [farmers.csv] [--force]

Defaults:
    farmers.csv -> config.NDVI_FARMERS_CSV (docs/sample_ndvi_farmers.csv; override
                   with NDVI_FARMERS_CSV=data/farmers/farmers.csv in .env)

Input columns:  mahsooli_id, lat, lon[, radius_m][, sector]
                (sector: rainfed|irrigated; defaults to config.NDVI_DEFAULT_SECTOR -
                it selects which sector baseline curve the plot is compared against)
Output:         data/ndvi/farmers_normalized.csv
                (mahsooli_id, lat, lon, radius_m, sector, in_aoi)
"""

import argparse
import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
from pipeline_utils import PipelineError, run_main, write_csv_atomic

STEP = "farmers"

OUTPUT_FIELDS = ["mahsooli_id", "lat", "lon", "radius_m", "sector", "in_aoi"]


def parse_args():
    parser = argparse.ArgumentParser(description="Load and validate farmer plots for NDVI.")
    parser.add_argument(
        "farmers_csv",
        nargs="?",
        default=None,
        help="Farmer registry CSV (default: config.NDVI_FARMERS_CSV).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild even if the normalised manifest already exists.",
    )
    return parser.parse_args()


def load_farmers(farmers_csv: Path):
    """Parse + validate rows. Returns (rows, skipped, out_of_aoi)."""
    rows = []
    skipped = 0
    out_of_aoi = 0

    with open(farmers_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for raw in reader:
            mahsooli_id = (raw.get("mahsooli_id") or "").strip()
            try:
                lat = float(raw["lat"])
                lon = float(raw["lon"])
            except (KeyError, TypeError, ValueError):
                print(f"WARN [{STEP}] invalid-row: malformed lat/lon, skipped: {raw}")
                skipped += 1
                continue

            if not mahsooli_id:
                print(f"WARN [{STEP}] invalid-row: missing mahsooli_id, skipped: {raw}")
                skipped += 1
                continue

            if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
                print(f"WARN [{STEP}] invalid-row: lat/lon out of range, skipped: "
                      f"{mahsooli_id} ({lat}, {lon})")
                skipped += 1
                continue

            radius_raw = (raw.get("radius_m") or "").strip()
            try:
                radius_m = float(radius_raw) if radius_raw else config.FARMER_RADIUS_M
            except ValueError:
                radius_m = config.FARMER_RADIUS_M

            sector = (raw.get("sector") or "").strip().lower()
            if sector and sector not in config.NDVI_SECTORS:
                print(f"WARN [{STEP}] {mahsooli_id}: unknown sector {sector!r} "
                      f"(expected one of {config.NDVI_SECTORS}) - using "
                      f"{config.NDVI_DEFAULT_SECTOR!r}")
                sector = ""
            sector = sector or config.NDVI_DEFAULT_SECTOR

            in_aoi = config.is_in_aoi(lat, lon, sector)
            if not in_aoi:
                out_of_aoi += 1
                print(
                    f"WARN - {mahsooli_id} ({lat:.4f}, {lon:.4f}) is outside the {sector} AOI "
                    f"- will be flagged for manual review, no NDVI alert raised."
                )

            rows.append({
                "mahsooli_id": mahsooli_id,
                "lat": lat,
                "lon": lon,
                "radius_m": radius_m,
                "sector": sector,
                "in_aoi": "yes" if in_aoi else "no",
            })

    return rows, skipped, out_of_aoi


def load_normalized_farmers(path: Path = None):
    """
    Read the manifest written by this step into a list of dicts.

    Shared by the baseline / current steps so all steps agree on the farmer schema.
    Returns rows with: mahsooli_id, lat (float), lon (float), radius_m (float),
    sector (str), in_aoi (bool).
    """
    path = path or config.FARMERS_NORMALIZED_CSV
    if not path.exists():
        raise PipelineError(
            STEP, "missing-prereq",
            f"normalised farmer manifest not found: {path}",
            "run this first: python ndvi/farmers.py", exit_code=3,
        )

    rows = []
    with open(path, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if "sector" not in (reader.fieldnames or []):
            raise PipelineError(
                STEP, "missing-prereq",
                f"{path} predates the sector-baseline methodology (no 'sector' column)",
                "rebuild it: python ndvi/farmers.py --force", exit_code=3,
            )
        for raw in reader:
            sector = ((raw.get("sector") or "").strip().lower()
                      or config.NDVI_DEFAULT_SECTOR)
            if sector not in config.NDVI_SECTORS:
                # An unknown sector would silently miss every baseline lookup
                # downstream and suppress all alerts for this farmer.
                raise PipelineError(
                    STEP, "missing-prereq",
                    f"{path} has sector {sector!r} (expected one of "
                    f"{config.NDVI_SECTORS}) for {raw.get('mahsooli_id')}",
                    "rebuild it: python ndvi/farmers.py --force", exit_code=3,
                )
            rows.append({
                "mahsooli_id": (raw.get("mahsooli_id") or "").strip(),
                "lat": float(raw["lat"]),
                "lon": float(raw["lon"]),
                "radius_m": float(raw["radius_m"]),
                "sector": sector,
                "in_aoi": (raw.get("in_aoi") or "").strip().lower() == "yes",
            })
    return rows


def main() -> int:
    args = parse_args()

    farmers_csv = Path(args.farmers_csv) if args.farmers_csv else config.NDVI_FARMERS_CSV
    if farmers_csv is None:
        raise PipelineError(
            STEP, "missing-prereq", "NDVI_FARMERS_CSV is not configured",
            "set it in .env or pass a path", exit_code=3,
        )
    if not farmers_csv.exists():
        raise PipelineError(
            STEP, "missing-prereq", f"farmer registry CSV not found: {farmers_csv}",
            "create it with columns: mahsooli_id, lat, lon[, radius_m], or set "
            "NDVI_FARMERS_CSV in .env (the tracked demo is docs/sample_ndvi_farmers.csv)",
            exit_code=3,
        )

    out_path = config.FARMERS_NORMALIZED_CSV

    print("=" * 90)
    print("NDVI step 0 - load and validate farmer plots")
    print("=" * 90)
    print(f"Input:  {farmers_csv}")
    print(f"Output: {out_path}")
    print(f"Default radius: {config.FARMER_RADIUS_M} m")
    print("=" * 90)

    if out_path.exists() and out_path.stat().st_size > 0 and not args.force:
        print(f"SKIP - normalised manifest already exists: {out_path}")
        print("       (use --force to rebuild)")
        return 0

    rows, skipped, out_of_aoi = load_farmers(farmers_csv)

    if not rows:
        raise PipelineError(
            STEP, "invalid-input",
            f"0 valid farmer rows in {farmers_csv} ({skipped} skipped)",
            "fix the registry columns: mahsooli_id, lat, lon[, radius_m]",
            exit_code=2,
        )

    write_csv_atomic(out_path, fieldnames=OUTPUT_FIELDS, rows=rows)

    print()
    print("=" * 90)
    print(f"Valid plots: {len(rows)}   Skipped: {skipped}   Outside AOI: {out_of_aoi}")
    print(f"Saved: {out_path}")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    run_main(main, STEP)
