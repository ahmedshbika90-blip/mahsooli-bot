"""
Snap farmer GPS coordinates to the grid and score them (standalone helper).

This is the runnable reference for the Google Sheets workflow (see
docs/lookup_in_google_sheets.md): it takes a list of farmer GPS coordinates,
snaps each one to its CHIRPS 0.05 deg grid cell, looks the cell up in the
lookup table produced by the averaging step (chirps/3_average.py), and reports
the rainfall score. Coordinates that fall outside the Mahala AOI get a clear,
non-technical fallback message instead of an error.

Usage:
    python tools/snap_score.py [farmers.csv] [lookup.csv]

Defaults:
    farmers.csv -> config.SNAP_FARMERS_CSV (docs/sample_farmers.csv unless overridden
                   in .env; the single place to swap farm coordinates)
    lookup.csv  -> the newest CSV in DATA_ROOT/05_tables

The input CSV must have lat, lon and an id column (farmer_id, mahsooli_id or id).
Results are printed and also written to DATA_ROOT/05_tables/farmer_scores.csv.
"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config

OUT_OF_AOI_MESSAGE = "Outside coverage area - no rainfall score (escalate for manual review)"


def load_lookup(lookup_csv: Path) -> dict:
    """Loads the lookup table into {grid_key: score} (and keeps the avg column)."""
    table = {}
    with open(lookup_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        avg_col = next((c for c in reader.fieldnames if c.startswith("avg_")), None)
        for row in reader:
            table[row["grid_key"]] = {
                "score": row.get("score_1_10", ""),
                "avg_mm": row.get(avg_col, "") if avg_col else "",
            }
    return table


def find_default_lookup() -> Path:
    candidates = sorted(config.TABLE_DIR.glob("Mahala_CHIRPS_grid_lookup_*.csv"))
    if not candidates:
        raise FileNotFoundError(
            f"No lookup CSV found in {config.TABLE_DIR}. Run the pipeline first "
            f"(python run_pipeline.py)."
        )
    return candidates[-1]


def process(farmers_csv: Path, lookup_csv: Path) -> int:
    print("=" * 90)
    print("Snap farmer coordinates to the CHIRPS grid and score them")
    print("=" * 90)
    print(f"Farmers: {farmers_csv}")
    print(f"Lookup:  {lookup_csv}")
    print(f"Cell size: {config.CELL_SIZE} deg")
    print("=" * 90)

    table = load_lookup(lookup_csv)

    farmers = config.load_farmers(farmers_csv)

    results = []
    out_of_aoi = 0

    for farmer in farmers:
        farmer_id = farmer["id"]
        lat = farmer["lat"]
        lon = farmer["lon"]

        clat, clon = config.snap_to_grid_center(lat, lon)
        grid_key = config.make_grid_key(clat, clon)
        match = table.get(grid_key)

        if match:
            score = match["score"]
            note = ""
        else:
            score = ""
            note = OUT_OF_AOI_MESSAGE
            out_of_aoi += 1

        results.append({
            "farmer_id": farmer_id,
            "lat": lat,
            "lon": lon,
            "grid_key": grid_key,
            "score_1_10": score,
            "note": note,
        })

        shown = score if score != "" else "-"
        print(f"  {farmer_id:<8} ({lat:.4f}, {lon:.4f}) -> {grid_key:<16} score={shown}  {note}")

    out_path = config.TABLE_DIR / "farmer_scores.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f, fieldnames=["farmer_id", "lat", "lon", "grid_key", "score_1_10", "note"]
        )
        writer.writeheader()
        writer.writerows(results)

    scored = sum(1 for r in results if r["score_1_10"] != "")
    print()
    print("=" * 90)
    print(f"Scored: {scored}/{len(results)}   Out of AOI: {out_of_aoi}")
    print(f"Results saved: {out_path}")
    print("=" * 90)

    # All listed farmers were handled (in-AOI scored, out-of-AOI flagged); never fails.
    return 0


def main() -> int:
    farmers_csv = Path(sys.argv[1]) if len(sys.argv) > 1 else config.SNAP_FARMERS_CSV
    lookup_csv = Path(sys.argv[2]) if len(sys.argv) > 2 else find_default_lookup()

    if not farmers_csv.exists():
        raise FileNotFoundError(f"Farmers CSV not found: {farmers_csv}")
    if not lookup_csv.exists():
        raise FileNotFoundError(f"Lookup CSV not found: {lookup_csv}")

    return process(farmers_csv, lookup_csv)


if __name__ == "__main__":
    sys.exit(main())
