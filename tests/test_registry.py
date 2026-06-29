"""Unit tests for ndvi/registry.py parsing + geometry validation (no EE, no network).

Run:  python -m unittest discover tests
"""

import sys
import unittest
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ndvi"))
import config  # noqa: E402
import registry  # noqa: E402


class DmsTests(unittest.TestCase):
    def test_mohamed_ahmed_plot(self):
        # 13deg59'45"N 36deg16'07"E from the client sheet.
        self.assertAlmostEqual(registry.parse_dms("13°59'45\"N"), 13.9958333, places=6)
        self.assertAlmostEqual(registry.parse_dms("36°16'07\"E"), 36.2686111, places=6)

    def test_fawaz_plot_with_decimal_seconds(self):
        # 15deg07'55.9"N 35deg41'56.5"E (New Halfa).
        self.assertAlmostEqual(registry.parse_dms("15°07'55.9\"N"), 15.1321944, places=6)
        self.assertAlmostEqual(registry.parse_dms("35°41'56.5\"E"), 35.6990278, places=6)

    def test_deg_spelling_and_hemispheres(self):
        self.assertAlmostEqual(registry.parse_dms("13deg59'45\"N"), 13.9958333, places=6)
        self.assertAlmostEqual(registry.parse_dms("13°59'45\"S"), -13.9958333, places=6)

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            registry.parse_dms("Faras West")

    def test_parse_coordinate_accepts_decimal(self):
        self.assertEqual(registry.parse_coordinate("15.1321944"), 15.1321944)


class WktTests(unittest.TestCase):
    def test_parses_and_keeps_closed_ring(self):
        ring = registry.parse_wkt_polygon(
            "POLYGON((35.0 13.0, 35.1 13.0, 35.1 13.1, 35.0 13.0))")
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 4)

    def test_auto_closes_open_ring(self):
        ring = registry.parse_wkt_polygon("POLYGON((35.0 13.0, 35.1 13.0, 35.1 13.1))")
        self.assertEqual(ring[0], ring[-1])
        self.assertEqual(len(ring), 4)

    def test_rejects_degenerate_ring(self):
        with self.assertRaises(ValueError):
            registry.parse_wkt_polygon("POLYGON((35.0 13.0, 35.1 13.0))")

    def test_rejects_non_polygon(self):
        with self.assertRaises(ValueError):
            registry.parse_wkt_polygon("POINT(35.0 13.0)")


class GeometryChecks(unittest.TestCase):
    def test_simple_square_does_not_self_intersect(self):
        ring = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]]
        self.assertFalse(registry.ring_self_intersects(ring))

    def test_bow_tie_self_intersects(self):
        ring = [[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]
        self.assertTrue(registry.ring_self_intersects(ring))

    def test_concave_ring_is_fine(self):
        ring = [[0, 0], [2, 0], [2, 2], [1, 0.5], [0, 2], [0, 0]]
        self.assertFalse(registry.ring_self_intersects(ring))

    def test_shoelace_area_of_known_square(self):
        # ~1.11 km x ~1.09 km square at 13 deg N.
        ring = [[35.0, 13.0], [35.01, 13.0], [35.01, 13.01], [35.0, 13.01], [35.0, 13.0]]
        area = registry.ring_area_m2(ring)
        self.assertAlmostEqual(area, 111_320 * 0.01 * 0.974370 * 110_540 * 0.01,
                               delta=area * 0.01)


class RealRegistryTests(unittest.TestCase):
    """Load the actual committed registry the pipeline will run with."""

    @classmethod
    def setUpClass(cls):
        cls.plots = registry.load_registry(
            REPO_ROOT / "data" / "farmers" / "baseline_plots.csv",
            today=date(2026, 6, 11),
        )
        cls.by_id = {p["plot_id"]: p for p in cls.plots}

    def test_eight_plots_two_sectors(self):
        self.assertEqual(len(self.plots), 8)
        sectors = {p["sector"] for p in self.plots}
        self.assertEqual(sectors, {"rainfed", "irrigated"})
        self.assertEqual(self.by_id["BP008"]["sector"], "irrigated")

    def test_bahaa_pre_s2_seasons_skipped(self):
        bp003 = self.by_id["BP003"]
        self.assertEqual(bp003["seasons"], [2019, 2021, 2023, 2025])
        self.assertEqual([y for y, _ in bp003["seasons_skipped"]], [2013, 2015, 2017])

    def test_point_plot_radii_derived_from_feddan(self):
        self.assertAlmostEqual(self.by_id["BP007"]["radius_m"], 1066.0, places=1)
        self.assertAlmostEqual(self.by_id["BP008"]["radius_m"], 115.6, places=1)

    def test_polygons_have_closed_rings(self):
        for p in self.plots:
            if p["geometry_type"] == "polygon":
                self.assertEqual(p["coordinates"][0], p["coordinates"][-1],
                                 f"{p['plot_id']} ring not closed")
                self.assertGreaterEqual(len(p["coordinates"]), 4)

    def test_all_plots_inside_sector_aoi(self):
        # The sector AOI boxes were sized around exactly these plots, so every
        # one must be inside (incl. Bahaa at 12.8 and New Halfa at 15.13).
        for p in self.plots:
            self.assertTrue(p["in_aoi"], f"{p['plot_id']} unexpectedly outside AOI")

    def test_dms_points_converted(self):
        self.assertAlmostEqual(self.by_id["BP007"]["lat"], 13.9958333, places=6)
        self.assertAlmostEqual(self.by_id["BP007"]["lon"], 36.2686111, places=6)
        self.assertAlmostEqual(self.by_id["BP008"]["lat"], 15.1321944, places=6)
        self.assertAlmostEqual(self.by_id["BP008"]["lon"], 35.6990278, places=6)


class PolygonVertexRangeTests(unittest.TestCase):
    """A WKT vertex outside lat/lon range must fail at parse, not inside EE."""

    def _row(self, wkt):
        return {"plot_id": "BPX", "sector": "rainfed", "geometry_type": "polygon",
                "geometry_wkt": wkt, "seasons": "2023"}

    def test_rejects_out_of_range_vertex(self):
        from pipeline_utils import PipelineError
        bad = "POLYGON((35.0 13.0, 35.1 13.0, 35.1 95.0, 35.0 13.0))"  # lat 95
        with self.assertRaises(PipelineError) as cm:
            registry._normalize_row(self._row(bad), line_no=2, today=date(2026, 6, 11))
        self.assertIn("out of range", str(cm.exception))

    def test_accepts_in_range_vertex(self):
        good = "POLYGON((35.0 13.0, 35.1 13.0, 35.1 13.1, 35.0 13.0))"
        plot = registry._normalize_row(self._row(good), line_no=2, today=date(2026, 6, 11))
        self.assertEqual(plot["geometry_type"], "polygon")


if __name__ == "__main__":
    unittest.main()
