"""
Step 3 - Seasonal totals, multi-year average, and the score lookup table.

For each year, sums the in-season monthly clipped rasters (default Jun+Jul+Aug+Sep)
into a seasonal-total raster, then averages those totals across all years. Finally
writes the grid lookup CSV mapping each valid 0.05 deg cell to its average rainfall
and Mahsooli 1-10 score.

  Input:   data/02_clip/<year>/chirps-v2.0.<year>.<MM>_<month>.tif
  Output:  data/03_seasonal_totals/<year>/Mahala_CHIRPS_<season>_total_<year>.tif
           data/04_average/Mahala_CHIRPS_<season>_average_<start>_<end>_<n>years.tif
           data/05_tables/Mahala_CHIRPS_grid_lookup_<start>_<end>_<n>years.csv

A seasonal cell is valid only where all in-season months have data. All paths,
the period, and the scoring rubric come from config.py / .env.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config

# Configure PROJ before importing rasterio (see config.configure_proj_database).
config.configure_proj_database()

import numpy as np
import rasterio
from rasterio.transform import xy


def ensure_dirs() -> None:
    config.SEASONAL_DIR.mkdir(parents=True, exist_ok=True)
    config.AVERAGE_DIR.mkdir(parents=True, exist_ok=True)
    config.TABLE_DIR.mkdir(parents=True, exist_ok=True)


def find_month_tif(year: int, month: int, suffix: str):
    """Finds the clipped monthly TIFF produced by step 2."""
    year_dir = config.CLIP_DIR / str(year)
    if not year_dir.exists():
        return None

    expected = year_dir / f"{config.PRODUCT_PREFIX}.{year}.{month:02d}_{suffix}.tif"
    if expected.exists():
        return expected

    candidates = sorted(year_dir.glob(f"*{year}.{month:02d}*{suffix}*.tif"))
    if candidates:
        return candidates[0]

    candidates = sorted(year_dir.glob(f"*{year}.{month:02d}*.tif"))
    if candidates:
        return candidates[0]

    return None


def read_raster_as_nan(tif_path: Path):
    """Reads a raster as float32, converting NoData to np.nan."""
    with rasterio.open(tif_path) as src:
        arr = src.read(1).astype("float32")
        profile = src.profile.copy()
        transform = src.transform
        crs = src.crs

        nodata = src.nodata
        if nodata is not None:
            arr = np.where(arr == nodata, np.nan, arr)

        # CHIRPS / common NoData safety net.
        arr = np.where(arr <= -9000, np.nan, arr)

    return arr, profile, transform, crs


def write_float_raster(out_tif: Path, arr: np.ndarray, profile: dict) -> None:
    """Writes a float32 GeoTIFF with NoData filled in."""
    out_tif.parent.mkdir(parents=True, exist_ok=True)

    out_profile = profile.copy()
    out_profile.update(
        driver="GTiff",
        dtype="float32",
        count=1,
        nodata=config.NODATA,
        compress="deflate",
        height=arr.shape[0],
        width=arr.shape[1],
    )

    # Avoid block-size problems on small clipped rasters.
    out_profile.pop("blockxsize", None)
    out_profile.pop("blockysize", None)
    out_profile.pop("tiled", None)

    out_arr = np.where(np.isfinite(arr), arr, config.NODATA).astype("float32")

    with rasterio.open(out_tif, "w", **out_profile) as dst:
        dst.write(out_arr, 1)


def season_tag() -> str:
    """
    Short season tag for filenames.

    A contiguous month run uses 'First_Last' (e.g. 'Jun_Sep' for 6..9); a single
    month uses just that month; non-contiguous months join all abbreviations so
    two different SEASON_MONTHS never collide on the same output filename.
    """
    months = sorted(config.MONTHS.keys())
    abbrevs = [config.MONTH_NAMES[m][1][:3].capitalize() for m in months]
    contiguous = all(months[i + 1] - months[i] == 1 for i in range(len(months) - 1))

    if len(abbrevs) == 1:
        return abbrevs[0]
    if contiguous:
        return f"{abbrevs[0]}_{abbrevs[-1]}"
    return "_".join(abbrevs)


def calculate_seasonal_total_for_year(year: int):
    """Sums the in-season months for one year into a seasonal-total raster."""
    arrays = []
    reference_profile = None
    reference_transform = None
    reference_shape = None

    print(f"Calculating seasonal total for {year}...")

    for month, (_folder, suffix) in config.MONTHS.items():
        tif_path = find_month_tif(year, month, suffix)
        if tif_path is None:
            raise FileNotFoundError(
                f"Missing clipped raster for {year}-{month:02d} in {config.CLIP_DIR / str(year)}"
            )

        print(f"  Reading: {tif_path.name}")
        arr, profile, transform, _crs = read_raster_as_nan(tif_path)

        if reference_shape is None:
            reference_shape = arr.shape
            reference_profile = profile
            reference_transform = transform
        elif arr.shape != reference_shape:
            raise ValueError(
                f"Shape mismatch for {tif_path}: {arr.shape} != {reference_shape}"
            )

        arrays.append(arr)

    stack = np.stack(arrays, axis=0)

    # Valid only where all in-season months have values.
    valid_all_months = np.all(np.isfinite(stack), axis=0)
    seasonal_total = np.where(
        valid_all_months,
        np.sum(stack, axis=0),
        np.nan,
    ).astype("float32")

    out_tif = config.SEASONAL_DIR / str(year) / f"Mahala_CHIRPS_{season_tag()}_total_{year}.tif"
    write_float_raster(out_tif, seasonal_total, reference_profile)
    print(f"  Saved: {out_tif}")

    return seasonal_total, reference_profile, reference_transform


def write_lookup_csv(csv_path, seasonal_by_year, average_arr, reference_transform):
    """Writes one CSV row per valid CHIRPS grid cell."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    years = list(config.YEARS)
    avg_start, avg_end, avg_count = min(years), max(years), len(years)
    avg_col = f"avg_{season_tag().lower()}_{avg_start}_{avg_end}_mm"

    headers = ["grid_key", "lat_center", "lon_center"]
    for year in years:
        headers.append(f"{season_tag().lower()}_total_{year}_mm")
    headers.extend([avg_col, "score_1_10"])

    height, width = average_arr.shape

    # The clean two-column lookup (grid_key, score_1_10) is the importable
    # Google-Sheets deliverable. It is written alongside the rich table from the
    # same per-cell values, so the two files can never disagree.
    two_col_path = csv_path.with_name(
        csv_path.name.replace("grid_lookup", "score_lookup_2col")
    )

    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f, \
            open(two_col_path, "w", newline="", encoding="utf-8-sig") as f2:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer2 = csv.writer(f2)
        writer2.writerow(["grid_key", "score_1_10"])

        for row in range(height):
            for col in range(width):
                avg_mm = average_arr[row, col]
                if not np.isfinite(avg_mm):
                    continue  # outside the Mahala polygon / NoData

                lon, lat = xy(reference_transform, row, col, offset="center")

                grid_key = config.make_grid_key(float(lat), float(lon))
                score = config.score_from_rainfall(float(avg_mm))

                record = {
                    "grid_key": grid_key,
                    "lat_center": round(float(lat), 6),
                    "lon_center": round(float(lon), 6),
                    avg_col: round(float(avg_mm), 3),
                    "score_1_10": score,
                }
                for year in years:
                    val = seasonal_by_year[year][row, col]
                    record[f"{season_tag().lower()}_total_{year}_mm"] = (
                        round(float(val), 3) if np.isfinite(val) else ""
                    )

                writer.writerow(record)
                writer2.writerow([grid_key, score])

    print(f"CSV saved: {csv_path}")
    print(f"2-col CSV saved: {two_col_path}")


