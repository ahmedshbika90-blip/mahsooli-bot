# NDVI Monitoring — Handover & Sign-Off

This document is the **acceptance gate** for the NDVI crop-health monitoring
pipeline. Handover is complete when the Product Manager (PM) can operate the pipeline
and act on its output **without contacting the contractor**, and the sign-off below is
recorded.

- **Deliverable:** Sentinel-2 NDVI crop-health monitoring for registered Mahala farmer plots.
- **PM operating guide:** [`NDVI_PM_GUIDE.md`](NDVI_PM_GUIDE.md) (one page, plain English).
- **Methodology / data provenance:** [`NDVI_METHODOLOGY.md`](NDVI_METHODOLOGY.md).

---

## 1. Prerequisites (technical contact — complete before the handover call)

The automatic schedule and the "Run workflow" button are **deferred until these are set**.
Configure in GitHub → **Settings → Secrets and variables → Actions**:

- [ ] **Secret** `GEE_SERVICE_ACCOUNT_INFO` — the full service-account key JSON.
- [ ] **Variable** `EE_PROJECT_ID` — the Earth Engine project ID.
- [ ] **Variable** `NDVI_SHEET_ID` — the spreadsheet ID of the Mahsooli output Sheet.
- [ ] Service account has **Earth Engine Writer** + `serviceusage.serviceUsageConsumer` roles.
- [ ] Service account email has **Editor** access to the output Google Sheet (service
      accounts have 0 GB Drive storage, so the Sheet must be human-created and shared).
- [ ] The baseline-donor plot registry `data/farmers/baseline_plots.csv` is populated
      (tracked in git, phone numbers stripped) and `python ndvi/registry.py` runs clean.
- [ ] *(optional, for the Drive run archive)* **Secret** `GOOGLE_DRIVE_SERVICE_ACCOUNT_INFO`,
      **Variables** `GOOGLE_DRIVE_FOLDER` (a **Shared Drive** folder — service accounts
      cannot write to a plain "My Drive") and `NDVI_DRIVE_ARCHIVE=true`; verified once with
      a small test upload before relying on it.
- [ ] `.github/workflows/e1.2-ndvi-monitor.yml` is pushed to the default branch.
- [ ] One end-to-end CI run has completed green (Actions → "E1.2 - NDVI Crop-Health Monitor").

**Technical contact for issues:** _______________________  (name / email)

---

## 2. Handover call (PM + technical contact)

- [ ] Walked through [`NDVI_PM_GUIDE.md`](NDVI_PM_GUIDE.md) end to end.
- [ ] Explained the five **Alert flag** values: `Yes`, `No`, `No data`, `No coverage`,
      `Off-season`.
- [ ] Showed the Google Sheet `NDVI_Log` tab (seven columns) and the `Sector_Baseline`
      tab (the rainfed / irrigated "normal" curves; irrigated is advisory — one donor plot).
- [ ] Showed where a run's imagery + run log live (GitHub run artifact "ndvi-run";
      Google Drive `E1.2_runs/<date>_cycle` when archiving is enabled).
- [ ] Explained the in-season auto-schedule (1st / 11th / 21st, June–March; Apr–May
      reports Off-season).
- [ ] Call date: _______________   Recording / notes link: _______________

---

## 3. PM acceptance demonstration (PM acts unaided — contractor observes only)

The PM performs all of the following **without contractor assistance**:

- [ ] Triggered one monitoring cycle via GitHub → Actions → "NDVI monitor" →
      **Run workflow** (a 7–10 day window).
- [ ] Confirmed the run finished green and new rows appeared in the `NDVI_Log` tab.
- [ ] Located a plot flagged **`Yes`** (or, if none this cycle, correctly explained what
      a `Yes` row would mean and the action it triggers).
- [ ] **Acted on the alert** — recorded the decision to schedule a field visit / call the
      farmer for that Mahsooli ID.
- [ ] Correctly interpreted a `No data` row (clouds, not crop failure — no action) and a
      `No coverage` row (check the GPS) if present.

Demonstration date: _______________   Mahsooli ID acted on: _______________

---

## 4. Sign-off

