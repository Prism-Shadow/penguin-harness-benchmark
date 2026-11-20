import importlib.util
import io
import json
import os
from pathlib import Path
import tarfile
import tempfile
import unittest

from run_controls import behavior_result, changed, comment_only, old_cilium_manifests, replace_once


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release_inputs", ROOT / "environment/offline-inputs/release_inputs.py")
INPUTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUTS)


class InputTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR"))
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.inputs = self.root / "inputs"
        self.inputs.mkdir()
        (self.inputs / "image-lock.json").write_text(json.dumps({"upstream_inputs": [
            {"id": identifier, "url": url, "path": filename, "status": "missing", "sha256": None}
            for identifier, (url, filename) in INPUTS.SOURCES.items()]}))

    def chart(self, member="cilium/templates/example.yaml", kind=tarfile.REGTYPE):
        path = self.root / "fixture.tgz"
        with tarfile.open(path, "w:gz") as archive:
            for name, body, member_type in [("cilium/Chart.yaml", b"name: cilium\nversion: 1.15.2\n", tarfile.REGTYPE),
                                            (member, b"kind: ConfigMap\n", kind)]:
                info = tarfile.TarInfo(name)
                info.type, info.size = member_type, len(body)
                info.linkname = "/outside" if kind == tarfile.SYMTYPE else ""
                archive.addfile(info, io.BytesIO(body))
        return path

    def import_fixture(self, identifier):
        source = self.chart() if identifier.startswith("cilium") else self.root / "fixture.yaml"
        if not identifier.startswith("cilium"):
            source.write_text("apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: fixture-only\n")
        checksum = INPUTS.digest(source)
        provenance = self.root / "receipt.json"
        provenance.write_text(json.dumps({"url": INPUTS.SOURCES[identifier][0], "sha256": checksum,
                                         "verification": "UNIT FIXTURE ONLY, not authentic release evidence"}))
        INPUTS.import_input(self.inputs, identifier, source, checksum, provenance)

    def test_missing_closure_is_not_pass(self):
        with self.assertRaisesRegex(ValueError, "missing authentic"):
            INPUTS.verify(self.inputs)

    def test_import_verify_and_tamper(self):
        for identifier in INPUTS.SOURCES:
            self.import_fixture(identifier)
        self.assertEqual(set(INPUTS.verify(self.inputs)), set(INPUTS.SOURCES))
        path = self.inputs / INPUTS.SOURCES["canal-v3.27.2"][1]
        path.write_text(path.read_text() + "tampered")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            INPUTS.verify(self.inputs)

    def test_unapproved_checksum_rejected(self):
        source = self.chart()
        with self.assertRaisesRegex(ValueError, "approved SHA256"):
            INPUTS.import_input(self.inputs, "cilium-chart-1.15.2", source, "0" * 64, self.root / "absent")

    def test_receipt_tamper_and_duplicate_ids_rejected(self):
        for identifier in INPUTS.SOURCES:
            self.import_fixture(identifier)
        receipt = self.inputs / "canal-v3.27.2.provenance.json"
        receipt.write_text(receipt.read_text() + " ")
        with self.assertRaisesRegex(ValueError, "provenance checksum"):
            INPUTS.verify(self.inputs)
        lock_path = self.inputs / "image-lock.json"
        lock = json.loads(lock_path.read_text())
        lock["upstream_inputs"].append(lock["upstream_inputs"][0])
        lock_path.write_text(json.dumps(lock))
        with self.assertRaisesRegex(ValueError, "exactly the three"):
            INPUTS.verify(self.inputs)

    def test_archive_escape_symlink_and_duplicate_rejected(self):
        for member, kind in [("../escape", tarfile.REGTYPE), ("cilium/link", tarfile.SYMTYPE),
                             ("cilium/Chart.yaml", tarfile.REGTYPE)]:
            with self.subTest(member=member):
                with tarfile.open(self.chart(member, kind)) as archive:
                    with self.assertRaisesRegex(ValueError, "unsafe chart member"):
                        INPUTS.chart_members(archive)

    def test_mutation_restoration_even_when_control_errors(self):
        path = self.root / "source.go"
        path.write_text("mode = 0o755")
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with changed(path, replace_once("0o755", "0o700")):
                self.assertEqual(path.read_text(), "mode = 0o700")
                raise RuntimeError("interrupted")
        self.assertEqual(path.read_text(), "mode = 0o755")
        with self.assertRaisesRegex(ValueError, "match once"):
            with changed(path, replace_once("absent", "new")):
                self.fail("invalid mutation ran")
        self.assertEqual(path.read_text(), "mode = 0o755")

    def test_compile_or_zero_tests_cannot_kill_mutant(self):
        name = "TestProduction"
        for text in ("undefined: Missing", '{"Action":"fail","Package":"pkg/tasks"}',
                     '{"Action":"fail","Test":"AnotherTest"}'):
            self.assertFalse(behavior_result(1, text, name, True))
        event = json.dumps({"Action": "fail", "Test": name})
        self.assertTrue(behavior_result(1, event, name, True))
        self.assertFalse(behavior_result(0, event, name, True))
        self.assertTrue(behavior_result(0, json.dumps({"Action": "pass", "Test": name}), name, False))

    def test_comment_only_control_really_only_changes_comment(self):
        baseline = (ROOT / "tests/native_task/base/addons/cni-cilium/cilium.yaml").read_text()
        mutated = comment_only("unused")
        differences = [(before, after) for before, after in zip(baseline.splitlines(), mutated.splitlines()) if before != after]
        self.assertEqual(len(differences), 1)
        self.assertTrue(all(line.startswith("#") for line in differences[0]))

    def test_old_cilium_control_is_not_a_duplicate_object_failure(self):
        directory = self.root / "addons/cni-cilium"
        directory.mkdir(parents=True)
        (directory / "cilium.yaml").write_text("current")
        (directory / "hubble.yaml").write_text("separate dynamic objects")
        before = {path.name: path.read_bytes() for path in directory.iterdir()}
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with old_cilium_manifests(self.root):
                self.assertFalse((directory / "hubble.yaml").exists())
                self.assertEqual((directory / "cilium.yaml").read_text(), comment_only(""))
                raise RuntimeError("interrupted")
        self.assertEqual({path.name: path.read_bytes() for path in directory.iterdir()}, before)


if __name__ == "__main__":
    unittest.main()
