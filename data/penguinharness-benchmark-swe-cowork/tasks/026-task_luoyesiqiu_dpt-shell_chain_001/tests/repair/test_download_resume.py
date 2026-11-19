import hashlib
import http.client
import importlib.util
import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("resumable_recipe", ROOT / "environment/build-inputs/acquire.py")
RECIPE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RECIPE)
URL = "https://dl.google.com/android/repository/fixed-version.zip"
DATA = b"first portion\x00second portion\xfffinal portion"
CHECKSUM = hashlib.sha256(DATA).hexdigest()


class Response(io.BytesIO):
    def __init__(self, data, status=200, headers=None, interrupt=False):
        super().__init__(data)
        self.status = status
        self.url = URL
        self.headers = headers if headers is not None else {"Content-Length": str(len(data)), "ETag": '"release-1"'}
        self.interrupt = interrupt

    def read1(self, count):
        if self.interrupt and self.tell():
            raise TimeoutError("fixture transport interrupted")
        return super().read1(count)


def partial_response():
    return Response(DATA[:13], headers={"Content-Length": str(len(DATA)), "ETag": '"release-1"'}, interrupt=True)


def resumed_response(offset=13):
    return Response(DATA[offset:], status=206, headers={
        "Content-Range": f"bytes {offset}-{len(DATA) - 1}/{len(DATA)}",
        "Content-Length": str(len(DATA) - offset), "ETag": '"release-1"'})


class DownloadResumeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.sleep = patch.object(RECIPE.time, "sleep")
        self.sleep.start()
        self.addCleanup(self.sleep.stop)

    def interrupt(self):
        downloads = RECIPE.Downloads(self.root, attempts=1)
        with patch.object(downloads.opener, "open", return_value=partial_response()):
            with self.assertRaisesRegex(RECIPE.RecipeError, "budget exhausted"):
                downloads.fetch("sdk.zip", URL, CHECKSUM)
        self.assertEqual((downloads.root / "sdk.zip.part").read_bytes(), DATA[:13])
        self.assertFalse((downloads.root / "sdk.zip").exists())
        self.assertFalse(downloads.receipt.exists())

    def test_restart_resumes_exact_bytes_and_reuses_verified_cache_offline(self):
        self.interrupt()
        restarted = RECIPE.Downloads(self.root)
        with patch.object(restarted.opener, "open", return_value=resumed_response()) as opening:
            result = restarted.fetch("sdk.zip", URL, CHECKSUM)
        request = opening.call_args.args[0]
        self.assertEqual(request.get_header("Range"), "bytes=13-")
        self.assertEqual(request.get_header("If-range"), '"release-1"')
        self.assertEqual(result.read_bytes(), DATA)
        self.assertFalse((restarted.root / "sdk.zip.part.json").exists())
        lock = json.loads(restarted.receipt.read_text())
        self.assertEqual(lock["sdk.zip"]["sha256"], CHECKSUM)
        replay = RECIPE.Downloads(self.root, lock)
        with patch.object(replay.opener, "open", side_effect=AssertionError("network on verified hit")):
            self.assertEqual(replay.fetch("sdk.zip", URL, CHECKSUM), result)

    def test_retry_in_same_invocation_preserves_partial_bytes(self):
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", side_effect=[partial_response(), resumed_response()]) as opening:
            self.assertEqual(downloads.fetch("sdk.zip", URL, CHECKSUM).read_bytes(), DATA)
        self.assertEqual(opening.call_count, 2)
        self.assertEqual(opening.call_args.args[0].get_header("Range"), "bytes=13-")

    def test_range_ignored_restarts_instead_of_appending(self):
        self.interrupt()
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=Response(DATA)):
            self.assertEqual(downloads.fetch("sdk.zip", URL, CHECKSUM).read_bytes(), DATA)

    def test_short_eof_is_not_promoted_and_is_resumed(self):
        downloads = RECIPE.Downloads(self.root)
        short = partial_response()
        short.interrupt = False
        with patch.object(downloads.opener, "open", side_effect=[short, resumed_response()]):
            self.assertEqual(downloads.fetch("sdk.zip", URL, CHECKSUM).read_bytes(), DATA)

    def test_real_http_parser_streams_partial_body_into_resume(self):
        class SocketFixture:
            def makefile(self, mode):
                return io.BytesIO(b"HTTP/1.1 200 OK\r\nContent-Length: " + str(len(DATA)).encode() +
                                  b'\r\nETag: "release-1"\r\n\r\n' + DATA[:13])

        response = http.client.HTTPResponse(SocketFixture())
        response.begin()
        response.url = URL
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", side_effect=[response, resumed_response()]):
            self.assertEqual(downloads.fetch("sdk.zip", URL, CHECKSUM).read_bytes(), DATA)

    def test_cached_digest_still_must_match_current_official_digest(self):
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=Response(DATA)):
            downloads.fetch("sdk.zip", URL, CHECKSUM)
        replay = RECIPE.Downloads(self.root)
        with patch.object(replay.opener, "open", side_effect=AssertionError("unexpected fetch")):
            with self.assertRaisesRegex(RECIPE.RecipeError, "official checksum mismatch"):
                replay.fetch("sdk.zip", URL, "0" * 64)

    def test_nontransient_http_error_does_not_retry(self):
        downloads = RECIPE.Downloads(self.root)
        error = urllib.error.HTTPError(URL, 404, "not found", {}, None)
        with patch.object(downloads.opener, "open", side_effect=error) as opening:
            with self.assertRaisesRegex(RECIPE.RecipeError, "HTTP error 404"):
                downloads.fetch("sdk.zip", URL, CHECKSUM)
        self.assertEqual(opening.call_count, 1)

    def test_invalid_range_or_changed_validator_cannot_poison_cache(self):
        for header, value in (("Content-Range", "bytes 0-1/2"), ("ETag", '"another-release"'),
                              ("Content-Range", "garbage"), ("Content-Length", "1"),
                              ("Content-Encoding", "gzip")):
            with self.subTest(header=header, value=value):
                self.interrupt()
                response = resumed_response()
                response.headers[header] = value
                downloads = RECIPE.Downloads(self.root)
                with patch.object(downloads.opener, "open", return_value=response):
                    with self.assertRaises(RECIPE.RecipeError):
                        downloads.fetch("sdk.zip", URL, CHECKSUM)
                self.assertFalse((downloads.root / "sdk.zip").exists())
                self.assertFalse((downloads.root / "sdk.zip.part").exists())
                self.assertFalse(downloads.receipt.exists())

    def test_checksum_failure_never_creates_success_receipt(self):
        self.interrupt()
        response = resumed_response()
        response.getbuffer()[-1] ^= 1
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=response):
            with self.assertRaisesRegex(RECIPE.RecipeError, "official checksum mismatch"):
                downloads.fetch("sdk.zip", URL, CHECKSUM)
        self.assertFalse(downloads.receipt.exists())
        self.assertFalse((downloads.root / "sdk.zip").exists())
        self.assertFalse((downloads.root / "sdk.zip.part").exists())

    def test_official_sha1_and_locked_sha256_are_both_required(self):
        lock = {"sdk.zip": {"url": URL, "sha256": "0" * 64}}
        downloads = RECIPE.Downloads(self.root, lock)
        with patch.object(downloads.opener, "open", return_value=Response(DATA)):
            with self.assertRaisesRegex(RECIPE.RecipeError, "locked checksum mismatch"):
                downloads.fetch("sdk.zip", URL, hashlib.sha1(DATA).hexdigest(), "sha1")
        self.assertFalse(downloads.receipt.exists())

    def test_failed_range_then_full_download_is_bounded(self):
        self.interrupt()
        downloads = RECIPE.Downloads(self.root)
        error = urllib.error.HTTPError(URL, 416, "range unsatisfiable", {}, None)
        with patch.object(downloads.opener, "open", side_effect=[error, Response(DATA)]) as opening:
            self.assertEqual(downloads.fetch("sdk.zip", URL, CHECKSUM).read_bytes(), DATA)
        self.assertIsNone(opening.call_args.args[0].get_header("Range"))

    def test_retry_count_and_socket_wait_are_bounded(self):
        downloads = RECIPE.Downloads(self.root, attempts=3, deadline=60, idle_timeout=7)
        with patch.object(downloads.opener, "open", side_effect=TimeoutError("offline")) as opening:
            with self.assertRaisesRegex(RECIPE.RecipeError, "budget exhausted"):
                downloads.fetch("sdk.zip", URL, CHECKSUM)
        self.assertEqual(opening.call_count, 3)
        self.assertTrue(all(call.kwargs["timeout"] <= 7 for call in opening.call_args_list))

    def test_budget_cannot_be_disabled_or_expanded(self):
        for options in ({"deadline": 0}, {"deadline": float("inf")}, {"deadline": float("nan")},
                        {"deadline": 601}, {"attempts": 5}, {"idle_timeout": 16}):
            with self.subTest(options=options), self.assertRaisesRegex(RECIPE.RecipeError, "invalid download budget"):
                RECIPE.Downloads(self.root, **options)

    def test_slow_trickle_cannot_reset_wall_clock_budget(self):
        downloads = RECIPE.Downloads(self.root, attempts=4, deadline=2)
        clock = iter([0, 0, 1, 3, 4, 5])
        with patch.object(RECIPE.time, "monotonic", side_effect=lambda: next(clock)), \
                patch.object(downloads.opener, "open", return_value=Response(DATA)) as opening:
            with self.assertRaisesRegex(RECIPE.RecipeError, "wall-clock"):
                downloads.fetch("sdk.zip", URL, CHECKSUM)
        self.assertEqual(opening.call_count, 1)
        self.assertFalse(downloads.receipt.exists())

    def test_changed_release_restarts_without_reusing_partial(self):
        self.interrupt()
        updated = DATA + b"new revision"
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=Response(updated)) as opening:
            result = downloads.fetch("sdk.zip", URL, hashlib.sha256(updated).hexdigest())
        self.assertIsNone(opening.call_args.args[0].get_header("Range"))
        self.assertEqual(result.read_bytes(), updated)

    def test_cache_tampering_symlinks_and_unsafe_names_are_rejected(self):
        downloads = RECIPE.Downloads(self.root)
        with patch.object(downloads.opener, "open", return_value=Response(DATA)):
            downloaded = downloads.fetch("sdk.zip", URL, CHECKSUM)
        downloaded.write_bytes(b"corrupt cache")
        with self.assertRaisesRegex(RECIPE.RecipeError, "changed cached"):
            downloads.fetch("sdk.zip", URL, CHECKSUM)
        for name in (".", "..", "../other"):
            with self.assertRaisesRegex(RECIPE.RecipeError, "unsafe download name"):
                downloads.fetch(name, URL, CHECKSUM)
        downloaded.unlink()
        downloaded.symlink_to(self.root / "outside")
        with self.assertRaisesRegex(RECIPE.RecipeError, "symlink"):
            RECIPE.Downloads(self.root)


if __name__ == "__main__":
    unittest.main()