def process() -> None:
    ensure_dirs()

    years = list(config.YEARS)

    print("=" * 90)
    print(f"CHIRPS Mahala - seasonal totals and {len(years)}-year average")
    print("=" * 90)
    print(f"Input clipped rasters: {config.CLIP_DIR}")
    print(f"Period: {min(years)}-{max(years)} ({len(years)} years)")
    print("=" * 90)

    seasonal_by_year = {}
    reference_profile = None
    reference_transform = None
    reference_shape = None

    print()
    print("=" * 90)
    print("STEP 1 - Calculate seasonal totals for each year")
    print("=" * 90)

    for year in years:
        seasonal_total, profile, transform = calculate_seasonal_total_for_year(year)

        if reference_shape is None:
            reference_shape = seasonal_total.shape
            reference_profile = profile
            reference_transform = transform
        elif seasonal_total.shape != reference_shape:
            raise ValueError(
                f"Seasonal raster shape mismatch for {year}: "
                f"{seasonal_total.shape} != {reference_shape}"
            )

        seasonal_by_year[year] = seasonal_total

    print()
    print("=" * 90)
    print("STEP 2 - Calculate average seasonal rainfall")
    print("=" * 90)

    avg_stack = np.stack([seasonal_by_year[year] for year in years], axis=0)
    valid_count = np.sum(np.isfinite(avg_stack), axis=0)

    # A cell is averaged only where ALL years have a seasonal total, matching the
    # per-year rule that requires every in-season month. This keeps the averaging
    # denominator equal to the number of years named in the output filename/column.
    with np.errstate(invalid="ignore"):
        average_arr = np.nanmean(avg_stack, axis=0)
    average_arr = np.where(valid_count == len(years), average_arr, np.nan).astype("float32")

    avg_start, avg_end, avg_count = min(years), max(years), len(years)
    avg_tif = config.AVERAGE_DIR / (
        f"Mahala_CHIRPS_{season_tag()}_average_{avg_start}_{avg_end}_{avg_count}years.tif"
    )
    write_float_raster(avg_tif, average_arr, reference_profile)
    print(f"Average raster saved: {avg_tif}")

    print()
    print("=" * 90)
    print("STEP 3 - Create CSV lookup table")
    print("=" * 90)

    csv_path = config.TABLE_DIR / (
        f"Mahala_CHIRPS_grid_lookup_{avg_start}_{avg_end}_{avg_count}years.csv"
    )
    write_lookup_csv(csv_path, seasonal_by_year, average_arr, reference_transform)

    print()
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Seasonal totals folder: {config.SEASONAL_DIR}")
    print(f"Average folder:         {config.AVERAGE_DIR}")
    print(f"CSV table folder:       {config.TABLE_DIR}")


if __name__ == "__main__":
    process()
