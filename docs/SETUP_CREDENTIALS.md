# Setup: APIs & credentials (local and GitHub Actions)

This is the **one-time** guide for the parts of the project that talk to Google:
the **NDVI crop-health monitor** (Earth Engine + Google Sheets) and the optional
**Google Cloud Storage run archive**. Follow it once, and the project runs both
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
| NDVI run archive (`NDVI_GCS_ARCHIVE=true`) | Optional | Google Cloud Storage |

The same **one service account** can serve Earth Engine, Sheets, and Cloud Storage —
you do **not** need separate keys. The archive bucket lives in the same Cloud
project as Earth Engine, so the GCS archive reuses the Earth Engine credentials.

### How a credential is supplied: file path (local) vs. JSON contents (CI)

The code reads each credential **two ways** and always prefers the CI-friendly one
when present. This is the crucial point for GitHub Actions: **on a CI runner there
are no files on disk, so you give it the JSON *contents* as a secret string, not a
file path.**

| Credential | Local (`.env`) — a **file path** | GitHub Actions — the **JSON contents** | Read in code |
|---|---|---|---|
| Earth Engine + Sheets key | `GEE_SERVICE_ACCOUNT_JSON` | `GEE_SERVICE_ACCOUNT_INFO` | `ndvi/ee_auth.py`, `ndvi/sheets.py` |
| GCS archive key *(optional; reuses the EE key if unset)* | `GCS_SERVICE_ACCOUNT_JSON` | `GCS_SERVICE_ACCOUNT_INFO` | `gcs.py` |
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
| **E1.1 - CHIRPS Rainfall Lookup Table** | `e1.1-chirps-lookup.yml` | none | none |
| **E1.2 - NDVI Crop-Health Monitor** | `e1.2-ndvi-monitor.yml` | `GEE_SERVICE_ACCOUNT_INFO` **(required)**, `GCS_SERVICE_ACCOUNT_INFO` *(optional)* | `EE_PROJECT_ID`, `NDVI_SHEET_ID` **(required)**; `GCS_BUCKET`, `NDVI_GCS_ARCHIVE` *(optional)* |
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

2. **Enable the APIs.**
   In the project, open **APIs & Services → Library** and enable each of:
   - **Earth Engine API**
   - **Google Sheets API**
   - **Cloud Storage API** (only if you use the optional GCS run archive — Step 6)

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
   `NDVI_FARMERS_CSV` set, it uses `data/farmers/farmers.csv`; point
   `NDVI_FARMERS_CSV` at a private/git-ignored registry when production farmer
   data cannot be committed.

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

### 5.3 Add Variables

Same page → **Variables** tab → **New repository variable**:

| Name | Value |
|---|---|
| `EE_PROJECT_ID` | your Project ID (step 2.1) |
| `NDVI_SHEET_ID` | your Sheet ID (step 3.2) |
| `NDVI_MONITOR_FARMERS` | `true` (default if omitted) |
| `NDVI_FARMERS_CSV` | optional path to a private farmer CSV available to the runner |
| `NDVI_REQUIRE_EXPORTS` | `true` (default if omitted; required raw imagery failures block green runs) |

> The names must match **exactly** — the workflow reads
> `${{ secrets.GEE_SERVICE_ACCOUNT_INFO }}`, `${{ vars.EE_PROJECT_ID }}`, and
> `${{ vars.NDVI_SHEET_ID }}`.

### 5.4 Make the workflow active and run it

- The workflow goes live once the Secret + Variables exist **and** the workflow
  file is on the repository's **default branch**.
- **Run it manually:** repo → **Actions** tab → **E1.2 - NDVI Crop-Health Monitor**
  → **Run workflow** (you can leave the date blank for "today").
- **Or wait for the schedule:** it runs automatically on the **1st, 11th, and
  21st at 06:00 UTC, January–March and June–December** (`cron: "0 6 1,11,21 1-3,6-12 *"`).
- CI installs only `earthengine-api`, `google-api-python-client`, and
  `google-auth` — **not** `google-auth-oauthlib`, which is only for the local
  browser sign-in flow.

That's it: with `GEE_SERVICE_ACCOUNT_INFO` (the contents) plus the two Variables,
the run authenticates headlessly and writes to your Sheet.

---

## 6. Optional: Google Cloud Storage run archive

To mirror each NDVI run folder (imagery + tables + run log) to a bucket for
traceability, set up a bucket in the **same Cloud project** as Earth Engine. No new
credential is needed — the archive reuses the EE service account.

1. **Create the bucket** (Console → Cloud Storage, or):
   ```bash
   gcloud storage buckets create gs://<your-bucket> \
     --project <EE_PROJECT_ID> --location <region>
   ```
2. **Grant the EE service account write access** (the `client_email` from the key
   JSON):
   ```bash
   gcloud storage buckets add-iam-policy-binding gs://<your-bucket> \
     --member "serviceAccount:<service-account-email>" \
     --role roles/storage.objectAdmin
   ```
3. **Enable archiving:** set the Variables `GCS_BUCKET=<your-bucket>` and
   `NDVI_GCS_ARCHIVE=true` (locally in `.env`, or as CI Variables on the E1.2
   workflow). To use a *separate* key instead of the EE credentials, set the secret
   `GCS_SERVICE_ACCOUNT_INFO`; otherwise leave it empty and the EE key is reused.

Re-uploads are idempotent: objects of unchanged size are skipped unless
`GCS_OVERWRITE=true`.

---

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Actions tab is empty / no workflows listed | The `.github/workflows/` folder is not on the repo's **default branch** — often dropped when a ZIP is unzipped/uploaded (it's a hidden folder), or the files landed on a non-default branch. | Commit the hidden `.github/workflows/` folder (the three `.yml` files) to the default branch. The branch may be named `main` — it need not be `develop`. |
| `GEE_SERVICE_ACCOUNT_INFO is not valid JSON` | The secret value is truncated, escaped, or not the full file. | Re-copy the **entire** key file and paste it as-is into the secret. |
| Earth Engine init fails / "not registered" | The project was never registered for Earth Engine. | Complete step 2.3 at `code.earthengine.google.com/register?project=<PROJECT_ID>`. |
| `403` / permission denied writing the Sheet | Sheet not shared with the service account. | Share the Sheet as **Editor** with the service-account email (step 3.3). |
| GCS archive fails with `403` / `AccessDenied` | The service account lacks write access to the bucket. | Grant `roles/storage.objectAdmin` on `GCS_BUCKET` to the service-account email (Step 6.2). |
| EE calls denied despite a valid key | Missing roles. | Grant `serviceusage.serviceUsageConsumer` **and** Earth Engine **Writer** (step 2.5). |
| `EE_PROJECT_ID is required` | Variable not set or misnamed. | Add `EE_PROJECT_ID` (CI Variable, or `.env` locally). |

All variable names and defaults live in
[`.env.example`](../.env.example) and `config.py` — those are the source of truth.
