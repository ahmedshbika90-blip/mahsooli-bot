"""Unit tests for E1.3 pilot launch checks."""

import csv
import tempfile
import unittest
from pathlib import Path

import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import tools.pilot_launch_check as pilot_launch_check  # noqa: E402


class PilotFarmerSelectionTests(unittest.TestCase):
    def _farmers_csv(self, rows):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        path = Path(tmp.name) / "farmers.csv"
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["mahsooli_id", "lat", "lon"])
            writer.writerows(rows)
        return path

    def test_none_limit_checks_all_rows(self):
        path = self._farmers_csv([
            ["M001", "13.470", "35.980"],
            ["M002", "13.462", "36.031"],
            ["M003", "13.431", "35.829"],
        ])

        farmers = pilot_launch_check.load_first_farmers(path, limit=None)

        self.assertEqual([f["id"] for f in farmers], ["M001", "M002", "M003"])

    def test_explicit_limit_requires_enough_rows(self):
        path = self._farmers_csv([
            ["M001", "13.470", "35.980"],
            ["M002", "13.462", "36.031"],
        ])

        with self.assertRaises(ValueError) as ctx:
            pilot_launch_check.load_first_farmers(path, limit=10)

        self.assertIn("contains 2 valid farmer rows, fewer than requested limit 10", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
