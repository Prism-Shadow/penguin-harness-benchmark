import hashlib
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from test_bootstrap_inputs import BUILDER
from test_bootstrap_recovery import Response


class ReleaseTransportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin_dir = self.root / "bin"
        self.bin_dir.mkdir()
        self.api = "https://api.github.com/repos/kubernetes-sigs/kustomize"
        self.base = "https://github.com/kubernetes-sigs/kustomize/releases/download/kustomize%2Fv5.3.0"
        self.metadata_url = self.api + "/releases/tags/kustomize%2Fv5.3.0"
        self.filename = "kustomize_v5.3.0_linux_amd64.tar.gz"
        stream = io.BytesIO()
        with tarfile.open(fileobj=stream, mode="w:gz") as archive:
            member = tarfile.TarInfo("kustomize")
            content = b"synthetic transport fixture, not an upstream executable\n"
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
        self.archive = stream.getvalue()
        self.payloads = {
            self.filename: self.archive,
            "checksums.txt": (hashlib.sha256(self.archive).hexdigest() + "  " + self.filename + "\n").encode(),
        }
        self.metadata = {"tag_name": "kustomize/v5.3.0", "draft": False, "prerelease": False, "assets": []}
        for identifier, (name, content) in enumerate(self.payloads.items(), 1):
            self.metadata["assets"].append({
                "id": identifier, "name": name, "size": len(content),
                "url": f"{self.api}/releases/assets/{identifier}",
                "browser_download_url": f"{self.base}/{name}",
                "digest": "sha256:" + hashlib.sha256(content).hexdigest(),
            })
        self.calls = []
        self.downloads = BUILDER.Downloads(self.root / "cache", budget=30, attempts=1)

    def open(self, request, timeout):
        self.calls.append(request)
        self.assertGreater(timeout, 0)
        self.assertLessEqual(timeout, 15)
        if request.full_url == self.metadata_url:
            content = json.dumps(self.metadata).encode()
        else:
            self.assertEqual(request.get_header("Accept"), "application/octet-stream")
            asset = next(entry for entry in self.metadata["assets"] if entry["url"] == request.full_url)
            content = self.payloads[asset["name"]]
        return Response([content], headers={"Content-Length": str(len(content))}, url=request.full_url)

    def install(self):
        return BUILDER.install_binary(self.root, self.bin_dir, "kustomize",
            f"{self.base}/{self.filename}", self.base + "/checksums.txt", "kustomize")

    def test_exact_release_api_installs_when_browser_host_is_unreachable(self):
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=self.open):
            receipt = self.install()
        self.assertEqual(len(self.calls), 3)
        self.assertTrue(all(request.full_url.startswith(self.api) for request in self.calls))
        self.assertEqual(receipt["sha256"], hashlib.sha256(self.archive).hexdigest())
        self.assertEqual(receipt["download_source"], self.api + "/releases/assets/1")
        self.assertEqual(receipt["checksum_download_source"], self.api + "/releases/assets/2")
        self.assertEqual((self.bin_dir / "kustomize").stat().st_mode & 0o777, 0o755)
        with patch.object(BUILDER, "fetch", side_effect=AssertionError("must reuse checked installation")):
            self.assertEqual(self.install(), receipt)
        (self.bin_dir / "kustomize").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "verified checkpoint"):
            self.install()

    def test_fresh_process_reuses_api_cache_without_network(self):
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=self.open):
            self.install()
        with patch.object(BUILDER, "DOWNLOADS", BUILDER.Downloads(self.root / "cache")), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=AssertionError("offline cache reuse")):
            content, source = BUILDER.release_asset(f"{self.base}/{self.filename}")
        self.assertEqual(content, self.archive)
        self.assertEqual(source, self.api + "/releases/assets/1")

    def test_legacy_verified_browser_cache_needs_no_api(self):
        url = f"{self.base}/{self.filename}"
        key = hashlib.sha256(url.encode()).hexdigest()
        (self.downloads.root / key).write_bytes(self.archive)
        (self.downloads.root / (key + ".json")).write_text(json.dumps({
            "url": url, "size": len(self.archive), "sha256": hashlib.sha256(self.archive).hexdigest()}))
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=AssertionError("verified legacy cache")):
            self.assertEqual(BUILDER.release_asset(url), (self.archive, url))

    def test_api_unavailable_uses_official_browser_asset(self):
        url = f"{self.base}/{self.filename}"
        def transport(request, timeout):
            self.calls.append(request)
            if request.full_url == self.metadata_url:
                raise urllib.error.URLError("API unavailable")
            self.assertEqual(request.full_url, url)
            return Response([self.archive], url=url)
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=transport):
            self.assertEqual(BUILDER.release_asset(url), (self.archive, url))
        self.assertEqual(len(self.calls), 2)

    def test_wrong_release_identity_does_not_fall_back(self):
        original = json.dumps(self.metadata)
        mutations = [
            lambda value: value.update(tag_name="kustomize/v5.4.0"),
            lambda value: value.update(draft=True),
            lambda value: value.update(prerelease=True),
            lambda value: value["assets"].append(value["assets"][0]),
            lambda value: value["assets"][0].update(url="https://example.invalid/asset"),
            lambda value: value["assets"][0].update(browser_download_url=self.base + "/wrong.tar.gz"),
            lambda value: value["assets"][0].update(size=BUILDER.MAX_BYTES + 1),
        ]
        for mutate in mutations:
            with self.subTest(mutation=mutate):
                metadata = json.loads(original)
                mutate(metadata)
                with patch.object(BUILDER, "fetch", return_value=json.dumps(metadata).encode()) as fetch:
                    with self.assertRaises(ValueError):
                        BUILDER.release_asset(f"{self.base}/{self.filename}")
                self.assertEqual(fetch.call_count, 1)

    def test_matching_asset_metadata_cannot_override_release_checksum(self):
        self.payloads["checksums.txt"] = ("0" * 64 + "  " + self.filename + "\n").encode()
        self.metadata["assets"][1]["digest"] = "sha256:" + hashlib.sha256(self.payloads["checksums.txt"]).hexdigest()
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=self.open):
            with self.assertRaisesRegex(ValueError, "upstream SHA256"):
                self.install()
        self.assertFalse((self.bin_dir / "kustomize").exists())

    def test_asset_digest_and_size_are_checked(self):
        for field, value in [("digest", "sha256:" + "0" * 64), ("size", len(self.archive) + 1)]:
            with self.subTest(field=field):
                asset = self.metadata["assets"][0].copy()
                self.metadata["assets"][0][field] = value
                with patch.object(BUILDER, "fetch", side_effect=[json.dumps(self.metadata).encode(), self.archive]):
                    with self.assertRaises(ValueError):
                        BUILDER.release_asset(f"{self.base}/{self.filename}")
                self.metadata["assets"][0] = asset

    def test_binary_and_json_cache_representations_cannot_collide(self):
        url = self.api + "/releases/assets/1"
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response([b'{"metadata":true}'])):
            self.downloads.fetch(url, BUILDER.MAX_BYTES)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=self.open):
            content = self.downloads.fetch(url, BUILDER.MAX_BYTES, "application/octet-stream")
        self.assertEqual(content, self.archive)
        self.assertEqual(len(self.calls), 1)

    def test_interrupted_binary_resumes_with_same_accept_and_range(self):
        url = self.api + "/releases/assets/1"
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response(
                [self.archive[:8], TimeoutError("interrupted")], url=url)):
            with self.assertRaises(TimeoutError):
                self.downloads.fetch(url, BUILDER.MAX_BYTES, "application/octet-stream")
        def resumed(request, timeout):
            self.assertEqual(request.get_header("Range"), "bytes=8-")
            self.assertEqual(request.get_header("Accept"), "application/octet-stream")
            return Response([self.archive[8:]], status=206, headers={
                "Content-Range": f"bytes 8-{len(self.archive)-1}/{len(self.archive)}"}, url=url)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=resumed):
            content = BUILDER.Downloads(self.root / "cache").fetch(url, BUILDER.MAX_BYTES, "application/octet-stream")
        self.assertEqual(content, self.archive)

    def test_expired_shared_budget_prevents_both_network_routes(self):
        self.downloads.deadline = 0
        with patch.object(BUILDER, "DOWNLOADS", self.downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=AssertionError("budget exhausted")):
            with self.assertRaises(TimeoutError):
                BUILDER.release_asset(f"{self.base}/{self.filename}")


if __name__ == "__main__":
    unittest.main()
