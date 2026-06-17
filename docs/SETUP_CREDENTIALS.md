# Setup: APIs & credentials (local and GitHub Actions)

This is the **one-time** guide for the parts of the project that talk to Google:
the **NDVI crop-health monitor** (Earth Engine + Google Sheets) and the
optional **Step-5 Google Drive upload**. Follow it once, and the project runs both
on your machine and headlessly on GitHub Actions.

If you only need the CHIRPS rainfall score table (steps 0–4 in the
[README](../README.md)), **stop here — that part needs no credentials at all.** It
uses public CHIRPS data and runs out of the box.

---

## 1. What needs credentials (and what doesn't)

| What you run | Needs credentials? | Google services |
|---|---|---|
| CHIRPS pipeline (`0`–`3`) + farmer scoring (`4`) + E1.3 pilot check | **No** | none (public CHIRPS data) |
| **NDVI monitor** (`ndvi_run_pipeline.py`, the E1.2 workflow) | **Yes** | Earth Engine + Google Sheets |
| Step-5 Drive upload (`tools/google_sheets_lookup.py --upload-google-drive`, E1.1 option) | Optional | Google Drive |

The same **one service account** can serve Earth Engine, Sheets, and Drive — you
do **not** need three different keys.

### How a credential is supplied: file path (local) vs. JSON contents (CI)

The code reads each credential **two ways** and always prefers the CI-friendly one
when present. This is the crucial point for GitHub Actions: **on a CI runner there
are no files on disk, so you give it the JSON *contents* as a secret string, not a
file path.**

| Credential | Local (`.env`) — a **file path** | GitHub Actions — the **JSON contents** | Read in code |
|---|---|---|---|
| Earth Engine + Sheets key | `GEE_SERVICE_ACCOUNT_JSON` | `GEE_SERVICE_ACCOUNT_INFO` | `ndvi/ee_auth.py`, `ndvi/sheets.py` |
| Drive upload key | `GOOGLE_DRIVE_SERVICE_ACCOUNT_JSON` | `GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO` | `tools/google_sheets_lookup.py` |
| Earth Engine project | `EE_PROJECT_ID` (a plain ID, same value both places) | | |
| Output Sheet | `NDVI_SHEET_ID` (a plain ID, same value both places) | | |

When a `*_INFO` variable is set it **wins** over the matching `*_JSON` path (and
over the local browser-OAuth flow), so a deployed run authenticates with no file
and no browser. Both are parsed in-memory with `json.loads` — same service-account
key, just delivered as a string instead of a file.

### The three GitHub Actions workflows (which needs what)

Each Engagement-1 deliverable has its own workflow in the **Actions** tab, named so
a PM can pick the right one. Only E1.2 needs credentials to do its core job.

| Workflow (Actions tab) | File | Secrets | Variables |
|---|---|---|---|
| **E1.1 - CHIRPS Rainfall Lookup Table** | `e1.1-chirps-lookup.yml` | `GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO` *(optional — only to publish the live Sheet)* | `GOOGLE_DRIVE_FOLDER` *(optional, has a default)* |
| **E1.2 - NDVI Crop-Health Monitor** | `e1.2-ndvi-monitor.yml` | `GEE_SERVICE_ACCOUNT_INFO` **(required)** | `EE_PROJECT_ID`, `NDVI_SHEET_ID` **(required)** |
| **E1.3 - Pilot Launch Check** | `e1.3-pilot-check.yml` | none | none |

All three commit their small deliverables back to the repo (and upload them as
downloadable **Artifacts**): E1.1 the lookup CSV + average raster, E1.2 the NDVI
baseline + cycle logs, E1.3 the sign-off package. **Run E1.1 once before E1.3** —
E1.3 reads the committed lookup CSV.

---

## 2. One-time Google Cloud setup

You need a Google account with permission to create a Google Cloud project. Do
these in order.

1. **Create or select a Google Cloud project.**
   Go to <https://console.cloud.google.com/projectcreate>, create a project (or
   pick an existing one), and copy its **Project ID** (e.g. `mahala-monitor-123`).
   → this is your **`EE_PROJECT_ID`**.

