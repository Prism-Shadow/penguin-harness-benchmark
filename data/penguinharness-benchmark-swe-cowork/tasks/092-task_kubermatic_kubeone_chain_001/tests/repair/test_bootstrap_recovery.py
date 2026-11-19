import base64
import csv
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error
import zipfile

import test_bootstrap_inputs
from test_bootstrap_inputs import BUILDER


class Response:
    def __init__(self, chunks, status=200, headers=None, url="https://example.invalid/archive"):
        self.chunks = iter(chunks)
        self.status = status
        self.headers = headers or {}
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def geturl(self):
        return self.url

    def read1(self, size):
        chunk = next(self.chunks, b"")
        if isinstance(chunk, Exception):
            raise chunk
        return chunk


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.url = "https://example.invalid/archive"

    def wheel(self, extra=None, corrupt_record=False, tag=None):
        prefix = "PyYAML-6.0.2.dist-info/"
        files = {
            "yaml/__init__.py": b"__version__ = '6.0.2'\n",
            prefix + "METADATA": b"Metadata-Version: 2.1\nName: PyYAML\nVersion: 6.0.2\n",
            prefix + "WHEEL": ("Wheel-Version: 1.0\nRoot-Is-Purelib: false\nTag: "
                               + (tag or BUILDER.supported_yaml_tags()[0]) + "\n").encode(),
        }
        files.update(extra or {})
        record = io.StringIO()
        writer = csv.writer(record)
        for name, content in files.items():
            digest = base64.urlsafe_b64encode(hashlib.sha256(content).digest()).decode().rstrip("=")
            writer.writerow([name, "sha256=" + ("invalid" if corrupt_record else digest), len(content)])
        writer.writerow([prefix + "RECORD", "", ""])
        files[prefix + "RECORD"] = record.getvalue().encode()
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, content in files.items():
                archive.writestr(name, content)
        return output.getvalue()

    def test_install_and_resume_in_actual_pip_free_python(self):
        content = self.wheel()
        tag = BUILDER.supported_yaml_tags()[0]
        item = {"filename": f"PyYAML-6.0.2-{tag}.whl", "packagetype": "bdist_wheel",
                "url": "https://files.pythonhosted.org/fixture.whl",
                "digests": {"sha256": hashlib.sha256(content).hexdigest()}}
        (self.root / "wheel.whl").write_bytes(content)
        (self.root / "metadata.json").write_text(json.dumps({"info": {"version": "6.0.2"}, "urls": [item]}))
        script = """
import importlib.util, json, pathlib, sys
from unittest.mock import patch
assert importlib.util.find_spec('pip') is None
assert importlib.util.find_spec('yaml') is None
spec = importlib.util.spec_from_file_location('builder', sys.argv[1])
builder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)
root = pathlib.Path(sys.argv[2])
target = root / 'installed'
def fetch(url):
    return (root / ('metadata.json' if url.endswith('/json') else 'wheel.whl')).read_bytes()
with patch.object(builder, 'fetch', side_effect=fetch) as request:
    first = builder.install_yaml(root, target)
    assert request.call_count == 2
with patch.object(builder, 'fetch', side_effect=AssertionError('must reuse verified installation')):
    assert builder.install_yaml(root, target) == first
assert importlib.util.find_spec('pip') is None
(target / 'yaml/__init__.py').write_text("__version__ = 'incorrect'\\n")
try:
    builder.install_yaml(root, target)
except ValueError as error:
    assert 'checkpoint' in str(error)
else:
    raise AssertionError('corrupted installation was accepted')
print('PASS: pip-free isolated installation, version import, resume and tamper rejection (synthetic wheel)')
"""
        result = subprocess.run([sys.executable, "-I", "-S", "-B", "-c", script,
            BUILDER.__file__, str(self.root)], capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        print(result.stdout.strip())

    def test_wheel_rejects_traversal_metadata_abi_and_record_corruption(self):
        for content, message in [
            (self.wheel(extra={"../escape": b"no"}), "unsafe wheel"),
            (self.wheel(extra={"pip/__init__.py": b"no"}), "unsafe wheel"),
            (self.wheel(extra={"yaml//alias.py": b"no"}), "unsafe wheel"),
            (self.wheel(corrupt_record=True), "RECORD checksum"),
            (self.wheel(tag="cp399-cp399-manylinux2014_x86_64"), "metadata"),
            (self.wheel(extra={"PyYAML-6.0.2.dist-info/METADATA":
                b"Name: PyYAML\nVersion: 6.0.2\nRequires-Dist: unwanted\n"}), "metadata"),
        ]:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                BUILDER.unpack_yaml_wheel(content, self.root / "unpacked")

    def test_wheel_outer_sha256_still_required(self):
        item = {"filename": f"PyYAML-6.0.2-{BUILDER.supported_yaml_tags()[0]}.whl",
                "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/fixture.whl",
                "digests": {"sha256": "0" * 64}}
        metadata = json.dumps({"info": {"version": "6.0.2"}, "urls": [item]}).encode()
        with patch.object(BUILDER, "fetch", side_effect=[metadata, self.wheel()]):
            with self.assertRaisesRegex(ValueError, "upstream SHA256"):
                BUILDER.install_yaml(self.root, self.root / "installed")
        self.assertFalse((self.root / "installed").exists())

    def test_wheel_tags_reject_unsupported_runtime(self):
        for libc in [("musl", "1.2"), ("glibc", "2.16")]:
            with patch.object(BUILDER.platform, "libc_ver", return_value=libc):
                with self.assertRaisesRegex(ValueError, "glibc"):
                    BUILDER.supported_yaml_tags()
        with patch.object(BUILDER.sysconfig, "get_config_var", return_value=1):
            with self.assertRaisesRegex(ValueError, "standard CPython"):
                BUILDER.supported_yaml_tags()

    def test_interrupted_download_resumes_then_reuses_verified_cache(self):
        cache = self.root / "cache"
        failed = Response([b"abc", TimeoutError("interrupted")], headers={"Content-Length": "6"})
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=failed):
            with self.assertRaises(TimeoutError):
                BUILDER.Downloads(cache, attempts=1).fetch(self.url, 8)
        resumed = Response([b"def"], 206, {"Content-Range": "bytes 3-5/6"})
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=resumed) as request:
            self.assertEqual(BUILDER.Downloads(cache).fetch(self.url, 8), b"abcdef")
            self.assertEqual(request.call_args.args[0].get_header("Range"), "bytes=3-")
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=AssertionError("must stay offline")):
            content = BUILDER.Downloads(cache).fetch(self.url, 8)
            self.assertEqual(BUILDER.checked(content, hashlib.sha256(b"abcdef").hexdigest()), b"abcdef")
        key = hashlib.sha256(self.url.encode()).hexdigest()
        (cache / key).write_bytes(b"tamper")
        with self.assertRaisesRegex(ValueError, "SHA256"):
            BUILDER.Downloads(cache).fetch(self.url, 8)

    def test_range_ignored_restarts_and_wrong_range_is_rejected(self):
        key = hashlib.sha256(self.url.encode()).hexdigest()
        partial = self.root / (key + ".part")
        partial.write_bytes(b"old")
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response([b"new"], headers={"Content-Length": "3"})):
            self.assertEqual(BUILDER.Downloads(self.root).fetch(self.url, 8), b"new")
        (self.root / (key + ".json")).unlink()
        partial.write_bytes(b"old")
        with patch.object(BUILDER.urllib.request, "urlopen", return_value=Response([b"bad"], 206, {"Content-Range": "bytes 2-4/5"})):
            with self.assertRaisesRegex(ValueError, "range"):
                BUILDER.Downloads(self.root).fetch(self.url, 8)

    def test_deadline_and_retry_count_bound_network_failures(self):
        with patch.object(BUILDER.urllib.request, "urlopen") as request:
            with self.assertRaisesRegex(TimeoutError, "budget"):
                BUILDER.Downloads(self.root, budget=0).fetch(self.url, 8)
            request.assert_not_called()
        with patch.object(BUILDER.urllib.request, "urlopen", side_effect=urllib.error.URLError("DNS unavailable")) as request:
            with patch.object(BUILDER.time, "sleep"), self.assertRaises(urllib.error.URLError):
                BUILDER.Downloads(self.root, attempts=2).fetch(self.url, 8)
            self.assertEqual(request.call_count, 2)

    def test_wall_clock_budget_interrupts_blocked_io(self):
        with self.assertRaisesRegex(TimeoutError, "wall-clock budget"):
            with BUILDER.preparation_timeout(0.05):
                BUILDER.time.sleep(5)
        with BUILDER.preparation_timeout(5):
            self.assertEqual(BUILDER.signal.getitimer(BUILDER.signal.ITIMER_REAL)[1], 0)
        self.assertEqual(BUILDER.signal.getitimer(BUILDER.signal.ITIMER_REAL), (0, 0))

    def test_download_size_truncation_and_https_remain_enforced(self):
        for response, error in [
            (Response([b"012345678"], headers={"Content-Length": "9"}), ValueError),
            (Response([b"abc"], headers={"Content-Length": "6"}), BUILDER.http.client.IncompleteRead),
            (Response([b"abc"], url="http://example.invalid/archive"), ValueError),
        ]:
            with patch.object(BUILDER.urllib.request, "urlopen", return_value=response):
                with self.assertRaises(error):
                    BUILDER.Downloads(self.root, attempts=1).fetch(self.url, 8)
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            BUILDER.Downloads(self.root).fetch("http://example.invalid/archive", 8)

    def test_provision_recovers_after_interrupted_publication(self):
        fixture = test_bootstrap_inputs.BootstrapTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original = BUILDER.os.replace
        def interrupt(source, target):
            if str(target).endswith("resolved-lock.json"):
                raise OSError("interrupted publication")
            return original(source, target)
        responses = fixture.responses()
        with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
            with patch.object(BUILDER.os, "replace", side_effect=interrupt):
                with self.assertRaisesRegex(OSError, "interrupted publication"):
                    BUILDER.provision(fixture.inputs, fixture.work)
            BUILDER.provision(fixture.inputs, fixture.work)
        self.assertTrue((fixture.inputs / "resolved-lock.json").exists())


if __name__ == "__main__":
    unittest.main()
