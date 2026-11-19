#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("prepare_playwright", ROOT / "environment/prepare-playwright.py")
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


class PlaywrightPreparationRegression(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="browser-regression-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)

    def test_real_subprocess_success_and_failure_are_preserved(self):
        output = PREPARE.run([sys.executable, "-c", "print('controlled child output')"],
                             timeout=5, capture=True)
        self.assertEqual(output.strip(), "controlled child output")
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            PREPARE.run([sys.executable, "-c", "raise SystemExit(7)"], timeout=5)
        self.assertEqual(caught.exception.returncode, 7)

    def test_deadline_kills_real_descendant_and_is_not_success(self):
        marker = self.work / "late-child-output"
        pid_file = self.work / "child-pid"
        child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).write_text('leaked')"
        parent = ("import subprocess, sys, time; from pathlib import Path; "
                  f"child = subprocess.Popen([sys.executable, '-c', {child!r}]); "
                  f"Path({str(pid_file)!r}).write_text(str(child.pid)); time.sleep(10)")
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            PREPARE.run([sys.executable, "-c", parent], timeout=0.5, capture=True)
        self.assertLess(time.monotonic() - started, 5)
        self.assertTrue(pid_file.is_file())
        time.sleep(1.1)
        self.assertFalse(marker.exists(), "timed-out npm descendant remained alive")

    def test_only_reviewed_exact_versions_are_accepted(self):
        for version in PREPARE.VERSIONS:
            command = PREPARE.command(version, ["install", "chromium"], offline=False)
            self.assertIn(f"--package=playwright@{version}", command)
            self.assertEqual(command[-2:], ["install", "chromium"])
        with self.assertRaises(ValueError):
            PREPARE.command("latest", [], offline=False)

    def test_download_deadline_retries_identical_command_once(self):
        with patch.object(PREPARE, "run", side_effect=[subprocess.TimeoutExpired(["fixture"], 900), ""]) as runner:
            with patch.object(PREPARE.time, "sleep") as sleep:
                PREPARE.install("1.56.0")
        self.assertEqual(runner.call_count, 2)
        self.assertEqual(runner.call_args_list[0], runner.call_args_list[1])
        self.assertEqual(runner.call_args.kwargs["timeout"], 900)
        sleep.assert_called_once_with(5)

    def native_plan(self, prefix=PREPARE.CFT_CDN):
        return (f"browser: chromium version 145.0.7632.6\n"
                f"  Download url: {prefix}145.0.7632.6/linux64/chrome-linux64.zip\n"
                "  Download fallback 1: https://unused.example/fallback.zip\n"
                "browser: ffmpeg\n"
                "  Download url: https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-linux.zip\n"
                "browser: chromium-headless-shell version 145.0.7632.6\n"
                f"  Download url: {prefix}145.0.7632.6/linux64/chrome-headless-shell-linux64.zip\n"
                "browser: ffmpeg\n"
                "  Download url: https://cdn.playwright.dev/dbazure/download/playwright/builds/ffmpeg/1011/ffmpeg-linux.zip\n")

    def controlled_native_plan(self, arguments, *, environment=None, **kwargs):
        self.assertEqual(arguments, PREPARE.command("1.58.0", ["install", "--dry-run", "chromium"], offline=False))
        prefix = PREPARE.CFT_CDN if environment is None else environment[PREPARE.CHROMIUM_HOST] + "/"
        return self.native_plan(prefix)

    def test_origin_routes_only_matching_native_cft_artifacts(self):
        original_environment = {"PATH": os.environ.get("PATH", ""), "RETAIN_FIXTURE": "present"}
        with patch.dict(os.environ, original_environment, clear=True):
            with patch.object(PREPARE, "run", side_effect=self.controlled_native_plan) as runner:
                environment = PREPARE.origin_environment("1.58.0")
            self.assertEqual(dict(os.environ), original_environment)
        self.assertEqual(environment[PREPARE.CHROMIUM_HOST], "https://storage.googleapis.com/chrome-for-testing-public")
        self.assertEqual(environment["RETAIN_FIXTURE"], "present")
        self.assertNotIn("PLAYWRIGHT_DOWNLOAD_HOST", environment)
        self.assertEqual(runner.call_args_list[0].args, runner.call_args_list[1].args)
        self.assertEqual(runner.call_args.args[0][-3:], ["install", "--dry-run", "chromium"])
        self.assertEqual(runner.call_args.kwargs["timeout"], PREPARE.CHECK_TIMEOUT_SECONDS)
        self.assertEqual(runner.call_args.kwargs["environment"], environment)

    def test_origin_rejects_drift_ignored_override_and_missing_artifacts(self):
        for routed in [self.native_plan(), self.native_plan("https://storage.googleapis.com/"),
                       self.native_plan(PREPARE.CFT_ORIGIN).replace("145.0.7632.6", "146.0.0.0"),
                       self.native_plan(PREPARE.CFT_ORIGIN).replace("ffmpeg/1011", "ffmpeg/9999"),
                       self.native_plan(PREPARE.CFT_ORIGIN).replace("chrome-headless-shell-linux64.zip", "different.zip")]:
            with self.subTest(routed=routed), patch.dict(os.environ, {}, clear=True):
                with patch.object(PREPARE, "run", side_effect=[self.native_plan(), routed]):
                    with self.assertRaisesRegex(ValueError, "artifact identity"):
                        PREPARE.origin_environment("1.58.0")
        for original in ["empty", self.native_plan().replace("https://", "http://"),
                         self.native_plan().replace("https://cdn.playwright.dev/dbazure", "http://cdn.playwright.dev/dbazure"),
                         self.native_plan().replace("chrome-headless-shell-linux64.zip", "../../foreign.zip"),
                         self.native_plan().replace("145.0.7632.6/linux64/chrome-headless", "146.0.0.0/linux64/chrome-headless"),
                         self.native_plan().replace("linux64", "linux-arm64")]:
            with self.subTest(original=original), patch.dict(os.environ, {}, clear=True):
                with patch.object(PREPARE, "run", return_value=original) as runner:
                    with self.assertRaises(ValueError):
                        PREPARE.origin_environment("1.58.0")
                    self.assertEqual(runner.call_count, 1)

    def test_origin_rejects_inherited_download_overrides_and_other_versions(self):
        for variable in ("PLAYWRIGHT_DOWNLOAD_HOST", PREPARE.CHROMIUM_HOST):
            with patch.dict(os.environ, {variable: "https://unreviewed.invalid"}, clear=True):
                with patch.object(PREPARE, "run") as runner, self.assertRaisesRegex(ValueError, "inherited"):
                    PREPARE.origin_environment("1.58.0")
                runner.assert_not_called()
        with self.assertRaises(ValueError):
            PREPARE.origin_environment("1.56.0")

    def test_pinned_installer_uses_validated_origin_and_does_not_skip_browsers(self):
        environment = {PREPARE.CHROMIUM_HOST: "https://storage.googleapis.com/chrome-for-testing-public"}
        with patch.object(PREPARE, "origin_environment", return_value=environment) as routing:
            with patch.object(PREPARE, "run", return_value="") as runner:
                PREPARE.install("1.58.0")
        routing.assert_called_once_with("1.58.0")
        runner.assert_called_once_with(PREPARE.command("1.58.0", ["install", "chromium"], offline=False),
                                       timeout=4200, progress_timeout=900, environment=environment)

    def progress_child(self, statements):
        return [sys.executable, "-u", "-c", "import sys, time; " + statements]

    def test_real_forward_progress_survives_multiple_idle_windows(self):
        statements = ("print('Downloading Chrome from https://example.invalid/chrome.zip'); "
                      "print('|    | 0% of 1 MiB'); "
                      "time.sleep(0.25); print('|x   | 10% of 1 MiB'); "
                      "time.sleep(0.25); print('|xx  | 20% of 1 MiB'); "
                      "time.sleep(0.25); print('|xxx | 100% of 1 MiB')")
        started = time.monotonic()
        PREPARE.run(self.progress_child(statements), timeout=3, progress_timeout=0.6)
        self.assertGreater(time.monotonic() - started, 0.6)

    def test_real_artifact_transition_resets_progress(self):
        statements = ("print('Downloading Chrome from https://example.invalid/chrome.zip'); "
                      "print('|xxx | 100% of 1 MiB'); time.sleep(0.3); "
                      "print('Downloading Shell from https://example.invalid/shell.zip'); "
                      "print('|    | 0% of 2 MiB'); time.sleep(0.3); "
                      "print('|x   | 10% of 2 MiB'); time.sleep(0.3)")
        PREPARE.run(self.progress_child(statements), timeout=3, progress_timeout=0.6)

    def test_real_log_noise_retries_and_regressions_do_not_extend_idle_budget(self):
        for message in ["still alive", "|xx | 20% of 1 MiB", "|x | 10% of 1 MiB",
                        "|xx | 101% of 1 MiB", "Downloading Chrome from https://example.invalid/chrome.zip"]:
            statements = ("print('Downloading Chrome from https://example.invalid/chrome.zip'); "
                          "print('|xx | 20% of 1 MiB'); "
                          f"exec(\"for cycle in range(20):\\n print({message!r})\\n time.sleep(0.1)\")")
            with self.subTest(message=message), self.assertRaises(subprocess.TimeoutExpired):
                PREPARE.run(self.progress_child(statements), timeout=3, progress_timeout=0.4)

    def test_real_progress_never_extends_absolute_deadline(self):
        statements = ("print('Downloading Chrome from https://example.invalid/chrome.zip'); "
                      "exec(\"for percent in range(100):\\n print(f'|x | {percent}% of 1 MiB')\\n time.sleep(0.1)\")")
        started = time.monotonic()
        with self.assertRaises(subprocess.TimeoutExpired):
            PREPARE.run(self.progress_child(statements), timeout=0.55, progress_timeout=0.4)
        self.assertLess(time.monotonic() - started, 2)

    def test_real_idle_timeout_kills_descendants_even_after_stdout_closes(self):
        marker = self.work / "idle-descendant"
        child = f"import time; from pathlib import Path; time.sleep(1); Path({str(marker)!r}).touch()"
        parent = ("import subprocess, os; "
                  f"subprocess.Popen([sys.executable, '-c', {child!r}], stdout=subprocess.DEVNULL); "
                  "os.close(1); time.sleep(10)")
        with self.assertRaises(subprocess.TimeoutExpired):
            PREPARE.run(self.progress_child(parent), timeout=3, progress_timeout=0.4)
        time.sleep(1.1)
        self.assertFalse(marker.exists())

    def test_real_closed_stdout_and_native_error_are_not_success(self):
        for statements, status in [("import os; os.close(1); time.sleep(0.1); raise SystemExit(7)", 7),
                                   ("print('native failure'); raise SystemExit(23)", 23)]:
            with self.subTest(status=status), self.assertRaises(subprocess.CalledProcessError) as caught:
                PREPARE.run(self.progress_child(statements), timeout=3, progress_timeout=0.6)
            self.assertEqual(caught.exception.returncode, status)

    def test_real_progress_handles_fragmented_unicode_and_carriage_returns(self):
        statements = ("data = 'Downloading Chrome from https://example.invalid/chrome.zip\\r|■■ | 20% of 1 MiB\\r'.encode(); "
                      "exec('for offset in range(0, len(data), 2):\\n sys.stdout.buffer.write(data[offset:offset+2]); sys.stdout.buffer.flush()'); "
                      "time.sleep(0.3); print('|■■■■ | 40% of 1 MiB'); time.sleep(0.3)")
        PREPARE.run(self.progress_child(statements), timeout=3, progress_timeout=0.6)

    def test_total_install_budget_includes_fallback_and_sleep(self):
        with patch.object(PREPARE, "origin_environment", return_value={}):
            with patch.object(PREPARE.time, "monotonic", side_effect=[0, 0, 4205]):
                with patch.object(PREPARE.time, "sleep"):
                    with patch.object(PREPARE, "run", side_effect=[subprocess.TimeoutExpired(["origin"], 4200), ""]) as runner:
                        PREPARE.install("1.58.0")
        self.assertEqual([call.kwargs["timeout"] for call in runner.call_args_list], [4200, 895])
        self.assertEqual([call.kwargs["progress_timeout"] for call in runner.call_args_list], [900, 900])

    def test_exhausted_total_budget_prevents_fallback(self):
        with patch.object(PREPARE, "origin_environment", return_value={}):
            with patch.object(PREPARE.time, "monotonic", side_effect=[0, 0, 5101]):
                with patch.object(PREPARE.time, "sleep"):
                    with patch.object(PREPARE, "run", side_effect=subprocess.TimeoutExpired(["origin"], 4200)) as runner:
                        with self.assertRaises(subprocess.TimeoutExpired):
                            PREPARE.install("1.58.0")
        self.assertEqual(runner.call_count, 1)

    def test_origin_failure_falls_back_to_original_native_route_once(self):
        environment = {PREPARE.CHROMIUM_HOST: "https://storage.googleapis.com/chrome-for-testing-public"}
        for failure in [subprocess.TimeoutExpired(["origin"], 900), subprocess.CalledProcessError(23, ["origin"])]:
            with self.subTest(failure=type(failure).__name__), patch.object(PREPARE, "origin_environment", return_value=environment):
                with patch.object(PREPARE, "run", side_effect=[failure, ""]) as runner:
                    with patch.object(PREPARE.time, "sleep"):
                        PREPARE.install("1.58.0")
                self.assertEqual(runner.call_count, 2)
                self.assertEqual(runner.call_args_list[0].args, runner.call_args_list[1].args)
                self.assertEqual(runner.call_args_list[0].kwargs["environment"], environment)
                self.assertIsNone(runner.call_args_list[1].kwargs["environment"])
        with patch.object(PREPARE, "origin_environment", return_value=environment):
            with patch.object(PREPARE, "run", side_effect=subprocess.CalledProcessError(23, ["native"])) as runner:
                with patch.object(PREPARE.time, "sleep"), self.assertRaises(subprocess.CalledProcessError):
                    PREPARE.install("1.58.0")
            self.assertEqual(runner.call_count, 2)

    def test_install_carries_checked_bucket_path_into_native_download(self):
        calls = []

        def controlled_cli(arguments, **kwargs):
            calls.append((arguments, kwargs))
            if "--dry-run" in arguments:
                return self.controlled_native_plan(arguments, **kwargs)
            self.assertEqual(arguments, PREPARE.command("1.58.0", ["install", "chromium"], offline=False))
            self.assertEqual(kwargs["environment"][PREPARE.CHROMIUM_HOST],
                             "https://storage.googleapis.com/chrome-for-testing-public")
            return ""

        with patch.dict(os.environ, {}, clear=True), patch.object(PREPARE, "run", side_effect=controlled_cli):
            PREPARE.install("1.58.0")
        self.assertEqual(len(calls), 3)
        self.assertEqual(calls[1][1]["environment"], calls[2][1]["environment"])

    def test_route_validation_handles_other_native_browser_versions(self):
        def controlled_cli(arguments, **kwargs):
            return self.controlled_native_plan(arguments, **kwargs).replace("145.0.7632.6", "145.0.7632.7")

        with patch.dict(os.environ, {}, clear=True), patch.object(PREPARE, "run", side_effect=controlled_cli):
            environment = PREPARE.origin_environment("1.58.0")
        self.assertEqual(environment[PREPARE.CHROMIUM_HOST], "https://storage.googleapis.com/chrome-for-testing-public")

    def test_invalid_origin_plan_prevents_any_install_attempt(self):
        with patch.object(PREPARE, "origin_environment", side_effect=ValueError("invalid plan")):
            with patch.object(PREPARE, "run") as runner, self.assertRaisesRegex(ValueError, "invalid plan"):
                PREPARE.install("1.58.0")
            runner.assert_not_called()

    def test_real_child_environment_is_explicit_and_not_global(self):
        environment = dict(os.environ, BROWSER_ROUTE_FIXTURE="child-only")
        output = PREPARE.run([sys.executable, "-c", "import os; print(os.environ['BROWSER_ROUTE_FIXTURE'])"],
                             timeout=5, capture=True, environment=environment)
        self.assertEqual(output.strip(), "child-only")
        self.assertNotIn("BROWSER_ROUTE_FIXTURE", os.environ)

    def test_exhausted_deadline_and_native_errors_are_not_suppressed(self):
        for failure, expected_calls in [(subprocess.TimeoutExpired(["fixture"], 900), 2),
                                        (subprocess.CalledProcessError(23, ["fixture"]), 1)]:
            with self.subTest(failure=type(failure).__name__), patch.object(PREPARE, "run", side_effect=failure) as runner:
                with patch.object(PREPARE.time, "sleep"), self.assertRaises(type(failure)):
                    PREPARE.install("1.56.0")
                self.assertEqual(runner.call_count, expected_calls)

    def test_main_preserves_failure_classification(self):
        for failure, expected in [(subprocess.TimeoutExpired(["fixture"], 900), 124),
                                  (subprocess.CalledProcessError(23, ["fixture"]), 23),
                                  (subprocess.CalledProcessError(-9, ["fixture"]), 137)]:
            with self.subTest(expected=expected), patch.object(sys, "argv", ["prepare", "install", "1.56.0"]):
                with patch.object(PREPARE, "install", side_effect=failure):
                    self.assertEqual(PREPARE.main(), expected)

    def test_offline_check_invokes_real_cli_path_not_just_file_inventory(self):
        calls = []

        def controlled_cli(command, **kwargs):
            calls.append(command)
            self.assertIn("--offline", command)
            self.assertIn("--package=playwright@1.58.0", command)
            if command[-1] == "--version":
                self.assertTrue(kwargs["capture"])
                return "Version 1.58.0\n"
            self.assertIn("screenshot", command)
            self.assertIn("--browser=chromium", command)
            self.assertTrue(command[-2].startswith("data:text/html,"))
            Path(command[-1]).write_bytes(b"controlled screenshot fixture; not a real browser")
            return ""

        with patch.object(PREPARE, "run", side_effect=controlled_cli):
            PREPARE.check("1.58.0", self.work)
        self.assertEqual(len(calls), 2)

    def test_offline_version_drift_prevents_launch(self):
        with patch.object(PREPARE, "run", return_value="Version 1.59.0\n") as runner:
            with self.assertRaisesRegex(ValueError, "version drift"):
                PREPARE.check("1.58.0", self.work)
        self.assertEqual(runner.call_count, 1)

    def test_offline_launch_failure_missing_output_and_stale_output_rejected(self):
        for failure in (subprocess.CalledProcessError(1, ["browser"]), ""):
            with patch.object(PREPARE, "run", side_effect=["Version 1.56.0\n", failure]):
                with self.assertRaises((ValueError, subprocess.CalledProcessError)):
                    PREPARE.check("1.56.0", self.work)
        (self.work / "chromium-1.56.0.png").write_bytes(b"stale")
        with patch.object(PREPARE, "run", return_value="Version 1.56.0\n") as runner:
            with self.assertRaisesRegex(ValueError, "fresh output"):
                PREPARE.check("1.56.0", self.work)
        self.assertEqual(runner.call_count, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
