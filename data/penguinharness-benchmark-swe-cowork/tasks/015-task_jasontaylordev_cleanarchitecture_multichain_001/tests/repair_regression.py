#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "environment/workplace-service"))
sys.path.insert(0, str(ROOT / "tests"))

from grade_runner import _stage_probe_tree, summarize
from harbor_dynamic_colleague_adapter import SemanticRuntimeState, _transactional_dispatch
from production_checks import run_checks
import purge_probe
from test_outputs import run_one

specification = importlib.util.spec_from_file_location("prepare_npm", ROOT / "environment/prepare-npm.py")
npm_preparation = importlib.util.module_from_spec(specification)
specification.loader.exec_module(npm_preparation)

contract_specification = importlib.util.spec_from_file_location("render_contracts", ROOT / "solution/render_contracts.py")
contract_renderer = importlib.util.module_from_spec(contract_specification)
contract_specification.loader.exec_module(contract_renderer)


class PurgeProbeOrchestrationRegression(unittest.TestCase):
    def test_unavailable_sdk_does_not_start_a_build(self):
        with tempfile.TemporaryDirectory() as folder, patch("purge_probe.shutil.which", return_value=None), patch(
                "purge_probe.subprocess.run") as process, redirect_stdout(io.StringIO()) as output:
            self.assertEqual(purge_probe.run(Path(folder), Path(folder) / "NuGet.Config"), 2)
            process.assert_not_called()
            self.assertIn("infrastructure_error", output.getvalue())

    def test_restore_build_and_behavior_failures_remain_distinct(self):
        success = subprocess.CompletedProcess([], 0)
        failure = subprocess.CompletedProcess([], 1)
        for outcomes, expected in (([failure], 2), ([success, failure], 3), ([success, success, failure], 1)):
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as folder, patch(
                    "purge_probe.shutil.which", return_value="dotnet"), patch(
                    "purge_probe.subprocess.run", side_effect=outcomes) as process, redirect_stdout(io.StringIO()):
                self.assertEqual(purge_probe.run(Path(folder), Path(folder) / "NuGet.Config"), expected)
                self.assertEqual(process.call_count, len(outcomes))

    def test_success_references_production_project_and_requires_strict_offline_restore(self):
        import xml.etree.ElementTree as ET

        commands = []
        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            config = repository / "NuGet.Config"

            def invoke(command, **arguments):
                commands.append(command)
                self.assertEqual(arguments["cwd"], repository)
                self.assertEqual(arguments["env"]["DOTNET_PROCESSOR_COUNT"], "2")
                self.assertEqual(arguments["env"]["DOTNET_NUGET_SIGNATURE_VERIFICATION"], "true")
                self.assertEqual(arguments["env"]["NUGET_CERT_REVOCATION_MODE"], "offline")
                if command[1] == "restore":
                    project = ET.parse(command[2])
                    self.assertEqual(project.findtext("PropertyGroup/EnableDefaultCompileItems"), "false")
                    self.assertEqual(project.find("ItemGroup/Compile").attrib["Include"], "Program.cs")
                    self.assertEqual(project.find("ItemGroup/ProjectReference").attrib["Include"],
                                     str(repository / "src/Infrastructure/Infrastructure.csproj"))
                    self.assertEqual(list(project.iter("PackageReference")), [])
                    self.assertIn(str(config), command)
                    self.assertIn("-warnaserror:NU1603,NU1605,NU1801", command)
                    self.assertNotIn("--ignore-failed-sources", command)
                return subprocess.CompletedProcess(command, 0)

            with patch("purge_probe.shutil.which", return_value="dotnet"), patch(
                    "purge_probe.subprocess.run", side_effect=invoke), redirect_stdout(io.StringIO()):
                self.assertEqual(purge_probe.run(repository, config), 0)
            self.assertEqual([command[1] for command in commands], ["restore", "build", "run"])
            self.assertIn("--no-restore", commands[1])
            self.assertIn("--no-restore", commands[2])
            self.assertEqual(list((repository / "artifacts").iterdir()), [])


