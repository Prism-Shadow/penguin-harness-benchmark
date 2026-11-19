import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import ssl
import stat
import tempfile
import unittest
from unittest import mock
import urllib.error
import zipfile


MODULE_PATH = Path(__file__).resolve().parents[2] / "environment/fetch-premake-source.py"
SPEC = importlib.util.spec_from_file_location("premake_source", MODULE_PATH)
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)


def archive_bytes(prefix=""):
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(prefix + "Bootstrap.mak", "linux:\n\t@echo fixture-only\n")
        executable = zipfile.ZipInfo(prefix + "run.sh")
        executable.external_attr = (stat.S_IFREG | 0o755) << 16
        archive.writestr(executable, "#!/bin/sh\nexit 0\n")
    return output.getvalue()


def release_record(payload):
    return {
        "tag_name": SOURCE.TAG,
        "draft": False,
        "id": 101,
        "assets": [{
            "id": 202,
            "name": SOURCE.ASSET_NAME,
            "browser_download_url": SOURCE.ASSET_URL,
            "size": len(payload),
            "digest": "sha256:" + hashlib.sha256(payload).hexdigest(),
        }],
    }


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.destination = self.root / "source"

    def acquire(self, payload, record=None, pin=None, served_payload=None):
        metadata = json.dumps(record or release_record(payload)).encode()
        responses = [io.BytesIO(metadata), io.BytesIO(payload if served_payload is None else served_payload)]
        with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=responses) as opener:
            with contextlib.redirect_stdout(io.StringIO()):
                SOURCE.acquire(self.destination, pin)
            self.assertEqual(opener.call_count, 2)
            self.assertEqual(opener.call_args_list[0].args[0].get_header("Accept"), "application/vnd.github+json")
        return json.loads((self.destination / ".source-provenance.json").read_text())

    def test_root_and_single_directory_archives(self):
        for prefix in ("", "premake-release/"):
            with self.subTest(prefix=prefix):
                self.destination = self.root / ("nested" if prefix else "flat")
                payload = archive_bytes(prefix)
                record = self.acquire(payload)
                self.assertEqual(record["archive_sha256"], hashlib.sha256(payload).hexdigest())
                self.assertEqual(record["archive_sha256"], record["published_sha256"])
                self.assertFalse(record["independently_pinned"])
                self.assertEqual((self.destination / "run.sh").stat().st_mode & 0o777, 0o755)
                self.assertTrue((self.destination / "Bootstrap.mak").is_file())
        self.assertEqual(sorted(path.name for path in self.root.iterdir()), ["flat", "nested"])

    def test_matching_independent_pin(self):
        payload = archive_bytes()
        self.assertTrue(self.acquire(payload, pin=hashlib.sha256(payload).hexdigest())["independently_pinned"])

    def test_mismatched_pin_fails_before_source_download(self):
        payload = archive_bytes()
        with mock.patch.object(SOURCE.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(release_record(payload)).encode())) as opener:
            with self.assertRaisesRegex(ValueError, "independent pin"):
                SOURCE.acquire(self.destination, "0" * 64)
            self.assertEqual(opener.call_count, 1)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_corrupt_payload_does_not_publish_source(self):
        payload = archive_bytes()
        with self.assertRaisesRegex(ValueError, "SHA256 mismatch"):
            self.acquire(payload, served_payload=b"x" * len(payload))
        self.assertEqual(list(self.root.iterdir()), [])

    def test_release_identity_size_and_digest_fail_closed(self):
        for field, value in (("name", "other.zip"), ("browser_download_url", "https://example.invalid/source.zip"),
                             ("digest", None), ("size", 0), ("size", SOURCE.MAX_ARCHIVE_BYTES + 1)):
            with self.subTest(field=field, value=value):
                release = release_record(archive_bytes())
                release["assets"][0][field] = value
                with self.assertRaises(ValueError):
                    SOURCE.select_asset(release)
        for field, value in (("tag_name", "v9"), ("draft", True), ("assets", [])):
            release = release_record(archive_bytes())
            release[field] = value
            with self.assertRaises(ValueError):
                SOURCE.select_asset(release)
        release = release_record(archive_bytes())
        release["assets"] *= 2
        with self.assertRaises(ValueError):
            SOURCE.select_asset(release)

    def test_unsafe_archive_paths_and_links(self):
        for filename, mode in (("../outside", stat.S_IFREG), ("/absolute", stat.S_IFREG),
                               ("path\\escape", stat.S_IFREG), ("C:escape", stat.S_IFREG),
                               ("link", stat.S_IFLNK), ("pipe", stat.S_IFIFO)):
            with self.subTest(filename=filename):
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w") as archive:
                    archive.writestr("Bootstrap.mak", "fixture")
                    info = zipfile.ZipInfo(filename)
                    info.external_attr = (mode | 0o777) << 16
                    archive.writestr(info, "outside")
                with self.assertRaises(ValueError):
                    self.acquire(output.getvalue())
                self.assertEqual(list(self.root.iterdir()), [])

    def test_expansion_limit_and_missing_bootstrap(self):
        with mock.patch.object(SOURCE, "MAX_EXPANDED_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "expands"):
                self.acquire(archive_bytes())
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            archive.writestr("README", "not source")
        with self.assertRaisesRegex(ValueError, "Bootstrap.mak"):
            self.acquire(output.getvalue())
        self.assertEqual(list(self.root.iterdir()), [])

    def test_existing_destination_is_never_overwritten(self):
        self.destination.mkdir()
        marker = self.destination / "keep"
        marker.write_text("original")
        with self.assertRaisesRegex(ValueError, "must not exist"):
            SOURCE.acquire(self.destination)
        self.assertEqual(marker.read_text(), "original")

    def test_transient_transport_retries(self):
        failures = [urllib.error.URLError("TLS terminated"), urllib.error.HTTPError(SOURCE.ASSET_URL, 503, "temporary", {}, None)]
        responses = failures + [io.BytesIO(b"complete")]
        with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=responses) as opener, mock.patch.object(SOURCE.time, "sleep") as sleep:
            SOURCE.download(SOURCE.ASSET_URL, self.destination, 8)
            self.assertEqual(opener.call_count, 3)
            self.assertEqual([call.args[0] for call in sleep.call_args_list], [1, 2])
        self.assertEqual(self.destination.read_bytes(), b"complete")

    def test_partial_transfer_is_reset_before_retry(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [b"partial", ConnectionResetError("reset")]
        with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=[response, io.BytesIO(b"complete")]), mock.patch.object(SOURCE.time, "sleep"):
            SOURCE.download(SOURCE.ASSET_URL, self.destination, 8)
        self.assertEqual(self.destination.read_bytes(), b"complete")

    def test_tls_eof_during_stream_is_retried(self):
        response = mock.MagicMock()
        response.__enter__.return_value = response
        response.read.side_effect = [b"part", ssl.SSLEOFError("TLS terminated")]
        with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=[response, io.BytesIO(b"complete")]), mock.patch.object(SOURCE.time, "sleep"):
            SOURCE.download(SOURCE.ASSET_URL, self.destination, 8)
        self.assertEqual(self.destination.read_bytes(), b"complete")

    def test_short_transfer_is_retried(self):
        with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=[io.BytesIO(b"part"), io.BytesIO(b"complete")]) as opener, mock.patch.object(SOURCE.time, "sleep"):
            SOURCE.download(SOURCE.ASSET_URL, self.destination, 8, expected_size=8)
            self.assertEqual(opener.call_count, 2)
        self.assertEqual(self.destination.read_bytes(), b"complete")

    def test_retry_budget_and_permanent_http_failure(self):
        for error, count in ((urllib.error.URLError("offline"), 4),
                             (urllib.error.HTTPError(SOURCE.ASSET_URL, 404, "missing", {}, None), 1)):
            with self.subTest(count=count):
                with mock.patch.object(SOURCE.urllib.request, "urlopen", side_effect=error) as opener, mock.patch.object(SOURCE.time, "sleep"):
                    with self.assertRaises(urllib.error.URLError):
                        SOURCE.download(SOURCE.ASSET_URL, self.destination, 100)
                    self.assertEqual(opener.call_count, count)
                self.assertFalse(self.destination.exists())

    def test_transfer_size_limit(self):
        with mock.patch.object(SOURCE.urllib.request, "urlopen", return_value=io.BytesIO(b"oversize")):
            with self.assertRaisesRegex(ValueError, "size limit"):
                SOURCE.download(SOURCE.ASSET_URL, self.destination, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
