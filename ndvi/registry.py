"""
NDVI step 0b - Load and validate the baseline-donor plot registry (local only).

Reads the client-supplied plot registry (config.NDVI_PLOTS_REGISTRY, see
data/farmers/baseline_plots.csv) - the plots used to extract the rainfed /
irrigated sector baseline curves. These farmers are NOT the ones being
financed; their plots exist only because no single farmer has enough cotton
history for a representative baseline.

Like ndvi/farmers.py this is a cheap local prep step with no Earth Engine
dependency, so inputs are checked before any quota is spent. Per plot it:

  - parses the geometry: a WKT POLYGON (lon lat order) or a single point
    (decimal degrees; DMS like 13deg59'45"N is also accepted) buffered by a
    radius derived from the stated area (radius = sqrt(area_feddan*4200/pi))
    unless an explicit radius_m is given;
  - sanity-checks polygons: ring closure, >=3 distinct vertices, planar area
    vs the stated feddan (warn when off by >50% - catches transposed
    coordinates), and self-intersection (WARN and proceed with Earth Engine's
    even-odd interpretation - never silently "fixed");
  - filters the listed cotton seasons through seasons.usable_seasons(): years
    before MIN_SEASON_YEAR (no Sentinel-2 SR over Sudan) and unfinished
    seasons are skipped WITH the reason recorded in the manifest;
  - flags coordinates outside the sector's AOI box (warn only, never dropped).

Usage:
    python ndvi/registry.py [baseline_plots.csv] [--force]

Output: data/ndvi/plots_normalized.json   (polygon rings don't fit a flat CSV)
"""

import argparse
import csv
import math
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
import seasons
from pipeline_utils import PipelineError, run_main, write_json_atomic

STEP = "registry"

REQUIRED_COLUMNS = [
    "plot_id", "farmer_name", "sector", "geometry_type", "geometry_wkt",
    "lat", "lon", "area_feddan", "radius_m", "seasons",
]

_DMS_RE = re.compile(
    r"""^\s*(?P<deg>\d{1,3})\s*(?:°|deg)\s*
         (?P<min>\d{1,2})\s*['’]\s*
         (?:(?P<sec>\d{1,2}(?:\.\d+)?)\s*["”]\s*)?
         (?P<hemi>[NSEW])\s*$""",
    re.VERBOSE | re.IGNORECASE,
)


def parse_dms(raw: str) -> float:
    """'13deg59'45"N' / '13°59'45"N' -> 13.995833 (negative for S/W)."""
    m = _DMS_RE.match(raw or "")
    if not m:
        raise ValueError(f"not a DMS coordinate: {raw!r}")
    value = (int(m.group("deg"))
             + int(m.group("min")) / 60.0
             + float(m.group("sec") or 0.0) / 3600.0)
    if m.group("hemi").upper() in ("S", "W"):
        value = -value
    return value


def parse_coordinate(raw: str) -> float:
    """Decimal degrees, falling back to DMS."""
    raw = (raw or "").strip()
    try:
        return float(raw)
    except ValueError:
        return parse_dms(raw)


def parse_wkt_polygon(wkt: str):
    """
    'POLYGON((lon lat, lon lat, ...))' -> closed ring [[lon, lat], ...].

    Validates >=3 distinct vertices and auto-closes an open ring (the client
    sheets sometimes repeat the first point, sometimes not).
    """
    m = re.match(r"^\s*POLYGON\s*\(\(\s*(.+?)\s*\)\)\s*$", wkt or "", re.IGNORECASE)
    if not m:
        raise ValueError(f"not a WKT POLYGON: {wkt[:60]!r}...")
    ring = []
    for pair in m.group(1).split(","):
        parts = pair.split()
        if len(parts) != 2:
            raise ValueError(f"bad WKT coordinate pair: {pair!r}")
        lon, lat = float(parts[0]), float(parts[1])
        ring.append([lon, lat])
    if ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    if len(set(map(tuple, ring[:-1]))) < 3:
        raise ValueError("polygon needs >= 3 distinct vertices")
    return ring


def _local_meters(ring):
    """Project a lon/lat ring to local planar metres (good enough at plot scale)."""
    lat0 = sum(lat for _, lat in ring[:-1]) / (len(ring) - 1)
    kx = 111_320.0 * math.cos(math.radians(lat0))  # m per deg lon
    ky = 110_540.0                                  # m per deg lat
    return [((lon - ring[0][0]) * kx, (lat - ring[0][1]) * ky) for lon, lat in ring]


def ring_area_m2(ring) -> float:
    """Planar (shoelace) area of a closed lon/lat ring, in m2."""
    pts = _local_meters(ring)
    area2 = 0.0
    for (x1, y1), (x2, y2) in zip(pts[:-1], pts[1:]):
        area2 += x1 * y2 - x2 * y1
    return abs(area2) / 2.0


