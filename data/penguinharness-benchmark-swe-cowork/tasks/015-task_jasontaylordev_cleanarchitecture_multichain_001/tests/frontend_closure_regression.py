import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
specification = importlib.util.spec_from_file_location("frontend_closure", ROOT / "environment/frontend-closure.py")
closure = importlib.util.module_from_spec(specification)
specification.loader.exec_module(closure)


class FrontendClosureRegression(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.catalog = self.root / "catalog"
        self.repository = self.root / "repository"
        for name, relative in closure.CLIENTS.items():
            source = self.root / "source" / name
            package = source / "node_modules/example"
            package.mkdir(parents=True)
            (source / "package.json").write_text(json.dumps({"name": name, "dependencies": {"example": "1.0.0"}}))
            (source / "package-lock.json").write_text(json.dumps({"lockfileVersion": 3, "packages": {"": {"name": name}}}))
            (package / "index.js").write_text("module.exports = 7;\n")
            (source / "node_modules/.package-lock.json").write_text("{}")
            client = self.repository / relative
            client.mkdir(parents=True)
            for filename in ("package.json", "package-lock.json"):
                (client / filename).write_bytes((source / filename).read_bytes())
            closure.seal(source, self.catalog, "migrated-" + name)

    def test_exact_graph_activates_without_subprocess_and_writable_view_is_separate(self):
        closure.activate(self.repository, self.catalog, self.root / "views")
        client = self.repository / closure.CLIENTS["react"]
        self.assertEqual((client / "node_modules/example/index.js").read_text(), "module.exports = 7;\n")
        (client / "node_modules/.vite-temp/example").touch()
        self.assertFalse((self.catalog / "migrated-react/node_modules/.vite-temp").exists())
        closure.activate(self.repository, self.catalog, self.root / "views")
        self.assertFalse((client / "node_modules/.vite-temp/example").exists())
        subprocess.run(["git", "init", "-q", str(self.repository)], check=True)
        (self.repository / ".gitignore").write_text("node_modules/\n")
        subprocess.run(["git", "add", "-A", "."], cwd=self.repository, check=True)
        tracked = subprocess.check_output(["git", "ls-files"], cwd=self.repository, text=True)
        self.assertNotIn("node_modules", tracked)

    def test_equivalent_manifest_formatting_retains_exact_graph(self):
        manifest = self.repository / closure.CLIENTS["angular"] / "package.json"
        manifest.write_text(json.dumps(json.loads(manifest.read_text()), indent=4, sort_keys=True))
        self.assertEqual(len(closure.select(self.repository, self.catalog)), 2)

    def test_changed_manifest_or_unknown_lock_fails_closed(self):
        client = self.repository / closure.CLIENTS["react"]
        lock = client / "package-lock.json"
        lock.write_text("{}")
        self.assertIsNone(closure.select(self.repository, self.catalog, True))
        with self.assertRaisesRegex(ValueError, "no exact preinstalled"):
            closure.activate(self.repository, self.catalog, self.root / "views", True)
        self.assertFalse((client / "node_modules").exists())

    def test_corrupted_installed_graph_is_not_accepted(self):
        package = self.catalog / "migrated-react/node_modules/example/index.js"
        package.write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "installed graph integrity mismatch"):
            closure.activate(self.repository, self.catalog, self.root / "views")
        self.assertFalse((self.repository / closure.CLIENTS["angular"] / "node_modules").exists())

    def test_published_locks_are_exact_prior_native_capture(self):
        hashes = {"angular": "24d444c76423d40a149683ceda69819673d0fb42d2a75a79e6d19b5a387a5b58",
                  "react": "4b76686d1ca2b2f2ab34b1e096a175b32f07c75962dfa9666c9693d4af05edcc"}
        for name, expected in hashes.items():
            self.assertEqual(closure.digest(ROOT / "environment/offline-target" / name / "package-lock.json"), expected)


if __name__ == "__main__":
    unittest.main()
