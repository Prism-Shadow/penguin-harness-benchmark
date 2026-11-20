import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_prepare_phantomjs import seed_cache


INSTALLER = Path(__file__).resolve().parents[1] / "environment/runtime/install-repository-deps.sh"
FAKE_NPM = r'''#!/bin/bash
set -eu
printf '%s|%s|%s|%s|%s|%s\n' "$*" "$npm_config_jobs" "$npm_config_maxsockets" "$npm_config_prefer_offline" "$npm_config_offline" "$GIT_CONFIG_VALUE_0" >> "$TEST_ROOT/calls"
count=$(wc -l < "$TEST_ROOT/calls")
case "$TEST_CASE" in
  transient)
    if [ "$count" -eq 1 ]; then echo 'npm error network read ETIMEDOUT'; exit 146; fi ;;
  nested)
    if [ "$count" -eq 1 ]; then
      mkdir -p "$npm_config_cache/_logs"
      echo 'npm error git dep preparation failed'
      echo 'ETIMEDOUT nested Git dependency' > "$npm_config_cache/_logs/current-debug-0.log"
      exit 146
    fi ;;
  permanent) echo 'npm error ETIMEDOUT'; exit 146 ;;
  socket)
    if [ "$count" -eq 1 ]; then echo 'Error: socket hang up'; exit 1; fi ;;
  deadline-term|deadline-kill)
    if [ "$count" -eq 1 ]; then
      if [ "$TEST_CASE" = deadline-kill ]; then trap '' TERM; fi
      sleep 30 &
      echo "$!" > "$TEST_ROOT/child-pid"
      wait
    fi ;;
  unknown-kill) exit 137 ;;
  npm-124) exit 124 ;;
  not-network) echo 'ModuleNotFoundError'; exit 1 ;;
  deterministic) echo 'npm error EUSAGE lockfile mismatch'; exit 1 ;;
  offline-miss) echo 'npm error ENOTCACHED'; exit 1 ;;
  modified) printf '\n' >> package-lock.json ;;
esac
mkdir -p node_modules/.bin
for tool in tsc eslint ava; do
  if [ "$TEST_CASE" = missing-tool ] && [ "$tool" = ava ]; then continue; fi
  printf '#!/bin/bash\nprintf "%%s\\n" "%s $*" >> "$TEST_ROOT/tools"\n' "$tool" > "node_modules/.bin/$tool"
  chmod +x "node_modules/.bin/$tool"
done
'''


class DependencyInstallerTests(unittest.TestCase):
    def run_case(self, case, mode="online", overrides=None):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace = root / "repository"
            workspace.mkdir()
            for name in ("package.json", "package-lock.json"):
                (workspace / name).write_text("{}\n")
            binaries = root / "bin"
            binaries.mkdir()
            npm = binaries / "npm"
            npm.write_text(FAKE_NPM)
            npm.chmod(0o755)
            seed_cache(root / "cache/pinned-phantomjs-2.1.16")
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ["PATH"],
                               TEST_ROOT=str(root), TEST_CASE=case, HUBS_NPM_CACHE=str(root / "cache"),
                               HUBS_DEPENDENCY_MODE=mode, HUBS_DEPENDENCY_RETRY_DELAY="0",
                               HUBS_BUILD_TOOLS=str(root / "tools-root"),
                               HUBS_DEPENDENCY_ATTEMPT_TIMEOUT="1", HUBS_DEPENDENCY_KILL_GRACE="1")
            environment.update(overrides or {})
            completed = subprocess.run(["bash", str(INSTALLER), str(workspace)], env=environment,
                                       capture_output=True, text=True, timeout=15)
            calls = (root / "calls").read_text().splitlines() if (root / "calls").exists() else []
            tools = (root / "tools").read_text().splitlines() if (root / "tools").exists() else []
            self.assertFalse(list((root / "cache").glob("hubs-install.*")))
            child_path = root / "child-pid"
            if child_path.exists():
                process = Path("/proc") / child_path.read_text().strip() / "stat"
                if process.exists():
                    self.assertEqual(process.read_text().split()[2], "Z", "Timed-out child remained running")
            return completed, calls, tools

    def test_success_installs_full_dependencies_and_executes_all_tools(self):
        result, calls, tools = self.run_case("success")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(calls, ["ci --include=dev --no-audit --no-fund|2|2|true|false|ssh://git@github.com/"])
        self.assertEqual(tools, ["tsc --version", "eslint --version", "ava --version"])

    def test_network_and_nested_preparation_errors_retry(self):
        for case in ("transient", "nested", "socket"):
            with self.subTest(case=case):
                result, calls, tools = self.run_case(case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(tools), 3)
                self.assertIn("Transient fetch failure", result.stdout)
                if case == "nested":
                    self.assertIn("Nested npm diagnostic", result.stdout)

    def test_confirmed_term_and_kill_deadlines_retry_without_orphans(self):
        for case, status in (("deadline-term", 124), ("deadline-kill", 137)):
            with self.subTest(case=case):
                result, calls, tools = self.run_case(case)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(tools), 3)
                self.assertIn(f"deadline exceeded (exit {status})", result.stdout)

    def test_unknown_kill_and_bare_124_are_not_assumed_timeout(self):
        for case, status in (("unknown-kill", 137), ("npm-124", 124), ("not-network", 1)):
            with self.subTest(case=case):
                result, calls, tools = self.run_case(case)
                self.assertEqual(result.returncode, status)
                self.assertEqual(len(calls), 1)
                self.assertEqual(tools, [])
                self.assertNotIn("deadline exceeded", result.stdout)

    def test_timeout_overrides_cannot_remove_build_bounds(self):
        for variable, value in (("HUBS_DEPENDENCY_ATTEMPT_TIMEOUT", "0"),
                                ("HUBS_DEPENDENCY_ATTEMPT_TIMEOUT", "1201"),
                                ("HUBS_DEPENDENCY_KILL_GRACE", "31"),
                                ("HUBS_DEPENDENCY_RETRY_DELAY", "31")):
            with self.subTest(variable=variable, value=value):
                result, calls, tools = self.run_case("success", overrides={variable: value})
                self.assertEqual(result.returncode, 64)
                self.assertEqual(calls, [])
                self.assertEqual(tools, [])

    def test_exhausted_retries_preserve_failure(self):
        result, calls, tools = self.run_case("permanent")
        self.assertEqual(result.returncode, 146)
        self.assertEqual(len(calls), 3)
        self.assertEqual(tools, [])
        self.assertIn("no partial toolchain accepted", result.stderr)

    def test_non_network_failure_is_not_retried(self):
        result, calls, tools = self.run_case("deterministic")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(calls), 1)
        self.assertEqual(tools, [])

    def test_offline_missing_cache_fails_without_network_fallback(self):
        result, calls, tools = self.run_case("offline-miss", mode="offline")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(len(calls), 1)
        self.assertIn("|true|true|", calls[0])
        self.assertEqual(tools, [])

    def test_mutated_lockfile_is_rejected(self):
        result, calls, tools = self.run_case("modified")
        self.assertEqual(result.returncode, 65)
        self.assertEqual(len(calls), 1)
        self.assertEqual(tools, [])

    def test_partial_toolchain_is_rejected(self):
        result, calls, tools = self.run_case("missing-tool")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(tools, ["tsc --version", "eslint --version"])

    def test_invalid_mode_fails_before_install(self):
        result, calls, tools = self.run_case("success", mode="unknown")
        self.assertEqual(result.returncode, 64)
        self.assertEqual(calls, [])
        self.assertEqual(tools, [])


if __name__ == "__main__":
    unittest.main()
