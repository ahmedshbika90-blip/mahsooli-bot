"""Unit tests for the E1.1 VLOOKUP workbook data selection."""

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "tools"))

import tools.google_sheets_lookup as google_sheets_lookup  # noqa: E402


class FarmersDemoRowsTests(unittest.TestCase):
    def test_demo_rows_use_supplied_farmer_coordinates(self):
        lookup = {
            "13.475_35.975": {"score_1_10": 10},
            "13.475_36.025": {"score_1_10": 7},
        }
        farmers = [
            {"id": "M001", "lat": 13.470, "lon": 35.980},
            {"id": "M002", "lat": 13.462, "lon": 36.031},
        ]

        rows = google_sheets_lookup.build_demo_rows(farmers, lookup)

        self.assertEqual(
            rows,
            [
                {
                    "farmer_id": "M001",
                    "lat": 13.470,
                    "lon": 35.980,
                    "grid_key": "13.475_35.975",
                    "score_1_10": 10,
                    "note": "",
                },
                {
                    "farmer_id": "M002",
                    "lat": 13.462,
                    "lon": 36.031,
                    "grid_key": "13.475_36.025",
                    "score_1_10": 7,
                    "note": "",
                },
            ],
        )

    def test_demo_rows_mark_out_of_lookup_coordinates(self):
        rows = google_sheets_lookup.build_demo_rows(
            [{"id": "M010", "lat": 12.100, "lon": 33.500}],
            {},
        )

        self.assertEqual(rows[0]["farmer_id"], "M010")
        self.assertEqual(rows[0]["score_1_10"], "")
        self.assertIn("Outside coverage", rows[0]["note"])


if __name__ == "__main__":
    unittest.main()
