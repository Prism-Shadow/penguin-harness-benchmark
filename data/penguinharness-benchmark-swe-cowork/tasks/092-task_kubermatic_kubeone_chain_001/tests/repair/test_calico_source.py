import base64
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

from test_bootstrap_inputs import BUILDER
from test_bootstrap_recovery import Response


class CalicoSourceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.downloads = BUILDER.Downloads(self.root / "cache", attempts=1)
        self.content = b"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: calico-fixture\n"
        self.blob = hashlib.sha1(f"blob {len(self.content)}\0".encode() + self.content).hexdigest()
        self.commit = "3" * 40
        self.path = "manifests/calico-vxlan.yaml"
        self.raw = f"https://raw.githubusercontent.com/projectcalico/calico/{self.commit}/{self.path}"
        self.api = f"{BUILDER.CALICO_API}/git/blobs/{self.blob}"
        self.record = {"sha": self.blob, "size": len(self.content), "encoding": "base64",
                       "content": base64.encodebytes(self.content).decode()}
        self.payload = json.dumps(self.record).encode()
        self.calls = []
        self.addCleanup(patch.stopall)
        patch.object(BUILDER, "DOWNLOADS", self.downloads).start()

    def acquire(self):
        return BUILDER.calico_manifest(self.commit, self.path, self.blob)

    def test_blob_api_avoids_unavailable_raw_domain_and_reuses_verified_cache(self):
        def transport(request, timeout):
            self.assertEqual(request.full_url, self.api)
            self.assertLessEqual(timeout, 15)
            self.assertEqual(self.downloads.request_budget, 30)
            return Response([self.payload], url=self.api)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=transport) as opened:
            self.assertEqual(self.acquire(), (self.content, self.api))
            self.assertEqual(opened.call_count, 1)
        self.assertEqual(self.downloads.request_budget, 120)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("warm cache must be offline")):
            self.assertEqual(self.acquire(), (self.content, self.api))

    def test_legacy_raw_cache_is_checked_before_api_network(self):
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response([self.content], url=self.raw)):
            self.downloads.fetch(self.raw, BUILDER.MAX_BYTES)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("reuse previous verified bytes")):
            self.assertEqual(self.acquire(), (self.content, self.raw))

    def test_transport_failover_preserves_exact_commit_and_blob(self):
        for failure in (TimeoutError("API timeout"), urllib.error.HTTPError(self.api, 503, "unavailable", {}, None)):
            with self.subTest(failure=type(failure).__name__):
                def transport(request, timeout):
                    self.calls.append(request.full_url)
                    if request.full_url == self.api:
                        raise failure
                    self.assertEqual(request.full_url, self.raw)
                    return Response([self.content], url=self.raw)
                with tempfile.TemporaryDirectory(dir=self.root) as directory:
                    downloads = BUILDER.Downloads(Path(directory), attempts=1)
                    with patch.object(BUILDER, "DOWNLOADS", downloads), patch.object(
                            BUILDER.urllib.request, "urlopen", side_effect=transport):
                        self.assertEqual(self.acquire(), (self.content, self.raw))
                self.assertEqual(self.calls[-2:], [self.api, self.raw])
                self.assertEqual(downloads.request_budget, 120)

    def test_api_integrity_and_type_errors_never_fall_back(self):
        mutations = [
            {"sha": "0" * 40}, {"encoding": "utf-8"}, {"size": True},
            {"size": str(len(self.content))}, {"size": -1}, {"size": BUILDER.MAX_BYTES + 1},
            {"size": len(self.content) + 1}, {"content": 42}, {"content": "***"},
            {"content": base64.b64encode(b"x" * len(self.content)).decode()},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                record = dict(self.record, **mutation)
                with patch.object(BUILDER, "fetch", return_value=json.dumps(record).encode()) as fetch:
                    with self.assertRaises(ValueError):
                        self.acquire()
                    self.assertEqual(fetch.call_count, 1)
        for payload in (b"not JSON", b"[]"):
            with patch.object(BUILDER, "fetch", return_value=payload) as fetch:
                with self.assertRaises(ValueError):
                    self.acquire()
                self.assertEqual(fetch.call_count, 1)
        self.assertEqual(self.downloads.request_budget, 120)

    def test_raw_fallback_integrity_error_is_fatal(self):
        with patch.object(BUILDER, "fetch", side_effect=[TimeoutError("API"), self.content + b"changed"]) as fetch:
            with self.assertRaisesRegex(ValueError, "source Git blob"):
                self.acquire()
        self.assertEqual(fetch.call_count, 2)
        self.assertEqual(self.downloads.request_budget, 120)

    def test_corrupt_cache_and_self_consistent_wrong_blob_are_fatal(self):
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response([self.payload], url=self.api)):
            self.acquire()
        destination, receipt, partial = self.downloads.paths(self.api, None)
        corrupt = self.payload.replace(b'"base64"', b'"base65"')
        destination.write_bytes(corrupt)
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("no network on corruption")):
            with self.assertRaisesRegex(ValueError, "SHA256"):
                self.acquire()
            record = json.loads(receipt.read_text())
            record["sha256"] = hashlib.sha256(corrupt).hexdigest()
            BUILDER.atomic_json(receipt, record)
            with self.assertRaisesRegex(ValueError, "Git blob response"):
                self.acquire()

    def test_interrupted_blob_api_resumes_on_next_invocation(self):
        def interrupted(request, timeout):
            if request.full_url == self.api:
                return Response([self.payload[:19], TimeoutError("interrupted")], url=self.api)
            raise TimeoutError("raw domain unavailable")
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=interrupted):
            with self.assertRaises(TimeoutError):
                self.acquire()
        self.assertEqual(self.downloads.request_budget, 120)
        def resumed(request, timeout):
            self.assertEqual(request.full_url, self.api)
            self.assertEqual(request.get_header("Range"), "bytes=19-")
            return Response([self.payload[19:]], status=206, headers={
                "Content-Range": f"bytes 19-{len(self.payload)-1}/{len(self.payload)}"}, url=self.api)
        resumed_downloads = BUILDER.Downloads(self.root / "cache", attempts=1)
        with patch.object(BUILDER, "DOWNLOADS", resumed_downloads), patch.object(
                BUILDER.urllib.request, "urlopen", side_effect=resumed):
            self.assertEqual(self.acquire(), (self.content, self.api))

    def test_expired_shared_budget_blocks_both_routes_but_allows_verified_cache(self):
        self.downloads.deadline = 0
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("shared budget is exhausted")):
            with self.assertRaises(TimeoutError):
                self.acquire()
        fresh = BUILDER.Downloads(self.root / "cache", attempts=1)
        with patch.object(BUILDER, "DOWNLOADS", fresh), patch.object(
                BUILDER.urllib.request, "urlopen", return_value=Response([self.payload], url=self.api)):
            self.acquire()
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("cached bytes need no network")):
            self.assertEqual(self.acquire(), (self.content, self.api))

    def test_https_redirect_downgrade_never_falls_back(self):
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response(
                [self.payload], url="http://api.github.com/insecure")) as opened:
            with self.assertRaisesRegex(ValueError, "HTTPS"):
                self.acquire()
        self.assertEqual(opened.call_count, 1)


if __name__ == "__main__":
    unittest.main()