class ContractArtifactRegression(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.authoring = self.root / "environment/workplace-service/original/authoring"
        self.public = self.root / "environment/task_README.md"
        self.board = self.authoring / "corpus/board.json"
        self.owner = self.authoring / "orgchat_auto1/knowledge_packs/core-03.json"
        self.metadata = self.root / "task.toml"
        self.script = self.root / "solution/render_contracts.py"
        for path in (self.public, self.board, self.owner, self.script):
            path.parent.mkdir(parents=True, exist_ok=True)
        self.public.write_text("# Public contract\nRequests clamp to the available page boundary.\n")
        self.board.write_text(json.dumps({"cards": [{"project": "cleanarchitecture-core", "key": "CA-223",
                                                    "status": "Blocked", "description": "Evidence remains pending."}]}))
        self.owner.write_text(json.dumps({"owner": "core-03", "facts": [{"card_id": "CA-210", "iu": "pagination",
            "answer": "Reject invalid page sizes.", "disclosure": {"minimum_user_turns": 2}}]}))
        self.metadata.write_text('[metadata]\ntask_version = "fixture-r1"\n')
        self.script.write_text((ROOT / "solution/render_contracts.py").read_text())
        self.regenerate()

    def regenerate(self):
        self.artifacts = contract_renderer.render(self.root)
        for path, content in self.artifacts.items():
            path.write_text(content)

    def invoke(self, *arguments):
        return subprocess.run([sys.executable, str(self.script), *arguments], cwd=self.root,
                              text=True, capture_output=True, timeout=10)

    def test_check_success_emits_each_artifact_digest_and_count(self):
        import hashlib

        result = self.invoke("--check")
        self.assertEqual(result.returncode, 0, result.stderr)
        for path in self.artifacts:
            self.assertIn(f"PASS {path.relative_to(self.root)}:", result.stdout)
            self.assertIn(hashlib.sha256(path.read_bytes()).hexdigest(), result.stdout)
        self.assertIn(f"Contract check: {len(self.artifacts)}/{len(self.artifacts)} artifacts synchronized", result.stdout)

    def test_version_titles_follow_metadata_and_reject_stale_outputs(self):
        for content in self.artifacts.values():
            self.assertTrue(content.startswith("# fixture-r1: authoritative context\n"))
        self.metadata.write_text('[metadata]\ntask_version = "fixture-r2"\n')
        result = self.invoke("--check")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn(f"Contract check: 0/{len(self.artifacts)} artifacts synchronized", result.stdout)
        self.regenerate()
        for content in self.artifacts.values():
            self.assertTrue(content.startswith("# fixture-r2: authoritative context\n"))
        self.assertEqual(self.invoke("--check").returncode, 0)

    def test_each_contract_input_change_invalidates_every_artifact_without_rewriting(self):
        for source in (self.public, self.board, self.owner):
            with self.subTest(source=source.relative_to(self.root)):
                original = source.read_text()
                source.write_text(original + "\n")
                result = self.invoke("--check")
                self.assertEqual(result.returncode, 1, result.stderr)
                for path, content in self.artifacts.items():
                    self.assertIn(f"FAIL {path.relative_to(self.root)}: differs", result.stdout)
                    self.assertEqual(path.read_text(), content)
                source.write_text(original)

    def test_check_reports_all_missing_artifacts_without_short_circuit(self):
        for path in self.artifacts:
            path.unlink()
        result = self.invoke("--check")
        self.assertEqual(result.returncode, 1, result.stderr)
        for path in self.artifacts:
            self.assertIn(f"FAIL {path.relative_to(self.root)}: missing artifact", result.stdout)
            self.assertFalse(path.exists())
        self.assertIn(f"Contract check: 0/{len(self.artifacts)} artifacts synchronized", result.stdout)

    def test_individual_tampering_fails_without_masking_the_valid_artifact(self):
        for changed in self.artifacts:
            with self.subTest(artifact=changed.name):
                changed.write_text("Not generated from the current requirements.\n")
                result = self.invoke("--check")
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn(f"FAIL {changed.relative_to(self.root)}: differs", result.stdout)
                for unchanged in self.artifacts:
                    if unchanged != changed:
                        self.assertIn(f"PASS {unchanged.relative_to(self.root)}:", result.stdout)
                self.assertIn(f"Contract check: {len(self.artifacts) - 1}/{len(self.artifacts)} artifacts synchronized", result.stdout)
                changed.write_text(self.artifacts[changed])

    def test_owner_map_binds_owner_routes_to_the_input_digest(self):
        diagram = (self.root / "solution/OWNER_MAP.md").read_text()
        self.assertIn("core_03 --> CA_210", diagram)
        self.assertTrue(diagram.splitlines()[2].startswith("Input SHA256: "))
        self.assertNotIn("Reject invalid page sizes.", diagram)

    def test_generation_stdout_remains_an_apply_patch_stream(self):
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(result.stdout.startswith("*** Begin Patch\n"))
        self.assertTrue(result.stdout.endswith("*** End Patch\n"))
        self.assertNotIn("Contract check:", result.stdout)
        for path in self.artifacts:
            self.assertIn(f"*** Update File: {path.relative_to(self.root)}\n", result.stdout)


class OfflineSolutionLockRegression(unittest.TestCase):
    def make_clients(self, repository):
        for relative in npm_preparation.CLIENTS:
            client = repository / relative
            client.mkdir(parents=True)
            (client / "package.json").write_text(json.dumps({"dependencies": {"vite": "8.0.0"}}))
            (client / "package-lock.json").write_text(json.dumps({"packages": {"": {"dependencies": {"old": "1.0.0"}}}}))
            (client / "vite.config.js").write_text("export default { server: { port: 4321 } };\n")
            installed = client / "node_modules/@angular-devkit/build-angular"
            installed.mkdir(parents=True)
            (installed / "package.json").write_text('{"version": "18.2.19"}')
            (client / "node_modules/.package-lock.json").write_text('{"baseline": true}')

    def test_offline_resolution_updates_only_locks_and_uses_no_peer_exemption(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            self.make_clients(repository)
            originals = {path: path.read_bytes() for path in repository.rglob("*") if path.is_file() and path.name != "package-lock.json"}
            calls = []

            def resolve(command, *, cwd, online):
                calls.append((command, cwd, online))
                self.assertFalse((cwd / "node_modules").exists())
                self.assertFalse((cwd / "package-lock.json").exists())
                self.assertNotIn(cwd, [repository / relative for relative in npm_preparation.CLIENTS])
                (cwd / "package-lock.json").write_text(json.dumps({"packages": {"": json.loads((cwd / "package.json").read_text())}}))

            with patch.object(npm_preparation, "run_npm", side_effect=resolve):
                npm_preparation.resolve_offline_locks(repository)
            self.assertEqual(len(calls), 2)
            for command, client, online in calls:
                self.assertFalse(online)
                self.assertEqual(command, ["npm", "install", "--package-lock-only", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"])
                self.assertFalse(client.exists())
            for relative in npm_preparation.CLIENTS:
                client = repository / relative
                self.assertEqual(json.loads((client / "package-lock.json").read_text())["packages"][""],
                                 json.loads((client / "package.json").read_text()))
            for path, content in originals.items():
                self.assertEqual(path.read_bytes(), content)

    def test_offline_resolution_preserves_terminal_failure(self):
        for code in ("ERESOLVE", "ENOTCACHED"):
            with self.subTest(code=code), tempfile.TemporaryDirectory() as folder:
                repository = Path(folder)
                self.make_clients(repository)
                originals = {path: path.read_bytes() for path in repository.rglob("*") if path.is_file()}
                failure = subprocess.CalledProcessError(1, ["npm"], output=f"npm error code {code}")
                with patch.object(npm_preparation, "run_npm", side_effect=failure) as process, self.assertRaises(subprocess.CalledProcessError) as raised:
                    npm_preparation.resolve_offline_locks(repository)
                self.assertIs(raised.exception, failure)
                self.assertEqual(process.call_count, 1)
                self.assertFalse(list(repository.glob(".solution-lock-*")))
                for path, content in originals.items():
                    self.assertEqual(path.read_bytes(), content)

    def test_offline_resolution_rejects_unsynchronized_or_changed_inputs(self):
        for mutate in (False, True):
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as folder:
                repository = Path(folder)
                self.make_clients(repository)

                def invalid_resolution(command, *, cwd, online):
                    if mutate:
                        (cwd / "package.json").write_text('{"dependencies": {"vite": "9.0.0"}}')
                    (cwd / "package-lock.json").write_text('{"packages": {"": {"dependencies": {"old": "1.0.0"}}}}')

                with patch.object(npm_preparation, "run_npm", side_effect=invalid_resolution), self.assertRaises(ValueError):
                    npm_preparation.resolve_offline_locks(repository)

    def test_matching_lock_is_retained_and_repeated_resolution_is_isolated(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            self.make_clients(repository)
            for relative in npm_preparation.CLIENTS:
                client = repository / relative
                root = json.loads((client / "package.json").read_text())
                (client / "package-lock.json").write_text(json.dumps({"packages": {
                    "": root, "node_modules/vite": {"version": "8.0.0", "integrity": "pinned-fixture"}}}))
            original = {path: path.read_bytes() for path in repository.rglob("*") if path.is_file()}

            def resolve(command, *, cwd, online):
                self.assertFalse((cwd / "node_modules").exists())
                lock = json.loads((cwd / "package-lock.json").read_text())
                self.assertEqual(lock["packages"]["node_modules/vite"]["integrity"], "pinned-fixture")

            with patch.object(npm_preparation, "run_npm", side_effect=resolve) as process:
                npm_preparation.resolve_offline_locks(repository)
                npm_preparation.resolve_offline_locks(repository)
            self.assertEqual(process.call_count, 4)
            self.assertFalse(list(repository.glob(".solution-lock-*")))
            for path, content in original.items():
                self.assertEqual(path.read_bytes(), content)

    def test_missing_generated_lock_is_not_published(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            self.make_clients(repository)
            with patch.object(npm_preparation, "run_npm"), self.assertRaisesRegex(ValueError, "produced no lock"):
                npm_preparation.resolve_offline_locks(repository)
            self.assertFalse(list(repository.glob(".solution-lock-*")))

    def test_concurrent_input_change_is_not_overwritten(self):
        for filename in ("package.json", "package-lock.json"):
            with self.subTest(filename=filename), tempfile.TemporaryDirectory() as folder:
                repository = Path(folder)
                self.make_clients(repository)
                changed = repository / npm_preparation.CLIENTS[0] / filename
                replacement = b'{"changed": true}'

                def resolve(command, *, cwd, online):
                    (cwd / "package-lock.json").write_text(json.dumps({"packages": {
                        "": json.loads((cwd / "package.json").read_text())}}))
                    changed.write_bytes(replacement)

                with patch.object(npm_preparation, "run_npm", side_effect=resolve), self.assertRaisesRegex(ValueError, "changed during"):
                    npm_preparation.resolve_offline_locks(repository)
                self.assertEqual(changed.read_bytes(), replacement)

    def test_optional_and_peer_dependency_mismatches_fail_closed(self):
        for field in ("optionalDependencies", "peerDependencies"):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as folder:
                repository = Path(folder)
                self.make_clients(repository)

                def resolve(command, *, cwd, online):
                    root = json.loads((cwd / "package.json").read_text())
                    root[field] = {"wrong": "1.0.0"}
                    (cwd / "package-lock.json").write_text(json.dumps({"packages": {"": root}}))

                with patch.object(npm_preparation, "run_npm", side_effect=resolve), self.assertRaisesRegex(ValueError, field):
                    npm_preparation.resolve_offline_locks(repository)

    def test_real_helper_cli_uses_isolated_npm_working_directories(self):
        with tempfile.TemporaryDirectory() as folder:
            repository = Path(folder)
            self.make_clients(repository)
            binaries = repository / "bin"
            binaries.mkdir()
            executable = binaries / "npm"
            executable.write_text(f"#!{sys.executable}\n" + '''import json
import sys
from pathlib import Path
assert sys.argv[1:] == ["install", "--package-lock-only", "--offline", "--ignore-scripts", "--no-audit", "--no-fund"]
assert not Path("node_modules").exists()
assert not Path("package-lock.json").exists()
package = json.loads(Path("package.json").read_text())
Path("package-lock.json").write_text(json.dumps({"packages": {"": package}}))
print("PASS: fake npm observed isolated manifest and strict offline arguments")
''')
            executable.chmod(0o755)
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ.get("PATH", ""))
            result = subprocess.run([sys.executable, str(ROOT / "environment/prepare-npm.py"),
                                     "--resolve-offline-locks", "--repository", str(repository)],
                                    env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(result.stdout.count("PASS: fake npm"), 2)
            self.assertEqual(result.stdout.count("Resolved offline solution lock:"), 2)
            self.assertFalse(list(repository.glob(".solution-lock-*")))


class NoProvider:
    def configuration(self):
        return {"mode": "test-no-provider"}

    def render(self, envelope):
        raise AssertionError("navigation attempted provider rendering")

    def decide(self, envelope):
        raise AssertionError("navigation attempted a semantic decision")


class RepairRegression(unittest.TestCase):
    def state(self):
        return SemanticRuntimeState(
            ROOT / "environment/workplace-service/original/authoring",
            responder=NoProvider(), semantic_responder=NoProvider())

    def update(self, state, closeout=True, token=""):
        return _transactional_dispatch(state, {"action": "check_updates", "modules": [],
                                               "closeout": closeout, "worktree_progress": bool(token),
                                               "progress_token": token})

    def test_notification_retry_retains_ids_until_acknowledgment(self):
        state = self.state()
        first = self.update(state)
        self.assertEqual(first["released"], 8)
        self.assertEqual(first["unread_total"], 8)
        self.assertEqual(first["deferred_total"], 0)
        repeated = self.update(state)
        self.assertEqual(repeated["released"], 0)
        self.assertEqual([message["id"] for message in first["messages"]],
                         [message["id"] for message in repeated["messages"]])
        for conversation in state.messages:
            state.mark_read(conversation)
        final = self.update(state)
        self.assertEqual(final["messages"], [])
        self.assertEqual(final["unread_total"], 0)

    def test_progress_is_bounded_and_pending_visible(self):
        state = self.state()
        self.assertEqual(self.update(state, False)["released"], 0)
        first = self.update(state, False, "change-one")
        self.assertLessEqual(first["released"], 3)
        self.assertGreater(first["deferred_total"], 0)
        self.assertEqual(self.update(state, False, "change-one")["released"], 0)
        self.assertEqual(self.update(state)["released"] + first["released"], 8)

    def test_concurrent_final_sync_does_not_duplicate_notifications(self):
        state = self.state()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda request_index: self.update(state), range(2)))
        self.assertEqual(sum(result["released"] for result in results), 8)
        ids = [message["id"] for messages in state.messages.values() for message in messages]
        self.assertEqual(len(ids), len(set(ids)))

    def test_counting_does_not_conflate_nodes_reward_and_setup(self):
        config = {"f2p_node_ids": ["1", "2"], "p2p_node_ids": ["3", "4"]}
        rows = [{"pr_number": index, "return_code": code, "status": status}
                for index, code, status in [(1, 0, "passed"), (2, 1, "failed"),
                                             (3, 2, "infrastructure_error"), (4, 3, "compilation_error")]]
        normalized, counts = summarize(config, rows, {"status": "passed"})
        self.assertEqual(len(normalized), 4)
        self.assertEqual(counts["f2p_passed"], 1)
        self.assertEqual(counts["p2p_passed"], 0)
        for field in ("behavior_failures", "infrastructure_errors", "compilation_errors"):
            self.assertEqual(counts[field], 1)
        self.assertEqual(counts["reward"], 0)
        passed = [{"pr_number": index, "return_code": 0, "status": "passed"} for index in range(1, 5)]
        self.assertEqual(summarize(config, passed, {"status": "passed"})[1]["reward"], 1)
        self.assertEqual(summarize(config, passed, {"status": "compilation_error"})[1]["reward"], 0)
        self.assertEqual(summarize(config, passed + [passed[0]], {"status": "passed"})[1]["reward"], 0)
        self.assertEqual(summarize(config, passed[:-1], {"status": "passed"})[1]["infrastructure_errors"], 1)
        passed[0]["return_code"] = 3
        self.assertEqual(summarize(config, passed, {"status": "passed"})[1]["reward"], 0)

    def test_stale_results_are_not_staged(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            (source / ".segpipe_results.json").write_text('[{"status":"passed"}]')
            with patch.dict(os.environ, {"SEGPIPE_STAGE_ROOT": str(Path(folder) / "stage")}):
                stage = _stage_probe_tree(source)
            self.assertFalse((stage / "tests/.segpipe_results.json").exists())

    def test_setup_failure_attribution(self):
        with patch("production_checks.shutil.which", return_value=None):
            self.assertEqual(run_checks(ROOT)["status"], "infrastructure_error")
        success = subprocess.CompletedProcess([], 0, "Passed! - Failed: 0, Passed: 1, Skipped: 0, Total: 1")
        failure = subprocess.CompletedProcess([], 1, "diagnostic preserved")
        for results, expected in [([failure], "infrastructure_error"),
                                  ([success, failure], "infrastructure_error"),
                                  ([success, success, failure], "compilation_error"),
                                  ([success, success, success, failure], "failed")]:
            with patch("production_checks.shutil.which", return_value="dotnet"), patch(
                    "production_checks.subprocess.run", side_effect=results):
                report = run_checks(ROOT)
            self.assertEqual(report["status"], expected)
            self.assertEqual(report["steps"][-1]["output"], "diagnostic preserved")

    def test_real_probe_import_failure_is_infrastructure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            node = root / "1440"
            node.mkdir()
            (node / "check.py").write_text("import missing_repair_probe_support\n")
            result = run_one(root, 1440)
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(result["return_code"], 2)
        self.assertEqual(result["process_return_code"], 1)
        self.assertIn("ModuleNotFoundError", result["stderr"])

    def test_setup_distinguishes_unsupported_localdb_from_compiler_errors(self):
        unsupported = "System.PlatformNotSupportedException: LocalDB is not supported on this platform."
        compiler = "SqlTestDatabase.cs(43,50): error CS1503: cannot convert from 'string' to 'System.Data.Common.DbConnection'"
        success = subprocess.CompletedProcess([], 0, "Passed! - Failed: 0, Passed: 1, Skipped: 0, Total: 1")
        for output, expected in [(unsupported, "infrastructure_error"),
                                 (compiler, "compilation_error"),
                                 (unsupported + "\n" + compiler, "compilation_error")]:
            with self.subTest(output=output), patch("production_checks.shutil.which", return_value="available"), patch(
                    "production_checks.subprocess.run", side_effect=[success, success, subprocess.CompletedProcess([], 1, output)]) as runner:
                report = run_checks(ROOT)
            self.assertEqual(report["status"], expected)
            self.assertEqual(len(report["steps"]), 3)
            self.assertEqual(runner.call_count, 3)
            self.assertEqual(report["steps"][-1]["output"], output)
            self.assertEqual(report["steps"][-1]["return_code"], 1)
            self.assertEqual(report["steps"][-1]["terminal_state"], "exited")

    def test_setup_installs_current_client_graph_once_before_native_checks(self):
        with patch("production_checks.shutil.which", return_value="available"), patch(
                "production_checks.subprocess.run", return_value=subprocess.CompletedProcess([], 0, "Passed! - Failed: 0, Passed: 1, Skipped: 0, Total: 1")) as process:
            report = run_checks(ROOT)
        self.assertEqual(report["status"], "passed")
        commands = [call.args[0] for call in process.call_args_list]
        self.assertEqual(commands[0], ["python3", "/usr/local/lib/prepare-npm.py", "--repository", str(ROOT)])
        self.assertEqual([command[1] for command in commands[1:5]], ["restore", "build", "test", "test"])
        self.assertEqual(commands[5], ["python3", str(ROOT / "tests/purge_probe.py"), "--repository", str(ROOT)])
        self.assertIn("--configfile", commands[1])
        self.assertIn("/opt/nuget/NuGet.Config", commands[1])
        self.assertNotIn("--ignore-failed-sources", commands[1])
        self.assertEqual(len(report["steps"]), 6)
        self.assertTrue(all(call.kwargs["cwd"] == ROOT for call in process.call_args_list))

    def test_setup_separates_broken_project_or_lock_from_unavailable_dependency(self):
        success = subprocess.CompletedProcess([], 0, "Passed! - Failed: 0, Passed: 1, Skipped: 0, Total: 1")
        cases = [
            ([], "npm error code EUSAGE\nlock out of sync", "compilation_error"),
            ([], "npm error code ERESOLVE\nconflicting peer dependency", "compilation_error"),
            ([], "npm error code ENOTCACHED\nmissing cache", "infrastructure_error"),
            ([success], "error MSB3202: The project file was not found.", "compilation_error"),
            ([success], "error NU1010: PackageReference has no PackageVersion", "compilation_error"),
            ([success], "error NU1301: Unable to load service index", "infrastructure_error"),
        ]
        for prefix, output, expected in cases:
            with self.subTest(output=output), patch("production_checks.shutil.which", return_value="available"), patch(
                    "production_checks.subprocess.run", side_effect=prefix + [subprocess.CompletedProcess([], 1, output)]):
                report = run_checks(ROOT)
            self.assertEqual(report["status"], expected)
            self.assertEqual(report["steps"][-1]["return_code"], 1)
            self.assertEqual(report["steps"][-1]["output"], output)

    def test_production_purge_status_is_not_conflated_with_setup_compilation(self):
        success = subprocess.CompletedProcess([], 0, "Passed! - Failed: 0, Passed: 1, Skipped: 0, Total: 1")
        for code, status in ((1, "failed"), (2, "infrastructure_error"), (3, "compilation_error"), (127, "infrastructure_error")):
            with self.subTest(code=code), patch("production_checks.shutil.which", return_value="available"), patch(
                    "production_checks.subprocess.run", side_effect=[success] * 5 + [subprocess.CompletedProcess([], code, "purge diagnostic")]):
                report = run_checks(ROOT)
            self.assertEqual(report["status"], status)
            self.assertEqual(report["steps"][-1]["return_code"], code)
            self.assertEqual(report["steps"][-1]["output"], "purge diagnostic")

    def test_setup_rejects_zero_skipped_and_unreported_native_tests(self):
        success = subprocess.CompletedProcess([], 0, "build success")
        for output, expected in [("No test is available", "failed"),
                                 ("Passed! - Failed: 0, Passed: 0, Skipped: 0, Total: 0", "failed"),
                                 ("Passed! - Failed: 0, Passed: 1, Skipped: 1, Total: 2", "failed"),
                                 ("unparseable output", "infrastructure_error")]:
            with self.subTest(output=output), patch("production_checks.shutil.which", return_value="available"), patch(
                    "production_checks.subprocess.run", side_effect=[success]*3+[subprocess.CompletedProcess([], 0, output)]):
                self.assertEqual(run_checks(ROOT)["status"], expected)

    def test_setup_missing_npm_is_infrastructure_without_launching_checks(self):
        with patch("production_checks.shutil.which", side_effect=lambda executable: None if executable == "npm" else executable), patch(
                "production_checks.subprocess.run") as process:
            report = run_checks(ROOT)
        self.assertEqual(report["status"], "infrastructure_error")
        self.assertEqual(report["steps"], [])
        self.assertIn("npm", report["detail"])
        process.assert_not_called()

    def test_real_probe_exit_codes_survive_aggregation(self):
        config = {"f2p_node_ids": ["1440"], "p2p_node_ids": []}
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            node = root / "1440"
            node.mkdir()
            for code, status, normalized in [(0, "passed", 0), (7, "failed", 1),
                                              (2, "infrastructure_error", 2),
                                              (3, "compilation_error", 3)]:
                with self.subTest(code=code):
                    (node / "check.py").write_text(f"raise SystemExit({code})\n")
                    result = run_one(root, 1440)
                    self.assertEqual(result["return_code"], normalized)
                    self.assertEqual(result["process_return_code"], code)
                    self.assertEqual(result["status"], status)
                    rows, counts = summarize(config, [result], {"status": "passed"})
                    self.assertEqual(rows[0]["status"], status)
                    self.assertEqual(counts["reward"], int(code == 0))
                    self.assertEqual(counts["behavior_failures"], int(code == 7))

    def test_killed_probe_is_not_a_behavior_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            node = root / "1440"
            node.mkdir()
            (node / "check.py").write_text("import os, signal\nos.kill(os.getpid(), signal.SIGTERM)\n")
            result = run_one(root, 1440)
        self.assertEqual(result["status"], "infrastructure_error")
        self.assertEqual(result["return_code"], 2)
        self.assertLess(result["process_return_code"], 0)

    def test_setup_records_interrupted_command_without_inventing_exit_code(self):
        timeout = subprocess.TimeoutExpired(["dotnet", "build"], 900, output=b"partial build output\n")
        for failure, terminal in [(timeout, "timed_out"), (FileNotFoundError("dotnet vanished"), "launch_error")]:
            with self.subTest(terminal=terminal), patch("production_checks.shutil.which", return_value="dotnet"), patch(
                    "production_checks.subprocess.run", side_effect=[subprocess.CompletedProcess([], 0, "installed"), subprocess.CompletedProcess([], 0, "restored"), failure]):
                report = run_checks(ROOT)
            self.assertEqual(report["status"], "infrastructure_error")
            self.assertEqual(len(report["steps"]), 3)
            self.assertEqual(report["steps"][0]["terminal_state"], "exited")
            final = report["steps"][-1]
            self.assertEqual(final["terminal_state"], terminal)
            self.assertEqual(final["command"][1], "build")
            self.assertIsNone(final["return_code"])
            if terminal == "timed_out":
                self.assertEqual(final["output"], "partial build output\n")

    def test_probe_missing_sdk_is_not_behavior_failure(self):
        filename = ROOT / "tests/private-runtime/task-environment/probe_runtime.py"
        specification = importlib.util.spec_from_file_location("repair_probe", filename)
        module = importlib.util.module_from_spec(specification)
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, {
                "SEGPIPE_PROBE_CACHE": folder, "REPO_DIR_OVERRIDE": str(ROOT / "environment/base")}):
            specification.loader.exec_module(module)
            with patch.object(module, "dotnet_command", return_value=None):
                self.assertEqual(module.probe_1440(), 2)
                self.assertEqual(module.probe_1587(), 2)


class NpmPreparationRegression(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.repository = self.root / "repository"
        self.artifacts = self.root / "artifacts"
        self.original = {
            "lockfileVersion": 3,
            "packages": {
                "": {"name": "fixture", "dependencies": {"parent": "1.0.0"}},
                "node_modules/parent": {"version": "1.0.0", "integrity": "fixture-integrity",
                                        "peerDependencies": {"missing-peer": "^5.0.0"}},
            },
        }
        self.prepared = copy.deepcopy(self.original)
        self.prepared["packages"]["node_modules/missing-peer"] = {"version": "5.0.0"}
        for relative in npm_preparation.CLIENTS:
            client = self.repository / relative
            client.mkdir(parents=True)
            (client / "package.json").write_text(json.dumps(self.original["packages"][""]))
            (client / "package-lock.json").write_text(json.dumps(self.original))

    def fake_npm(self, command, *, cwd, online):
        self.assertTrue(online)
        if "--package-lock-only" in command:
            (cwd / "package-lock.json").write_text(json.dumps(self.prepared))
        return subprocess.CompletedProcess(command, 0)

    def warm(self):
        with patch.object(npm_preparation, "run_npm", side_effect=self.fake_npm) as process:
            npm_preparation.prepare(self.repository, self.artifacts, warm=True)
        return process.call_args_list

    def test_warm_adds_missing_peers_then_retains_strict_ci(self):
        calls = self.warm()
        self.assertEqual(len(calls), 4)
        for call in calls[1::2]:
            self.assertEqual(call.args[0][:2], ["npm", "ci"])
            self.assertNotIn("--legacy-peer-deps", call.args[0])
        for relative in npm_preparation.CLIENTS:
            saved = self.artifacts / Path(relative).name / "package-lock.json"
            self.assertEqual(json.loads(saved.read_text()), self.prepared)

    def test_rejects_upgrades_removals_manifest_and_integrity_changes(self):
        variants = []
        for field, value in [("version", "2.0.0"), ("integrity", "different"),
                             ("peerDependencies", {"missing-peer": "*"})]:
            changed = copy.deepcopy(self.prepared)
            changed["packages"]["node_modules/parent"][field] = value
            variants.append(changed)
        removed = copy.deepcopy(self.prepared)
        del removed["packages"]["node_modules/parent"]
        variants.append(removed)
        root_changed = copy.deepcopy(self.prepared)
        root_changed["packages"][""]["dependencies"]["parent"] = "2.0.0"
        variants.append(root_changed)
        for variant in variants:
            with self.subTest(variant=variant), self.assertRaises(ValueError):
                npm_preparation.validate_repair(self.original, variant)

    def test_reset_restores_prepared_lock_before_offline_ci_and_is_idempotent(self):
        self.warm()
        for relative in npm_preparation.CLIENTS:
            (self.repository / relative / "package-lock.json").write_text(json.dumps(self.original))
        for iteration in range(2):
            with patch.object(npm_preparation, "run_npm") as process:
                npm_preparation.prepare(self.repository, self.artifacts, warm=False)
            self.assertEqual(process.call_count, 2)
            for call in process.call_args_list:
                self.assertIn("--offline", call.args[0])
                self.assertFalse(call.kwargs["online"])
                self.assertEqual(call.args[0][:2], ["npm", "ci"])
                self.assertEqual(json.loads((call.kwargs["cwd"] / "package-lock.json").read_text()),
                                 self.prepared)

    def test_solver_manifest_and_lock_changes_are_never_overwritten(self):
        self.warm()
        for filename in ("package.json", "package-lock.json"):
            for relative in npm_preparation.CLIENTS:
                (self.repository / relative / "package.json").write_text(
                    json.dumps(self.original["packages"][""]))
                changed = self.repository / relative / filename
                changed.write_text('{"solver": "custom"}')
            with patch.object(npm_preparation, "run_npm"):
                npm_preparation.prepare(self.repository, self.artifacts, warm=False)
            for relative in npm_preparation.CLIENTS:
                self.assertEqual((self.repository / relative / filename).read_text(),
                                 '{"solver": "custom"}')

    def test_prepared_artifact_tampering_fails_closed(self):
        self.warm()
        artifact = self.artifacts / Path(npm_preparation.CLIENTS[0]).name / "package-lock.json"
        artifact.write_text('{}')
        with patch.object(npm_preparation, "run_npm") as process, self.assertRaises(ValueError):
            npm_preparation.prepare(self.repository, self.artifacts, warm=False)
        process.assert_not_called()

    def test_failed_ci_is_not_published_as_success(self):
        def npm_failure(command, *, cwd, online):
            if command[1] == "ci":
                raise subprocess.CalledProcessError(1, command)
            return self.fake_npm(command, cwd=cwd, online=online)

        with patch.object(npm_preparation, "run_npm", side_effect=npm_failure), self.assertRaises(
                subprocess.CalledProcessError):
            npm_preparation.prepare(self.repository, self.artifacts, warm=True)
        self.assertFalse(self.artifacts.exists())


class FrozenReactBaselineRegression(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.relative = "src/Web/ClientApp-React"
        self.repository = self.root / "repository"
        self.client = self.repository / self.relative
        self.client.mkdir(parents=True)
        # Model the whole checkout even when this unit isolates React's legacy
        # npm branch. A native image may also contain the sealed two-client
        # catalogue; an intentionally unknown Angular fixture makes that
        # shortcut inapplicable without depending on host /opt contents.
        angular = self.repository / "src/Web/ClientApp"
        angular.mkdir(parents=True)
        (angular / "package.json").write_text('{"name":"unknown-angular-unit-fixture","private":true}')
        (angular / "package-lock.json").write_text('{"lockfileVersion":3,"packages":{}}')
        self.artifacts = self.root / "artifacts"
        self.original = {}
        for filename in ("package.json", "package-lock.json"):
            content = (ROOT / "environment/base" / self.relative / filename).read_bytes()
            self.original[filename] = content
            (self.client / filename).write_bytes(content)
        executable = self.root / "npm"
        executable.write_text(
            f"#!{sys.executable}\nimport json, os, pathlib, sys\n"
            "with pathlib.Path('commands.jsonl').open('a') as output:\n"
            "    output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
            "raise SystemExit(int(os.environ.get('FAKE_NPM_EXIT', '0')))\n")
        executable.chmod(0o755)
        environment = patch.dict(os.environ, {
            "PATH": str(self.root) + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_NPM_EXIT": "0",
        })
        environment.start()
        self.addCleanup(environment.stop)
        clients = patch.object(npm_preparation, "CLIENTS", (self.relative,))
        clients.start()
        self.addCleanup(clients.stop)

    def prepare(self, warm):
        npm_preparation.prepare(self.repository, self.artifacts, warm=warm)

    def commands(self):
        return [json.loads(line) for line in (self.client / "commands.jsonl").read_text().splitlines()]

    def test_known_conflicting_graph_is_replayed_without_resolution_or_mutation(self):
        locked = json.loads(self.original["package-lock.json"])
        self.assertEqual(locked["lockfileVersion"], 2)
        self.assertEqual(locked["packages"]["node_modules/eslint"]["version"], "9.26.0")
        self.assertEqual(locked["packages"]["node_modules/eslint-config-react-app"]["peerDependencies"],
                         {"eslint": "^8.0.0"})
        self.prepare(warm=True)
        self.prepare(warm=False)
        self.prepare(warm=False)
        commands = self.commands()
        self.assertEqual(len(commands), 3)
        for index, command in enumerate(commands):
            self.assertEqual(command[0], "ci")
            self.assertIn("--legacy-peer-deps", command)
            self.assertEqual("--offline" in command, index > 0)
            self.assertNotIn("--force", command)
        for filename, content in self.original.items():
            self.assertEqual((self.client / filename).read_bytes(), content)
        saved = self.artifacts / "ClientApp-React"
        self.assertEqual((saved / "package-lock.json").read_bytes(), self.original["package-lock.json"])
        receipt = json.loads((saved / "receipt.json").read_text())
        self.assertEqual(receipt["original_lock_sha256"], receipt["prepared_lock_sha256"])
        self.assertEqual(receipt["install_arguments"], ["--legacy-peer-deps"])

    def test_path_manifest_and_lock_must_all_match_the_frozen_baseline(self):
        manifest = self.original["package.json"]
        lock = self.original["package-lock.json"]
        self.assertEqual(npm_preparation.baseline_install_arguments(self.relative, manifest, lock),
                         ["--legacy-peer-deps"])
        for relative, package, locked in [
                ("src/Web/ClientApp", manifest, lock),
                ("/opt/offline-target/react", manifest, lock),
                (self.relative, manifest + b"\n", lock),
                (self.relative, manifest, lock + b"\n")]:
            with self.subTest(relative=relative, package=package[-4:], locked=locked[-4:]):
                self.assertEqual(npm_preparation.baseline_install_arguments(relative, package, locked), [])

    def test_modified_react_inputs_never_inherit_receipt_peer_exemption(self):
        self.prepare(warm=True)
        for filename in self.original:
            for name, content in self.original.items():
                (self.client / name).write_bytes(content)
            changed = json.loads(self.original[filename])
            if filename == "package.json":
                changed["dependencies"]["react"] = "19.1.0"
            else:
                changed["packages"]["node_modules/eslint"]["version"] = "9.27.0"
            content = json.dumps(changed).encode()
            (self.client / filename).write_bytes(content)
            self.prepare(warm=False)
            self.assertNotIn("--legacy-peer-deps", self.commands()[-1])
            self.assertIn("--offline", self.commands()[-1])
            self.assertEqual((self.client / filename).read_bytes(), content)

    def test_failed_legacy_ci_never_publishes_a_receipt(self):
        with patch.dict(os.environ, {"FAKE_NPM_EXIT": "42"}), self.assertRaises(
                subprocess.CalledProcessError) as failure:
            self.prepare(warm=True)
        self.assertEqual(failure.exception.returncode, 42)
        self.assertEqual(len(self.commands()), 1)
        self.assertFalse(self.artifacts.exists())

    def test_untrusted_receipt_cannot_enable_legacy_policy_for_other_inputs(self):
        self.prepare(warm=True)
        manifest = self.original["package.json"] + b"\n"
        (self.client / "package.json").write_bytes(manifest)
        receipt_path = self.artifacts / "ClientApp-React/receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["manifest_sha256"] = npm_preparation.digest(manifest)
        receipt["install_arguments"] = ["--legacy-peer-deps", "--force"]
        receipt_path.write_text(json.dumps(receipt))
        self.prepare(warm=False)
        self.assertNotIn("--legacy-peer-deps", self.commands()[-1])
        self.assertNotIn("--force", self.commands()[-1])


class NpmRetryRegression(unittest.TestCase):
    def test_build_cli_forwards_target_install_arguments(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            executable = root / "npm"
            executable.write_text(
                f"#!{sys.executable}\nimport json, pathlib, sys\n"
                "pathlib.Path('arguments.json').write_text(json.dumps(sys.argv[1:]))\n")
            executable.chmod(0o755)
            environment = os.environ.copy()
            environment["PATH"] = str(root) + os.pathsep + environment.get("PATH", "")
            result = subprocess.run(
                [sys.executable, str(ROOT / "environment/prepare-npm.py"), "--retry-online", "--",
                 "install", "--ignore-scripts", "--no-audit", "--no-fund"],
                cwd=root, env=environment, capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(json.loads((root / "arguments.json").read_text()),
                             ["install", "--ignore-scripts", "--no-audit", "--no-fund"])
            self.assertIn("npm attempt 1/3", result.stdout)

    def controlled_process(self, *, failures, output, online=True, offline_flag=False):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            program = root / "controlled_npm.py"
            program.write_text(
                "import pathlib, sys\n"
                "counter = pathlib.Path('calls')\n"
                "attempt = int(counter.read_text()) + 1 if counter.exists() else 1\n"
                "counter.write_text(str(attempt))\n"
                f"print({output!r} if attempt <= {failures} else 'installed fixture')\n"
                f"sys.exit(146 if attempt <= {failures} else 0)\n")
            command = [sys.executable, str(program)] + (["--offline"] if offline_flag else [])
            captured = io.StringIO()
            error = None
            with patch.object(npm_preparation.time, "sleep") as sleep, redirect_stdout(captured):
                try:
                    npm_preparation.run_npm(command, cwd=root, online=online)
                except subprocess.CalledProcessError as failure:
                    error = failure
            return int((root / "calls").read_text()), captured.getvalue(), sleep.call_args_list, error

    def test_real_child_retry_recovers_transient_network_failure(self):
        calls, output, sleeps, error = self.controlled_process(failures=2, output="npm error code ETIMEDOUT")
        self.assertEqual(calls, 3)
        self.assertIsNone(error)
        self.assertIn("installed fixture", output)
        self.assertEqual(output.count("npm error code ETIMEDOUT"), 2)
        self.assertEqual([entry.args[0] for entry in sleeps], [5, 10])

    def test_exhausted_network_failure_preserves_last_exit_and_diagnostics(self):
        calls, output, sleeps, error = self.controlled_process(failures=8, output="npm error code ECONNRESET")
        self.assertEqual(calls, 3)
        self.assertEqual(len(sleeps), 2)
        self.assertEqual(error.returncode, 146)
        self.assertIn("ECONNRESET", error.output)
        self.assertNotIn("installed fixture", output)

    def test_dependency_auth_and_integrity_failures_never_retry(self):
        for code in ("EUSAGE", "ERESOLVE", "EINTEGRITY", "E401", "E403", "E404", "ENOTFOUND"):
            with self.subTest(code=code):
                calls, output, sleeps, error = self.controlled_process(failures=1, output=f"npm error code {code}")
                self.assertEqual(calls, 1)
                self.assertEqual(sleeps, [])
                self.assertEqual(error.returncode, 146)

    def test_offline_install_never_retries_or_switches_to_network(self):
        for online, offline_flag in [(False, False), (True, True)]:
            with self.subTest(online=online, offline_flag=offline_flag):
                calls, output, sleeps, error = self.controlled_process(
                    failures=1, output="npm error code ETIMEDOUT", online=online, offline_flag=offline_flag)
                self.assertEqual(calls, 1)
                self.assertEqual(sleeps, [])
                self.assertEqual(error.returncode, 146)

    def test_bare_timeout_word_does_not_trigger_retry(self):
        calls, output, sleeps, error = self.controlled_process(failures=1, output="project test failed: ETIMEDOUT")
        self.assertEqual(calls, 1)
        self.assertEqual(sleeps, [])
        self.assertIsNotNone(error)

    def test_process_deadline_preserves_output_and_propagates_after_exhaustion(self):
        error = subprocess.TimeoutExpired(["npm", "ci"], 600, output=b"last network diagnostic\n")
        captured = io.StringIO()
        with patch.object(npm_preparation.subprocess, "run", side_effect=error) as process, patch.object(
                npm_preparation.time, "sleep") as sleep, redirect_stdout(captured), self.assertRaises(subprocess.TimeoutExpired) as raised:
            npm_preparation.run_npm(["npm", "ci"], cwd=ROOT, online=True)
        self.assertIs(raised.exception, error)
        self.assertEqual(process.call_count, 3)
        for call in process.call_args_list:
            self.assertEqual(call.args[0], ["npm", "ci"])
            self.assertEqual(call.kwargs["timeout"], 600)
        self.assertEqual(captured.getvalue().count("last network diagnostic"), 3)
        self.assertEqual(captured.getvalue().count("terminal_state=timed_out"), 3)
        self.assertEqual([entry.args[0] for entry in sleep.call_args_list], [5, 10])

    def controlled_deadline(self, *, failures, online=True, offline_flag=False, diagnostic=""):
        real_run = subprocess.run
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            program = root / "controlled_deadline.py"
            program.write_text(
                "import pathlib, sys, time\n"
                "counter = pathlib.Path('calls')\n"
                "attempt = int(counter.read_text()) + 1 if counter.exists() else 1\n"
                "counter.write_text(str(attempt))\n"
                "print(f'progress attempt {attempt}', flush=True)\n"
                f"print({diagnostic!r}, flush=True)\n"
                f"time.sleep(10) if attempt <= {failures} else print('completed', flush=True)\n")
            command = [sys.executable, str(program)] + (["--offline"] if offline_flag else [])
            captured = io.StringIO()
            error = None

            def bounded_child(argv, **arguments):
                self.assertEqual(argv, command)
                self.assertEqual(arguments["timeout"], 600)
                arguments["timeout"] = 0.5
                return real_run(argv, **arguments)

            with patch.object(npm_preparation.subprocess, "run", side_effect=bounded_child) as process, patch.object(
                    npm_preparation.time, "sleep") as sleep, redirect_stdout(captured):
                try:
                    npm_preparation.run_npm(command, cwd=root, online=online)
                except subprocess.TimeoutExpired as failure:
                    error = failure
            return int((root / "calls").read_text()), captured.getvalue(), sleep.call_args_list, error, process.call_args_list

    def test_real_child_timeout_recovers_on_third_attempt(self):
        calls, output, sleeps, error, commands = self.controlled_deadline(failures=2)
        self.assertEqual(calls, 3)
        self.assertIsNone(error)
        self.assertIn("completed", output)
        self.assertEqual(output.count("terminal_state=timed_out"), 2)
        self.assertIn("terminal_state=exited return_code=0", output)
        self.assertEqual([entry.args[0] for entry in sleeps], [5, 10])
        for attempt in range(1, 4):
            self.assertIn(f"progress attempt {attempt}", output)
        self.assertEqual(len(commands), 3)

    def test_real_child_timeout_exhaustion_retains_final_exception(self):
        calls, output, sleeps, error, commands = self.controlled_deadline(failures=8)
        self.assertEqual(calls, 3)
        self.assertEqual([entry.args[0] for entry in sleeps], [5, 10])
        self.assertIsInstance(error, subprocess.TimeoutExpired)
        self.assertEqual(error.cmd, commands[-1].args[0])
        self.assertIn("progress attempt 3", npm_preparation.output_text(error.stdout))
        self.assertNotIn("completed", output)
        self.assertIn("npm attempt 3/3", output)

    def test_real_child_offline_timeout_never_retries(self):
        for online, offline_flag in [(False, False), (True, True)]:
            with self.subTest(online=online, offline_flag=offline_flag):
                calls, output, sleeps, error, commands = self.controlled_deadline(
                    failures=8, online=online, offline_flag=offline_flag)
                self.assertEqual(calls, 1)
                self.assertEqual(sleeps, [])
                self.assertIsInstance(error, subprocess.TimeoutExpired)
                self.assertIn("progress attempt 1", output)
                self.assertIn("npm attempt 1/1", output)
                self.assertEqual(len(commands), 1)

    def test_deterministic_error_in_partial_output_prevents_timeout_retry(self):
        for code in ("EUSAGE", "ERESOLVE", "EINTEGRITY", "ENOTCACHED", "E401"):
            with self.subTest(code=code):
                diagnostic = f"npm error code ETIMEDOUT\nnpm error code {code}"
                calls, output, sleeps, error, commands = self.controlled_deadline(failures=8, diagnostic=diagnostic)
                self.assertEqual(calls, 1)
                self.assertEqual(sleeps, [])
                self.assertIsInstance(error, subprocess.TimeoutExpired)
                self.assertIn(diagnostic, output)
                self.assertEqual(len(commands), 1)

    def test_mixed_terminal_errors_do_not_retry(self):
        calls, output, sleeps, error = self.controlled_process(
            failures=8, output="npm error code ETIMEDOUT\nnpm ERR! code ERESOLVE")
        self.assertEqual(calls, 1)
        self.assertEqual(sleeps, [])
        self.assertEqual(error.returncode, 146)
        self.assertIn("ERESOLVE", error.output)

    def test_online_diagnostics_preserve_command_and_environment(self):
        with patch.dict(os.environ, {"QUALITY_SENTINEL": "unchanged"}, clear=True), patch.object(
                npm_preparation.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "")) as process, redirect_stdout(io.StringIO()) as output:
            npm_preparation.run_npm(["npm", "ci", "--ignore-scripts"], cwd=ROOT, online=True)
            self.assertNotIn("npm_config_loglevel", os.environ)
        self.assertEqual(process.call_args.args[0], ["npm", "ci", "--ignore-scripts"])
        self.assertEqual(process.call_args.kwargs.get("env", {}), {"QUALITY_SENTINEL": "unchanged", "npm_config_loglevel": "verbose"})
        self.assertIn('["npm", "ci", "--ignore-scripts"]', output.getvalue())

    def test_explicit_loglevel_and_offline_environment_are_preserved(self):
        for online, environment in [(True, {"npm_config_loglevel": "info"}), (True, {"NPM_CONFIG_LOGLEVEL": "info"}), (False, {})]:
            with self.subTest(online=online), patch.dict(os.environ, environment, clear=True), patch.object(
                    npm_preparation.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "")) as process, redirect_stdout(io.StringIO()):
                npm_preparation.run_npm(["npm", "ci"], cwd=ROOT, online=online)
                self.assertEqual(process.call_args.kwargs.get("env", dict(os.environ)), environment)


if __name__ == "__main__":
    unittest.main(verbosity=2)
