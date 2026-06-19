"""Unit tests for E1.2 current-cycle export acceptance gates."""

import unittest
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "ndvi"))

import config  # noqa: E402
import current  # noqa: E402
from pipeline_utils import PipelineError  # noqa: E402


class RequiredExportGateTests(unittest.TestCase):
    def setUp(self):
        self._saved = config.NDVI_REQUIRE_EXPORTS

    def tearDown(self):
        config.NDVI_REQUIRE_EXPORTS = self._saved

    def test_required_export_failures_raise_clear_pipeline_error(self):
        config.NDVI_REQUIRE_EXPORTS = True

        with self.assertRaises(PipelineError) as ctx:
            current.check_required_exports(
                export_failures=["M001: timeout"],
                missing_exports=["M002: no cloud-free imagery in this window"],
                run_dir=Path("data/ndvi/runs/2026-06-17_cycle"),
            )

        self.assertEqual(ctx.exception.exit_code, 9)
        self.assertEqual(ctx.exception.cause, "imagery-export")
        self.assertIn("M001: timeout", str(ctx.exception))

    def test_missing_imagery_alone_does_not_raise(self):
        # No cloud-free imagery is normal in-season - a warning, never a failure.
        config.NDVI_REQUIRE_EXPORTS = True

        current.check_required_exports(
            export_failures=[],
            missing_exports=["M002: no cloud-free imagery in this window"],
            run_dir=Path("data/ndvi/runs/2026-06-17_cycle"),
        )

    def test_required_export_gate_can_be_disabled(self):
        config.NDVI_REQUIRE_EXPORTS = False

        current.check_required_exports(
            export_failures=["M001: timeout"],
            missing_exports=["M002: no cloud-free imagery in this window"],
            run_dir=Path("data/ndvi/runs/2026-06-17_cycle"),
        )


if __name__ == "__main__":
    unittest.main()
