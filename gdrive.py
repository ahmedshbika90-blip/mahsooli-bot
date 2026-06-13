"""
Shared Google Drive plumbing - auth, folders, file uploads, run archiving.

Extracted from tools/google_sheets_lookup.py (which now imports from here) so
the NDVI pipeline can mirror its dated run folders (imagery + tables +
run_log.json) to Google Drive for traceability. Stdlib-importable: the Google
client libraries are only imported inside the functions that need them.

Auth (same rules as before the extraction):
  - GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO  key JSON content (CI) - wins when set
  - GOOGLE_DRIVE_OAUTH_CLIENT_JSON     Desktop OAuth client (personal Drive)
  - GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON  key file path (local headless)

IMPORTANT service-account caveat: service accounts have no personal Drive
storage, so they can only create files inside a SHARED DRIVE or rely on the
OAuth-user flow. If GOOGLE_DRIVE_FOLDER is a plain "My Drive" folder, uploads
authenticated as a service account fail with storageQuotaExceeded.
"""

import importlib
import json
import mimetypes
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # repo root
import config
from pipeline_utils import PipelineError

GOOGLE_DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive"]
FOLDER_MIMETYPE = "application/vnd.google-apps.folder"


def resolve_google_drive_folder_id(raw_value: str) -> str:
    """Accept either a full Google Drive folder URL or a raw folder ID."""
    value = (raw_value or "").strip()
    if not value:
        raise ValueError(
            "GOOGLE_DRIVE_FOLDER is empty. Set it to a Google Drive folder ID or full folder URL."
        )

    match = re.search(r"/folders/([A-Za-z0-9_-]+)", value)
    if match:
        return match.group(1)

    if re.fullmatch(r"[A-Za-z0-9_-]{10,}", value):
        return value

    raise ValueError(
        "GOOGLE_DRIVE_FOLDER must be a Google Drive folder ID or full folder URL."
    )


def build_drive_service_from_service_account():
    """
    Build a Drive client authenticated as a service account.

    Prefers GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO (the whole key JSON as a string, for
    CI/GitHub Secrets — no file on disk); falls back to the
    GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON file path for local use.
    """
    info = (config.GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO or "").strip()
    credentials_path = config.GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON
    if not info and credentials_path is None:
        raise ValueError(
            "Neither GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO nor "
            "GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is set."
        )
    if not info and not credentials_path.exists():
        raise FileNotFoundError(
            f"Google Drive service-account JSON was not found: {credentials_path}"
        )

    # Validate the inline secret before importing the heavy Google libraries, so a
    # malformed GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO fails with a clear message.
    account_info = None
    if info:
        try:
            account_info = json.loads(info)
        except json.JSONDecodeError as e:
            raise ValueError(
                "GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO is not valid JSON. It must hold "
                "the full service-account key JSON (paste the file's contents)."
            ) from e

    try:
        service_account = importlib.import_module("google.oauth2.service_account")
        discovery = importlib.import_module("googleapiclient.discovery")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google Drive dependencies. Install them with:\n"
            "    python -m pip install google-api-python-client google-auth"
        ) from e

    if account_info is not None:
        credentials = service_account.Credentials.from_service_account_info(
            account_info,
            scopes=GOOGLE_DRIVE_SCOPES,
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            str(credentials_path),
            scopes=GOOGLE_DRIVE_SCOPES,
        )
    service = discovery.build("drive", "v3", credentials=credentials, cache_discovery=False)
    return service, "service_account"


def build_drive_service_from_oauth_user():
    """Build a Drive client authenticated as the signed-in user."""
    client_path = config.GOOGLE_DRIVE_OAUTH_CLIENT_JSON
    if client_path is None:
        raise ValueError("GOOGLE_DRIVE_OAUTH_CLIENT_JSON is not set.")
    if not client_path.exists():
        raise FileNotFoundError(
            f"Google Drive OAuth client JSON was not found: {client_path}"
        )

    token_path = config.GOOGLE_DRIVE_OAUTH_TOKEN_JSON
    if token_path is None:
        raise ValueError("GOOGLE_DRIVE_OAUTH_TOKEN_JSON could not be resolved.")

    try:
        oauth_credentials = importlib.import_module("google.oauth2.credentials")
        discovery = importlib.import_module("googleapiclient.discovery")
        requests_module = importlib.import_module("google.auth.transport.requests")
        oauth_flow = importlib.import_module("google_auth_oauthlib.flow")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google Drive OAuth dependencies. Install them with:\n"
            "    python -m pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from e

    credentials = None
    if token_path.exists():
        credentials = oauth_credentials.Credentials.from_authorized_user_file(
            str(token_path),
            GOOGLE_DRIVE_SCOPES,
        )

    if credentials is None or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(requests_module.Request())
        else:
            flow = oauth_flow.InstalledAppFlow.from_client_secrets_file(
                str(client_path),
                GOOGLE_DRIVE_SCOPES,
            )
            credentials = flow.run_local_server(port=0, open_browser=True)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(credentials.to_json(), encoding="utf-8")

    service = discovery.build("drive", "v3", credentials=credentials, cache_discovery=False)
    return service, "oauth_user"


