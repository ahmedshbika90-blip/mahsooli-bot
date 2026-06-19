"""Unit tests for gcs.py - run-folder archiving to Google Cloud Storage.

Fully mocked: no google-cloud-storage install, no network, no credentials.

Run:  python -m unittest discover tests
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
import config  # noqa: E402
import gcs  # noqa: E402
from pipeline_utils import PipelineError  # noqa: E402


def _make_run_dir(root: Path) -> Path:
    """A dated run folder with a top-level CSV and an imagery/ subdir PNG."""
    run_dir = root / "2026-06-17_baseline"
    (run_dir / "imagery").mkdir(parents=True)
    (run_dir / "baseline_sector.csv").write_text("week,ndvi\n1,0.3\n", encoding="utf-8")
    (run_dir / "run_log.json").write_text("{}", encoding="utf-8")
    (run_dir / "imagery" / "BP003_2024_ndvi.png").write_bytes(b"\x89PNG\r\n")
    return run_dir


class BlobNameTests(unittest.TestCase):
    def test_layout_uses_posix_separators(self):
        name = gcs._blob_name("E1.2_runs", "2026-06-17_baseline", Path("imagery") / "BP003.png")
        self.assertEqual(name, "E1.2_runs/2026-06-17_baseline/imagery/BP003.png")

    def test_top_level_file(self):
        name = gcs._blob_name("E1.2_runs", "2026-06-17_baseline", Path("run_log.json"))
        self.assertEqual(name, "E1.2_runs/2026-06-17_baseline/run_log.json")

    def test_empty_prefix_is_dropped(self):
        name = gcs._blob_name("", "2026-06-17_baseline", Path("run_log.json"))
        self.assertEqual(name, "2026-06-17_baseline/run_log.json")


class ArchiveTests(unittest.TestCase):
    def setUp(self):
        # Snapshot the config knobs the archiver reads, then set test values.
        self._saved = {
            k: getattr(config, k)
            for k in ("GCS_BUCKET", "GCS_ARCHIVE_PREFIX", "GCS_OVERWRITE")
        }
        config.GCS_BUCKET = "mahala-test-bucket"
        config.GCS_ARCHIVE_PREFIX = "E1.2_runs"
        config.GCS_OVERWRITE = False

        self._tmp = tempfile.TemporaryDirectory()
        self.run_dir = _make_run_dir(Path(self._tmp.name))

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)
        self._tmp.cleanup()

    def _client_returning(self, *, existing_blob=None):
        """A mock storage client whose bucket().blob()/get_blob() are mocks."""
        bucket = mock.MagicMock()
        bucket.blob.return_value = mock.MagicMock()
        bucket.get_blob.return_value = existing_blob
        client = mock.MagicMock()
        client.bucket.return_value = bucket
        return client, bucket

    def test_uploads_every_file(self):
        client, bucket = self._client_returning(existing_blob=None)
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.archive_run_dir_to_gcs(self.run_dir, "test")

        # 3 files: baseline_sector.csv, run_log.json, imagery/BP003_2024_ndvi.png
        self.assertEqual(uploaded, 3)
        self.assertEqual(bucket.blob.return_value.upload_from_filename.call_count, 3)
        client.bucket.assert_called_once_with("mahala-test-bucket")

        # Date-first layout: <date>/e1.2-<kind>/...; imagery keeps its subfolder.
        names = {c.args[0] for c in bucket.blob.call_args_list}
        self.assertIn("2026-06-17/e1.2-baseline/imagery/BP003_2024_ndvi.png", names)
        self.assertIn("2026-06-17/e1.2-baseline/baseline_sector.csv", names)

    def test_uploads_nested_subfolders(self):
        # Files nested deeper than imagery/ must still be archived (not silently
        # skipped) with a blob key that mirrors the local path under run_dir.
        nested = self.run_dir / "imagery" / "BP003" / "ndvi.tif"
        nested.parent.mkdir(parents=True)
        nested.write_bytes(b"II*\x00")

        client, bucket = self._client_returning(existing_blob=None)
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.archive_run_dir_to_gcs(self.run_dir, "test")

        self.assertEqual(uploaded, 4)
        names = {c.args[0] for c in bucket.blob.call_args_list}
        self.assertIn("2026-06-17/e1.2-baseline/imagery/BP003/ndvi.tif", names)

    def test_skips_when_size_matches(self):
        # Every file already exists with a matching size, so nothing re-uploads.
        prefix = f"2026-06-17/e1.2-baseline/"

        def get_blob(blob_name):
            rel = blob_name[len(prefix):]
            local = self.run_dir / rel
            stub = mock.MagicMock()
            stub.size = local.stat().st_size
            return stub

        client, bucket = self._client_returning()
        bucket.get_blob.side_effect = get_blob
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.archive_run_dir_to_gcs(self.run_dir, "test")

        self.assertEqual(uploaded, 0)
        bucket.blob.return_value.upload_from_filename.assert_not_called()

    def test_overwrite_flag_forces_upload(self):
        config.GCS_OVERWRITE = True
        existing = mock.MagicMock()
        existing.size = 999999  # size check is bypassed when overwrite is on
        client, bucket = self._client_returning(existing_blob=existing)
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.archive_run_dir_to_gcs(self.run_dir, "test")

        self.assertEqual(uploaded, 3)
        # get_blob must not even be consulted when overwrite is forced.
        bucket.get_blob.assert_not_called()

    def test_missing_bucket_raises_pipeline_error(self):
        config.GCS_BUCKET = ""
        with self.assertRaises(PipelineError) as ctx:
            gcs.archive_run_dir_to_gcs(self.run_dir, "test")
        self.assertEqual(ctx.exception.exit_code, 7)

    def test_upload_failure_raises_pipeline_error(self):
        client, bucket = self._client_returning(existing_blob=None)
        bucket.blob.return_value.upload_from_filename.side_effect = RuntimeError("boom")
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            with self.assertRaises(PipelineError) as ctx:
                gcs.archive_run_dir_to_gcs(self.run_dir, "test")
        self.assertEqual(ctx.exception.exit_code, 7)
        self.assertEqual(ctx.exception.cause, "gcs-upload")


class MirrorNdviTiffsTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: getattr(config, k)
            for k in ("GCS_BUCKET", "NDVI_TIFF_PREFIX", "GCS_OVERWRITE")
        }
        config.GCS_BUCKET = "mahala-test-bucket"
        config.NDVI_TIFF_PREFIX = "ndvi"
        config.GCS_OVERWRITE = False

        self._tmp = tempfile.TemporaryDirectory()
        # A baseline run folder with two NDVI tiffs plus an S2 tiff and a PNG that
        # must NOT be mirrored (only *_ndvi.tif belongs in the dedicated folder).
        self.run_dir = Path(self._tmp.name) / "2026-06-17_baseline"
        (self.run_dir / "imagery").mkdir(parents=True)
        img = self.run_dir / "imagery"
        (img / "BP003_2019-06-01_2020-03-31_ndvi.tif").write_bytes(b"II*\x00ndvi")
        (img / "BP004_2023-06-01_2024-03-31_ndvi.tif").write_bytes(b"II*\x00ndvi2")
        (img / "BP003_2019-06-01_2020-03-31_s2.tif").write_bytes(b"II*\x00s2")
        (img / "BP003_2019-06-01_2020-03-31_ndvi.png").write_bytes(b"\x89PNG\r\n")
        (self.run_dir / "baseline_sector.csv").write_text("week,ndvi\n1,0.3\n", encoding="utf-8")

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)
        self._tmp.cleanup()

    def _client_returning(self, *, existing_blob=None):
        bucket = mock.MagicMock()
        bucket.blob.return_value = mock.MagicMock()
        bucket.get_blob.return_value = existing_blob
        client = mock.MagicMock()
        client.bucket.return_value = bucket
        return client, bucket

    def test_mirrors_only_ndvi_tiffs_to_dedicated_dated_folder(self):
        client, bucket = self._client_returning(existing_blob=None)
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.mirror_ndvi_tiffs_to_gcs(self.run_dir, "baseline", "test")

        # Only the two *_ndvi.tif files, not the s2.tif, png, or csv.
        self.assertEqual(uploaded, 2)
        names = {c.args[0] for c in bucket.blob.call_args_list}
        self.assertEqual(
            names,
            {
                "ndvi/baseline/2026-06-17/BP003_2019-06-01_2020-03-31_ndvi.tif",
                "ndvi/baseline/2026-06-17/BP004_2023-06-01_2024-03-31_ndvi.tif",
            },
        )

    def test_current_kind_uses_current_segment(self):
        client, bucket = self._client_returning(existing_blob=None)
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            gcs.mirror_ndvi_tiffs_to_gcs(self.run_dir, "current", "test")
        names = {c.args[0] for c in bucket.blob.call_args_list}
        self.assertTrue(all(n.startswith("ndvi/current/2026-06-17/") for n in names))

    def test_no_tiffs_returns_zero_without_client(self):
        empty = Path(self._tmp.name) / "2026-06-18_baseline"
        (empty / "imagery").mkdir(parents=True)
        with mock.patch.object(gcs, "build_storage_client") as build:
            uploaded = gcs.mirror_ndvi_tiffs_to_gcs(empty, "baseline", "test")
        self.assertEqual(uploaded, 0)
        build.assert_not_called()  # no network when there is nothing to mirror

    def test_missing_bucket_raises_pipeline_error(self):
        config.GCS_BUCKET = ""
        with self.assertRaises(PipelineError) as ctx:
            gcs.mirror_ndvi_tiffs_to_gcs(self.run_dir, "baseline", "test")
        self.assertEqual(ctx.exception.exit_code, 7)

    def test_upload_failure_raises_classified_pipeline_error(self):
        client, bucket = self._client_returning(existing_blob=None)
        bucket.blob.return_value.upload_from_filename.side_effect = RuntimeError("boom")
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            with self.assertRaises(PipelineError) as ctx:
                gcs.mirror_ndvi_tiffs_to_gcs(self.run_dir, "baseline", "test")
        self.assertEqual(ctx.exception.exit_code, 7)
        self.assertEqual(ctx.exception.cause, "gcs-ndvi-mirror")


class DateFirstDestTests(unittest.TestCase):
    def setUp(self):
        self._saved = config.GCS_DATA_PREFIX

    def tearDown(self):
        config.GCS_DATA_PREFIX = self._saved

    def test_bucket_root_when_no_prefix(self):
        config.GCS_DATA_PREFIX = ""
        self.assertEqual(gcs.date_first_dest("2026-06-18", "e1.1-chirps"),
                         "2026-06-18/e1.1-chirps")

    def test_nested_under_data_prefix(self):
        config.GCS_DATA_PREFIX = "archive/"
        self.assertEqual(gcs.date_first_dest("2026-06-18", "e1.3-pilot"),
                         "archive/2026-06-18/e1.3-pilot")


class UploadFilesTests(unittest.TestCase):
    def setUp(self):
        self._saved = {k: getattr(config, k) for k in ("GCS_BUCKET", "GCS_OVERWRITE")}
        config.GCS_BUCKET = "mahala-test-bucket"
        config.GCS_OVERWRITE = False
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        # Two loose deliverables plus a directory tree (preserved by its own name).
        (root / "lookup.csv").write_text("grid,score\n", encoding="utf-8")
        (root / "average.tif").write_bytes(b"II*\x00avg")
        seasonal = root / "03_seasonal_totals" / "2014"
        seasonal.mkdir(parents=True)
        (seasonal / "total_2014.tif").write_bytes(b"II*\x002014")
        self.root = root

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)
        self._tmp.cleanup()

    def _client(self):
        bucket = mock.MagicMock()
        bucket.blob.return_value = mock.MagicMock()
        bucket.get_blob.return_value = None
        client = mock.MagicMock()
        client.bucket.return_value = bucket
        return client, bucket

    def test_files_flat_and_dir_preserves_structure(self):
        client, bucket = self._client()
        paths = [self.root / "lookup.csv", self.root / "average.tif",
                 self.root / "missing.txt",  # skipped silently
                 self.root / "03_seasonal_totals"]
        with mock.patch.object(gcs, "build_storage_client", return_value=(client, "service_account")):
            uploaded = gcs.upload_files_to_gcs(paths, "2026-06-18/e1.1-chirps", "E1.1")

        self.assertEqual(uploaded, 3)
        names = {c.args[0] for c in bucket.blob.call_args_list}
        self.assertEqual(names, {
            "2026-06-18/e1.1-chirps/lookup.csv",
            "2026-06-18/e1.1-chirps/average.tif",
            "2026-06-18/e1.1-chirps/03_seasonal_totals/2014/total_2014.tif",
        })

    def test_no_existing_files_returns_zero_without_client(self):
        with mock.patch.object(gcs, "build_storage_client") as build:
            uploaded = gcs.upload_files_to_gcs([self.root / "nope.csv"],
                                               "2026-06-18/e1.3-pilot", "E1.3")
        self.assertEqual(uploaded, 0)
        build.assert_not_called()

    def test_missing_bucket_raises_pipeline_error(self):
        config.GCS_BUCKET = ""
        with self.assertRaises(PipelineError) as ctx:
            gcs.upload_files_to_gcs([self.root / "lookup.csv"], "2026-06-18/e1.1-chirps", "E1.1")
        self.assertEqual(ctx.exception.exit_code, 7)


class CredentialFallbackTests(unittest.TestCase):
    def setUp(self):
        self._saved = {
            k: getattr(config, k)
            for k in (
                "GCS_SERVICE_ACCOUNT_INFO", "GCS_SERVICE_ACCOUNT_JSON",
                "GEE_SERVICE_ACCOUNT_INFO", "GEE_SERVICE_ACCOUNT_JSON",
                "EE_PROJECT_ID",
            )
        }

    def tearDown(self):
        for k, v in self._saved.items():
            setattr(config, k, v)

    def test_falls_back_to_ee_credentials(self):
        # No GCS-specific creds; the EE service-account JSON must be used.
        config.GCS_SERVICE_ACCOUNT_INFO = ""
        config.GCS_SERVICE_ACCOUNT_JSON = None
        ee_info = {"type": "service_account", "project_id": "mahala-ee", "client_email": "x@y.iam"}
        config.GEE_SERVICE_ACCOUNT_INFO = json.dumps(ee_info)
        config.GEE_SERVICE_ACCOUNT_JSON = None
        config.EE_PROJECT_ID = "mahala-ee"

        fake_sa = mock.MagicMock()
        fake_storage = mock.MagicMock()

        def fake_import(name):
            if name == "google.oauth2.service_account":
                return fake_sa
            if name == "google.cloud.storage":
                return fake_storage
            raise ImportError(name)

        with mock.patch.object(gcs.importlib, "import_module", side_effect=fake_import):
            client, auth_mode = gcs.build_storage_client()

        self.assertEqual(auth_mode, "service_account")
        fake_sa.Credentials.from_service_account_info.assert_called_once()
        passed_info = fake_sa.Credentials.from_service_account_info.call_args.args[0]
        self.assertEqual(passed_info, ee_info)
        # Client is built scoped to the EE project.
        _, kwargs = fake_storage.Client.call_args
        self.assertEqual(kwargs.get("project"), "mahala-ee")

    def test_no_credentials_raises_value_error(self):
        config.GCS_SERVICE_ACCOUNT_INFO = ""
        config.GCS_SERVICE_ACCOUNT_JSON = None
        config.GEE_SERVICE_ACCOUNT_INFO = ""
        config.GEE_SERVICE_ACCOUNT_JSON = None
        with self.assertRaises(ValueError):
            gcs.build_storage_client()


if __name__ == "__main__":
    unittest.main()
