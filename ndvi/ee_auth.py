"""
NDVI shared helper - Google Earth Engine authentication and NDVI building blocks.

This module is imported by ndvi/baseline.py and ndvi/current.py (it is NOT a
runnable pipeline step). It centralises:

  - initialize_earth_engine():  headless service-account auth + project-scoped init
  - build_plots_fc():           plot rows -> ee.FeatureCollection (registry
                                polygons / area-derived circles AND monitored
                                farmer point+buffer rows)
  - masked_s2_collection():     cloud-masked Sentinel-2, all bands (exports)
  - masked_ndvi_collection():   a cloud-masked Sentinel-2 NDVI ImageCollection

All Earth Engine settings come from config.py, so nothing here is hardcoded.

Earth Engine is now project-scoped: ee.Initialize(creds, project=...). The service
account must have roles/serviceusage.serviceUsageConsumer + the Earth Engine
"Writer" role, and the Cloud project must be registered for Earth Engine. Auth
mirrors tools/google_sheets_lookup.py: prefer the inline JSON string
(GEE_SERVICE_ACCOUNT_INFO, for CI), fall back to the JSON key file
(GEE_SERVICE_ACCOUNT_JSON, for local use).

Dependency (uncomment in requirements.txt to install):
    python -m pip install earthengine-api
"""

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
from pipeline_utils import PipelineError, retry_call


# Earth Engine + Cloud Platform are both needed for project-scoped init.
EE_SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
]

# Module-level guard so re-importing in the same process does not re-initialise.
_initialized = False


def _import_ee():
    """Import the earthengine-api with a clear message if it is not installed."""
    try:
        return importlib.import_module("ee")
    except ImportError as e:
        raise RuntimeError(
            "Missing dependency: earthengine-api. Install it with:\n"
            "    python -m pip install earthengine-api"
        ) from e


def initialize_earth_engine(step="ee-auth"):
    """
    Authenticate as the service account and initialise Earth Engine.

    Returns the imported, initialised `ee` module. Idempotent within a process.
    `step` labels any auth error with the calling pipeline step.
    """
    global _initialized

    ee = _import_ee()
    if _initialized:
        return ee

    if not config.EE_PROJECT_ID:
        raise PipelineError(
            step, "ee-auth",
            "EE_PROJECT_ID is required: Earth Engine init is project-scoped "
            "(ee.Initialize(credentials, project=EE_PROJECT_ID))",
            "set EE_PROJECT_ID in .env", exit_code=4,
        )

    info = (config.GEE_SERVICE_ACCOUNT_INFO or "").strip()
    key_path = config.GEE_SERVICE_ACCOUNT_JSON

    # Validate the inline secret before importing the heavy Google libraries, so a
    # malformed GEE_SERVICE_ACCOUNT_INFO fails with a clear message.
    account_info = None
    if info:
        try:
            account_info = json.loads(info)
        except json.JSONDecodeError as e:
            raise PipelineError(
                step, "ee-auth",
                "GEE_SERVICE_ACCOUNT_INFO is not valid JSON",
                "it must hold the full service-account key JSON (paste the file's contents)",
                exit_code=4,
            ) from e
    elif key_path is None:
        raise PipelineError(
            step, "ee-auth",
            "no Earth Engine credentials configured",
            "set GEE_SERVICE_ACCOUNT_INFO (key JSON content, for CI) or "
            "GEE_SERVICE_ACCOUNT_JSON (key file path)", exit_code=4,
        )
    elif not key_path.exists():
        raise PipelineError(
            step, "ee-auth",
            f"Earth Engine service-account JSON was not found: {key_path}",
            "fix GEE_SERVICE_ACCOUNT_JSON in .env or place the key file there",
            exit_code=4,
        )

    try:
        service_account = importlib.import_module("google.oauth2.service_account")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google auth dependency. Install it with:\n"
            "    python -m pip install google-auth"
        ) from e

    if account_info is not None:
        credentials = service_account.Credentials.from_service_account_info(
            account_info, scopes=EE_SCOPES
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            str(key_path), scopes=EE_SCOPES
        )

    try:
        ee.Initialize(credentials, project=config.EE_PROJECT_ID)
    except Exception as e:
        raise PipelineError(
            step, "ee-auth", str(e),
            "check that the service account has serviceusage.serviceUsageConsumer "
            "+ the Earth Engine Writer role on EE_PROJECT_ID and that the project "
            "is registered for Earth Engine; see docs/SETUP_CREDENTIALS.md",
            exit_code=4,
        ) from e
    _initialized = True
    return ee


# Substrings that mark an EE error as auth/permission (deterministic - retrying
# cannot help). Matching on message text is admittedly brittle across
# earthengine-api versions, but the safe default is "retry": retries are bounded
# (EE_RETRIES) so a misclassified deterministic error only costs the backoff time.
_NON_RETRYABLE_MARKERS = (
    "permission", "not registered", "caller does not", "unauthorized",
    "not signed up", "invalid_grant",
)


def _is_retryable(exc):
    text = str(exc).lower()
    return not any(marker in text for marker in _NON_RETRYABLE_MARKERS)


