"""
Run the full NDVI monitoring cycle with one command:

    python ndvi_run_pipeline.py

Executes the three NDVI steps in order, each in a fresh process using the same
Python interpreter, and stops immediately if any step fails. All steps are safe to
re-run: the farmer manifest and baseline are skipped if present, and the dated log
+ Sheet upsert are idempotent.

This is a SEPARATE pipeline from the CHIRPS rainfall chain (run_pipeline.py): it
uses Google Earth Engine, needs EE/Sheets credentials, and runs on the in-season
monitoring cadence. Whether step 2 writes to the Google Sheet is controlled by
NDVI_SHEET_PUSH in .env, imagery export by NDVI_EXPORT_ENABLED, and the Google
Cloud Storage run archive by NDVI_GCS_ARCHIVE (no flags needed here).

Steps:
    ndvi/registry.py   Load + validate the baseline-donor plot registry (local)
    ndvi/baseline.py   Build/refresh the sector NDVI baselines (EE)
    ndvi/current.py    Current NDVI + alerts + Sheets export + imagery + archive

(ndvi/farmers.py - the financed-farmer manifest - is not part of the default
chain; it joins the cycle once real farmers are registered and
NDVI_MONITOR_FARMERS=true is set. The old M001-M010 demo plots are retired.)
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
import config

STEPS = [
    ("0", "Load + validate baseline-donor plot registry", "ndvi/registry.py"),
    ("1", "Build/refresh sector NDVI baselines (Earth Engine)", "ndvi/baseline.py"),
    ("2", "Current NDVI + alerts + Sheet export + imagery", "ndvi/current.py"),
]
if config.NDVI_MONITOR_FARMERS:
    # Financed farmers join the cycle: refresh their manifest before step 2.
    STEPS.insert(0, ("0a", "Load + validate financed-farmer plots", "ndvi/farmers.py"))


def run_step(number: str, title: str, script: str) -> int:
    print()
    print("#" * 90)
    print(f"# NDVI STEP {number} - {title}  ({script})")
    print("#" * 90)

    result = subprocess.run([sys.executable, str(REPO_ROOT / script)], cwd=str(REPO_ROOT))
    return result.returncode


def main() -> int:
    print("=" * 90)
    print("Mahala NDVI monitoring pipeline")
    print("=" * 90)

    for number, title, script in STEPS:
        code = run_step(number, title, script)
        if code != 0:
            print()
            print("!" * 90)
            print(f"! Pipeline stopped: NDVI step {number} ({script}) exited with code {code}")
            print("!" * 90)
            return code

    print()
    print("=" * 90)
    print("NDVI PIPELINE COMPLETE - all steps finished successfully")
    print("=" * 90)
    return 0


if __name__ == "__main__":
    sys.exit(main())
