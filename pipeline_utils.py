"""
Shared pipeline plumbing - error type, retries, and atomic CSV writes.

Stdlib-only, importable from both the chirps/ and ndvi/ packages (every step
script already puts the repo root on sys.path). Three building blocks:

  - PipelineError / run_main():  one classified error per failure scenario, each
    rendered as `ERROR [<step>] <cause>: <detail> - <action>` and mapped to a
    stable exit code, so a production log line says what broke AND what to do.
  - retry_call():                bounded retries with exponential backoff
    (generalises the loop in chirps/0_download.py).
  - write_csv_atomic() / CsvPartWriter:  the `.part` + rename pattern from the
    CHIRPS download applied to CSVs - an interrupted run can never leave a
    truncated file under the final name.

Exit codes (documented in docs/ndvi/HANDOVER.md):
    0 success | 1 unexpected | 2 invalid input | 3 missing prerequisite
    4 EE auth/config | 5 EE transient (after retries) | 6 incomplete/corrupt output
    7 GCS upload failed | 8 Google Sheet push failed | 9 required imagery export failed
    (7, 8 and 9: local artifacts are intact)
"""

import csv
import json
import sys
import time
import urllib.request


class PipelineError(Exception):
    """A classified, operator-actionable pipeline failure."""

    def __init__(self, step, cause, detail, action, exit_code=1):
        self.step = step
        self.cause = cause
        self.detail = detail
        self.action = action
        self.exit_code = exit_code
        super().__init__(str(self))

    def __str__(self):
        return f"ERROR [{self.step}] {self.cause}: {self.detail} - {self.action}"


def run_main(main, step):
    """
    Wrap a step's main() for the `if __name__ == "__main__"` block.

    PipelineError -> its message + stable exit code; Ctrl-C -> exit 130 with a
    note that nothing was finalised; anything else -> a one-line classified
    ERROR before the traceback (so log greps still catch it), exit code 1.
    """
    try:
        sys.exit(main())
    except PipelineError as e:
        print(e)
        sys.exit(e.exit_code)
    except KeyboardInterrupt:
        print(f"\nINTERRUPTED [{step}] - no partial output was finalized")
        sys.exit(130)
    except Exception as e:
        print(f"ERROR [{step}] unexpected: {e!r} - see traceback below")
        raise


def retry_call(fn, *, attempts, base_delay, describe, retryable=lambda e: True):
    """
    Call fn() with up to `attempts` tries and exponential backoff.

    Prints a RETRY line per failed attempt. Re-raises immediately when
    retryable(exc) is False, and re-raises the last exception once exhausted -
    classification into PipelineError is the caller's job.
    """
    delay = base_delay
    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            if not retryable(e) or attempt == attempts:
                raise
            print(
                f"  RETRY [{describe}] attempt {attempt}/{attempts} failed: {e!r}; "
                f"retrying in {delay:.0f}s"
            )
            time.sleep(delay)
            delay *= 2


def write_csv_atomic(path, fieldnames, rows, header=None):
    """
    Write a CSV via `.part` + atomic rename (the chirps/0_download.py pattern).

    With `fieldnames`, rows are dicts (DictWriter); with `header`, rows are
    plain lists. The final filename only ever appears fully written.
    """
    with CsvPartWriter(path, fieldnames=fieldnames, header=header) as writer:
        writer.write_rows(rows)


def write_json_atomic(path, obj):
    """
    Write a JSON file via `.part` + atomic rename (same discipline as the CSV
    writers - the final filename only ever appears fully written).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".part")
    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2, ensure_ascii=False)
            f.write("\n")
        temp_path.replace(path)
    except BaseException:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass  # leftover .part is harmless (and git-ignored)
        raise


def download_atomic(url, path, timeout=120, chunk_bytes=1 << 20):
    """
    Download a URL to a file via `.part` + atomic rename. Returns bytes written.

    Used for Earth Engine getDownloadURL/getThumbURL artifacts; retries are the
    caller's job (wrap in retry_call), this only guarantees no truncated file
    ever sits under the final name.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".part")
    written = 0
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp, \
                open(temp_path, "wb") as out:
            while True:
                chunk = resp.read(chunk_bytes)
                if not chunk:
                    break
                out.write(chunk)
                written += len(chunk)
        temp_path.replace(path)
    except BaseException:
        try:
            if temp_path.exists():
                temp_path.unlink()
        except OSError:
            pass
        raise
    return written


class CsvPartWriter:
    """
    Incremental atomic CSV writer: rows go to `<name>.part`, and the temp file
    is renamed onto the final name only when finalize() is called. Leaving the
    `with` block on an exception removes the temp file instead - so a crash or
    Ctrl-C mid-build can never leave a truncated CSV under the final name.
    """

    def __init__(self, path, fieldnames=None, header=None, encoding="utf-8-sig"):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.temp_path = path.with_suffix(path.suffix + ".part")
        self._file = open(self.temp_path, "w", encoding=encoding, newline="")
        if fieldnames is not None:
            self._writer = csv.DictWriter(self._file, fieldnames=fieldnames)
            self._writer.writeheader()
        else:
            self._writer = csv.writer(self._file)
            if header is not None:
                self._writer.writerow(header)
        self._finalized = False

    def write_rows(self, rows):
        self._writer.writerows(rows)
        self._file.flush()

    def finalize(self):
        self._file.close()
        self.temp_path.replace(self.path)
        self._finalized = True

    def discard(self):
        if not self._file.closed:
            self._file.close()
        try:
            if self.temp_path.exists():
                self.temp_path.unlink()
        except OSError:
            pass  # leftover .part is harmless (and git-ignored)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None and not self._finalized:
            self.finalize()
        elif exc_type is not None:
            self.discard()
        return False
