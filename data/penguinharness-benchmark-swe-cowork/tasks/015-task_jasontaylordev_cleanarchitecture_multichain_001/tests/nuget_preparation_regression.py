#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import hashlib
import importlib.util
import json
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_nuget", ROOT / "environment/prepare-nuget.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class NuGetPreparationRegression(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="nuget-regression-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.baseline = self.root / "baseline"
        self.work = self.root / "preparation"
        self.packages = self.root / "nuget/packages"
        self.inputs = {
            "CleanArchitecture.slnx": '<Solution><Project Path="src/Web/Web.csproj" /></Solution>',
            "Directory.Packages.props": '<Project><ItemGroup><PackageVersion Include="Example" Version="1.0.0" /></ItemGroup></Project>',
            "src/Web/Web.csproj": '<Project Sdk="Microsoft.NET.Sdk"><ItemGroup><PackageReference Include="Example" /></ItemGroup></Project>',
        }
        PREPARE.materialize(self.inputs, self.baseline)
        self.snapshot = self.root / "dotnet-graph.json"
        self.target_inputs = dict(self.inputs)
        self.target_inputs["Directory.Packages.props"] = self.inputs["Directory.Packages.props"].replace("1.0.0", "2.0.0")
        self.snapshot.write_text(json.dumps({"schema": "nuget-restore-graph-v1", "inputs": self.target_inputs}))
        self.service = {"resources": [{"@id": PREPARE.SIGNATURE_INDEX, "@type": "RepositorySignatures/5.0.0"}]}
        self.signatures = {"allRepositorySigned": True,
                           "signingCertificates": [{"fingerprints": {"2.16.840.1.101.3.4.2.1": "AB" * 32}}]}
        self.commands = []
        self.envs = []
        self.drift = False
        self.metadata_drift = False
        self.extra_package = False

    def package(self, cache: Path, version: str, content: bytes = b"controlled fixture; not a real signed nupkg") -> Path:
        archive = cache / "example" / version / f"example.{version}.nupkg"
        archive.parent.mkdir(parents=True, exist_ok=True)
        archive.write_bytes(content)
        digest = base64.b64encode(hashlib.sha512(content).digest()).decode()
        canonical = base64.b64encode(hashlib.sha512(b"controlled canonical hash: " + content).digest()).decode()
        Path(str(archive) + ".sha512").write_text(digest)
        (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 2, "contentHash": canonical}))
        (archive.parent / "example.dll").write_bytes(b"controlled extracted payload: " + content)
        return archive

    def fake_run(self, command, cwd, env, check, timeout):
        self.assertTrue(check)
        self.assertEqual(timeout, 1800)
        self.commands.append(command)
        self.envs.append(env)
        if command[1] == "restore":
            config = ET.parse(cwd / "NuGet.Config")
            source = config.find("packageSources/add").attrib["value"]
            self.assertEqual(source, PREPARE.SERVICE_INDEX if not cwd.name.startswith("offline-") else str(self.packages))
            version = ET.parse(cwd / "Directory.Packages.props").find("ItemGroup/PackageVersion").attrib["Version"]
            if self.drift and cwd.name == "offline-target":
                version = "3.0.0"
            archive = self.package(Path(env["NUGET_PACKAGES"]), version)
            metadata_path = archive.parent / ".nupkg.metadata"
            metadata = json.loads(metadata_path.read_text())
            metadata["source"] = source
            metadata_path.write_text(json.dumps(metadata))
            if self.metadata_drift and cwd.name == "offline-target":
                canonical = base64.b64encode(hashlib.sha512(b"incorrect regenerated metadata").digest()).decode()
                (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 2, "contentHash": canonical}))
            if self.extra_package and cwd.name == "offline-target":
                self.package(Path(env["NUGET_PACKAGES"]), "4.0.0")
            asset = cwd / "artifacts/obj/Web/project.assets.json"
            asset.parent.mkdir(parents=True, exist_ok=True)
            asset.write_text(json.dumps({"project": {"restore": {"projectPath": str(cwd / "src/Web/Web.csproj")}},
                                         "targets": {"net10.0": {f"Example/{version}": {"type": "package"}}}}))
        return subprocess.CompletedProcess(command, 0)

    def warm(self):
        with patch.object(PREPARE, "read_public_json", side_effect=[self.service, self.signatures]), patch.object(
                PREPARE.subprocess, "run", side_effect=self.fake_run):
            PREPARE.warm(self.baseline, self.snapshot, self.work, self.packages)

    def test_both_graphs_are_isolated_then_checked_from_empty_caches(self):
        self.warm()
        with patch.object(PREPARE.subprocess, "run", side_effect=self.fake_run):
            PREPARE.check_offline(self.work, self.packages)
        self.assertEqual(len(self.commands), 6)
        restores = [command for command in self.commands if command[1] == "restore"]
        self.assertEqual(len(restores), 4)
        for command in restores:
            self.assertIn("--configfile", command)
            self.assertIn("--no-http-cache", command)
            self.assertIn("-m:2", command)
            self.assertNotIn("--ignore-failed-sources", command)
            self.assertIn("-warnaserror:NU1603,NU1605,NU1801", command)
        verification = [command for command in self.commands if command[1:3] == ["nuget", "verify"]]
        self.assertEqual(len(verification), 2)
        self.assertTrue(all("--all" in command for command in verification))
        self.assertEqual(len({env["NUGET_PACKAGES"] for command, env in zip(self.commands, self.envs) if command[1] == "restore"}), 4)
        self.assertTrue(all(env["DOTNET_NUGET_SIGNATURE_VERIFICATION"] == "true" for env in self.envs))
        self.assertEqual([env["NUGET_CERT_REVOCATION_MODE"] for env in self.envs], ["online"] * 4 + ["offline"] * 2)
        self.assertEqual(set(PREPARE.package_inventory(self.packages)),
                         {"example/1.0.0/example.1.0.0.nupkg", "example/2.0.0/example.2.0.0.nupkg"})
        self.assertEqual(PREPARE.restore_inputs(self.baseline), self.inputs)

    def test_offline_resolution_drift_fails(self):
        self.warm()
        self.drift = True
        with patch.object(PREPARE.subprocess, "run", side_effect=self.fake_run), self.assertRaisesRegex(ValueError, "resolution drift: target"):
            PREPARE.check_offline(self.work, self.packages)

    def test_signature_failure_prevents_cache_publication(self):
        def reject_signature(command, **kwargs):
            if command[1:3] == ["nuget", "verify"]:
                raise subprocess.CalledProcessError(1, command, output="signature rejected")
            return self.fake_run(command, **kwargs)
        with patch.object(PREPARE, "read_public_json", side_effect=[self.service, self.signatures]), patch.object(
                PREPARE.subprocess, "run", side_effect=reject_signature), self.assertRaises(subprocess.CalledProcessError):
            PREPARE.warm(self.baseline, self.snapshot, self.work, self.packages)
        self.assertFalse(self.packages.exists())
        self.assertFalse((self.packages.parent / "NuGet.Config").exists())

    def test_restore_failure_is_not_retried_or_suppressed(self):
        with patch.object(PREPARE.subprocess, "run", side_effect=subprocess.CalledProcessError(1, ["dotnet"], output="NU1603")) as runner:
            with self.assertRaises(subprocess.CalledProcessError):
                PREPARE.restore(self.baseline, self.root / "NuGet.Config", {})
        self.assertEqual(runner.call_count, 1)

    def test_tampered_package_fails_before_offline_restore(self):
        self.warm()
        next(self.packages.glob("*/*/*.nupkg")).write_bytes(b"tampered")
        with patch.object(PREPARE.subprocess, "run") as runner, self.assertRaisesRegex(ValueError, "closure changed"):
            PREPARE.check_offline(self.work, self.packages)
        runner.assert_not_called()

    def test_missing_exact_package_fails_even_if_other_version_exists(self):
        self.warm()
        next(self.packages.glob("example/1.0.0/*.nupkg")).unlink()
        with patch.object(PREPARE.subprocess, "run") as runner, self.assertRaisesRegex(ValueError, "closure changed"):
            PREPARE.check_offline(self.work, self.packages)
        runner.assert_not_called()

    def test_conflicting_same_identity_rejected_and_identical_copy_accepted(self):
        first = self.root / "first"
        second = self.root / "second"
        self.package(first, "1.0.0")
        self.package(second, "1.0.0")
        PREPARE.merge_packages(first, self.packages)
        PREPARE.merge_packages(second, self.packages)
        self.package(second, "1.0.0", b"different verified content")
        with self.assertRaisesRegex(ValueError, "conflicting package bytes"):
            PREPARE.merge_packages(second, self.packages)

    def test_missing_or_forged_checksum_metadata_rejected(self):
        archive = self.package(self.packages, "1.0.0")
        (archive.parent / ".nupkg.metadata").write_text('{"version":2,"contentHash":"forged"}')
        with self.assertRaisesRegex(ValueError, "invalid NuGet content hash"):
            PREPARE.package_inventory(self.packages)
        Path(str(archive) + ".sha512").unlink()
        with self.assertRaises(FileNotFoundError):
            PREPARE.package_inventory(self.packages)

    def test_signed_package_records_need_not_have_identical_hashes(self):
        archive = self.package(self.packages, "1.0.0")
        canonical = base64.b64encode(hashlib.sha512(b"unsigned package content").digest()).decode()
        legacy = base64.b64encode(hashlib.sha512(b"legacy package record").digest()).decode()
        Path(str(archive) + ".sha512").write_text(legacy)
        (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 2, "contentHash": canonical}))
        inventory = PREPARE.package_inventory(self.packages)
        digest = base64.b64encode(hashlib.sha512(archive.read_bytes()).digest()).decode()
        record = inventory[archive.relative_to(self.packages).as_posix()]
        self.assertEqual(record["archive_sha512"], digest)
        self.assertEqual(record["legacy_sha512"], legacy)
        self.assertEqual(record["content_hash"], canonical)
        self.assertEqual(len({digest, legacy, canonical}), 3)

    def test_metadata_and_checksum_tampering_fail_before_offline_restore(self):
        self.warm()
        archive = next(self.packages.glob("*/*/*.nupkg"))
        files = [archive.parent / ".nupkg.metadata", Path(str(archive) + ".sha512"), archive.parent / "example.dll"]
        for path in files:
            original = path.read_bytes()
            digest = base64.b64encode(hashlib.sha512(b"forged valid hash").digest()).decode()
            content = json.dumps({"version": 2, "contentHash": digest}) if path.name == ".nupkg.metadata" else digest
            path.write_text(content)
            with self.subTest(path=path.name), patch.object(PREPARE.subprocess, "run") as runner:
                with self.assertRaisesRegex(ValueError, "closure changed"):
                    PREPARE.check_offline(self.work, self.packages)
                runner.assert_not_called()
            path.write_bytes(original)

    def test_offline_native_metadata_must_reproduce_online_records(self):
        self.warm()
        self.metadata_drift = True
        with patch.object(PREPARE.subprocess, "run", side_effect=self.fake_run):
            with self.assertRaisesRegex(ValueError, "offline package bytes or metadata differ: target"):
                PREPARE.check_offline(self.work, self.packages)

    def test_offline_package_set_must_reproduce_complete_online_closure(self):
        self.warm()
        self.extra_package = True
        with patch.object(PREPARE.subprocess, "run", side_effect=self.fake_run):
            with self.assertRaisesRegex(ValueError, "offline package bytes or metadata differ: target"):
                PREPARE.check_offline(self.work, self.packages)

    def test_same_archive_with_conflicting_metadata_cannot_merge(self):
        first = self.root / "first"
        second = self.root / "second"
        self.package(first, "1.0.0")
        archive = self.package(second, "1.0.0")
        digest = base64.b64encode(hashlib.sha512(b"other metadata").digest()).decode()
        (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 2, "contentHash": digest}))
        PREPARE.merge_packages(first, self.packages)
        with self.assertRaisesRegex(ValueError, "conflicting package bytes or metadata"):
            PREPARE.merge_packages(second, self.packages)

    def test_invalid_legacy_hash_and_metadata_version_rejected(self):
        archive = self.package(self.packages, "1.0.0")
        checksum = Path(str(archive) + ".sha512")
        valid = checksum.read_text()
        for malformed in ("not-base64", base64.b64encode(b"short").decode(), valid[:-3] + "AA="):
            checksum.write_text(malformed)
            with self.subTest(malformed=malformed), self.assertRaisesRegex(ValueError, "invalid NuGet legacy SHA512"):
                PREPARE.package_inventory(self.packages)
        checksum.write_text(valid)
        (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 1, "contentHash": valid}))
        with self.assertRaisesRegex(ValueError, "unsupported NuGet metadata version"):
            PREPARE.package_inventory(self.packages)

    def test_cache_mutation_during_signature_verification_rejected(self):
        def mutate_cache(command, **kwargs):
            outcome = self.fake_run(command, **kwargs)
            if command[1:3] == ["nuget", "verify"]:
                archive = Path(command[-1])
                (archive.parent / "example.dll").write_bytes(b"modified during verification")
            return outcome
        with patch.object(PREPARE, "read_public_json", side_effect=[self.service, self.signatures]):
            with patch.object(PREPARE.subprocess, "run", side_effect=mutate_cache):
                with self.assertRaisesRegex(ValueError, "cache changed during signature verification"):
                    PREPARE.warm(self.baseline, self.snapshot, self.work, self.packages)
        self.assertFalse(self.packages.exists())

    def test_missing_or_added_payload_file_rejected(self):
        self.warm()
        archive = next(self.packages.glob("*/*/*.nupkg"))
        payload = archive.parent / "example.dll"
        original = payload.read_bytes()
        payload.unlink()
        with patch.object(PREPARE.subprocess, "run") as runner, self.assertRaisesRegex(ValueError, "closure changed"):
            PREPARE.check_offline(self.work, self.packages)
        runner.assert_not_called()
        payload.write_bytes(original)
        (archive.parent / "injected.dll").write_bytes(b"unexpected assembly")
        with patch.object(PREPARE.subprocess, "run") as runner, self.assertRaisesRegex(ValueError, "closure changed"):
            PREPARE.check_offline(self.work, self.packages)
        runner.assert_not_called()

    def test_equivalent_hash_records_remain_accepted(self):
        archive = self.package(self.packages, "1.0.0")
        digest = Path(str(archive) + ".sha512").read_text()
        (archive.parent / ".nupkg.metadata").write_text(json.dumps({"version": 2, "contentHash": digest}))
        record = PREPARE.package_inventory(self.packages)[archive.relative_to(self.packages).as_posix()]
        self.assertEqual(record["archive_sha512"], record["legacy_sha512"])
        self.assertEqual(record["archive_sha512"], record["content_hash"])

    def test_nonempty_offline_cache_rejected(self):
        self.warm()
        (self.work / "offline-packages-baseline").mkdir()
        with patch.object(PREPARE.subprocess, "run") as runner, self.assertRaisesRegex(ValueError, "requires empty"):
            PREPARE.check_offline(self.work, self.packages)
        runner.assert_not_called()

    def test_offline_config_contains_only_local_source_and_required_trust(self):
        config = ET.fromstring(PREPARE.configuration(str(self.packages), ["AB" * 32]))
        self.assertIsNotNone(config.find("packageSources/clear"))
        self.assertIsNotNone(config.find("fallbackPackageFolders/clear"))
        self.assertEqual([source.attrib["value"] for source in config.findall("packageSources/add")], [str(self.packages)])
        self.assertEqual(config.find("config/add").attrib, {"key": "signatureValidationMode", "value": "require"})
        self.assertEqual(config.find("trustedSigners/repository/certificate").attrib,
                         {"fingerprint": "AB" * 32, "hashAlgorithm": "SHA256", "allowUntrustedRoot": "false"})

    def test_repository_metadata_rejects_untrusted_or_invalid_shape(self):
        self.assertEqual(PREPARE.repository_certificates(self.service, self.signatures), ["AB" * 32])
        variants = [{}, {"allRepositorySigned": False, "signingCertificates": self.signatures["signingCertificates"]},
                    {"allRepositorySigned": True, "signingCertificates": []}]
        broken = copy.deepcopy(self.signatures)
        broken["signingCertificates"][0]["fingerprints"] = {"sha1": "AB" * 20}
        variants.append(broken)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                PREPARE.repository_certificates(self.service, variant)
        with self.assertRaises(ValueError):
            PREPARE.repository_certificates({"resources": []}, self.signatures)
        with self.assertRaises(ValueError):
            PREPARE.read_public_json("https://untrusted.invalid/index.json")

    def test_materialized_inputs_exclude_sources_and_reject_traversal(self):
        (self.baseline / "Program.cs").write_text("production code must not be exported")
        self.assertEqual(PREPARE.restore_inputs(self.baseline), self.inputs)
        for relative in ("../outside.props", "/outside.props", "src/Program.cs", "src\\outside.props"):
            with self.subTest(relative=relative), self.assertRaises(ValueError):
                PREPARE.materialize({**self.inputs, relative: "forbidden"}, self.root / "isolated")

    def test_all_solution_projects_need_asset_results(self):
        with self.assertRaisesRegex(ValueError, "missing restored projects"):
            PREPARE.resolved_graph(self.baseline)


if __name__ == "__main__":
    print("CONTROLLED FIXTURES: subprocess outcomes are simulated; no real NuGet restore or signature verification is claimed.", flush=True)
    unittest.main(verbosity=2)
