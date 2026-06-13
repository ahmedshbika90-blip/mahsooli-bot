"""
NDVI shared helper - structured per-run log for error traceability (stdlib only).

Every baseline / current / exports run writes a run_log.json into its dated
run folder (data/ndvi/runs/<YYYY-MM-DD>_<kind>/), which the Drive archive then
mirrors. The log captures what a future debugging session needs to reconstruct
the run: parameters, a whitelisted config snapshot (never credentials), the
per-plot statuses, skipped seasons, every artifact produced, and any errors -
so a wrong number in the Sheet can always be traced back to the exact inputs
and settings that produced it.
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
from pipeline_utils import write_json_atomic

# Settings worth snapshotting per run. Deliberately a whitelist: secrets
# (GEE_*, GOOGLE_DRIVE_*, NDVI_SHEET_ID) must never end up in an archived log.
_CONFIG_SNAPSHOT_KEYS = [
    "S2_COLLECTION", "CLOUD_MASK_METHOD", "SCL_DROP_CLASSES",
    "CLOUD_SCORE_PLUS_MIN", "NDVI_SCALE_M", "FARMER_RADIUS_M",
    "SEASON_START_MONTH", "SEASON_START_DAY", "SEASON_END_MONTH",
    "SEASON_END_DAY", "MIN_SEASON_YEAR", "NDVI_WEEK_DAYS", "NDVI_SEASON_WEEKS",
    "BASELINE_MIN_COUNT", "NDVI_CURRENT_WINDOW_DAYS", "NDVI_CURRENT_MIN_COUNT",
    "NDVI_DEVIATION_ALERT_PCT", "NDVI_VEG_FLOOR", "NDVI_ABS_DROP_FLOOR",
    "NDVI_EXPORT_BANDS", "NDVI_EXPORT_BBOX_BUFFER_M", "NDVI_EXPORT_RGB_MAX",
    "NDVI_EXPORT_NDVI_MIN", "NDVI_EXPORT_NDVI_MAX", "AOI_BOXES",
]


def run_dir_for(run_date, kind: str) -> Path:
    """The dated local run folder, e.g. data/ndvi/runs/2026-06-11_cycle."""
    return config.NDVI_RUNS_DIR / f"{run_date.isoformat()}_{kind}"


class RunLog:
    """Collects one run's metadata; .write() saves it atomically as JSON."""

    def __init__(self, step: str, kind: str, run_date):
        self.data = {
            "run": f"{run_date.isoformat()}_{kind}",
            "step": step,
            "kind": kind,
            "run_date": run_date.isoformat(),
            "started_utc": _utc_now(),
            "finished_utc": None,
            "params": {},
            "config": {
                k: _jsonable(getattr(config, k)) for k in _CONFIG_SNAPSHOT_KEYS
            },
            "plots": {},
            "skipped_seasons": [],
            "artifacts": [],
            "errors": [],
        }

    def set_param(self, key, value):
        self.data["params"][key] = _jsonable(value)

    def plot_status(self, plot_id, **fields):
        self.data["plots"].setdefault(plot_id, {}).update(
            {k: _jsonable(v) for k, v in fields.items()}
        )

    def skipped_season(self, plot_id, year, reason):
        self.data["skipped_seasons"].append(
            {"plot_id": plot_id, "season": year, "reason": reason}
        )

    def artifact(self, path, kind, **extra):
        entry = {"file": str(path), "kind": kind}
        entry.update({k: _jsonable(v) for k, v in extra.items()})
        self.data["artifacts"].append(entry)

    def error(self, message):
        self.data["errors"].append(str(message))

    def write(self, run_dir: Path, name: str = "run_log.json") -> Path:
        """
        Finalize and save into `run_dir`/`name`. Returns the path. Re-runs
        that only retry a push/archive pass name="run_log_rerun.json" so they
        never clobber the original run's full log.
        """
        self.data["finished_utc"] = _utc_now()
        path = run_dir / name
        write_json_atomic(path, self.data)
        return path


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _jsonable(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_jsonable(v) for v in value]
    return str(value)
