import base64
import hashlib
import io
import json
import os
import shutil
import subprocess
import tarfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import test_dependency_preparation as fixtures


preparation = fixtures.preparation
SCRIPT = r'''#!/usr/bin/env python3
import json
import os
import sys
import time
from pathlib import Path

root = Path(os.environ['LOCK_TEST_ROOT'])
arguments = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as output:
    output.write(json.dumps(arguments) + '\n')
assert '--maxsockets=2' in arguments
assert '--update-notifier=false' in arguments
assert os.environ['npm_config_registry'] == 'https://registry.npmjs.org'
assert os.environ['npm_config_maxsockets'] == '2'
plan = json.loads((root / 'plan.json').read_text())
step = plan.pop(0)
(root / 'plan.json').write_text(json.dumps(plan))
if step == 'success':
    assert not Path('package-lock.json').exists(), 'Incomplete lock must not seed resolution'
    Path('package-lock.json').write_bytes((root / 'valid-lock.json').read_bytes())
elif step == 'interrupted':
    Path('package-lock.json').write_text('incomplete')
    (root / 'metadata-progress').write_text('retained')
    time.sleep(2)
else:
    print('npm error code ' + step, flush=True)
    raise SystemExit(1)
'''

SEED_METADATA = r'''
const fs = require('node:fs');
const path = require('node:path');
const cacache = require(path.join(process.argv[1], 'node_modules/cacache'));
const documents = JSON.parse(fs.readFileSync(process.argv[3]));
(async () => {
  for (const document of documents) {
    const url = 'https://registry.npmjs.org/' + document.name;
    await cacache.put(process.argv[2], 'make-fetch-happen:request-cache:' + url,
      JSON.stringify(document), {metadata: {time: 1, url,
        reqHeaders: {accept: 'application/json'},
        resHeaders: {'content-type': 'application/json', 'cache-control': 'max-age=0'},
        options: {compress: true}}});
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
'''


