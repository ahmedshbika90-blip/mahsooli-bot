"""
Run the full Mahala CHIRPS pipeline with one command:

    python run_pipeline.py

Executes the four steps in order, each in a fresh process using the same Python
interpreter, and stops immediately if any step fails. All steps are safe to
re-run: existing downloads and clipped rasters are skipped.

Steps:
    chirps/0_download.py        Download + unzip CHIRPS monthly rasters
    chirps/1_close_boundary.py  Close Mahala.geojson into a polygon
    chirps/2_clip.py            Clip monthly rasters to the polygon
    chirps/3_average.py         Seasonal totals, multi-year average, score lookup CSV
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

STEPS = [
    ("0", "Download CHIRPS monthly rasters", "chirps/0_download.py"),
    ("1", "Close Mahala boundary", "chirps/1_close_boundary.py"),
    ("2", "Clip rasters to boundary", "chirps/2_clip.py"),
    ("3", "Seasonal totals + average + lookup CSV", "chirps/3_average.py"),
]


def run_step(number: str, title: str, script: str) -> int:
    print()
    print("#" * 90)
    print(f"# STEP {number} - {title}  ({script})")
    print("#" * 90)

    result = subprocess.run([sys.executable, str(REPO_ROOT / script)], cwd=str(REPO_ROOT))
    return result.returncode


def main() -> int:
    print("=" * 90)
    print("Mahala CHIRPS pipeline")
    print("=" * 90)

    for number, title, script in STEPS:
        code = run_step(number, title, script)
        if code != 0:
            print()
            print("!" * 90)
            print(f"! Pipeline stopped: step {number} ({script}) exited with code {code}")
            print("!" * 90)
            return code

    print()
    print("=" * 90)
    print("PIPELINE COMPLETE - all steps finished successfully")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
