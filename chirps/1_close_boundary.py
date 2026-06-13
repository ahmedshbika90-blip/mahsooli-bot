"""
Step 1 - Close the Mahala boundary into a polygon.

The source `Mahala.geojson` is an open LineString. This script closes it into a
valid ring and writes `Mahala_closed.geojson` (a Polygon by default), which step 2
uses to clip the rasters.

Closure strategy: if the first and last points already coincide, the ring is used
as-is. Otherwise the first and last segments are extended until they intersect, and
that intersection point is used to close the ring. If the segments are parallel
(no intersection), the ring is closed directly back to the first point.

Input/output paths come from config.py / .env.
"""

import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config

INPUT_GEOJSON = config.INPUT_GEOJSON
OUTPUT_GEOJSON = config.CLOSED_GEOJSON

# "Polygon" = closed area, "LineString" = closed line only.
OUTPUT_GEOMETRY_TYPE = "Polygon"

# True = keep the original endpoints and add the computed intersection point.
KEEP_ORIGINAL_ENDPOINTS = True

EPS = 1e-12


def xy(pt):
    return float(pt[0]), float(pt[1])


def distance(p1, p2):
    x1, y1 = xy(p1)
    x2, y2 = xy(p2)
    return math.hypot(x2 - x1, y2 - y1)


def line_intersection(p1, p2, p3, p4):
    """
    Intersection of two infinite lines:
        line 1: p1 -> p2
        line 2: p3 -> p4
    Returns None if the lines are parallel.
    """
    x1, y1 = xy(p1)
    x2, y2 = xy(p2)
    x3, y3 = xy(p3)
    x4, y4 = xy(p4)

    den = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(den) < EPS:
        return None

    det1 = x1 * y2 - y1 * x2
    det2 = x3 * y4 - y3 * x4

    px = (det1 * (x3 - x4) - (x1 - x2) * det2) / den
    py = (det1 * (y3 - y4) - (y1 - y2) * det2) / den

    return [px, py]


def get_coords(data):
    if data.get("type") == "FeatureCollection":
        feature = data["features"][0]
        properties = dict(feature.get("properties") or {})
        geom = feature["geometry"]
    elif data.get("type") == "Feature":
        properties = dict(data.get("properties") or {})
        geom = data["geometry"]
    else:
        properties = {}
        geom = data

    gtype = geom["type"]
    coords = geom["coordinates"]

    if gtype == "LineString":
        return coords, properties

    if gtype == "MultiLineString":
        longest = max(coords, key=lambda part: len(part))
        return longest, properties

    if gtype == "Polygon":
        return coords[0], properties

    raise ValueError(f"Unsupported geometry type: {gtype}")


def ring_area(ring):
    """Absolute polygon area via the shoelace formula (planar lon/lat units)."""
    area = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = xy(ring[i])
        x2, y2 = xy(ring[i + 1])
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


def close_coords_by_extension(coords):
    if len(coords) < 4:
        raise ValueError("At least 4 points are required.")

    if distance(coords[0], coords[-1]) < 1e-10:
        ring = coords[:]
        ring[-1] = ring[0]
        return ring, coords[0], "already_closed"

    intersection = line_intersection(
        coords[0], coords[1],
        coords[-2], coords[-1]
    )

    if intersection is None:
        ring = coords[:]
        ring.append(coords[0])
        return ring, coords[0], "direct_close_parallel_segments"

    closure_point = [
        round(intersection[0], 12),
        round(intersection[1], 12),
    ]

    if KEEP_ORIGINAL_ENDPOINTS:
        ring = [closure_point] + coords[:] + [closure_point]
    else:
        ring = [closure_point] + coords[1:-1] + [closure_point]

    return ring, closure_point, "extended_first_last_segments"


def main():
    print("=" * 80)
    print("Close Mahala GeoJSON")
    print("=" * 80)

    if not INPUT_GEOJSON.exists():
        raise FileNotFoundError(f"Input GeoJSON not found: {INPUT_GEOJSON}")

    with open(INPUT_GEOJSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    coords, properties = get_coords(data)
    ring, closure_point, method = close_coords_by_extension(coords)

    # Guard against a degenerate closure (e.g. an intersection that collapses the
    # ring to near-zero area), which would silently clip nothing downstream.
    if ring_area(ring) < 1e-12:
        raise ValueError(
            f"Closed ring has near-zero area (method={method}); check the input geometry."
        )

    properties.update({
        "closed": True,
        "closure_method": method,
        "closure_lon": closure_point[0],
        "closure_lat": closure_point[1],
    })

    if OUTPUT_GEOMETRY_TYPE.lower() == "polygon":
        geometry = {
            "type": "Polygon",
            "coordinates": [ring],
        }
    else:
        geometry = {
            "type": "LineString",
            "coordinates": ring,
        }

    out_data = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": properties,
                "geometry": geometry,
            }
        ],
    }

    OUTPUT_GEOJSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_GEOJSON, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    print("DONE")
    print(f"Output: {OUTPUT_GEOJSON}")
    print(f"Closure method: {method}")
    print(f"Closure point lon/lat: {closure_point[0]}, {closure_point[1]}")
    print(f"Google Maps lat/lon: {closure_point[1]}, {closure_point[0]}")


if __name__ == "__main__":
    main()
