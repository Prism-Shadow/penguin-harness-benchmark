import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path

ASSETS = Path(__file__).resolve().parents[1] / "environment/developer-checks"
SPEC = importlib.util.spec_from_file_location("fixture_installer", ASSETS / "install.py")
INSTALLER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INSTALLER)


class DevelopmentFixtureTests(unittest.TestCase):
    def test_fixture_does_not_hide_new_solver_tests_or_change_tracked_source(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            (repo / "bunfig.toml").write_text('[test]\npreload = "./tests/setup.ts"\n')
            subprocess.run(["git", "-C", str(repo), "add", "bunfig.toml"], check=True)
            before = subprocess.check_output(["git", "-C", str(repo), "diff", "--cached"])
            first = INSTALLER.install(repo, ASSETS)
            self.assertEqual(INSTALLER.install(repo, ASSETS), first)
            self.assertFalse(first["production_behavior_tested"])
            (repo / "tests/solver_regression.test.ts").write_text("// new solver test\n")
            visible = subprocess.check_output(["git", "-C", str(repo), "ls-files", "--others", "--exclude-standard"], text=True)
            self.assertEqual(visible.strip(), "tests/solver_regression.test.ts")
            self.assertEqual(before, subprocess.check_output(["git", "-C", str(repo), "diff", "--cached"]))

    def test_existing_user_setup_cannot_be_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            (repo / "tests").mkdir()
            existing = repo / "tests/setup.ts"
            existing.write_text("// independently authored setup\n")
            with self.assertRaises(ValueError):
                INSTALLER.install(repo, ASSETS)
            self.assertEqual(existing.read_text(), "// independently authored setup\n")

    def test_symlinked_tests_cannot_write_outside_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            repo = root / "repo"
            repo.mkdir()
            outside = root / "outside"
            outside.mkdir()
            (repo / "tests").symlink_to(outside, target_is_directory=True)
            with self.assertRaises(ValueError):
                INSTALLER.install(repo, ASSETS)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