def build_drive_service():
    """Pick the simplest available Google auth flow for Drive uploads."""
    # A service-account key passed as raw JSON content is the CI/headless signal;
    # it wins so a deployed run never falls into the browser-based OAuth flow.
    if config.GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO.strip():
        return build_drive_service_from_service_account()

    if config.GOOGLE_DRIVE_OAUTH_CLIENT_JSON is not None:
        return build_drive_service_from_oauth_user()

    if config.GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON is not None:
        return build_drive_service_from_service_account()

    raise ValueError(
        "Google Drive upload is enabled, but no auth JSON is configured.\n"
        "Set GOOGLE_DRIVE_OAUTH_CLIENT_JSON to a Desktop OAuth client JSON for your own Drive,\n"
        "set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON to a service-account key file, or\n"
        "set GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO to the service-account key JSON content (CI)."
    )


def ensure_folder(service, parent_id: str, name: str) -> str:
    """
    Return the id of folder `name` under `parent_id`, creating it if absent.
    Idempotent, so re-archived runs reuse their folder instead of duplicating.
    """
    safe_name = name.replace("'", "\\'")
    files = service.files().list(
        q=(f"name = '{safe_name}' and '{parent_id}' in parents and "
           f"mimeType = '{FOLDER_MIMETYPE}' and trashed = false"),
        spaces="drive",
        fields="files(id)",
        pageSize=1,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute().get("files", [])
    if files:
        return files[0]["id"]

    created = service.files().create(
        body={"name": name, "parents": [parent_id], "mimeType": FOLDER_MIMETYPE},
        fields="id",
        supportsAllDrives=True,
    ).execute()
    return created["id"]


def upload_file(service, folder_id: str, path: Path) -> dict:
    """
    Upload one file into a Drive folder as-is (no Google-format conversion).
    A file of the same name in the folder is updated in place (re-run
    idempotency); otherwise a new file is created. Returns {id, name, action}.
    """
    drive_http = importlib.import_module("googleapiclient.http")

    mimetype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    media = drive_http.MediaFileUpload(str(path), mimetype=mimetype, resumable=False)

    safe_name = path.name.replace("'", "\\'")
    existing = service.files().list(
        q=f"name = '{safe_name}' and '{folder_id}' in parents and trashed = false",
        spaces="drive",
        fields="files(id)",
        pageSize=1,
        includeItemsFromAllDrives=True,
        supportsAllDrives=True,
    ).execute().get("files", [])

    if existing:
        result = service.files().update(
            fileId=existing[0]["id"],
            media_body=media,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        action = "updated"
    else:
        result = service.files().create(
            body={"name": path.name, "parents": [folder_id]},
            media_body=media,
            fields="id, name",
            supportsAllDrives=True,
        ).execute()
        action = "created"
    return {"id": result["id"], "name": result["name"], "action": action}


def archive_run_dir(run_dir: Path, step: str) -> int:
    """
    Mirror a local run folder (data/ndvi/runs/<date>_<kind>/) to
    GOOGLE_DRIVE_FOLDER / NDVI_DRIVE_ARCHIVE_ROOT / <folder name>, including
    one level of subfolders (imagery/).

    Local artifacts are already finalized when this runs, so a Drive failure
    is reported as a distinct, classified error (exit code 7) and never costs
    any data - re-run with --archive to retry the upload only.
    """
    print()
    print(f"Archiving run folder to Google Drive: {run_dir.name}")
    try:
        service, auth_mode = build_drive_service()
        root_id = resolve_google_drive_folder_id(config.GOOGLE_DRIVE_FOLDER)
        archive_root_id = ensure_folder(service, root_id, config.NDVI_DRIVE_ARCHIVE_ROOT)
        run_folder_id = ensure_folder(service, archive_root_id, run_dir.name)

        uploaded = 0
        for path in sorted(run_dir.iterdir()):
            if path.is_file():
                info = upload_file(service, run_folder_id, path)
                print(f"  {info['action']}: {path.name}")
                uploaded += 1
            elif path.is_dir():
                sub_id = ensure_folder(service, run_folder_id, path.name)
                for sub in sorted(path.iterdir()):
                    if sub.is_file():
                        info = upload_file(service, sub_id, sub)
                        print(f"  {info['action']}: {path.name}/{sub.name}")
                        uploaded += 1
        print(f"  Archived {uploaded} file(s) (auth: {auth_mode}) under "
              f"{config.NDVI_DRIVE_ARCHIVE_ROOT}/{run_dir.name}")
        return uploaded
    except PipelineError:
        raise
    except Exception as e:
        hint = (
            "check GOOGLE_DRIVE_FOLDER access; note a service account can only "
            "write into a SHARED DRIVE (storageQuotaExceeded on My Drive) - the "
            f"local artifacts in {run_dir} are intact, re-run with --archive to retry"
        )
        raise PipelineError(step, "drive-upload", str(e), hint, exit_code=7) from e
