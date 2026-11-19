import base64
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import tarfile
import tempfile
import unittest
from unittest.mock import patch

from test_release_inputs import INPUTS


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("bootstrap_inputs", ROOT / "environment/bootstrap_release_inputs.py")
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "public"
        self.inputs.mkdir()
        self.work = self.root / "build"
        self.work.mkdir()
        shutil.copyfile(ROOT / "environment/offline-inputs/release_inputs.py", self.inputs / "release_inputs.py")
        shutil.copyfile(ROOT / "environment/offline-inputs/image-lock.json", self.inputs / "image-lock.json")

    def archive(self, members):
        output = io.BytesIO()
        with tarfile.open(fileobj=output, mode="w:gz") as archive:
            for name, content, kind in members:
                entry = tarfile.TarInfo(name)
                entry.size, entry.type = len(content), kind
                entry.linkname = "/outside" if kind == tarfile.SYMTYPE else ""
                archive.addfile(entry, io.BytesIO(content))
        return output.getvalue()

    def chart(self):
        return self.archive([("cilium/Chart.yaml", b"name: cilium\nversion: 1.15.2\n", tarfile.REGTYPE),
                             ("cilium/templates/fixture.yaml", b"kind: ConfigMap\n", tarfile.REGTYPE)])

    def responses(self):
        chart = self.chart()
        chart_url = INPUTS.SOURCES["cilium-chart-1.15.2"][0]
        commit, tree = "1" * 40, "2" * 40
        responses = {
            BUILDER.INDEX_URL: json.dumps({"entries": {"cilium": [{"version": "1.15.2", "urls": [chart_url],
                "digest": hashlib.sha256(chart).hexdigest()}]}}).encode(),
            chart_url: chart,
            BUILDER.CALICO_API + "/commits/v3.27.2": json.dumps({"sha": commit, "commit": {"tree": {"sha": tree}}}).encode(),
        }
        entries = []
        for filename in ("calico-vxlan.yaml", "canal.yaml"):
            content = f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: fixture-{filename}\n".encode()
            blob = hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()
            entries.append({"path": "manifests/" + filename, "sha": blob, "type": "blob", "mode": "100644"})
            responses[f"{BUILDER.CALICO_API}/git/blobs/{blob}"] = json.dumps({
                "sha": blob, "size": len(content), "encoding": "base64",
                "content": base64.b64encode(content).decode()}).encode()
        responses[f"{BUILDER.CALICO_API}/git/trees/{tree}?recursive=1"] = json.dumps({
            "sha": tree, "truncated": False, "tree": entries}).encode()
        return responses

    def test_provision_uses_authenticated_bytes_and_keeps_public_recipe(self):
        original = (self.inputs / "image-lock.json").read_bytes()
        responses = self.responses()
        with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]) as fetch:
            BUILDER.provision(self.inputs, self.work)
            self.assertEqual(fetch.call_count, len(responses))
        entries = INPUTS.verify(self.inputs)
        self.assertEqual(set(entries), set(INPUTS.SOURCES))
        self.assertEqual((self.inputs / "image-lock.json").read_bytes(), original)
        self.assertTrue((self.inputs / "resolved-lock.json").is_file())
        with patch.object(BUILDER, "fetch", side_effect=AssertionError("published inputs must not be fetched again")):
            BUILDER.provision(self.inputs, self.work)
        receipt = json.loads((self.inputs / "canal-v3.27.2.provenance.json").read_text())
        self.assertEqual(receipt["verification"]["commit"], "1" * 40)
        self.assertEqual(receipt["verification"]["retrieved_url"],
                         BUILDER.CALICO_API + "/git/blobs/" + receipt["verification"]["blob"])

    def test_chart_checksum_failure_cannot_publish_closure(self):
        responses = self.responses()
        responses[INPUTS.SOURCES["cilium-chart-1.15.2"][0]] += b"tampered"
        with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
            with self.assertRaisesRegex(ValueError, "upstream SHA256"):
                BUILDER.provision(self.inputs, self.work)
        self.assertFalse((self.inputs / "resolved-lock.json").exists())
        with self.assertRaisesRegex(ValueError, "missing authentic"):
            INPUTS.verify(self.inputs)

    def test_calico_blob_mismatch_and_truncated_tree_rejected(self):
        for alteration in ("blob", "tree"):
            responses = self.responses()
            if alteration == "blob":
                url = next(url for url in responses if "/git/blobs/" in url)
                record = json.loads(responses[url])
                record["content"] = base64.b64encode(b"tampered").decode()
                record["size"] = len(b"tampered")
                responses[url] = json.dumps(record).encode()
            else:
                url = next(url for url in responses if "?recursive=1" in url)
                tree = json.loads(responses[url])
                tree["truncated"] = True
                responses[url] = json.dumps(tree).encode()
            with self.subTest(alteration=alteration), patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
                with self.assertRaises(ValueError):
                    BUILDER.calico_inputs()

    def test_duplicate_chart_version_and_wrong_origin_rejected(self):
        for alteration in ("duplicate", "origin"):
            responses = self.responses()
            index = json.loads(responses[BUILDER.INDEX_URL])
            entries = index["entries"]["cilium"]
            if alteration == "duplicate":
                entries.append(entries[0])
            else:
                entries[0]["urls"] = ["https://unrelated.invalid/chart.tgz"]
            responses[BUILDER.INDEX_URL] = json.dumps(index).encode()
            with self.subTest(alteration=alteration), patch.object(BUILDER, "fetch", side_effect=responses.__getitem__):
                with self.assertRaisesRegex(ValueError, "official index"):
                    BUILDER.chart_input()

    def test_resolved_checksum_or_revision_failure_never_falls_back(self):
        responses = self.responses()
        with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
            BUILDER.provision(self.inputs, self.work)
        path = self.inputs / "resolved-lock.json"
        lock = json.loads(path.read_text())
        lock["revision"] = "stale"
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "requirements revision"):
            INPUTS.verify(self.inputs)

    def test_preapproved_source_pin_cannot_be_overridden_by_resolved_lock(self):
        responses = self.responses()
        with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
            BUILDER.provision(self.inputs, self.work)
        path = self.inputs / "image-lock.json"
        lock = json.loads(path.read_text())
        lock["upstream_inputs"][0].update(status="available", sha256="0" * 64)
        path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "preapproved source checksums"):
            INPUTS.verify(self.inputs)

    def test_binary_checksum_and_member_are_verified_before_install(self):
        url, checksum_url = "https://example.invalid/tool.tgz", "https://example.invalid/checksums.txt"
        for kind in (tarfile.REGTYPE, tarfile.SYMTYPE):
            binary = self.archive([("tool", b"fixture, not executable", kind)])
            responses = {url: binary, checksum_url: (hashlib.sha256(binary).hexdigest() + "  tool.tgz\n").encode()}
            with patch.object(BUILDER, "fetch", side_effect=lambda url, *args: responses[url]):
                if kind == tarfile.REGTYPE:
                    receipt = BUILDER.install_binary(self.work, self.root, "tool", url, checksum_url, "tool")
                    self.assertEqual(receipt["sha256"], hashlib.sha256(binary).hexdigest())
                    self.assertEqual((self.root / "tool").read_bytes(), b"fixture, not executable")
                    with patch.object(BUILDER, "fetch", side_effect=AssertionError("must reuse verified binary")):
                        self.assertEqual(BUILDER.install_binary(self.work, self.root, "tool", url, checksum_url, "tool"), receipt)
                    (self.root / "tool").chmod(0o644)
                    with self.assertRaisesRegex(ValueError, "checkpoint"):
                        BUILDER.install_binary(self.work, self.root, "tool", url, checksum_url, "tool")
                else:
                    (self.work / "installed-tool.json").unlink()
                    with self.assertRaisesRegex(ValueError, "invalid release binary"):
                        BUILDER.install_binary(self.work, self.root, "tool", url, checksum_url, "tool")
        with self.assertRaisesRegex(ValueError, "one official checksum"):
            BUILDER.checksum_for(b"0" * 64 + b"  another.tgz\n", "tool.tgz")
        with self.assertRaisesRegex(ValueError, "upstream SHA256"):
            BUILDER.checked(b"tampered", "0" * 64)

    def test_pyyaml_selection_rejects_yanked_or_incompatible_wheel(self):
        item = {"filename": "PyYAML-6.0.2-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl",
                "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/fixture.whl"}
        metadata = {"info": {"version": "6.0.2"}, "urls": [item]}
        self.assertEqual(BUILDER.yaml_wheel(metadata, ["cp312-cp312-manylinux2014_x86_64"]), item)
        with self.assertRaisesRegex(ValueError, "no compatible"):
            BUILDER.yaml_wheel(metadata, ["cp311-cp311-manylinux2014_x86_64"])
        item["yanked"] = True
        with self.assertRaisesRegex(ValueError, "no compatible"):
            BUILDER.yaml_wheel(metadata, ["cp312-cp312-manylinux2014_x86_64"])

    def test_http_is_not_an_upstream_verification_channel(self):
        with self.assertRaisesRegex(ValueError, "HTTPS"):
            BUILDER.fetch("http://example.invalid/release")

    def test_pypi_source_distribution_does_not_hide_compatible_wheel(self):
        source = {"filename": "pyyaml-6.0.2.tar.gz", "packagetype": "sdist"}
        wheel = {"filename": "PyYAML-6.0.2-cp310-cp310-manylinux2014_x86_64.whl",
                 "packagetype": "bdist_wheel", "url": "https://files.pythonhosted.org/fixture.whl"}
        metadata = {"info": {"version": "6.0.2"}, "urls": [source, wheel]}
        self.assertEqual(BUILDER.yaml_wheel(metadata, ["cp310-cp310-manylinux2014_x86_64"]), wheel)
        wheel["filename"] = "../PyYAML-6.0.2-cp310-cp310-manylinux2014_x86_64.whl"
        with self.assertRaisesRegex(ValueError, "unsafe PyPI filename"):
            BUILDER.yaml_wheel(metadata, ["cp310-cp310-manylinux2014_x86_64"])

    def test_go_distribution_hash_version_and_members(self):
        members = [("go/bin/go", b"fixture", tarfile.REGTYPE), ("go/bin/gofmt", b"fixture", tarfile.REGTYPE),
                   ("go/VERSION", b"go1.22.1\n", tarfile.REGTYPE)]
        content = self.archive(members)
        filename = "go1.22.1.linux-amd64.tar.gz"
        metadata = [{"version": "go1.22.1", "files": [{"os": "linux", "arch": "amd64", "kind": "archive",
            "filename": filename, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()}]}]
        responses = {"https://go.dev/dl/?mode=json&include=all": json.dumps(metadata).encode(),
                     "https://dl.google.com/go/" + filename: content}
        def fetch(url, **kwargs):
            return responses[url]
        with patch.object(BUILDER, "fetch", side_effect=fetch), patch.dict(os.environ):
            receipt = BUILDER.install_go(self.work, self.root / "go1.22.1", "amd64")
        self.assertEqual(receipt["version"], "go1.22.1")
        self.assertEqual((self.root / "go1.22.1/VERSION").read_text(), "go1.22.1\n")
        with patch.object(BUILDER, "fetch", side_effect=AssertionError("must reuse verified Go")), patch.dict(os.environ):
            self.assertEqual(BUILDER.install_go(self.work, self.root / "go1.22.1", "amd64"), receipt)
        (self.root / "go1.22.1/bin/go").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "checkpoint"):
            BUILDER.install_go(self.work, self.root / "go1.22.1", "amd64")
        for name, kind in [("../escape", tarfile.REGTYPE), ("go/link", tarfile.SYMTYPE)]:
            with tarfile.open(fileobj=io.BytesIO(self.archive(members + [(name, b"unsafe", kind)]))) as archive:
                with self.assertRaisesRegex(ValueError, "unsafe Go"):
                    BUILDER.go_archive_members(archive)


if __name__ == "__main__":
    unittest.main()
