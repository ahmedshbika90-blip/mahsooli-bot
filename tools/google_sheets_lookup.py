"""
Create ONE Excel workbook with a working VLOOKUP demo, and optionally publish
it as a live Google Sheet (standalone helper).

This version is made to be robust in Excel and Google Sheets:

  - Sheet 1: score_lookup
      grid_key, score_1_10

  - Sheet 2: farmers_demo
      farmer_id, lat, lon, grid_key, rainfall_score_vlookup, expected_score_python_check

Important:
  The grid_key in column D is written as a real value, not as a formula.
  The VLOOKUP in column E is the working formula demonstration.

Why:
  Some Excel installs do not immediately calculate formulas written by openpyxl,
  or they repair the workbook and leave formula cells blank. If D is blank,
  VLOOKUP returns #N/A. Writing D as a value makes the demo reliable.
  (Google Sheets recalculates VLOOKUP on open, so the published Sheet always
  shows live results.)

Output:
    data/05_tables/Mahala_VLOOKUP.xlsx       (always written locally)
    On upload, a live Google Sheet at https://docs.google.com/spreadsheets/...

Run:
  python tools/google_sheets_lookup.py
    python tools/google_sheets_lookup.py --upload-google-drive

Dependency:
  python -m pip install openpyxl

Optional Google Drive upload (publishes a NATIVE Google Sheet, not a raw .xlsx):
        - Easiest for a personal Drive folder: set GOOGLE_DRIVE_OAUTH_CLIENT_JSON
            to a Desktop OAuth client JSON and sign in once in the browser.
        - Alternative for automation: set GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON to a
            service-account JSON key and share the target folder with that email.
            NOTE: service accounts have no personal Drive storage, so creating a
            Sheet in a normal "My Drive" folder fails with a storage-quota error;
            use a Shared Drive (or the OAuth-user flow) for that case.
    - Pass --upload-google-drive or set GOOGLE_DRIVE_UPLOAD=true.

The .xlsx is uploaded with its target mimeType set to a Google Sheet, so Drive
imports and converts it on the fly. The result lives at docs.google.com and is
re-imported in place on later runs (matched by name + appProperties marker, so
there are no duplicates).

Additional upload dependencies:
        python -m pip install google-api-python-client google-auth google-auth-oauthlib
"""

import argparse
import csv
import importlib
import sys
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config
from gdrive import (  # shared Drive plumbing (moved out of this tool)
    build_drive_service,
    resolve_google_drive_folder_id,
)


try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError as e:
    raise SystemExit(
        "Missing dependency: openpyxl\n"
        "Install it with:\n"
        "    python -m pip install openpyxl\n"
    ) from e


LOOKUP_SHEET_NAME = "score_lookup"
DEMO_SHEET_NAME = "farmers_demo"
METHODOLOGY_SHEET_NAME = "methodology"

PROCESSING_DATE = date.today().isoformat()

BASE_DOC_NAME = "Mahsooli_CHIRPS_v2_RainfallLookup_Gedaref_2014-2024"

OUT_XLSX = config.TABLE_DIR / f"{BASE_DOC_NAME}_processed_{PROCESSING_DATE}.xlsx"

# Name of the published Google Sheet. A native Sheet has no .xlsx extension.
DRIVE_DOC_NAME = f"{BASE_DOC_NAME}_processed_{PROCESSING_DATE}"
# appProperties marker so we can re-find and update the same Sheet regardless of
# its name/extension (a name-only match breaks once Drive converts to a Sheet).
DRIVE_APP_TAG_KEY = "mahsooli_artifact"
DRIVE_APP_TAG_VALUE = "mahala_vlookup"

DEMO_SAMPLE_COUNT = 5
# mimeType of the local file we upload as the request body...
XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
# ...and the target mimeType that tells Drive to convert it to a native Sheet.
GOOGLE_SHEETS_MIMETYPE = "application/vnd.google-apps.spreadsheet"


def choose_output_workbook_path(preferred_path: Path) -> Path:
    """
    Pick a writable output path.

    If today's workbook is already open in Excel, Windows may lock it for writes.
    In that case, save to a timestamp-suffixed sibling file instead of failing
    before the Google Drive upload step.
    """
    if not preferred_path.exists():
        return preferred_path

    try:
        with open(preferred_path, "ab"):
            pass
        return preferred_path
    except PermissionError:
        timestamp = datetime.now().strftime("%H%M%S")
        return preferred_path.with_name(
            f"{preferred_path.stem}_{timestamp}{preferred_path.suffix}"
        )


def parse_args():
    """CLI flags for optional post-processing actions."""
    parser = argparse.ArgumentParser(
        description="Create the Excel workbook and optionally upload it to Google Drive."
    )
    parser.add_argument(
        "--upload-google-drive",
        action="store_true",
        help="Upload the generated workbook to the configured Google Drive folder.",
    )
    return parser.parse_args()


