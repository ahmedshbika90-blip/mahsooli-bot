"""Unit tests for E1.2 baseline export acceptance gates."""

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ndvi"))

import baseline  # noqa: E402
import config  # noqa: E402
from pipeline_utils import PipelineError  # noqa: E402


class RequiredBaselineExportGateTests(unittest.TestCase):
    def setUp(self):
        self._saved = config.NDVI_REQUIRE_EXPORTS

    def tearDown(self):
        config.NDVI_REQUIRE_EXPORTS = self._saved

    def test_required_baseline_export_failures_raise(self):
        config.NDVI_REQUIRE_EXPORTS = True

        with self.assertRaises(PipelineError) as ctx:
            baseline.check_required_baseline_exports(
                failures=["BP003 2023: download failed"],
                missing=["BP004 2025: no cloud-free imagery"],
                run_dir=Path("data/ndvi/runs/2026-06-17_baseline"),
            )

        self.assertEqual(ctx.exception.exit_code, 9)
        self.assertEqual(ctx.exception.cause, "imagery-export")
        self.assertIn("BP003 2023", str(ctx.exception))

    def test_missing_baseline_imagery_alone_does_not_raise(self):
        # Donor plot/seasons with no cloud-free imagery are a warning, not a failure.
        config.NDVI_REQUIRE_EXPORTS = True

        baseline.check_required_baseline_exports(
            failures=[],
            missing=["BP004 2025: no cloud-free imagery"],
            run_dir=Path("data/ndvi/runs/2026-06-17_baseline"),
        )


if __name__ == "__main__":
    unittest.main()
