import hashlib
import importlib.util
import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INSTALLER = load("input_installer", ROOT / "environment/runtime-smoke/install-build-inputs.py")
BUILD = load("input_build_contract", ROOT / "tests/tests/build_contract.py")


class BuildInputTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.inputs = self.root / "inputs"
        self.payload = self.inputs / "payload"
        self.destination = self.root / "installed"
        files = {"sdk/platforms/android-33/android.jar": b"fixture only",
                 "sdk/cmake/3.18.1/bin/cmake": b"#!/bin/sh\nexit 0\n",
                 "sdk/ndk/21.1.6352462/source.properties": b"Pkg.Revision = 21.1.6352462\n",
                 "sdk/ndk/21.1.6352462/build/cmake/android.toolchain.cmake": b"fixture only",
                 "minizip/CMakeLists.txt": b"fixture only",
                 "gradle/wrapper/dists/gradle-6.5-bin/fixture/gradle-6.5/bin/gradle": b"#!/bin/sh\nexit 0\n",
                 "gradle/caches/modules-2/files-2.1/com.android.tools.build/gradle/4.1.0/fixture/gradle-4.1.0.jar": b"fixture only"}
        for name, data in files.items():
            path = self.payload / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            if "/bin/" in name:
                path.chmod(0o755)
        self.document = {"schema": "dpt-offline-build-inputs-v1",
                         "versions": {"sdk": "33", "cmake": "3.18.1", "agp": "4.1.0", "gradle": "6.5",
                                      "ndk": "21.1.6352462", "minizip_commit": "a" * 40}, "files": {}}
        self.inventory()

    def inventory(self):
        self.document["files"] = {path.relative_to(self.payload).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                                  for path in self.payload.rglob("*") if path.is_file()}
        self.write_manifest()

    def write_manifest(self):
        (self.inputs / "manifest.json").write_text(json.dumps(self.document))

    def test_integrity_install_preserves_bytes_modes_and_reports_not_verified(self):
        receipt = INSTALLER.install(self.inputs, self.destination)
        self.assertFalse(receipt["integration_verified"])
        for name, expected in self.document["files"].items():
            target = self.destination / name
            self.assertEqual(INSTALLER.digest(target), expected)
            self.assertNotEqual(target.stat().st_ino, (self.payload / name).stat().st_ino)
        self.assertTrue(os.access(self.destination / "sdk/cmake/3.18.1/bin/cmake", os.X_OK))
        policy = self.destination / "gradle/init.d/dependency-repositories.gradle"
        self.assertEqual(policy.read_bytes(), (ROOT / "environment/runtime-smoke/dependency-repositories.gradle").read_bytes())
        self.assertEqual(receipt["repository_policy_sha256"], INSTALLER.digest(policy))

    def test_absent_real_bundle_is_diagnostic_exit_two(self):
        result = subprocess.run(["python3", str(ROOT / "environment/runtime-smoke/install-build-inputs.py"),
                                 str(ROOT / "environment/build-inputs"), str(self.destination)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("missing generated build-inputs/manifest.json", result.stderr)
        self.assertFalse(self.destination.exists())

    def test_checksum_failure_creates_no_destination(self):
        (self.payload / "minizip/CMakeLists.txt").write_bytes(b"tampered")
        with self.assertRaisesRegex(INSTALLER.InputError, "checksum mismatch"):
            INSTALLER.install(self.inputs, self.destination)
        self.assertFalse(self.destination.exists())

    def test_unlisted_file_and_symlink_fail_before_copy(self):
        extra = self.payload / "minizip/extra"
        extra.write_text("unlisted")
        with self.assertRaisesRegex(INSTALLER.InputError, "unlisted"):
            INSTALLER.install(self.inputs, self.destination)
        extra.unlink()
        extra.symlink_to(self.root)
        with self.assertRaisesRegex(INSTALLER.InputError, "symlinks"):
            INSTALLER.install(self.inputs, self.destination)
        self.assertFalse(self.destination.exists())

    def test_shared_destination_is_not_modified(self):
        self.destination.mkdir()
        marker = self.destination / "keep"
        marker.write_text("unchanged")
        with self.assertRaisesRegex(INSTALLER.InputError, "never overwrite"):
            INSTALLER.install(self.inputs, self.destination)
        self.assertEqual(marker.read_text(), "unchanged")

    def test_init_scripts_and_target_classes_are_rejected(self):
        script = self.payload / "gradle/init.d/unsafe.gradle"
        script.parent.mkdir(parents=True)
        script.write_text("throw new Error()")
        self.inventory()
        with self.assertRaisesRegex(INSTALLER.InputError, "non-dependency"):
            INSTALLER.validate(self.inputs)
        script.unlink()
        archive = self.payload / "gradle/caches/target.jar"
        with zipfile.ZipFile(archive, "w") as stream:
            stream.writestr("com/luoye/dpt/Dpt.class", b"target")
        self.inventory()
        with self.assertRaisesRegex(INSTALLER.InputError, "target bytecode"):
            INSTALLER.validate(self.inputs)

    def add_official_gradle_readme(self):
        relative = ("gradle/wrapper/dists/gradle-6.5-bin/6nifqtx7604sqp1q6g8wikw7p/"
                    "gradle-6.5/init.d/readme.txt")
        target = self.payload / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((Path(__file__).parent / "fixtures/gradle-6.5-init-readme.txt").read_bytes())
        self.inventory()
        return target

    def test_official_distribution_readme_installs_byte_for_byte(self):
        source = self.add_official_gradle_readme()
        receipt = INSTALLER.install(self.inputs, self.destination)
        self.assertEqual((self.destination / source.relative_to(self.payload)).read_bytes(), source.read_bytes())
        self.assertFalse(receipt["integration_verified"])

    def test_modified_readme_cannot_be_admitted_by_regenerated_manifest(self):
        source = self.add_official_gradle_readme()
        source.write_bytes(source.read_bytes() + b"\ninjected configuration")
        self.inventory()
        with self.assertRaisesRegex(INSTALLER.InputError, "non-dependency"):
            INSTALLER.install(self.inputs, self.destination)
        self.assertFalse(self.destination.exists())

    def test_official_readme_hash_cannot_mask_modified_payload(self):
        source = self.add_official_gradle_readme()
        source.write_bytes(b"different bytes with unchanged official hash in manifest")
        with self.assertRaisesRegex(INSTALLER.InputError, "checksum mismatch"):
            INSTALLER.install(self.inputs, self.destination)
        self.assertFalse(self.destination.exists())

    def test_official_readme_content_is_not_allowed_at_other_paths(self):
        source = self.add_official_gradle_readme()
        data = source.read_bytes()
        source.unlink()
        paths = ["gradle/init.d/readme.txt", "sdk/init.d/readme.txt", "minizip/init.d/readme.txt",
                 "gradle/wrapper/dists/gradle-6.5-bin/other/gradle-6.5/init.d/readme.txt",
                 "gradle/wrapper/dists/gradle-6.5-bin/6nifqtx7604sqp1q6g8wikw7p/gradle-6.5/init.d/sub/readme.txt",
                 "gradle/wrapper/dists/gradle-6.5-bin/6nifqtx7604sqp1q6g8wikw7p/gradle-7.0/init.d/readme.txt",
                 "vendor/init.d/readme.txt"]
        for relative in paths:
            with self.subTest(path=relative):
                target = self.payload / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                self.inventory()
                with self.assertRaises(INSTALLER.InputError):
                    INSTALLER.validate(self.inputs)
                target.unlink()

    def test_distribution_init_scripts_remain_rejected_with_official_readme(self):
        source = self.add_official_gradle_readme()
        for filename in ["init.gradle", "init.gradle.kts", "readme.gradle"]:
            with self.subTest(filename=filename):
                target = source.with_name(filename)
                target.write_bytes(source.read_bytes())
                self.inventory()
                with self.assertRaisesRegex(INSTALLER.InputError, "non-dependency"):
                    INSTALLER.validate(self.inputs)
                target.unlink()

    def test_wrong_versions_and_unpinned_source_rejected(self):
        for key, value in [("gradle", "8.0"), ("ndk", "latest"), ("minizip_commit", "main")]:
            with self.subTest(key=key):
                original = self.document["versions"][key]
                self.document["versions"][key] = value
                self.write_manifest()
                with self.assertRaises(INSTALLER.InputError):
                    INSTALLER.validate(self.inputs)
                self.document["versions"][key] = original

    def test_dependency_fallback_does_not_overwrite_submitted_content(self):
        submitted = self.root / "repo/shell/src/main/cpp/minizip-ng"
        submitted.mkdir(parents=True)
        with patch.dict(os.environ, {"DPT_MINIZIP_SOURCE": str(self.payload / "minizip")}):
            self.assertEqual(BUILD.minizip_source(self.root / "repo"), self.payload / "minizip")
            (submitted / "CMakeLists.txt").write_text("solver changes")
            self.assertEqual(BUILD.minizip_source(self.root / "repo"), submitted)
            self.assertEqual((submitted / "CMakeLists.txt").read_text(), "solver changes")

    def test_public_entry_restores_dependency_only_after_successful_preflight(self):
        repo = self.root / "repo"
        repo.mkdir()
        (repo / "gradlew").write_text('test -f shell/src/main/cpp/minizip-ng/CMakeLists.txt || exit 42\nprintf "%s\\n" "$@" > called-arguments\n')
        java = self.root / "jdk/bin/java"
        java.parent.mkdir(parents=True)
        java.write_text('#!/bin/sh\nprintf \'openjdk version "11.0.fixture"\\n\' >&2\n')
        java.chmod(0o755)
        environment = dict(os.environ, JAVA_HOME=str(java.parents[1]), ANDROID_SDK_ROOT=str(self.payload / "sdk"),
                           GRADLE_USER_HOME=str(self.payload / "gradle"), DPT_MINIZIP_SOURCE=str(self.payload / "minizip"),
                           HOME=str(self.root / "home"))
        script = ROOT / "environment/runtime-smoke/build-check.sh"
        result = subprocess.run(["bash", str(script), str(repo)], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        submitted = repo / "shell/src/main/cpp/minizip-ng/CMakeLists.txt"
        self.assertEqual(submitted.read_text(), "fixture only")
        self.assertIn("--offline\n--no-daemon\n--max-workers=2", (repo / "called-arguments").read_text())
        submitted.write_text("submitted dependency edits")
        result = subprocess.run(["bash", str(script), str(repo)], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(submitted.read_text(), "submitted dependency edits")
        submitted.unlink()
        environment["JAVA_HOME"] = str(self.root / "absent-jdk")
        (repo / "called-arguments").unlink()
        result = subprocess.run(["bash", str(script), str(repo)], env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(submitted.exists())
        self.assertFalse((repo / "called-arguments").exists())


if __name__ == "__main__":
    unittest.main()
