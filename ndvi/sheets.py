"""
NDVI shared helper - write the NDVI log into an existing Google Sheet.

Imported by ndvi/current.py (not a runnable step). Uses the raw Google Sheets
API v4 (no gspread), reusing the same service-account plumbing as
tools/google_sheets_lookup.py - the only addition is the Sheets scope.

Why a pre-existing, human-created Sheet (NDVI_SHEET_ID):
  Service accounts have no Drive storage, so they cannot create/own a Sheet. They
  CAN write into one a human owns and has shared with them (Editor). So the
  workbook must already exist and be shared with the service-account email; this
  helper only ever opens it by ID and appends - it never calls create().

Idempotency:
  Rows are upserted by the (Mahsooli ID, Date) key. read_existing_keys() returns
  the keys already present; the current step appends only the genuinely new rows,
  so re-runs never duplicate a cycle.

Dependencies (uncomment in requirements.txt to install):
    python -m pip install google-api-python-client google-auth
"""

import importlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config


SHEETS_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def build_sheets_service():
    """
    Build a Sheets v4 client authenticated as the service account.

    Prefers GEE_SERVICE_ACCOUNT_INFO (key JSON content, for CI); falls back to the
    GEE_SERVICE_ACCOUNT_JSON file path for local use. The same service account is
    reused for Earth Engine and Sheets.
    """
    info = (config.GEE_SERVICE_ACCOUNT_INFO or "").strip()
    key_path = config.GEE_SERVICE_ACCOUNT_JSON

    if not info and key_path is None:
        raise ValueError(
            "Neither GEE_SERVICE_ACCOUNT_INFO nor GEE_SERVICE_ACCOUNT_JSON is set; "
            "cannot authenticate to Google Sheets."
        )
    if not info and not key_path.exists():
        raise FileNotFoundError(
            f"Service-account JSON for Sheets was not found: {key_path}"
        )

    account_info = None
    if info:
        try:
            account_info = json.loads(info)
        except json.JSONDecodeError as e:
            raise ValueError(
                "GEE_SERVICE_ACCOUNT_INFO is not valid JSON (full key file contents)."
            ) from e

    try:
        service_account = importlib.import_module("google.oauth2.service_account")
        discovery = importlib.import_module("googleapiclient.discovery")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google Sheets dependencies. Install them with:\n"
            "    python -m pip install google-api-python-client google-auth"
        ) from e

    if account_info is not None:
        credentials = service_account.Credentials.from_service_account_info(
            account_info, scopes=SHEETS_SCOPES
        )
    else:
        credentials = service_account.Credentials.from_service_account_file(
            str(key_path), scopes=SHEETS_SCOPES
        )

    return discovery.build("sheets", "v4", credentials=credentials, cache_discovery=False)


def ensure_tab_and_header(service, spreadsheet_id: str, tab: str, header: list):
    """Create the tab if missing and write the header row once."""
    meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
    titles = [s["properties"]["title"] for s in meta.get("sheets", [])]

    if tab not in titles:
        service.spreadsheets().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body={"requests": [{"addSheet": {"properties": {"title": tab}}}]},
        ).execute()

    # Write the header only if A1 is empty (don't clobber an existing header).
    first_row = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{tab}!A1:A1")
        .execute()
        .get("values", [])
    )
    if not first_row:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"{tab}!A1",
            valueInputOption="RAW",
            body={"values": [header]},
        ).execute()


def read_existing_keys(service, spreadsheet_id: str, tab: str, id_col=0, date_col=1) -> set:
    """Return the set of (id, date) keys already present (header row skipped)."""
    resp = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range=f"{tab}!A2:B")
        .execute()
    )
    keys = set()
    for row in resp.get("values", []):
        if len(row) > max(id_col, date_col):
            keys.add((str(row[id_col]).strip(), str(row[date_col]).strip()))
    return keys


def append_rows(service, spreadsheet_id: str, tab: str, rows: list):
    """Append rows below the existing table (never overwrites)."""
    if not rows:
        return 0
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"{tab}!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": rows},
    ).execute()
    return len(rows)


def overwrite_tab(service, spreadsheet_id: str, tab: str, header: list, rows: list):
    """
    Clear the tab and rewrite header + rows.

    For snapshot tables (e.g. Sector_Baseline) that are REPLACED on each push,
    unlike the append-only NDVI_Log. The NDVI_Log tab itself must never go
    through this - its history is the deliverable.
    """
    ensure_tab_and_header(service, spreadsheet_id, tab, header)
    service.spreadsheets().values().clear(
        spreadsheetId=spreadsheet_id, range=tab
    ).execute()
    service.spreadsheets().values().update(
        spreadsheetId=spreadsheet_id,
        range=f"{tab}!A1",
        valueInputOption="RAW",
        body={"values": [header] + rows},
    ).execute()
    return len(rows)