def getinfo_with_retry(obj, step, describe):
    """
    obj.getInfo() with bounded exponential-backoff retries.

    Transient EE failures (quota, 429/503, computation timeouts, network errors)
    are retried EE_RETRIES times; auth/permission errors fail fast. Either way
    the caller gets a classified PipelineError, never a raw EE traceback.
    """
    try:
        return retry_call(
            obj.getInfo,
            attempts=config.EE_RETRIES,
            base_delay=config.EE_RETRY_BASE_DELAY,
            describe=describe,
            retryable=_is_retryable,
        )
    except PipelineError:
        raise
    except Exception as e:
        if not _is_retryable(e):
            raise PipelineError(
                step, "ee-auth", f"{describe}: {e}",
                "check the service-account roles / Earth Engine registration for "
                "EE_PROJECT_ID; see docs/SETUP_CREDENTIALS.md", exit_code=4,
            ) from e
        raise PipelineError(
            step, "ee-transient",
            f"{describe} failed after {config.EE_RETRIES} attempts: {e}",
            "re-run later (Earth Engine quota/backend issue); "
            "no partial output was finalized", exit_code=5,
        ) from e


def plot_geometry(ee, plot):
    """
    The ee.Geometry of one plot dict.

    Registry plots (ndvi/registry.py) carry geometry_type "polygon" (a closed
    lon/lat ring in `coordinates`) or "point" (buffered by radius_m, which the
    registry derives from the stated feddan area). Monitored-farmer rows
    (ndvi/farmers.py) have no geometry_type and stay point+buffer.
    """
    if plot.get("geometry_type") == "polygon":
        return ee.Geometry.Polygon([plot["coordinates"]])
    return ee.Geometry.Point(
        [float(plot["lon"]), float(plot["lat"])]
    ).buffer(float(plot["radius_m"]))


def plot_id_of(plot) -> str:
    """The join id of a plot dict: plot_id (registry) or mahsooli_id (farmers)."""
    return plot.get("plot_id") or plot.get("mahsooli_id")


def build_plots_fc(ee, plots):
    """
    Turn plot/farmer rows into an ee.FeatureCollection.

    Accepts both registry plots (polygons or area-derived circles, id plot_id)
    and monitored-farmer rows (points buffered by radius_m, id mahsooli_id).
    Every feature carries a `mahsooli_id` property holding the join id, so
    reduceRegions results join back identically for both kinds.
    """
    features = []
    for p in plots:
        props = {"mahsooli_id": plot_id_of(p)}
        if p.get("sector"):
            props["sector"] = p["sector"]
        features.append(ee.Feature(plot_geometry(ee, p), props))
    return ee.FeatureCollection(features)


def _mask_scl(ee, img):
    """Drop the configured SCL classes (cloud/shadow/cirrus/snow)."""
    scl = img.select("SCL")
    keep = None
    for cls in config.SCL_DROP_CLASSES:
        condition = scl.neq(cls)
        keep = condition if keep is None else keep.And(condition)
    return img.updateMask(keep) if keep is not None else img


def _mask_cloud_score_plus(ee, img):
    """Mask using Google's Cloud Score+ band linked onto the image."""
    band = config.CLOUD_SCORE_PLUS_BAND
    return img.updateMask(img.select(band).gte(config.CLOUD_SCORE_PLUS_MIN))


def masked_s2_collection(ee, region, start_date, end_date):
    """
    Cloud-masked Sentinel-2 ImageCollection (ALL bands) over a date range.

    The shared masking core: SCL (default) or Cloud Score+ depending on
    config.CLOUD_MASK_METHOD. masked_ndvi_collection() maps NDVI on top of
    this for statistics; ndvi/exports.py composites it directly for the raw
    clipped / RGB imagery downloads.
    """
    collection = (
        ee.ImageCollection(config.S2_COLLECTION)
        .filterBounds(region)
        .filterDate(str(start_date), str(end_date))
    )

    use_cloud_score = config.CLOUD_MASK_METHOD == "cloudscore"
    if use_cloud_score:
        # Link the Cloud Score+ band onto each S2 image by system:index.
        csp = ee.ImageCollection(config.CLOUD_SCORE_PLUS_COLLECTION)
        collection = collection.linkCollection(csp, [config.CLOUD_SCORE_PLUS_BAND])

    def mask(img):
        if use_cloud_score:
            return _mask_cloud_score_plus(ee, img)
        return _mask_scl(ee, img)

    return collection.map(mask)


def masked_ndvi_collection(ee, plots, start_date, end_date):
    """
    Build a cloud-masked Sentinel-2 NDVI ImageCollection over a date range.

    NDVI = (NIR - RED) / (NIR + RED) on top of masked_s2_collection(). Returns
    an ImageCollection of single 'NDVI' band images, ready for compositing +
    reduceRegions.
    """
    nir, red = config.NDVI_NIR_BAND, config.NDVI_RED_BAND

    def to_ndvi(img):
        ndvi = img.normalizedDifference([nir, red]).rename("NDVI")
        # normalizedDifference drops metadata; carry the timestamp so downstream
        # date filtering still works.
        return ndvi.set("system:time_start", img.get("system:time_start"))

    return masked_s2_collection(ee, plots.geometry(), start_date, end_date).map(to_ndvi)
