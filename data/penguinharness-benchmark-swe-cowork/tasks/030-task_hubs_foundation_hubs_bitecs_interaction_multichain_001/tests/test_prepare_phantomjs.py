import base64
import contextlib
import hashlib
import importlib.util
import io
import json
import subprocess
import tarfile
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


SOURCE = Path(__file__).resolve().parents[1] / "environment/runtime/prepare-phantomjs.py"
SPEC = importlib.util.spec_from_file_location("prepare_phantomjs", SOURCE)
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def write_archive(path, mode, files):
    with tarfile.open(path, mode) as archive:
        for name, content in files.items():
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))


def seed_cache(cache, version="2.1.1", checksum_override=None, member_name=None):
    cache.mkdir(parents=True, exist_ok=True)
    binary_archive = cache / PREPARE.ARCHIVE_NAME
    write_archive(binary_archive, "w:bz2", {
        member_name or "phantomjs-2.1.1-linux-x86_64/bin/phantomjs":
        f"#!/bin/sh\nprintf '%s\\n' '{version}'\n".encode()})
    checksum = checksum_override or hashlib.sha256(binary_archive.read_bytes()).hexdigest()
    package = cache / "phantomjs-prebuilt-2.1.16.tgz"
    write_archive(package, "w:gz", {
        "package/package.json": b'{"name":"phantomjs-prebuilt","version":"2.1.16"}',
        "package/lib/phantomjs.js": b"exports.version = '2.1.1'\n",
        "package/lib/util.js": ("downloadUrl += 'linux-x86_64.tar.bz2'\nchecksum = '" + checksum + "'\n").encode()})
    integrity = "sha512-" + base64.b64encode(hashlib.sha512(package.read_bytes()).digest()).decode()
    metadata = {"name": "phantomjs-prebuilt", "version": "2.1.16",
                "dist": {"tarball": PREPARE.PACKAGE_URL, "integrity": integrity}}
    (cache / "package-metadata.json").write_text(json.dumps(metadata))
    return checksum


class PinnedAcquisitionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.cache = self.root / "cache"
        self.destination = self.root / "tools"

    def prepare(self, offline=True, fetcher=None):
        fetcher = fetcher or mock.Mock(side_effect=AssertionError("Unexpected network access"))
        with contextlib.redirect_stdout(io.StringIO()):
            PREPARE.prepare(self.cache, self.destination, offline, fetcher)
        return json.loads((self.destination / "acquisition.json").read_text())

    def test_offline_cache_verifies_archive_and_runs_extracted_binary(self):
        expected = seed_cache(self.cache)
        receipt = self.prepare()
        self.assertEqual(receipt["archive_sha256"], expected)
        self.assertEqual(receipt["binary_version"], "2.1.1")
        binary = self.destination / "bin/phantomjs"
        self.assertEqual(subprocess.check_output([str(binary), "--version"], text=True), "2.1.1\n")
        self.assertEqual(receipt["binary_sha256"], hashlib.sha256(binary.read_bytes()).hexdigest())

    def test_cold_acquisition_uses_only_fixed_urls_and_preserves_receipt(self):
        upstream = self.root / "upstream"
        seed_cache(upstream)
        content = {PREPARE.METADATA_URL: upstream / "package-metadata.json",
                   PREPARE.PACKAGE_URL: upstream / "phantomjs-prebuilt-2.1.16.tgz",
                   PREPARE.ARCHIVE_URL: upstream / PREPARE.ARCHIVE_NAME}
        requested = []

        def fetcher(url, destination, limit):
            requested.append(url)
            payload = content[url].read_bytes()
            self.assertLess(len(payload), limit)
            destination.write_bytes(payload)

        receipt = self.prepare(offline=False, fetcher=fetcher)
        self.assertEqual(requested, list(content))
        self.assertEqual(self.prepare(), receipt)

    def test_missing_offline_input_never_falls_back_to_network(self):
        with self.assertRaisesRegex(FileNotFoundError, "Offline dependency cache miss"):
            self.prepare()

    def test_corrupted_package_is_rejected_before_execution(self):
        seed_cache(self.cache)
        (self.cache / "phantomjs-prebuilt-2.1.16.tgz").write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "SHA512 integrity mismatch"):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_corrupted_binary_archive_is_rejected_before_execution(self):
        seed_cache(self.cache)
        (self.cache / PREPARE.ARCHIVE_NAME).write_bytes(b"corrupt")
        with self.assertRaisesRegex(ValueError, "archive SHA256 mismatch"):
            self.prepare()
        self.assertFalse(self.destination.exists())

    def test_checksum_from_package_is_mandatory(self):
        seed_cache(self.cache, checksum_override="missing")
        with self.assertRaisesRegex(ValueError, "checksum layout"):
            self.prepare()

    def test_wrong_binary_version_is_not_published(self):
        seed_cache(self.cache, version="3.0.0")
        with self.assertRaisesRegex(ValueError, "binary version mismatch"):
            self.prepare()
        self.assertFalse((self.destination / "bin/phantomjs").exists())
        self.assertFalse((self.destination / "acquisition.json").exists())

    def test_traversal_member_is_not_extracted(self):
        seed_cache(self.cache, member_name="../escaped")
        with self.assertRaises(KeyError):
            self.prepare()
        self.assertFalse((self.root / "escaped").exists())

    def test_unexpected_metadata_identity_url_or_hash_is_rejected(self):
        for field, value in (("version", "2.1.17"), ("tarball", "http://untrusted/package.tgz"),
                             ("integrity", "sha1-old")):
            with self.subTest(field=field):
                seed_cache(self.cache)
                path = self.cache / "package-metadata.json"
                metadata = json.loads(path.read_text())
                target = metadata if field == "version" else metadata["dist"]
                target[field] = value
                path.write_text(json.dumps(metadata))
                with self.assertRaises(ValueError):
                    self.prepare()

    def test_fetch_retries_transient_errors_with_bounded_attempts(self):
        self.cache.mkdir()
        destination = self.cache / "download"
        response = io.BytesIO(b"payload")
        response.geturl = lambda: PREPARE.PACKAGE_URL
        with mock.patch.object(PREPARE.urllib.request, "urlopen", side_effect=[
                urllib.error.URLError("socket hang up"), response]) as request, \
                mock.patch.object(PREPARE.time, "sleep") as sleep, contextlib.redirect_stdout(io.StringIO()):
            PREPARE.fetch(PREPARE.PACKAGE_URL, destination, 100)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(1)
        self.assertEqual(destination.read_bytes(), b"payload")
        self.assertFalse(destination.with_suffix(".part").exists())
        destination.unlink()
        with mock.patch.object(PREPARE.urllib.request, "urlopen", side_effect=urllib.error.URLError("DNS")) as request, \
                mock.patch.object(PREPARE.time, "sleep"), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(urllib.error.URLError):
                PREPARE.fetch(PREPARE.PACKAGE_URL, destination, 100)
        self.assertEqual(request.call_count, 3)
        self.assertFalse(destination.exists())

    def test_fetch_does_not_retry_404_or_accept_http_redirect(self):
        self.cache.mkdir()
        destination = self.cache / "download"
        error = urllib.error.HTTPError(PREPARE.PACKAGE_URL, 404, "missing", {}, None)
        with mock.patch.object(PREPARE.urllib.request, "urlopen", side_effect=error) as request, \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaises(urllib.error.HTTPError):
                PREPARE.fetch(PREPARE.PACKAGE_URL, destination, 100)
        self.assertEqual(request.call_count, 1)
        response = io.BytesIO(b"payload")
        response.geturl = lambda: "http://untrusted/package.tgz"
        with mock.patch.object(PREPARE.urllib.request, "urlopen", return_value=response), \
                contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(ValueError, "away from HTTPS"):
                PREPARE.fetch(PREPARE.PACKAGE_URL, destination, 100)
        self.assertFalse(destination.exists())


if __name__ == "__main__":
    unittest.main()