2. **Enable the three APIs.**
   In the project, open **APIs & Services → Library** and enable each of:
   - **Earth Engine API**
   - **Google Sheets API**
   - **Google Drive API** (needed by Sheets writes and the optional Step-5 upload)

3. **Register the project for Earth Engine** (web-only — cannot be scripted).
   Open, replacing the placeholder with your Project ID:
   `https://code.earthengine.google.com/register?project=<PROJECT_ID>`
   Follow the prompts (non-commercial / commercial as appropriate). Without this,
   Earth Engine calls fail even with a valid key.

4. **Create a service account.**
   **IAM & Admin → Service Accounts → Create service account.** Give it a name
   (e.g. `ndvi-monitor`). After creating it, copy its **email** — it looks like
   `ndvi-monitor@<project>.iam.gserviceaccount.com`. You'll share the Sheet with
   this email in step 6.

5. **Grant the service account its roles.**
   It needs both:
   - `roles/serviceusage.serviceUsageConsumer` (Service Usage Consumer)
   - Earth Engine **Writer**

   Grant the Service Usage Consumer role under **IAM & Admin → IAM** (or
   **Earth Engine → project access**); grant the Earth Engine **Writer** role in
   the Earth Engine project-access settings. (These are exactly what the code
   requires — see the note at `config.py:322-325`.)

6. **Create and download a JSON key.**
   On the service account, open the **Keys** tab → **Add key → Create new key →
   JSON**. A `*.json` file downloads. **Treat this file like a password:**
   - Never commit it to git.
   - Its **contents** are what you'll paste into the GitHub Secret later.

---

## 3. Create the output Google Sheet

The NDVI run writes its results into the `NDVI_Log` tab of a Google Sheet.
**Service accounts have 0 GB of Drive storage and cannot create or own Sheets**,
so you create the Sheet yourself and share it with the service account.

1. With your **normal Google account**, create a blank Google Sheet.
2. Copy its **ID** from the URL — the part between `/d/` and `/edit`:
   `https://docs.google.com/spreadsheets/d/`**`<THIS_IS_THE_ID>`**`/edit`
   → this is your **`NDVI_SHEET_ID`**.
3. Click **Share**, add the **service-account email** from step 2.4, and give it
   **Editor** access. (The pipeline creates/updates the `NDVI_Log` tab itself.)

---

## 4. Run it locally first (recommended before CI)

Verifying on your machine first makes CI failures much easier to diagnose.

1. Install the libraries:
   ```bash
   pip install earthengine-api google-api-python-client google-auth
   ```
