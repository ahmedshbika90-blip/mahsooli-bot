"""
Shared Google Cloud Storage plumbing - auth and run-folder archiving.

The NDVI pipeline mirrors its dated run folders (imagery + tables + run_log.json)
to a GCS bucket for traceability.
Stdlib-importable: the google-cloud-storage client library is only imported
inside the functions that need it, so a plain pipeline run never imports it.

Auth (reuses the Earth Engine service account - same GCP project):
  - GCS_SERVICE_ACCOUNT_INFO  key JSON content (CI) - wins when set
  - GCS_SERVICE_ACCOUNT_JSON  key file path (local headless)
  - falls back to GEE_SERVICE_ACCOUNT_INFO / GEE_SERVICE_ACCOUNT_JSON

The service account needs roles/storage.objectAdmin on GCS_BUCKET (see
docs/SETUP_CREDENTIALS.md). Because the bucket lives in the same Cloud project as
Earth Engine, no separate credential is required - leave the GCS_* vars unset and
the EE credentials are used.
"""

import importlib
import json
import mimetypes
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # repo root
import config
from pipeline_utils import PipelineError

# Read/write scope is enough to create and overwrite objects; no bucket admin.
GCS_SCOPES = ["https://www.googleapis.com/auth/devstorage.read_write"]


def build_storage_client():
    """
    Build a google.cloud.storage.Client authenticated as a service account.

    Prefers GCS_SERVICE_ACCOUNT_INFO (the whole key JSON as a string, for
    CI/GitHub Secrets - no file on disk), then GCS_SERVICE_ACCOUNT_JSON (a key
    file path), then falls back to the Earth Engine credentials
    (GEE_SERVICE_ACCOUNT_INFO / GEE_SERVICE_ACCOUNT_JSON) since the bucket lives
    in the same Cloud project. Returns (client, auth_mode).
    """
    info = (config.GCS_SERVICE_ACCOUNT_INFO or config.GEE_SERVICE_ACCOUNT_INFO or "").strip()
    key_path = config.GCS_SERVICE_ACCOUNT_JSON or config.GEE_SERVICE_ACCOUNT_JSON

    if not info and key_path is None:
        raise ValueError(
            "No GCS credentials configured. Set GCS_SERVICE_ACCOUNT_INFO "
            "(key JSON content, for CI) or GCS_SERVICE_ACCOUNT_JSON (key file "
            "path), or configure the Earth Engine credentials "
            "(GEE_SERVICE_ACCOUNT_INFO / GEE_SERVICE_ACCOUNT_JSON), which GCS reuses."
        )
    if not info and not key_path.exists():
        raise FileNotFoundError(
            f"GCS service-account JSON was not found: {key_path}"
        )

    # Validate the inline secret before importing the heavy Google libraries, so a
    # malformed key JSON fails with a clear message (mirrors ndvi/ee_auth.py).
    account_info = None
    if info:
        try:
            account_info = json.loads(info)
        except json.JSONDecodeError as e:
            raise ValueError(
                "GCS service-account key is not valid JSON. It must hold the "
                "full service-account key JSON (paste the file's contents)."
            ) from e

    try:
        service_account = importlib.import_module("google.oauth2.service_account")
        storage = importlib.import_module("google.cloud.storage")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google Cloud Storage dependency. Install it with:\n"
            "    python -m pip install google-cloud-storage"
        ) from e

    if account_info is not None:
        credentials = service_account.Credentials.from_service_account_info(
            account_info, scopes=GCS_SCOPES
        )
        project = account_info.get("project_id")
    else:
        credentials = service_account.Credentials.from_service_account_file(
            str(key_path), scopes=GCS_SCOPES
        )
        project = getattr(credentials, "project_id", None)

    client = storage.Client(
        project=config.EE_PROJECT_ID or project,
        credentials=credentials,
    )
    return client, "service_account"


def _blob_name(prefix: str, run_dir_name: str, rel_path: Path) -> str:
    """Object key for one archived file - always POSIX separators."""
    parts = [p for p in (prefix, run_dir_name, rel_path.as_posix()) if p]
    return "/".join(parts)


def _upload_one(bucket, blob_name: str, path: Path) -> str:
    """
    Upload one local file to bucket/blob_name. Idempotent: skip when an object of
    the same size already exists, unless config.GCS_OVERWRITE is set. Returns the
    action taken ("uploaded" or "skipped").
    """
    blob = bucket.blob(blob_name)
    if not config.GCS_OVERWRITE:
        existing = bucket.get_blob(blob_name)
        if existing is not None and existing.size == path.stat().st_size:
            return "skipped"

    content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    blob.upload_from_filename(str(path), content_type=content_type)
    return "uploaded"


def date_first_dest(date_str: str, group: str) -> str:
    """
    Date-first destination prefix inside the bucket so every epic's outputs are
    classified by the day they were produced:
        [<GCS_DATA_PREFIX>/]<YYYY-MM-DD>/<group>
    e.g. "2026-06-18/e1.1-chirps", "2026-06-18/e1.2-baseline", "2026-06-18/e1.3-pilot".
    GCS_DATA_PREFIX is normally empty (bucket root); set it to nest everything
    under one folder if the bucket is shared with other data.
    """
    parts = [p for p in ((config.GCS_DATA_PREFIX or "").strip("/"), date_str, group) if p]
    return "/".join(parts)