# resolve_google_drive_folder_id / build_drive_service* now live in gdrive.py
# (imported above) so the NDVI run-archiver shares the exact same auth rules.


def find_existing_sheet(service, folder_id: str):
    """
    Find a previously published Sheet to update in place.

    Matched by the appProperties marker (survives the .xlsx -> Sheet name
    change), with a name fallback for Sheets created before the marker existed.
    Returns the file id, or None.
    """
    queries = [
        # Primary: our marker, regardless of name/extension.
        (
            f"appProperties has {{ key='{DRIVE_APP_TAG_KEY}' and "
            f"value='{DRIVE_APP_TAG_VALUE}' }} and "
            f"'{folder_id}' in parents and trashed = false"
        ),
        # Fallback: legacy artifacts named by this script (Sheet or raw .xlsx).
        (
            f"(name = '{DRIVE_DOC_NAME}' or name = '{DRIVE_DOC_NAME}.xlsx') and "
            f"'{folder_id}' in parents and trashed = false"
        ),
    ]

    for query in queries:
        files = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, webViewLink)",
            pageSize=1,
            includeItemsFromAllDrives=True,
            supportsAllDrives=True,
        ).execute().get("files", [])
        if files:
            return files[0]["id"]

    return None


def upload_workbook_to_google_drive(workbook_path: Path):
    """
    Publishes the workbook as a NATIVE Google Sheet in the configured folder.

    The local .xlsx is uploaded as the request body, but the target mimeType is
    set to a Google Sheet, so Drive converts it on import. The result is a live
    spreadsheet at docs.google.com, not a raw .xlsx download. Re-runs update the
    same Sheet in place (matched by the appProperties marker).
    """
    folder_id = resolve_google_drive_folder_id(config.GOOGLE_DRIVE_FOLDER)

    try:
        drive_errors = importlib.import_module("googleapiclient.errors")
        drive_http = importlib.import_module("googleapiclient.http")
    except ImportError as e:
        raise RuntimeError(
            "Missing Google Drive dependencies. Install them with:\n"
            "    python -m pip install google-api-python-client google-auth google-auth-oauthlib"
        ) from e

    service, auth_mode = build_drive_service()
    media = drive_http.MediaFileUpload(
        str(workbook_path),
        mimetype=XLSX_MIMETYPE,
        resumable=False,
    )

    try:
        existing_id = find_existing_sheet(service, folder_id)

        if existing_id:
            # Re-import the xlsx into the existing Sheet. No mimeType in the body:
            # the file is already a Sheet and Drive re-converts the uploaded media.
            result = service.files().update(
                fileId=existing_id,
                body={
                    "name": DRIVE_DOC_NAME,
                    "appProperties": {DRIVE_APP_TAG_KEY: DRIVE_APP_TAG_VALUE},
                },
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            ).execute()
            action = "updated"
        else:
            # Target mimeType = Google Sheet tells Drive to convert on import.
            result = service.files().create(
                body={
                    "name": DRIVE_DOC_NAME,
                    "parents": [folder_id],
                    "mimeType": GOOGLE_SHEETS_MIMETYPE,
                    "appProperties": {DRIVE_APP_TAG_KEY: DRIVE_APP_TAG_VALUE},
                },
                media_body=media,
                fields="id, name, webViewLink",
                supportsAllDrives=True,
            ).execute()
            action = "uploaded"
    except drive_errors.HttpError as e:
        auth_hint = ""
        if auth_mode == "service_account":
            auth_hint = (
                " Note: service accounts have no personal Drive storage, so creating a "
                "Sheet in a normal 'My Drive' folder fails. Use a Shared Drive, or "
                "download your Desktop OAuth client JSON and set GOOGLE_DRIVE_OAUTH_CLIENT_JSON instead."
            )
        raise RuntimeError(
            "Google Drive upload failed. Check GOOGLE_DRIVE_FOLDER and make sure the "
            f"folder is accessible to the configured Google auth identity.{auth_hint}"
        ) from e

    return {
        "action": action,
        "id": result["id"],
        "name": result["name"],
        "webViewLink": result.get("webViewLink", ""),
        "auth_mode": auth_mode,
    }


def find_latest_detailed_lookup() -> Path:
    """
    Finds the detailed lookup CSV created by 3_average.py.

    Required columns:
      - grid_key
      - lat_center
      - lon_center
      - score_1_10
    """
    candidates = sorted(config.TABLE_DIR.glob("Mahala_CHIRPS_grid_lookup_*.csv"))

    valid = []

    for path in candidates:
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                fields = set(reader.fieldnames or [])

                required = {"grid_key", "lat_center", "lon_center", "score_1_10"}
                if required.issubset(fields):
                    valid.append(path)

        except Exception:
            continue

    if not valid:
        raise FileNotFoundError(
            f"No detailed lookup CSV found in:\n"
            f"{config.TABLE_DIR}\n\n"
            f"Run this first:\n"
            f"    python 3_average.py"
        )

    return valid[-1]