def _segments_intersect(p, q, r, s):
    """True if segment pq strictly crosses segment rs (shared endpoints excluded)."""
    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    d1 = cross(r, s, p)
    d2 = cross(r, s, q)
    d3 = cross(p, q, r)
    d4 = cross(p, q, s)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def ring_self_intersects(ring) -> bool:
    """Check every non-adjacent segment pair of a closed ring (O(n^2), n is tiny)."""
    segs = list(zip(ring[:-1], ring[1:]))
    n = len(segs)
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue  # first and last segments share the ring's start vertex
            if _segments_intersect(segs[i][0], segs[i][1], segs[j][0], segs[j][1]):
                return True
    return False


def _normalize_row(raw, line_no, today=None):
    """One registry CSV row -> a normalized plot dict (raises PipelineError)."""
    def fail(detail):
        raise PipelineError(
            STEP, "invalid-input", f"registry line {line_no}: {detail}",
            f"fix {config.NDVI_PLOTS_REGISTRY} (see ndvi/registry.py docstring "
            f"for the schema)", exit_code=2,
        )

    plot_id = (raw.get("plot_id") or "").strip()
    if not plot_id:
        fail("missing plot_id")

    sector = (raw.get("sector") or "").strip().lower()
    if sector not in config.NDVI_SECTORS:
        fail(f"{plot_id}: sector {sector!r} not in {config.NDVI_SECTORS}")

    geometry_type = (raw.get("geometry_type") or "").strip().lower()
    area_raw = (raw.get("area_feddan") or "").strip()
    area_feddan = float(area_raw) if area_raw else None

    warnings = []

    if geometry_type == "polygon":
        try:
            ring = parse_wkt_polygon(raw.get("geometry_wkt") or "")
        except ValueError as e:
            fail(f"{plot_id}: {e}")
        for vlon, vlat in ring:
            if not (-90.0 <= vlat <= 90.0) or not (-180.0 <= vlon <= 180.0):
                fail(f"{plot_id}: polygon vertex out of range "
                     f"(lon={vlon}, lat={vlat}) - check WKT order is lon lat")
        coordinates = ring
        radius_m = None
        # Representative point = vertex centroid (for AOI check / display only).
        lon = sum(p[0] for p in ring[:-1]) / (len(ring) - 1)
        lat = sum(p[1] for p in ring[:-1]) / (len(ring) - 1)

        if ring_self_intersects(ring):
            warnings.append(
                "polygon ring SELF-INTERSECTS - proceeding with Earth Engine's "
                "even-odd interpretation; confirm the vertex order with the client"
            )
        if area_feddan:
            measured = ring_area_m2(ring)
            stated = area_feddan * config.FEDDAN_M2
            if not 0.5 <= measured / stated <= 1.5:
                warnings.append(
                    f"polygon area ~{measured / config.FEDDAN_M2:,.0f} feddan vs "
                    f"stated {area_feddan:,.0f} (off by >50%) - possible "
                    f"transposed/missing coordinates"
                )
    elif geometry_type == "point":
        try:
            lat = parse_coordinate(raw.get("lat"))
            lon = parse_coordinate(raw.get("lon"))
        except ValueError as e:
            fail(f"{plot_id}: {e}")
        if not (-90.0 <= lat <= 90.0) or not (-180.0 <= lon <= 180.0):
            fail(f"{plot_id}: lat/lon out of range ({lat}, {lon})")
        coordinates = [lon, lat]
        radius_raw = (raw.get("radius_m") or "").strip()
        if radius_raw:
            radius_m = float(radius_raw)
        elif area_feddan:
            radius_m = round(config.radius_from_feddan(area_feddan), 1)
        else:
            radius_m = config.FARMER_RADIUS_M
    else:
        fail(f"{plot_id}: geometry_type must be 'polygon' or 'point', "
             f"got {geometry_type!r}")

    try:
        listed = seasons.parse_seasons(raw.get("seasons") or "")
    except ValueError as e:
        fail(f"{plot_id}: bad seasons: {e}")
    if not listed:
        fail(f"{plot_id}: no seasons listed (the baseline needs at least one "
             f"cotton planting year)")
    kept, skipped = seasons.usable_seasons(listed, today=today)

    in_aoi = config.is_in_aoi(lat, lon, sector)

    return {
        "plot_id": plot_id,
        "farmer_name": (raw.get("farmer_name") or "").strip(),
        "sector": sector,
        "locality": (raw.get("locality") or "").strip(),
        "village": (raw.get("village") or "").strip(),
        "geometry_type": geometry_type,
        "coordinates": coordinates,
        "lat": round(lat, 7),
        "lon": round(lon, 7),
        "area_feddan": area_feddan,
        "radius_m": radius_m,
        "seasons": kept,
        "seasons_skipped": [[year, reason] for year, reason in skipped],
        "in_aoi": in_aoi,
        "warnings": warnings,
    }