def _upload_blobs(items, step, *, dest_label: str, cause: str) -> int:
    """
    Upload a list of (blob_name, local_path) pairs to GCS_BUCKET. Shared core for
    every archiver: validates the bucket, authenticates once, uploads each blob
    idempotently, and classifies any failure as a retryable PipelineError (the
    local artifacts are always intact). Returns the number of files uploaded.
    """
    if not (config.GCS_BUCKET or "").strip():
        raise PipelineError(
            step, "gcs-config",
            "GCS_BUCKET is not set",
            "set GCS_BUCKET to the target bucket; the local artifacts are intact, "
            "re-run with archiving enabled to retry the upload only",
            exit_code=7,
        )

    print(f"Archiving to gs://{config.GCS_BUCKET}/{dest_label}")
    try:
        client, auth_mode = build_storage_client()
        bucket = client.bucket(config.GCS_BUCKET)

        uploaded = 0
        for blob_name, path in items:
            action = _upload_one(bucket, blob_name, path)
            print(f"  {action}: {blob_name}")
            if action == "uploaded":
                uploaded += 1
        print(f"  Archived {uploaded} file(s) (auth: {auth_mode}) under "
              f"gs://{config.GCS_BUCKET}/{dest_label}")
        return uploaded
    except PipelineError:
        raise
    except Exception as e:
        hint = (
            f"check that bucket '{config.GCS_BUCKET}' exists and the service "
            "account has roles/storage.objectAdmin on it; the local artifacts are "
            "intact, re-run with archiving enabled to retry the upload only"
        )
        raise PipelineError(step, cause, str(e), hint, exit_code=7) from e


def archive_run_dir_to_gcs(run_dir: Path, step: str) -> int:
    """
    Mirror a local E1.2 run folder (data/ndvi/runs/<date>_<kind>/) to the
    date-first archive gs://GCS_BUCKET/<date>/e1.2-<kind>/, including nested
    subfolders (imagery/). Returns the number of files uploaded.

    Local artifacts are already finalized when this runs, so a GCS failure is
    reported as a distinct, classified error and never costs any data - re-run
    with --archive to retry the upload only.
    """
    print()
    date_str, _, kind = run_dir.name.partition("_")  # "2026-06-18_baseline"
    dest = date_first_dest(date_str, f"e1.2-{kind or 'run'}")

    items = []
    # Walk the whole run folder at any depth so nested imagery is never silently
    # dropped; each blob key mirrors the file's path under run_dir.
    for path in sorted(run_dir.rglob("*")):
        if path.is_file():
            rel = path.relative_to(run_dir)
            items.append((f"{dest}/{rel.as_posix()}", path))
    return _upload_blobs(items, step, dest_label=dest, cause="gcs-upload")


def upload_files_to_gcs(paths, dest_prefix: str, step: str) -> int:
    """
    Archive an explicit list of local deliverables to gs://GCS_BUCKET/<dest_prefix>/.
    Each entry may be a file (uploaded as <dest_prefix>/<name>) or a directory
    (walked recursively, preserving its own name and inner structure, e.g.
    <dest_prefix>/03_seasonal_totals/2014/file.tif). Missing paths are skipped.
    Used by the E1.1 (CHIRPS) and E1.3 (pilot-check) steps, which have no run
    folder. Idempotent + fail-graceful. Returns the number of files uploaded.
    """
    print()
    items = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.is_file():
                    rel = f.relative_to(p.parent)  # keep the dir's own name
                    items.append((f"{dest_prefix}/{rel.as_posix()}", f))
        elif p.is_file():
            items.append((f"{dest_prefix}/{p.name}", p))
        # silently skip anything that does not exist
    if not items:
        print(f"No files to archive to gs://{config.GCS_BUCKET or '<bucket>'}/{dest_prefix}")
        return 0
    return _upload_blobs(items, step, dest_label=dest_prefix, cause="gcs-upload")


def mirror_ndvi_tiffs_to_gcs(run_dir: Path, kind: str, step: str) -> int:
    """
    Copy just the NDVI GeoTIFFs from run_dir/imagery into a dedicated, browsable
    GCS folder so clients can find them without digging through the full run
    archive:
        gs://GCS_BUCKET/NDVI_TIFF_PREFIX/<kind>/<run-date>/<file>_ndvi.tif

    kind is "baseline" or "current"; the run date is taken from the run folder
    name (data/ndvi/runs/<date>_<kind>/). Returns the number of files uploaded.
    Idempotent (skips objects of unchanged size) and fail-graceful.
    """
    print()
    prefix = config.NDVI_TIFF_PREFIX
    date_str = run_dir.name.split("_", 1)[0]  # "2026-06-18_baseline" -> "2026-06-18"
    dest = f"{prefix}/{kind}/{date_str}"
    tiffs = sorted((run_dir / "imagery").glob("*_ndvi.tif"))
    if not tiffs:
        print(f"NDVI GeoTIFF folder: no *_ndvi.tif under {run_dir / 'imagery'} "
              f"- nothing to mirror to gs://{config.GCS_BUCKET or '<bucket>'}/{dest}")
        return 0
    items = [(f"{dest}/{p.name}", p) for p in tiffs]
    return _upload_blobs(items, step, dest_label=dest, cause="gcs-ndvi-mirror")
