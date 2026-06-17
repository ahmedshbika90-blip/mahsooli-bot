"""
Step 2 - Clip the monthly CHIRPS rasters by the closed Mahala boundary.

Reads each raw monthly GeoTIFF (from step 0) and clips it to the closed Mahala
polygon (from step 1), writing one clipped raster per month/year.

  Input rasters:   data/01_raw_africa_monthly/<year>/<MM_Month>/chirps-v2.0.<year>.<MM>.tif
  Boundary:        data/00_boundary/Mahala_closed.geojson
  Output:          data/02_clip/<year>/chirps-v2.0.<year>.<MM>_<month>.tif

CHIRPS Africa rasters and the Mahala boundary are both lon/lat WGS84 (EPSG:4326),
so no reprojection is performed. All paths come from config.py / .env.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config

# Configure PROJ before importing rasterio (see config.configure_proj_database).
config.configure_proj_database()

import rasterio
from rasterio.mask import mask


def load_geojson_geometries(geojson_path: Path):
    """Loads clipping geometries from GeoJSON, normalising lines into polygons."""
    if not geojson_path.exists():
        raise FileNotFoundError(f"Boundary GeoJSON not found: {geojson_path}")

    with open(geojson_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    geometries = []

    def normalize_geometry(geom):
        gtype = geom.get("type")
        coords = geom.get("coordinates")

        if gtype in ("Polygon", "MultiPolygon"):
            return geom

        if gtype == "LineString":
            ring = coords[:]
            if len(ring) < 4:
                raise ValueError("LineString has too few points to become a polygon.")
            if ring[0] != ring[-1]:
                ring.append(ring[0])
            return {"type": "Polygon", "coordinates": [ring]}

        if gtype == "MultiLineString":
            polygons = []
            for part in coords:
                ring = part[:]
                if len(ring) < 4:
                    continue
                if ring[0] != ring[-1]:
                    ring.append(ring[0])
                polygons.append([ring])

            if not polygons:
                raise ValueError("MultiLineString does not contain enough coordinates.")

            if len(polygons) == 1:
                return {"type": "Polygon", "coordinates": polygons[0]}

            return {"type": "MultiPolygon", "coordinates": polygons}

        raise ValueError(f"Unsupported geometry type: {gtype}")

    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            geom = feature.get("geometry")
            if geom:
                geometries.append(normalize_geometry(geom))
    elif data.get("type") == "Feature":
        geometries.append(normalize_geometry(data["geometry"]))
    else:
        geometries.append(normalize_geometry(data))

    if not geometries:
        raise ValueError(f"No valid geometry found in: {geojson_path}")

    return geometries


def find_input_tif(year: int, month: int, month_folder: str):
    """Locates the raw unzipped monthly TIFF for a given year/month."""
    folder = config.RAW_DIR / str(year) / month_folder

    if not folder.exists():
        return None

    expected_path = folder / f"{config.PRODUCT_PREFIX}.{year}.{month:02d}.tif"
    if expected_path.exists():
        return expected_path

    candidates = sorted(folder.glob("*.tif"))
    candidates = [p for p in candidates if not p.name.lower().endswith(".tif.gz")]
    if candidates:
        return candidates[0]

    return None


def clip_one_tif(input_tif: Path, output_tif: Path, geometries) -> bool:
    output_tif.parent.mkdir(parents=True, exist_ok=True)

    if output_tif.exists() and output_tif.stat().st_size > 0:
        print(f"SKIP - already clipped: {output_tif}")
        return True

    try:
        with rasterio.open(input_tif) as src:
            clipped_data, clipped_transform = mask(
                src,
                geometries,
                crop=True,
                nodata=config.NODATA,
                filled=True,
                all_touched=True,
            )

            profile = src.profile.copy()
            profile.update(
                driver="GTiff",
                height=clipped_data.shape[1],
                width=clipped_data.shape[2],
                transform=clipped_transform,
                nodata=config.NODATA,
                compress="deflate",
            )

            # Tiled output can fail on very small clips unless block sizes are set
            # correctly; for this small Mahala clip, non-tiled output is safer.
            profile.pop("blockxsize", None)
            profile.pop("blockysize", None)
            profile.pop("tiled", None)

            with rasterio.open(output_tif, "w", **profile) as dst:
                dst.write(clipped_data)

        print(f"OK clipped: {output_tif}")
        return True

    except Exception as e:
        print(f"ERROR clipping: {input_tif}")
        print(e)
        return False


def process() -> int:
    print("=" * 90)
    print("Clip CHIRPS monthly TIFFs by Mahala_closed.geojson")
    print("=" * 90)
    print(f"Input TIFF root: {config.RAW_DIR}")
    print(f"Boundary:       {config.CLOSED_GEOJSON}")
    print(f"Output root:    {config.CLIP_DIR}")
    print("=" * 90)

    geometries = load_geojson_geometries(config.CLOSED_GEOJSON)

    total = 0
    clipped = 0
    missing = []
    failed = []

    for year in config.YEARS:
        print()
        print("-" * 90)
        print(f"YEAR: {year}")
        print("-" * 90)

        year_output_dir = config.CLIP_DIR / str(year)
        year_output_dir.mkdir(parents=True, exist_ok=True)

        for month, (month_folder, month_suffix) in config.MONTHS.items():
            total += 1

            input_tif = find_input_tif(year, month, month_folder)
            if input_tif is None:
                expected_folder = config.RAW_DIR / str(year) / month_folder
                print(f"MISSING TIF: {expected_folder}")
                missing.append(str(expected_folder))
                continue

            output_name = f"{config.PRODUCT_PREFIX}.{year}.{month:02d}_{month_suffix}.tif"
            output_tif = year_output_dir / output_name

            if clip_one_tif(input_tif, output_tif, geometries):
                clipped += 1
            else:
                failed.append(str(input_tif))

    print()
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Expected files: {total}")
    print(f"Clipped/skipped: {clipped}")
    print(f"Missing: {len(missing)}")
    print(f"Failed: {len(failed)}")
    print(f"Output folder: {config.CLIP_DIR}")

    if missing:
        print()
        print("MISSING INPUT FOLDERS / FILES:")
        for item in missing:
            print(item)

    if failed:
        print()
        print("FAILED INPUT FILES:")
        for item in failed:
            print(item)

    return len(missing) + len(failed)


if __name__ == "__main__":
    # Non-zero exit on any missing/failed clip so run_pipeline.py stops here.
    sys.exit(1 if process() else 0)
