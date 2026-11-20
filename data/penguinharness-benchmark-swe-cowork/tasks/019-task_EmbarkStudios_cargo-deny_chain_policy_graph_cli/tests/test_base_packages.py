import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


TASK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(TASK / 'environment'))
import verify_base_packages


class BasePackageTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.release = self.root / 'os-release'
        self.release.write_text('NAME="Debian GNU/Linux"\nID=debian\nVERSION_CODENAME=bullseye\n')
        self.certificates = self.root / 'ca-certificates.crt'
        self.certificates.write_text('isolated certificate fixture\n')
        self.records = {
            'packages': {package: f'install ok installed\t{package}\t1.0-deb11\tamd64'
                         for package in verify_base_packages.PACKAGES},
            'tools': {'git': 'git version 2.30.2', 'patch': 'GNU patch 2.7.6',
                      'python3': 'Python 3.9.2', 'rustc': 'rustc 1.88.0 (fixture)',
                      'cargo': 'cargo 1.88.0 (fixture)'},
            'fail': [],
        }
        self.fixture = self.root / 'commands.json'
        self.calls = self.root / 'commands.log'
        self.executable = self.root / 'command-fixture'
        self.executable.write_text(f'#!{sys.executable}\n' + '''import json
import os
import sys
from pathlib import Path

name = Path(sys.argv[0]).name
fixture = Path(os.environ['PACKAGE_FIXTURE'])
records = json.loads(fixture.read_text())
with fixture.with_suffix('.log').open('a') as stream:
    stream.write(json.dumps([name, *sys.argv[1:]]) + '\\n')
if name in records['fail']:
    sys.exit(42)
if name == 'dpkg-query':
    record = records['packages'].get(sys.argv[-1])
else:
    record = records['tools'].get(name)
if record is None:
    sys.exit(43)
print(record)
''')
        self.executable.chmod(0o755)
        for command in ('dpkg-query', 'apt-get', 'curl', *self.records['tools']):
            (self.root / command).symlink_to(self.executable)

    def run_verifier(self):
        self.fixture.write_text(json.dumps(self.records))
        with patch.object(verify_base_packages, 'OS_RELEASE', self.release), \
             patch.object(verify_base_packages, 'CA_BUNDLE', self.certificates), \
             patch.dict(os.environ, {'PATH': str(self.root), 'PACKAGE_FIXTURE': str(self.fixture)}), \
             contextlib.redirect_stdout(io.StringIO()) as stream:
            verify_base_packages.verify()
        return stream.getvalue()

    def test_reuses_installed_packages_without_retrieval_and_logs_provenance(self):
        before = (self.release.read_bytes(), self.certificates.read_bytes())
        output = self.run_verifier()
        self.assertEqual(before, (self.release.read_bytes(), self.certificates.read_bytes()))
        self.assertEqual(json.loads(self.fixture.read_text()), self.records)
        commands = [json.loads(line) for line in self.calls.read_text().splitlines()]
        self.assertEqual([command[0] for command in commands],
                         ['dpkg-query'] * 4 + list(self.records['tools']))
        self.assertEqual([command[-1] for command in commands[:4]], list(verify_base_packages.PACKAGES))
        for record in self.records['packages'].values():
            self.assertIn(record, output)
        self.assertIn('Base prerequisites verified without changing the package set.', output)

    def test_rejects_wrong_distribution_before_running_commands(self):
        for release in ('ID=ubuntu\nVERSION_CODENAME=bullseye',
                        'ID=debian\nVERSION_CODENAME=bookworm'):
            with self.subTest(release=release):
                self.release.write_text(release)
                with self.assertRaisesRegex(RuntimeError, 'Debian bullseye'):
                    self.run_verifier()
                self.assertFalse(self.calls.exists())

    def test_rejects_missing_or_partially_installed_packages(self):
        for record in ('deinstall ok config-files\tgit\t2.30.2\tamd64',
                       'install ok unpacked\tgit\t2.30.2\tamd64',
                       'install ok installed\tgit\t\tamd64',
                       'install ok installed\tother\t2.30.2\tamd64'):
            with self.subTest(record=record):
                self.records['packages']['git'] = record
                with self.assertRaisesRegex(RuntimeError, 'not fully installed: git'):
                    self.run_verifier()

    def test_fails_closed_when_package_query_fails(self):
        del self.records['packages']['git']
        with self.assertRaises(verify_base_packages.subprocess.CalledProcessError):
            self.run_verifier()

    def test_rejects_missing_or_empty_ca_bundle(self):
        for exists in (True, False):
            with self.subTest(exists=exists):
                if exists:
                    self.certificates.write_text('')
                else:
                    self.certificates.unlink()
                with self.assertRaisesRegex(RuntimeError, 'CA certificate bundle'):
                    self.run_verifier()

    def test_rejects_missing_or_broken_executable(self):
        self.records['fail'] = ['git']
        with self.assertRaises(verify_base_packages.subprocess.CalledProcessError):
            self.run_verifier()
        (self.root / 'git').unlink()
        with self.assertRaises(FileNotFoundError):
            self.run_verifier()

    def test_rejects_toolchain_drift(self):
        for tool in ('rustc', 'cargo'):
            with self.subTest(tool=tool):
                original = self.records['tools'][tool]
                self.records['tools'][tool] = f'{tool} 1.89.0 (fixture)'
                with self.assertRaisesRegex(RuntimeError, 'pinned Rust 1.88.0'):
                    self.run_verifier()
                self.records['tools'][tool] = original

    def test_rejects_empty_version_output(self):
        self.records['tools']['git'] = ''
        with self.assertRaisesRegex(RuntimeError, 'Missing version output'):
            self.run_verifier()


if __name__ == '__main__':
    unittest.main(verbosity=2)