def load_lookup_rows(lookup_csv: Path):
    """
    Loads useful rows from detailed lookup CSV.
    """
    rows = []

    with open(lookup_csv, "r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        required = {"grid_key", "lat_center", "lon_center", "score_1_10"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns in {lookup_csv}: {sorted(missing)}")

        for row in reader:
            grid_key = (row.get("grid_key") or "").strip()
            lat_center = (row.get("lat_center") or "").strip()
            lon_center = (row.get("lon_center") or "").strip()
            score = (row.get("score_1_10") or "").strip()

            if not grid_key or not lat_center or not lon_center or not score:
                continue

            rows.append({
                "grid_key": grid_key,
                "lat_center": float(lat_center),
                "lon_center": float(lon_center),
                "score_1_10": int(float(score)),
            })

    if not rows:
        raise ValueError(f"No valid rows found in lookup CSV: {lookup_csv}")

    return rows


def style_sheet(ws):
    """
    Simple readable formatting.
    """
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF")
    thin = Side(style="thin", color="D9E2F3")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")
        cell.border = Border(bottom=thin)

    ws.freeze_panes = "A2"

    for col_idx, column_cells in enumerate(ws.columns, start=1):
        max_len = 0

        for cell in column_cells:
            value = "" if cell.value is None else str(cell.value)
            max_len = max(max_len, len(value))

        width = min(max(max_len + 2, 10), 65)
        ws.column_dimensions[get_column_letter(col_idx)].width = width