By signing, the PM confirms they can run a cycle and act on its results unaided, and the
contractor confirms the deliverable is handed over.

| Role | Name | Signature / approval | Date |
|------|------|----------------------|------|
| Product Manager (Mahsooli) | | | |
| Contractor | | | |

**Acceptance gate met:** ☐ Yes   ☐ No (open items below)

**Open items / notes:**

_______________________________________________________________________

---

## Known items to confirm at handover (from the build)

These are documented design choices, surfaced here so they are explicitly accepted:

- **Composite window length:** the in-season window defaults to **10 days**
  (`NDVI_CURRENT_WINDOW_DAYS`), the top of the spec's 7–10 day range, to maximise
  cloud-free pixels during the rainy season while aligning cleanly with the 1/11/21
  monitoring cadence. Widen it in `.env` if many plots return `No data`.
- **Alert rule is stricter than "any 20% drop":** an alert also requires real vegetation
  in the baseline (`NDVI_VEG_FLOOR`) and a material absolute drop (`NDVI_ABS_DROP_FLOOR`)
  to suppress arid bare-soil false alarms. Set both floors to `0` for the pure ±20% rule.
- **Alert flag column** carries `Yes` / `No` plus `No data` and `No coverage` so a missing
  reading is never shown as a healthy `No`.

## Error handling and run summaries

Every failure is classified and printed as one line —
`ERROR [<step>] <cause>: <detail> - <what to do>` — with a stable exit code, so a red
GitHub Actions run can be diagnosed from a single log line:

| Exit | Cause code | Meaning |
|---|---|---|
| 2 | `invalid-input` / `export-too-large` | a bad registry row / zero valid plots / an export that would exceed the download cap |
| 3 | `missing-prereq` | a required file is missing (the message names the command to run first) |
| 4 | `ee-auth` | Earth Engine credentials / project / IAM problem — retrying won't help |
| 5 | `ee-transient` | Earth Engine quota/backend failure that persisted through `EE_RETRIES` retries |
| 6 | `baseline-incomplete` / `baseline-corrupt` / `output-incomplete` | the baseline is truncated, stale, or EE returned short results — rebuild with `--refresh` |
| 7 | `drive-upload` | the Google Drive run archive failed — **local artifacts are intact**; re-run with `--archive` to retry the upload only |
| 8 | `sheet-push` | the Google Sheet push failed — **local CSV and run log are intact**; fix the Sheets credentials/sharing and re-run with `--push` |
| 1 | `unexpected` | anything else (a one-line ERROR precedes the traceback) |

Bad farmer rows are skipped with `WARN [farmers] invalid-row: ...` lines; transient EE
failures show `RETRY [...]` lines before either succeeding or failing as `ee-transient`.

All outputs (manifests, the three baseline CSVs, dated logs, imagery downloads, run
logs) are written to a `.part` temp file and atomically renamed only once complete —
the baseline additionally only finalises after a completeness check (every plot ×
season × week cell present), and both `baseline.py` (on its skip path) and
`current.py` (on load) re-validate, so a truncated baseline can never be silently
accepted. Each successful run ends with a grep-stable
`RUN-SUMMARY [registry|baseline|current|exports] ...` line that separates **no
cloud-free imagery**, **low confidence**, **out-of-coverage** and **off-season**
plots — different things that previously all read as "no data".

Behaviour notes to accept:

- Because the baseline is validated against the current plot manifest, **changing the
  donor-plot registry triggers an automatic baseline rebuild** on the next run. A full
  rebuild is ~220 Earth Engine calls (5 distinct seasons × 44 weeks) and produces
  full-file diffs of the three `baseline_*.csv` files in the CI commit-back.
- The legacy `data/ndvi/baseline.csv` (per-plot calendar-DOY methodology) is no longer
  read; a courtesy `WARN` says it is safe to delete.
- Imagery export failures during a cycle are recorded per plot in `run_log.json` and
  printed as `WARN` lines — they never block or discard the alert CSV / Sheet push.

The error paths are exercised end-to-end by the pilot test in `docs/ndvi/PILOT_TEST.md`.