def load_registry(registry_csv: Path, today=None):
    """Parse + validate the registry CSV into normalized plot dicts."""
    with open(registry_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing_cols = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing_cols:
            raise PipelineError(
                STEP, "invalid-input",
                f"{registry_csv} is missing columns: {missing_cols}",
                "see ndvi/registry.py docstring for the schema", exit_code=2,
            )
        plots = [_normalize_row(raw, line_no, today=today)
                 for line_no, raw in enumerate(reader, start=2)]

    ids = [p["plot_id"] for p in plots]
    dupes = sorted({i for i in ids if ids.count(i) > 1})
    if dupes:
        raise PipelineError(
            STEP, "invalid-input", f"duplicate plot_id(s): {dupes}",
            f"make plot ids unique in {registry_csv}", exit_code=2,
        )
    return plots


def load_normalized_plots(path: Path = None):
    """
    Read the manifest written by this step. Shared by baseline / current /
    exports so all steps agree on the plot schema.
    """
    import json

    path = path or config.PLOTS_NORMALIZED_JSON
    if not path.exists():
        raise PipelineError(
            STEP, "missing-prereq",
            f"normalised plot manifest not found: {path}",
            "run this first: python ndvi/registry.py", exit_code=3,
        )
    with open(path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    plots = manifest.get("plots", [])
    if not plots:
        raise PipelineError(
            STEP, "invalid-input", f"{path} contains no plots",
            "rebuild it: python ndvi/registry.py --force", exit_code=2,
        )
    return plots


def parse_args():
    parser = argparse.ArgumentParser(
        description="Load and validate the baseline-donor plot registry.")
    parser.add_argument("registry_csv", nargs="?", default=None,
                        help="Registry CSV (default: config.NDVI_PLOTS_REGISTRY).")
    parser.add_argument("--force", action="store_true",
                        help="Rewrite the manifest even when its content is unchanged.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    registry_csv = Path(args.registry_csv) if args.registry_csv else config.NDVI_PLOTS_REGISTRY
    if registry_csv is None or not registry_csv.exists():
        raise PipelineError(
            STEP, "missing-prereq",
            f"plot registry CSV not found: {registry_csv}",
            "create it (schema in ndvi/registry.py docstring) or set "
            "NDVI_PLOTS_REGISTRY in .env", exit_code=3,
        )

    out_path = config.PLOTS_NORMALIZED_JSON

    print("=" * 90)
    print("NDVI step 0b - load and validate baseline-donor plot registry")
    print("=" * 90)
    print(f"Input:  {registry_csv}")
    print(f"Output: {out_path}")
    print(f"Season window: Jun 1 -> Mar 31 (Y+1), {seasons.n_weeks()} weeks; "
          f"seasons before {config.MIN_SEASON_YEAR} are skipped")
    print("=" * 90)

    # The registry is ALWAYS re-parsed (cheap, local, no Earth Engine): the
    # manifest is committed to git, so a skip-if-exists here would make edits
    # to the registry CSV a dead letter in CI. The file on disk is only
    # rewritten when the content actually changed, so the built_utc stamp
    # does not churn the CI commit-back on every run.
    plots = load_registry(registry_csv)
    if not plots:
        raise PipelineError(
            STEP, "invalid-input", f"0 plots in {registry_csv}",
            "fill the registry (schema in ndvi/registry.py docstring)", exit_code=2,
        )

    for p in plots:
        for w in p["warnings"]:
            print(f"WARN [{STEP}] {p['plot_id']}: {w}")
        for year, reason in p["seasons_skipped"]:
            print(f"WARN [{STEP}] {p['plot_id']}: season {year} skipped - {reason}")
        if not p["in_aoi"]:
            print(f"WARN [{STEP}] {p['plot_id']} ({p['lat']:.4f}, {p['lon']:.4f}) "
                  f"is outside the {p['sector']} AOI box - flagged for manual "
                  f"review, still baselined/monitored")
        if not p["seasons"]:
            print(f"WARN [{STEP}] {p['plot_id']} has NO usable seasons - it will "
                  f"contribute nothing to the baseline")

    unchanged = False
    if out_path.exists() and not args.force:
        import json

        try:
            with open(out_path, "r", encoding="utf-8") as f:
                unchanged = json.load(f).get("plots") == json.loads(json.dumps(plots))
        except (json.JSONDecodeError, OSError):
            unchanged = False

    if unchanged:
        print(f"Manifest content unchanged - keeping existing {out_path}")
    else:
        manifest = {
            "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "source": str(registry_csv),
            "plots": plots,
        }
        write_json_atomic(out_path, manifest)

    by_sector = {}
    for p in plots:
        by_sector.setdefault(p["sector"], []).append(p)
    print()
    print("=" * 90)
    for sector in config.NDVI_SECTORS:
        sp = by_sector.get(sector, [])
        season_set = sorted({y for p in sp for y in p["seasons"]})
        print(f"  {sector:<10}: {len(sp)} plot(s), usable seasons {season_set}")
    n_skipped = sum(len(p["seasons_skipped"]) for p in plots)
    n_warn = sum(len(p["warnings"]) for p in plots)
    print(f"  Plots: {len(plots)}   Skipped seasons: {n_skipped}   "
          f"Geometry warnings: {n_warn}")
    print(f"  Manifest: {out_path}{' (unchanged)' if unchanged else ''}")
    print(f"RUN-SUMMARY [{STEP}] plots={len(plots)} "
          f"rainfed={len(by_sector.get('rainfed', []))} "
          f"irrigated={len(by_sector.get('irrigated', []))} "
          f"skipped_seasons={n_skipped} warnings={n_warn}")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    run_main(main, STEP)