def create_workbook(rows, source_lookup_csv: Path):
    """
    Creates one workbook with:
      - score_lookup
      - farmers_demo
    """
    out_xlsx = choose_output_workbook_path(OUT_XLSX)
    wb = Workbook()

    # Force Excel to recalculate formulas on open, where supported.
    try:
        wb.calculation.fullCalcOnLoad = True
        wb.calculation.forceFullCalc = True
        wb.calculation.calcMode = "auto"
    except Exception:
        pass

    # -------------------------------------------------------------------------
    # Sheet 1: score_lookup
    # -------------------------------------------------------------------------
    ws_lookup = wb.active
    ws_lookup.title = LOOKUP_SHEET_NAME

    ws_lookup.append(["grid_key", "score_1_10"])

    # Deduplicate by grid_key.
    seen = set()
    for row in rows:
        if row["grid_key"] in seen:
            continue
        seen.add(row["grid_key"])

        ws_lookup.append([
            row["grid_key"],
            row["score_1_10"],
        ])

    style_sheet(ws_lookup)

    # -------------------------------------------------------------------------
    # Sheet 2: farmers_demo
    # -------------------------------------------------------------------------
    ws_demo = wb.create_sheet(DEMO_SHEET_NAME)

    ws_demo.append([
        "farmer_id",
        "lat",
        "lon",
        "grid_key",
        "rainfall_score_vlookup",
        "expected_score_python_check",
        "check_vlookup_matches_python",
    ])

    sample_rows = rows[:DEMO_SAMPLE_COUNT]
    if len(sample_rows) < DEMO_SAMPLE_COUNT:
        raise ValueError(
            f"Need at least {DEMO_SAMPLE_COUNT} valid lookup rows for demo. "
            f"Found {len(sample_rows)}."
        )

    for excel_row_num, row in enumerate(sample_rows, start=2):
        # Use existing grid-cell centres as sample farmer coordinates.
        # grid_key is written directly as a text value so the VLOOKUP demo
        # works immediately in Excel and Google Sheets.
        lat = row["lat_center"]
        lon = row["lon_center"]
        grid_key = row["grid_key"]

        # Working VLOOKUP formula:
        # D = grid_key
        # score_lookup!A:B = lookup table with grid_key + score
        vlookup_formula = (
            f'=VLOOKUP(D{excel_row_num},\'{LOOKUP_SHEET_NAME}\'!A:B,2,FALSE)'
        )

        ws_demo.append([
            f"F{excel_row_num - 1:03d}",
            lat,
            lon,
            grid_key,
            vlookup_formula,
            row["score_1_10"],
            f"=E{excel_row_num}=F{excel_row_num}",
        ])

    # Number formats
    for row_idx in range(2, ws_demo.max_row + 1):
        ws_demo[f"B{row_idx}"].number_format = "0.000000"
        ws_demo[f"C{row_idx}"].number_format = "0.000000"
        ws_demo[f"E{row_idx}"].number_format = "0"
        ws_demo[f"F{row_idx}"].number_format = "0"

    style_sheet(ws_demo)

    # Explanatory note below demo
    note_row = ws_demo.max_row + 3
    ws_demo[f"A{note_row}"] = "How the formulas work"
    ws_demo[f"A{note_row}"].font = Font(bold=True)

    ws_demo[f"A{note_row + 1}"] = (
        "Column D contains the CHIRPS 0.05 degree grid_key for each sample farmer coordinate."
    )
    ws_demo[f"A{note_row + 2}"] = (
        "Column E contains the working VLOOKUP formula that finds that grid_key in score_lookup and returns score_1_10."
    )
    ws_demo[f"A{note_row + 3}"] = (
        "Formula used in E2:"
    )
    ws_demo[f"B{note_row + 3}"] = (
        f" =VLOOKUP(D2,'{LOOKUP_SHEET_NAME}'!A:B,2,FALSE)"
    )
    ws_demo[f"A{note_row + 4}"] = (
        "For real farmer data, calculate grid_key from lat/lon using the same 0.05 degree CHIRPS grid rule, then copy the VLOOKUP formula down."
    )
    ws_demo[f"A{note_row + 5}"] = (
        f"Source detailed lookup CSV: {source_lookup_csv.name}"
    )


    # -------------------------------------------------------------------------
    # Sheet 3: methodology
    # -------------------------------------------------------------------------
    ws_method = wb.create_sheet(METHODOLOGY_SHEET_NAME)

    methodology_rows = [
        ("Item", "Value"),
        ("Data source", "CHIRPS v2.0 monthly precipitation"),
        ("Source website", "data.chc.ucsb.edu"),
        ("Area", "Gedaref bounding box, approx. lat 13.5-14.5 N, lon 35.0-36.5 E"),
        ("Grid resolution", "0.05 degrees"),
        ("Season", "June-September"),
        ("Data period", "2014-2024"),
        ("Download/processing date", PROCESSING_DATE),
        ("Scoring scale", ">=350 mm = 10; 250-349 mm = 7; 150-249 mm = 4; <150 mm = 1"),
        ("Lookup table tab", LOOKUP_SHEET_NAME),
        ("Demo tab", DEMO_SHEET_NAME),
        ("Source detailed lookup CSV", source_lookup_csv.name),
        ("Generated workbook name", out_xlsx.name),
        ("Published Google Sheet name", DRIVE_DOC_NAME),
    ]

    for item, value in methodology_rows:
        ws_method.append([item, value])

    style_sheet(ws_method)
    ws_method.column_dimensions["A"].width = 28
    ws_method.column_dimensions["B"].width = 120
    ws_method["B11"].alignment = Alignment(wrap_text=True, vertical="top")


    # Save
    config.TABLE_DIR.mkdir(parents=True, exist_ok=True)
    wb.save(out_xlsx)

    return out_xlsx


def main():
    args = parse_args()

    print("=" * 90)
    print("Create single Excel workbook with lookup + VLOOKUP demo")
    print("=" * 90)

    lookup_csv = find_latest_detailed_lookup()
    print(f"Input detailed lookup: {lookup_csv}")

    rows = load_lookup_rows(lookup_csv)
    print(f"Valid lookup rows loaded: {len(rows)}")

    out_xlsx = create_workbook(rows, lookup_csv)
    upload_enabled = args.upload_google_drive or config.GOOGLE_DRIVE_UPLOAD
    drive_file = None

    if upload_enabled:
        print(f"Google Drive upload enabled -> target folder: {config.GOOGLE_DRIVE_FOLDER}")
        try:
            drive_file = upload_workbook_to_google_drive(out_xlsx)
        except Exception as e:
            raise SystemExit(
                f"Workbook was saved locally at:\n"
                f"    {out_xlsx}\n\n"
                f"Google Drive upload failed:\n"
                f"    {e}"
            ) from e

    print()
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Workbook saved: {out_xlsx}")
    print()
    print("Workbook sheets:")
    print(f"  1. {LOOKUP_SHEET_NAME}")
    print(f"  2. {DEMO_SHEET_NAME}")
    print(f"  3. {METHODOLOGY_SHEET_NAME}")
    if drive_file:
        print()
        print("Google Sheet (live, online):")
        print(f"  Auth: {drive_file['auth_mode']}")
        print(f"  {drive_file['action'].capitalize()}: {drive_file['name']}")
        print(f"  File ID: {drive_file['id']}")
        if drive_file["webViewLink"]:
            print(f"  Open: {drive_file['webViewLink']}")
    print()
    print("Open the workbook. The VLOOKUP should return score_1_10 in farmers_demo column E.")


if __name__ == "__main__":
    main()