2. In your `.env` (copy from `.env.example` if you haven't), set:
   ```dotenv
   EE_PROJECT_ID=<your-project-id>
   GEE_SERVICE_ACCOUNT_JSON=/absolute/or/relative/path/to/key.json
   NDVI_SHEET_ID=<your-sheet-id>
   NDVI_SHEET_PUSH=true
   ```
   Locally you use the **file path** (`GEE_SERVICE_ACCOUNT_JSON`). Leave
   `GEE_SERVICE_ACCOUNT_INFO` blank on your machine.
3. Run:
   ```bash
   python ndvi_run_pipeline.py
   ```
4. **Expected:** rows appear in the `NDVI_Log` tab of your Sheet. With no
   `NDVI_FARMERS_CSV` set, it uses the tracked demo registry
   `docs/sample_ndvi_farmers.csv`; point `NDVI_FARMERS_CSV` at your real (local,
   git-ignored) registry for production runs.

---

## 5. Run it on GitHub Actions

The workflow [`.github/workflows/e1.2-ndvi-monitor.yml`](../.github/workflows/e1.2-ndvi-monitor.yml)
already runs the pipeline on a button click and on an in-season schedule. You just
have to give the repository the credentials.

**Why you paste contents, not a path:** the runner is a fresh machine with no key
file on it. The workflow passes the key's JSON **string** through the
`GEE_SERVICE_ACCOUNT_INFO` environment variable (see the `Run NDVI pipeline` step's
`env:` block in `e1.2-ndvi-monitor.yml`), and the code parses it in memory and
prefers it over any file path.

### 5.1 Get the JSON contents

Open the key file you downloaded in step 2.6 in any text editor and **copy the
entire file** — the whole multi-line `{ ... }` block, including the braces.
GitHub Secrets accept multi-line values, so **paste it verbatim** — do **not**
strip newlines, escape it, or put it on one line.

### 5.2 Add one Secret

Repo → **Settings → Secrets and variables → Actions → Secrets** tab →
**New repository secret**:

| Name | Value |
|---|---|
| `GEE_SERVICE_ACCOUNT_INFO` | the full key JSON contents from step 5.1 |

### 5.3 Add two Variables

Same page → **Variables** tab → **New repository variable** (add both):

| Name | Value |
|---|---|
| `EE_PROJECT_ID` | your Project ID (step 2.1) |
| `NDVI_SHEET_ID` | your Sheet ID (step 3.2) |

> The names must match **exactly** — the workflow reads
> `${{ secrets.GEE_SERVICE_ACCOUNT_INFO }}`, `${{ vars.EE_PROJECT_ID }}`, and
> `${{ vars.NDVI_SHEET_ID }}`.

### 5.4 Make the workflow active and run it

- The workflow goes live once the Secret + Variables exist **and** the workflow
  file is on the repository's **default branch**.
- **Run it manually:** repo → **Actions** tab → **E1.2 - NDVI Crop-Health Monitor**
  → **Run workflow** (you can leave the date blank for "today").
- **Or wait for the schedule:** it runs automatically on the **1st, 11th, and
  21st at 06:00 UTC, June–September** (`cron: "0 6 1,11,21 6-9 *"`).
- CI installs only `earthengine-api`, `google-api-python-client`, and
  `google-auth` — **not** `google-auth-oauthlib`, which is only for the local
  browser sign-in flow.

That's it: with `GEE_SERVICE_ACCOUNT_INFO` (the contents) plus the two Variables,
the run authenticates headlessly and writes to your Sheet.

---

## 6. Optional: Step-5 Google Drive upload in CI

If you also want `tools/google_sheets_lookup.py --upload-google-drive` to run in CI,
it follows the same pattern with a different secret:

- Store the key JSON **contents** in a secret named
  `GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO` (it can be the **same** service account).
- Set `GOOGLE_DRIVE_FOLDER` to a **Shared Drive** (or a folder shared with the
  service-account email). A plain personal "My Drive" folder fails — service
  accounts have no personal Drive storage.
- Set `GOOGLE_DRIVE_UPLOAD=true`.

See the ready-made `env:` snippet in the README under
[**Automated / CI upload (GitHub Actions)**](../README.md#automated--ci-upload-github-actions).

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GEE_SERVICE_ACCOUNT_INFO is not valid JSON` | The secret value is truncated, escaped, or not the full file. | Re-copy the **entire** key file and paste it as-is into the secret. |
| Earth Engine init fails / "not registered" | The project was never registered for Earth Engine. | Complete step 2.3 at `code.earthengine.google.com/register?project=<PROJECT_ID>`. |
| `403` / permission denied writing the Sheet | Sheet not shared with the service account. | Share the Sheet as **Editor** with the service-account email (step 3.3). |
| "service accounts have no storage" / Drive upload fails | Uploading into a personal "My Drive" folder. | Point `GOOGLE_DRIVE_FOLDER` at a **Shared Drive** or a shared folder. |
| EE calls denied despite a valid key | Missing roles. | Grant `serviceusage.serviceUsageConsumer` **and** Earth Engine **Writer** (step 2.5). |
| `EE_PROJECT_ID is required` | Variable not set or misnamed. | Add `EE_PROJECT_ID` (CI Variable, or `.env` locally). |

All variable names and defaults live in
[`.env.example`](../.env.example) and `config.py` — those are the source of truth.
