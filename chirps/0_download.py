"""
Step 0 - Download CHIRPS v2.0 Africa monthly rainfall rasters.

Downloads one GeoTIFF per in-season month and year (default June-September,
2014-2024) from the CHIRPS v2.0 africa_monthly archive, then unzips each
`.tif.gz` to `.tif` in place.

Behaviour:
  - Files that already exist and are non-empty are skipped (safe to re-run).
  - Downloads are written to a `.part` temp file and renamed atomically, so an
    interrupted run never leaves a corrupt `.tif.gz` behind.
  - By default the `.tif.gz` archive is kept next to the unzipped `.tif`
    (set KEEP_GZ=false in .env to delete it after unzip and halve raw storage).

All paths and the period come from config.py / .env.
"""

import gzip
import shutil
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # repo root, for `import config` (assumes one level below root)
import config


def download_file(url: str, out_path: Path, retries: int = None) -> bool:
    """Downloads one file, skipping it if it already exists and is non-empty."""
    if retries is None:
        retries = config.DOWNLOAD_RETRIES

    if out_path.exists() and out_path.stat().st_size > 0:
        print(f"SKIP - already exists: {out_path}")
        return True

    out_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = out_path.with_suffix(out_path.suffix + ".part")

    for attempt in range(1, retries + 1):
        try:
            print(f"Downloading [{attempt}/{retries}]: {url}")

            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})

            with urlopen(request, timeout=config.DOWNLOAD_TIMEOUT) as response:
                with open(temp_path, "wb") as f:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)

            temp_path.replace(out_path)
            print(f"OK: {out_path}")
            return True

        except HTTPError as e:
            print(f"HTTP ERROR {e.code}: {url}")
        except URLError as e:
            print(f"URL ERROR: {e}")
        except Exception as e:
            print(f"ERROR: {e}")

        if temp_path.exists():
            try:
                temp_path.unlink()
            except Exception:
                pass

        if attempt < retries:
            print("Retrying in 5 seconds...")
            time.sleep(5)

    print(f"FAILED: {url}")
    return False


def unzip_gz(gz_path: Path) -> bool:
    """Unzips a `.tif.gz` to `.tif` in the same folder, honouring KEEP_GZ."""
    tif_path = gz_path.with_suffix("")  # removes .gz, keeps .tif

    already_unzipped = tif_path.exists() and tif_path.stat().st_size > 0
    if already_unzipped:
        print(f"SKIP - already unzipped: {tif_path}")
    else:
        try:
            print(f"Unzipping: {gz_path.name}")
            with gzip.open(gz_path, "rb") as f_in:
                with open(tif_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            print(f"OK unzipped: {tif_path}")
        except Exception as e:
            print(f"UNZIP ERROR: {gz_path}")
            print(e)
            return False

    if not config.KEEP_GZ and gz_path.exists():
        try:
            gz_path.unlink()
            print(f"Removed archive: {gz_path.name}")
        except Exception:
            pass

    return True


def process() -> int:
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 90)
    print("CHIRPS v2.0 monthly rainfall download")
    print("=" * 90)
    print(f"Output root: {config.RAW_DIR}")
    print(f"Years: {config.START_YEAR}-{config.END_YEAR}")
    print(f"Months: {', '.join(name for _, (name, _) in config.MONTHS.items())}")
    print(f"Keep .gz after unzip: {config.KEEP_GZ}")
    print("=" * 90)

    total = 0
    ok_count = 0
    failed = []

    for year in config.YEARS:
        print()
        print("-" * 90)
        print(f"YEAR: {year}")
        print("-" * 90)

        for month, (month_folder, _suffix) in config.MONTHS.items():
            filename = f"{config.PRODUCT_PREFIX}.{year}.{month:02d}.tif.gz"
            url = f"{config.BASE_URL}/{filename}"

            out_path = config.RAW_DIR / str(year) / month_folder / filename

            total += 1
            if download_file(url, out_path):
                unzip_gz(out_path)
                ok_count += 1
            else:
                failed.append(url)

    print()
    print("=" * 90)
    print("DONE")
    print("=" * 90)
    print(f"Total files expected: {total}")
    print(f"Successfully downloaded/skipped: {ok_count}")
    print(f"Failed: {len(failed)}")

    if failed:
        print()
        print("FAILED URLS:")
        for url in failed:
            print(url)

    print()
    print(f"Files saved in: {config.RAW_DIR}")

    return len(failed)


if __name__ == "__main__":
    # Non-zero exit on any failed download so run_pipeline.py stops here.
    sys.exit(1 if process() else 0)