class LockResolutionTests(unittest.TestCase):
    setUp = fixtures.DependencyPreparationTests.setUp
    make_archive = fixtures.DependencyPreparationTests.make_archive
    cache_archive = fixtures.DependencyPreparationTests.cache_archive

    def fake_npm(self, steps):
        (self.project / 'package-lock.json').unlink()
        (self.root / 'valid-lock.json').write_text(json.dumps(self.lock))
        (self.root / 'plan.json').write_text(json.dumps(steps))
        (self.state / 'tmp').mkdir()
        binary = self.root / 'bin'
        binary.mkdir()
        executable = binary / 'npm'
        executable.write_text(SCRIPT)
        executable.chmod(0o755)
        self.addCleanup(patch.stopall)
        patch.dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                   LOCK_TEST_ROOT=str(self.root)).start()

    def calls(self):
        return [json.loads(line) for line in (self.root / 'calls.jsonl').read_text().splitlines()]

    def resolve(self, offline=False, deadline=None):
        return preparation.resolve_verifier_lock(self.project, self.state,
                                                  deadline or time.monotonic() + 60, offline)

    def test_warm_metadata_resolves_without_online_attempt(self):
        self.fake_npm(['success'])
        self.assertEqual(json.loads(self.resolve()), self.lock)
        self.assertEqual(len(self.calls()), 1)
        self.assertIn('--offline', self.calls()[0])

    def test_cache_miss_reuses_metadata_then_retries_transport_only(self):
        self.fake_npm(['ENOTCACHED', 'EAI_AGAIN', 'success'])
        self.assertEqual(json.loads(self.resolve()), self.lock)
        self.assertEqual([call[2] for call in self.calls()],
                         ['--offline', '--prefer-offline', '--prefer-offline'])

    def test_every_transient_code_is_bounded(self):
        codes = ['EAI_AGAIN', 'ENOTFOUND', 'ECONNRESET', 'ECONNREFUSED', 'ETIMEDOUT',
                 'ESOCKETTIMEDOUT', 'ENETUNREACH', 'EHOSTUNREACH', 'E408', 'E429',
                 'E500', 'E502', 'E503', 'E504']
        self.fake_npm([])
        for code in codes:
            with self.subTest(code=code):
                (self.root / 'calls.jsonl').unlink(missing_ok=True)
                (self.root / 'plan.json').write_text(json.dumps(['ENOTCACHED', code, code, 'success']))
                with self.assertRaisesRegex(RuntimeError, 'bounded cache-first'):
                    self.resolve()
                self.assertEqual(len(self.calls()), 3)
                self.assertFalse((self.project / 'package-lock.json').exists())

    def test_semantic_authentication_integrity_and_unknown_errors_do_not_retry(self):
        self.fake_npm([])
        for code in ['ETARGET', 'ERESOLVE', 'EINTEGRITY', 'E401', 'E403', 'E404',
                     'CERT_HAS_EXPIRED', 'SELF_SIGNED_CERT_IN_CHAIN', 'UNKNOWN']:
            for cache_miss in [False, True]:
                with self.subTest(code=code, cache_miss=cache_miss):
                    (self.root / 'calls.jsonl').unlink(missing_ok=True)
                    (self.root / 'plan.json').write_text(json.dumps(
                        (['ENOTCACHED'] if cache_miss else []) + [code, 'success']))
                    with self.assertRaises(preparation.NpmPhaseError):
                        self.resolve()
                    self.assertEqual(len(self.calls()), 2 if cache_miss else 1)

    def test_offline_miss_never_goes_online(self):
        self.fake_npm(['ENOTCACHED', 'success'])
        with self.assertRaises(preparation.NpmPhaseError):
            self.resolve(offline=True)
        self.assertEqual(len(self.calls()), 1)

    def test_timeout_retains_cache_and_rejects_incomplete_lock(self):
        self.fake_npm(['ENOTCACHED', 'interrupted', 'success'])
        original = preparation.run_npm

        def short_phase(arguments, project, state, deadline, phase_budget=180):
            return original(arguments, project, state, deadline, phase_budget=0.15)

        with patch.object(preparation, 'run_npm', side_effect=short_phase):
            self.assertEqual(json.loads(self.resolve()), self.lock)
        self.assertEqual((self.root / 'metadata-progress').read_text(), 'retained')
        self.assertEqual(len(self.calls()), 3)
        self.assertEqual(len(list(self.state.glob('npm-phase-*.log'))), 3)

    def test_expired_budget_cannot_spawn_npm(self):
        self.fake_npm(['success'])
        with self.assertRaises(TimeoutError):
            self.resolve(deadline=time.monotonic() - 1)
        self.assertFalse((self.root / 'calls.jsonl').exists())

    def test_resolution_reserves_installation_time(self):
        self.fake_npm(['success'])
        deadline = time.monotonic() + 600
        original = preparation.run_npm
        with patch.object(preparation, 'run_npm', wraps=original) as npm:
            self.resolve(deadline=deadline)
        self.assertLessEqual(npm.call_args.args[3], deadline - 179)
        self.assertGreater(npm.call_args.kwargs['phase_budget'], 0)
        self.assertLessEqual(npm.call_args.kwargs['phase_budget'], 60)

    def test_active_resolution_honors_shared_deadline(self):
        self.fake_npm(['interrupted', 'interrupted', 'success'])
        started = time.monotonic()
        with self.assertRaises(TimeoutError):
            self.resolve(deadline=started + 0.3)
        self.assertLess(time.monotonic() - started, 0.7)
        self.assertEqual(len(self.calls()), 1)
        self.assertFalse(list(self.state.rglob('verified-lock.json')))

    def test_resolved_wrong_version_cannot_freeze(self):
        self.fake_npm(['success'])
        self.lock['packages']['node_modules/dependency-probe']['version'] = '1.2.4'
        (self.root / 'valid-lock.json').write_text(json.dumps(self.lock))
        with self.assertRaisesRegex(ValueError, 'Exact root version mismatch'):
            preparation.prepare(self.project, self.state, resolve_lock=True, budget=60)
        self.assertFalse(list(self.state.rglob('verified-lock.json')))
        self.assertFalse((self.project / 'dependency-receipt.json').exists())

    def seed_real_metadata(self):
        documents = []
        for name, version, dependencies, source in [
                ('dependency-probe', '1.2.3', {'child-probe': '^2.0.0'},
                 'module.exports = { add: (left, right) => require("child-probe").add(left, right) };'),
                ('child-probe', '2.1.0', {}, 'exports.add = (left, right) => left + right;')]:
            manifest = dict(name=name, version=version, main='index.js', dependencies=dependencies,
                            scripts={'install': 'node -e "process.exit(42)"'})
            output = io.BytesIO()
            with tarfile.open(fileobj=output, mode='w:gz') as archive:
                for filename, content in [('package/package.json', json.dumps(manifest)),
                                          ('package/index.js', source)]:
                    entry = tarfile.TarInfo(filename)
                    entry.size = len(content.encode())
                    archive.addfile(entry, io.BytesIO(content.encode()))
            content = output.getvalue()
            checksum = hashlib.sha512(content).hexdigest()
            (self.archives / (checksum + '.tgz')).write_bytes(content)
            manifest['dist'] = {'tarball': f'https://registry.npmjs.org/{name}/-/{name}-{version}.tgz',
                                'integrity': 'sha512-' + base64.b64encode(bytes.fromhex(checksum)).decode()}
            newer = dict(manifest, version='3.0.0')
            documents.append({'name': name, 'dist-tags': {'latest': '3.0.0'},
                              'versions': {version: manifest, '3.0.0': newer}})
        document_path = self.root / 'metadata.json'
        document_path.write_text(json.dumps(documents))
        npm_root = Path(shutil.which('npm')).resolve().parent.parent
        subprocess.run(['node', '-e', SEED_METADATA, str(npm_root), str(self.state / 'npm-cache/_cacache'),
                        str(document_path)], check=True, timeout=10)

    def test_real_npm_resolves_complete_cached_graph_installs_and_reuses_frozen_lock(self):
        (self.project / 'package-lock.json').unlink()
        self.seed_real_metadata()
        with patch.object(preparation, 'open_archive', side_effect=AssertionError('No archive network')):
            result = preparation.prepare(self.project, self.state, resolve_lock=True, offline=True, budget=60)
        lock = json.loads((self.project / 'package-lock.json').read_text())
        self.assertEqual(lock['packages']['node_modules/dependency-probe']['version'], '1.2.3')
        self.assertEqual(lock['packages']['node_modules/child-probe']['version'], '2.1.0')
        self.assertEqual(result['archive_count'], 2)
        subprocess.run(['node', '-e', 'if(require("dependency-probe").add(19, 23)!==42) process.exit(1)'],
                       cwd=self.project, check=True, timeout=10)
        (self.project / 'package-lock.json').unlink()
        with patch.object(preparation, 'resolve_verifier_lock', side_effect=AssertionError('Frozen lock must be reused')):
            replay = preparation.prepare(self.project, self.state, resolve_lock=True, offline=True, budget=60)
        self.assertEqual(replay['lock_sha256'], result['lock_sha256'])

    def test_real_npm_corrupt_metadata_cannot_publish_lock_or_install(self):
        (self.project / 'package-lock.json').unlink()
        self.seed_real_metadata()
        for content in (self.state / 'npm-cache/_cacache/content-v2').rglob('*'):
            if content.is_file():
                content.write_bytes(b'corrupt metadata')
        with self.assertRaises(preparation.NpmPhaseError):
            preparation.prepare(self.project, self.state, resolve_lock=True, offline=True, budget=60)
        self.assertFalse((self.project / 'package-lock.json').exists())
        self.assertFalse(list(self.state.rglob('verified-lock.json')))
        self.assertFalse((self.project / 'node_modules').exists())


if __name__ == '__main__':
    unittest.main()
