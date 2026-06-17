"""Unit tests for the two-stage baseline averaging in ndvi/baseline.py.

Pure fixture data - no Earth Engine, no network.
Run:  python -m unittest discover tests
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ndvi"))
import baseline  # noqa: E402

BUILT = "2026-06-11T00:00:00Z"

PLOTS = [
    {"plot_id": "P1", "sector": "rainfed", "geometry_type": "polygon",
     "seasons": [2023, 2025], "seasons_skipped": [[2013, "pre-S2"]],
     "in_aoi": True, "warnings": []},
    {"plot_id": "P2", "sector": "rainfed", "geometry_type": "point",
     "seasons": [2025], "seasons_skipped": [], "in_aoi": True, "warnings": []},
    {"plot_id": "P3", "sector": "irrigated", "geometry_type": "point",
     "seasons": [2024], "seasons_skipped": [], "in_aoi": True, "warnings": []},
]


def ps_row(plot_id, sector, season, week, ndvi, obs):
    return {"plot_id": plot_id, "sector": sector, "season": season, "week": week,
            "ndvi": ndvi, "obs_count": obs, "built_utc": BUILT}


PS_ROWS = [
    # P1 week 1: two trusted seasons -> mean 0.4
    ps_row("P1", "rainfed", 2023, 1, 0.3, 5),
    ps_row("P1", "rainfed", 2025, 1, 0.5, 4),
    # P1 week 2: only one season has data, and it is thin (obs 1 < min 3)
    ps_row("P1", "rainfed", 2023, 2, 0.2, 1),
    ps_row("P1", "rainfed", 2025, 2, "", 0),
    # P2 week 1: single trusted season
    ps_row("P2", "rainfed", 2025, 1, 0.6, 3),
    # P3 (irrigated): no data anywhere this fixture
]


class PlotAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows = baseline.aggregate_plot_curves(PS_ROWS, PLOTS, BUILT)
        cls.by_key = {(r["plot_id"], r["week"]): r for r in rows}
        cls.rows = rows

    def test_every_plot_week_cell_exists(self):
        import baseline_io
        self.assertEqual(len(self.rows), len(PLOTS) * baseline_io.n_weeks())

    def test_mean_over_seasons_with_data(self):
        r = self.by_key[("P1", 1)]
        self.assertEqual(r["baseline_ndvi"], 0.4)
        self.assertEqual(r["n_seasons_used"], 2)
        self.assertEqual(r["n_seasons_listed"], 3)  # 2 usable + 1 skipped
        self.assertEqual(r["obs_total"], 9)
        self.assertEqual(r["low_confidence"], "no")

    def test_thin_only_week_is_low_confidence_but_keeps_value(self):
        r = self.by_key[("P1", 2)]
        self.assertEqual(r["baseline_ndvi"], 0.2)
        self.assertEqual(r["n_seasons_used"], 1)
        self.assertEqual(r["low_confidence"], "yes")

    def test_no_data_week_is_empty(self):
        r = self.by_key[("P1", 3)]
        self.assertEqual(r["baseline_ndvi"], "")
        self.assertEqual(r["n_seasons_used"], 0)
        self.assertEqual(r["low_confidence"], "yes")


class SectorAggregationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        plot_rows = baseline.aggregate_plot_curves(PS_ROWS, PLOTS, BUILT)
        rows = baseline.aggregate_sector_curves(plot_rows, PLOTS, BUILT)
        cls.by_key = {(r["sector"], r["week"]): r for r in rows}
        cls.rows = rows

    def test_every_sector_week_cell_exists(self):
        import baseline_io
        self.assertEqual({(r["sector"], r["week"]) for r in self.rows},
                         baseline_io.expected_sector_keys())

    def test_mean_over_plot_curves(self):
        r = self.by_key[("rainfed", 1)]
        self.assertEqual(r["baseline_ndvi"], 0.5)  # mean of P1=0.4, P2=0.6
        self.assertEqual(r["n_plots"], 2)
        self.assertEqual(r["n_plot_weeks_with_data"], 2)
        self.assertEqual(r["low_confidence"], "no")

    def test_only_low_confidence_contributors_propagates(self):
        r = self.by_key[("rainfed", 2)]
        self.assertEqual(r["baseline_ndvi"], 0.2)  # P1's thin value
        self.assertEqual(r["n_plot_weeks_with_data"], 1)
        self.assertEqual(r["low_confidence"], "yes")

    def test_sector_with_no_data_has_empty_rows_not_missing_rows(self):
        r = self.by_key[("irrigated", 1)]
        self.assertEqual(r["baseline_ndvi"], "")
        self.assertEqual(r["n_plots"], 1)  # P3 exists, just no data
        self.assertEqual(r["n_plot_weeks_with_data"], 0)
        self.assertEqual(r["low_confidence"], "yes")


if __name__ == "__main__":
    unittest.main()
