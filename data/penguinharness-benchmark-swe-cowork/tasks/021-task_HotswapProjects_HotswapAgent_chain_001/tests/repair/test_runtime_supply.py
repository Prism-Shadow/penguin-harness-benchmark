import copy
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'environment/task-environment/materialize-offline-runtime.py'
SPEC = importlib.util.spec_from_file_location('runtime_supply', SCRIPT)
supply = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supply)


class RuntimeSupplyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.template = self.root / 'template.json'
        self.approved = self.root / 'approved.json'
        self.bundle = self.root / 'bundle'
        self.repository = self.root / 'repository'
        self.java_home = self.root / 'jdk'
        self.lock = json.loads((ROOT / 'environment/task-environment/offline-runtime-lock.json').read_text())
        self.lock['maven_artifacts'] = self.lock['maven_artifacts'][:1]
        self.record = self.lock['maven_artifacts'][0]
        self.pom = b'<project><packaging>pom</packaging></project>'
        self.record['sha256'] = hashlib.sha256(self.pom).hexdigest()
        self.lock['dcevm']['version'] = '11.0.9'
        self.lock['dcevm']['release_url'] = supply.RELEASES + '/tag/11.0.9'
        self.lock['dcevm']['archive_url'] = (
            'https://github.com/TravaOpenJDK/trava-jdk-11-dcevm/releases/download/11.0.9/fixture.tar.gz')
        self.archive = self.make_archive()
        self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
        self.write_locks()

    def make_archive(self, extra=(), version='11.0.9', module_entries=None, inspector_status=0):
        agent = io.BytesIO()
        with zipfile.ZipFile(agent, 'w') as stream:
            stream.writestr('org/hotswap/agent/PluginManager.class', b'controlled unwanted agent')
        if module_entries is None:
            module_entries = ['java/lang/Object.class']
        inspector = '#!/bin/sh\nprintf "%s\\n" "Module: java.base"'
        inspector += ''.join(' "' + entry + '"' for entry in module_entries)
        inspector += '\nexit ' + str(inspector_status) + '\n'
        data = io.BytesIO()
        with tarfile.open(fileobj=data, mode='w:gz') as stream:
            for name, contents in [
                    ('release', f'JAVA_VERSION="{version}"\nOS_NAME="Linux"\nOS_ARCH="amd64"\n'.encode()),
                    ('bin/java', b'controlled java fixture; never executed'),
                    ('bin/javac', b'controlled javac fixture; never executed'),
                    ('bin/jar', b'controlled jar fixture; never executed'),
                    ('bin/jimage', inspector.encode()),
                    ('lib/modules', b'controlled module fixture; not a real JDK image'),
                    ('lib/hotswap/agent.jar', agent.getvalue())]:
                member = tarfile.TarInfo('jdk/' + name)
                member.size = len(contents)
                member.mode = 0o755 if name.startswith('bin/') else 0o644
                stream.addfile(member, io.BytesIO(contents))
            for member, contents in extra:
                stream.addfile(member, io.BytesIO(contents) if contents else None)
        return data.getvalue()

    def write_locks(self):
        self.approved.write_text(json.dumps(self.lock))
        template = copy.deepcopy(self.lock)
        template['dcevm']['sha256'] = None
        template['dcevm']['archive_url'] = None
        template['maven_artifacts'][0]['sha256'] = None
        self.template.write_text(json.dumps(template))

    def controlled_response(self, url, timeout):
        self.assertEqual(60, timeout)
        self.assertIn(url, (self.record['source'], self.lock['dcevm']['archive_url']))
        response = io.BytesIO(self.pom if url == self.record['source'] else self.archive)
        response.url = url
        return response

    def fetch(self):
        with patch.object(supply.urllib.request, 'urlopen', side_effect=self.controlled_response) as network:
            result = supply.fetch(self.approved, self.template, self.bundle)
        self.assertEqual(2, network.call_count)
        self.assertFalse(result['ready'])
        return result

    def install(self):
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline install network')):
            return supply.install(self.bundle, self.template, self.repository, self.java_home)

    def prepare_inputs(self):
        self.bundle.mkdir()
        (self.bundle / supply.LOCK_NAME).write_bytes(self.approved.read_bytes())
        cached = self.repository / self.record['path']
        cached.parent.mkdir(parents=True)
        cached.write_bytes(self.pom)
        return cached

    def test_prepare_lock_only_reuses_pinned_cache_and_fetches_only_missing_jdk(self):
        cached = self.prepare_inputs()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=self.controlled_response) as network:
            result = supply.prepare(self.bundle, self.template, self.repository, output, True)
        network.assert_called_once_with(self.lock['dcevm']['archive_url'], timeout=60)
        self.assertEqual({'repository/' + self.record['path']: 'repository', 'jdk.tar.gz': 'download'},
                         result['payload_sources'])
        self.assertFalse(result['ready'])
        self.assertNotEqual(cached.stat().st_ino, (output / 'repository' / self.record['path']).stat().st_ino)
        self.assertEqual({supply.LOCK_NAME}, {path.name for path in self.bundle.iterdir()})
        self.assertEqual(self.pom, cached.read_bytes())
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            installed = supply.install(output, self.template, self.repository, self.java_home)
        self.assertTrue(installed['installed'])

    def input_snapshot(self):
        return {path.relative_to(self.root).as_posix():
                (path.lstat().st_ino, path.lstat().st_mode,
                 os.readlink(path) if path.is_symlink() else path.read_bytes() if path.is_file() else None)
                for path in self.root.rglob('*')}

    def run_plan(self, allow_download=False):
        command = [sys.executable, str(SCRIPT), '--template', str(self.template),
                   'plan', '--bundle', str(self.bundle), '--repository', str(self.repository)]
        if allow_download:
            command.append('--allow-download')
        result = subprocess.run(command, text=True, capture_output=True)
        return result.returncode, json.loads(result.stdout)

    def test_plan_offline_is_read_only_and_matches_real_preparation(self):
        self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        before = self.input_snapshot()
        with patch.object(supply, 'download', side_effect=AssertionError('plan network')):
            planned = supply.plan(self.bundle, self.template, self.repository)
        self.assertEqual(before, self.input_snapshot())
        self.assertTrue(planned['preparation_possible'])
        self.assertFalse(planned['requires_download'])
        self.assertFalse(planned['ready'])
        self.assertEqual(supply.digest(self.approved), planned['lock_sha256'])
        self.assertEqual(supply.digest(self.template), planned['template_sha256'])
        prepared = supply.prepare(self.bundle, self.template, self.repository, self.root / 'prepared')
        self.assertEqual(prepared['payload_sources'], planned['payload_sources'])

    def test_plan_connected_reports_downloads_without_fetching(self):
        self.prepare_inputs()
        before = self.input_snapshot()
        with patch.object(supply, 'download', side_effect=AssertionError('plan network')):
            result = supply.plan(self.bundle, self.template, self.repository, True)
        self.assertEqual(before, self.input_snapshot())
        self.assertTrue(result['requires_download'])
        self.assertEqual(['jdk.tar.gz'], result['missing_files'])
        self.assertEqual([], result['missing_approvals'])
        self.assertFalse(result['ready'])
        self.assertEqual('download', result['payload_sources']['jdk.tar.gz'])

    def test_plan_offline_cli_rejects_download_only_inputs(self):
        self.prepare_inputs()
        code, report = self.run_plan()
        self.assertEqual(2, code)
        self.assertFalse(report['preparation_possible'])
        self.assertEqual('build_input_preflight', report['phase'])
        self.assertEqual(['jdk.tar.gz'], report['missing_files'])
        self.assertEqual([], report['missing_approvals'])
        self.assertFalse(report['solver_failure'])

    def test_plan_connected_cli_never_approves_the_incomplete_task_lock(self):
        before = self.input_snapshot()
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertFalse(report['preparation_possible'])
        self.assertFalse(report['ready'])
        self.assertIn(self.record['source'], report['missing_approvals'])
        self.assertIn(self.lock['dcevm']['release_url'], report['missing_approvals'])
        self.assertEqual(before, self.input_snapshot())

    def test_plan_cli_accepts_both_approved_lock_locations_without_writes(self):
        self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        for source in ('bundle', 'template'):
            with self.subTest(source=source):
                if source == 'template':
                    self.template.write_bytes(self.approved.read_bytes())
                    (self.bundle / supply.LOCK_NAME).unlink()
                before = self.input_snapshot()
                code, report = self.run_plan()
                self.assertEqual(0, code)
                self.assertEqual(source, report['lock_source'])
                self.assertTrue(report['preparation_possible'])
                self.assertFalse(report['requires_download'])
                self.assertFalse(report['ready'])
                self.assertEqual(before, self.input_snapshot())

    def test_plan_observes_payload_changes_between_calls(self):
        cached = self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        self.assertEqual(0, self.run_plan()[0])
        cached.write_bytes(b'corrupt after successful plan')
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertIn('checksum mismatch', report['error'])
        self.assertFalse(report['preparation_possible'])
        cached.write_bytes(self.pom)
        self.assertEqual(0, self.run_plan()[0])
        (self.bundle / 'jdk.tar.gz').unlink()
        self.assertEqual(2, self.run_plan()[0])
        code, report = self.run_plan(True)
        self.assertEqual(0, code)
        self.assertTrue(report['requires_download'])

    def test_plan_cannot_hide_corrupt_supplied_bytes_behind_valid_cache(self):
        self.prepare_inputs()
        supplied = self.bundle / 'repository' / self.record['path']
        supplied.parent.mkdir(parents=True)
        supplied.write_bytes(b'wrong bytes')
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertIn('checksum mismatch', report['error'])

    def test_plan_rejects_noncanonical_pins_and_symlinks(self):
        cached = self.prepare_inputs()
        original = cached.read_bytes()
        cached.unlink()
        cached.symlink_to(self.approved)
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertIn('symlink', report['error'])
        cached.unlink()
        cached.write_bytes(original)
        changed = copy.deepcopy(self.lock)
        changed['maven_artifacts'][0]['source'] = 'https://example.org/unreviewed.pom'
        (self.bundle / supply.LOCK_NAME).write_text(json.dumps(changed))
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertIn('artifact contract changed', report['error'])

    def test_plan_cli_cannot_silently_ignore_a_malformed_supply_lock(self):
        self.prepare_inputs()
        self.template.write_bytes(self.approved.read_bytes())
        (self.bundle / supply.LOCK_NAME).write_text('{malformed')
        code, report = self.run_plan(True)
        self.assertEqual(2, code)
        self.assertFalse(report['preparation_possible'])
        self.assertFalse(report['ready'])

    def test_prepare_sparse_supply_and_cache_are_sufficient_without_network(self):
        self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        (self.bundle / 'unlisted-solution.txt').write_text('must not propagate')
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            result = supply.prepare(self.bundle, self.template, self.repository, output)
        self.assertEqual('supplied', result['payload_sources']['jdk.tar.gz'])
        self.assertFalse((output / 'unlisted-solution.txt').exists())
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))

    def test_prepare_approved_template_needs_no_duplicate_supply_lock(self):
        cached = self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        self.template.write_bytes(self.approved.read_bytes())
        original_template = self.template.read_bytes()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=self.controlled_response) as network:
            result = supply.prepare(self.bundle, self.template, self.repository, output, True)
        network.assert_called_once_with(self.lock['dcevm']['archive_url'], timeout=60)
        self.assertEqual('template', result['lock_source'])
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))
        self.assertEqual(original_template, self.template.read_bytes())
        self.assertEqual(self.pom, cached.read_bytes())
        self.assertFalse((self.bundle / supply.LOCK_NAME).exists())
        self.assertFalse(result['ready'])

    def test_prepare_approved_template_with_offline_payloads(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        self.template.write_bytes(self.approved.read_bytes())
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            result = supply.prepare(self.bundle, self.template, self.repository, output)
        self.assertEqual('template', result['lock_source'])
        self.assertEqual('supplied', result['payload_sources']['jdk.tar.gz'])
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))

    def test_prepare_unapproved_template_does_not_bootstrap_its_own_pins(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        output = self.root / 'prepared'
        for missing in ('maven', 'jdk_digest', 'jdk_url'):
            with self.subTest(missing=missing):
                incomplete = copy.deepcopy(self.lock)
                if missing == 'maven':
                    incomplete['maven_artifacts'][0]['sha256'] = None
                else:
                    incomplete['dcevm']['sha256' if missing == 'jdk_digest' else 'archive_url'] = None
                self.template.write_text(json.dumps(incomplete))
                with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('unapproved network')):
                    with self.assertRaises(supply.SupplyPrerequisiteError) as failure:
                        supply.prepare(self.bundle, self.template, self.repository, output, True)
                expected = self.record['source'] if missing == 'maven' else self.lock['dcevm']['release_url']
                self.assertEqual([expected], failure.exception.missing_approvals)
                self.assertFalse(output.exists())

    def test_prepare_template_digests_and_url_still_require_full_validation(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        output = self.root / 'prepared'
        for field, value in (('sha256', 'not-a-sha256'), ('archive_url', 'https://example.invalid/jdk.tar.gz')):
            with self.subTest(field=field):
                invalid = copy.deepcopy(self.lock)
                invalid['dcevm'][field] = value
                self.template.write_text(json.dumps(invalid))
                with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('invalid network')):
                    with self.assertRaises(ValueError):
                        supply.prepare(self.bundle, self.template, self.repository, output, True)
                self.assertFalse(output.exists())

    def test_prepare_existing_supply_lock_cannot_fall_back_to_template(self):
        self.prepare_inputs()
        self.template.write_bytes(self.approved.read_bytes())
        output = self.root / 'prepared'
        altered = copy.deepcopy(self.lock)
        altered['maven_artifacts'][0]['sha256'] = '0' * 64
        for contents in (json.dumps(altered), '{malformed'):
            with self.subTest(contents=contents):
                (self.bundle / supply.LOCK_NAME).write_text(contents)
                with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('fallback network')):
                    with self.assertRaises(ValueError):
                        supply.prepare(self.bundle, self.template, self.repository, output, True)
                self.assertFalse(output.exists())

    def test_prepare_supply_lock_directory_does_not_enable_template_fallback(self):
        self.prepare_inputs()
        self.template.write_bytes(self.approved.read_bytes())
        manifest = self.bundle / supply.LOCK_NAME
        manifest.unlink()
        manifest.mkdir()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('fallback network')):
            with self.assertRaisesRegex(ValueError, 'lock is not a file'):
                supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertFalse(output.exists())

    def test_prepare_approved_template_reports_missing_offline_payload_not_lock(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        self.template.write_bytes(self.approved.read_bytes())
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            with self.assertRaises(supply.SupplyPrerequisiteError) as failure:
                supply.prepare(self.bundle, self.template, self.repository, output)
        self.assertEqual(['jdk.tar.gz'], failure.exception.missing_files)
        self.assertEqual([], failure.exception.missing_approvals)
        self.assertFalse(output.exists())

    def test_prepare_cli_accepts_pinned_template_without_duplicate_lock(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        self.template.write_bytes(self.approved.read_bytes())
        output = self.root / 'prepared'
        captured = io.StringIO()
        command = [str(SCRIPT), '--template', str(self.template), 'prepare', '--bundle', str(self.bundle),
                   '--repository', str(self.repository), '--output', str(output)]
        with patch.object(sys, 'argv', command), contextlib.redirect_stdout(captured):
            status = supply.main()
        self.assertEqual(0, status, captured.getvalue())
        result = json.loads(captured.getvalue())
        self.assertEqual('template', result['lock_source'])
        self.assertFalse(result['ready'])
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))

    def test_prepare_cli_rejects_noncanonical_template_even_with_matching_bytes(self):
        self.prepare_inputs()
        (self.bundle / supply.LOCK_NAME).unlink()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        invalid = copy.deepcopy(self.lock)
        invalid['dcevm']['archive_url'] = 'https://example.invalid/jdk.tar.gz'
        self.template.write_text(json.dumps(invalid))
        output = self.root / 'prepared'
        captured = io.StringIO()
        command = [str(SCRIPT), '--template', str(self.template), 'prepare', '--bundle', str(self.bundle),
                   '--repository', str(self.repository), '--output', str(output)]
        with patch.object(sys, 'argv', command), contextlib.redirect_stdout(captured):
            status = supply.main()
        self.assertEqual(2, status, captured.getvalue())
        self.assertFalse(json.loads(captured.getvalue())['solver_failure'])
        self.assertFalse(output.exists())

    def test_prepare_connected_missing_maven_and_jdk_are_both_pinned(self):
        cached = self.prepare_inputs()
        cached.unlink()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=self.controlled_response) as network:
            result = supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertEqual(2, network.call_count)
        self.assertEqual({'download'}, set(result['payload_sources'].values()))
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))
        self.assertFalse(cached.exists())

    def test_prepare_complete_supply_needs_no_cache_or_network(self):
        self.fetch()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            result = supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertEqual({'supplied'}, set(result['payload_sources'].values()))
        self.assertEqual(self.lock, supply.verify_bundle(output, self.template))

    def test_prepare_offline_reports_only_unsatisfied_payloads(self):
        self.prepare_inputs()
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('offline network')):
            with self.assertRaises(supply.SupplyPrerequisiteError) as failure:
                supply.prepare(self.bundle, self.template, self.repository, output)
        self.assertEqual(['jdk.tar.gz'], failure.exception.missing_files)
        self.assertEqual([], failure.exception.missing_approvals)
        self.assertFalse(output.exists())

    def test_prepare_missing_approval_fails_even_in_connected_mode(self):
        self.prepare_inputs()
        unapproved = copy.deepcopy(self.lock)
        unapproved['dcevm']['sha256'] = None
        (self.bundle / supply.LOCK_NAME).write_text(json.dumps(unapproved))
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('unapproved network')):
            with self.assertRaisesRegex(ValueError, 'missing approved DCEVM'):
                supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertFalse(output.exists())

    def test_prepare_corrupt_or_symlinked_cache_cannot_fall_back_to_download(self):
        cached = self.prepare_inputs()
        output = self.root / 'prepared'
        cached.write_bytes(b'corruption')
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('fallback network')):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                supply.prepare(self.bundle, self.template, self.repository, output, True)
            cached.unlink()
            outside = self.root / 'outside.pom'
            outside.write_bytes(self.pom)
            cached.symlink_to(outside)
            with self.assertRaisesRegex(ValueError, 'symlink'):
                supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertFalse(output.exists())
        self.assertEqual(self.pom, outside.read_bytes())

    def test_prepare_conflicting_supplied_bytes_cannot_be_masked_by_valid_cache(self):
        self.prepare_inputs()
        supplied = self.bundle / 'repository' / self.record['path']
        supplied.parent.mkdir(parents=True)
        supplied.write_bytes(b'corruption')
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('fallback network')):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                supply.prepare(self.bundle, self.template, self.repository, self.root / 'prepared', True)

    def test_prepare_bad_download_leaves_inputs_unchanged_and_no_published_output(self):
        cached = self.prepare_inputs()
        response = io.BytesIO(b'bad JDK archive')
        response.url = self.lock['dcevm']['archive_url']
        output = self.root / 'prepared'
        with patch.object(supply.urllib.request, 'urlopen', return_value=response):
            with self.assertRaisesRegex(ValueError, 'checksum mismatch'):
                supply.prepare(self.bundle, self.template, self.repository, output, True)
        self.assertEqual(self.pom, cached.read_bytes())
        self.assertEqual(self.approved.read_bytes(), (self.bundle / supply.LOCK_NAME).read_bytes())
        self.assertFalse(output.exists())
        self.assertEqual([], list(self.root.glob('runtime-prepare-*')))

    def test_prepare_rejects_symlinked_output_and_existing_output(self):
        self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        output = self.root / 'prepared'
        output.mkdir()
        with self.assertRaisesRegex(ValueError, 'already exists'):
            supply.prepare(self.bundle, self.template, self.repository, output)
        alias = self.root / 'alias'
        alias.symlink_to(output, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'symlink'):
            supply.prepare(self.bundle, self.template, self.repository, alias / 'new')
        self.assertEqual([], list(output.iterdir()))

    def test_prepare_cli_offline_roundtrip_and_missing_input_classification(self):
        self.prepare_inputs()
        (self.bundle / 'jdk.tar.gz').write_bytes(self.archive)
        output = self.root / 'prepared'
        command = [sys.executable, str(SCRIPT), '--template', str(self.template), 'prepare',
                   '--bundle', str(self.bundle), '--repository', str(self.repository), '--output', str(output)]
        process = subprocess.run(command, text=True, capture_output=True)
        self.assertEqual(0, process.returncode, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)['bundle_integrity_verified'])
        self.assertFalse(json.loads(process.stdout)['ready'])
        (self.bundle / supply.LOCK_NAME).unlink()
        process = subprocess.run(command + ['--allow-download'], text=True, capture_output=True)
        self.assertEqual(2, process.returncode, process.stdout + process.stderr)
        self.assertTrue(json.loads(process.stdout)['prerequisite_missing'])
        self.assertFalse(json.loads(process.stdout)['solver_failure'])
        self.assertEqual([supply.LOCK_NAME], json.loads(process.stdout)['missing_files'])

    def test_both_recipes_prepare_the_approved_supply_before_offline_install(self):
        for name in ('Dockerfile', 'Dockerfile.source'):
            recipe = (ROOT / 'environment' / name).read_text()
            prepare_position = recipe.index('materialize-offline-runtime.py prepare')
            install_position = recipe.index('materialize-offline-runtime.py install')
            offline_position = recipe.index('SEGPIPE_PREFETCH_OFFLINE=1')
            self.assertLess(prepare_position, install_position)
            self.assertLess(install_position, offline_position)
            self.assertIn('--output /opt/runtime-prepared --allow-download', recipe)
            self.assertIn('check --bundle /opt/runtime-prepared', recipe)
            self.assertIn('--bundle /opt/runtime-prepared --repository /root/.m2/repository', recipe)
            self.assertIn('check-offline-runtime.py', recipe)

    def test_fetch_install_roundtrip_preserves_bytes_and_removes_bundled_agent(self):
        self.fetch()
        result = self.install()
        self.assertTrue(result['installed'])
        self.assertFalse(result['ready'])
        self.assertEqual(['lib/hotswap/agent.jar'], result['removed_bundled_agent_jars'])
        self.assertEqual(1, result['jdk_leakage_audit']['module_class_count'])
        self.assertEqual(0, result['jdk_leakage_audit']['module_inspection_exit_code'])
        self.assertFalse((self.java_home / 'lib/hotswap/agent.jar').exists())
        self.assertTrue(os.access(self.java_home / 'bin/java', os.X_OK))
        self.assertEqual(self.pom, (self.repository / self.record['path']).read_bytes())
        self.assertEqual(self.lock, json.loads(self.template.read_text()))
        self.assertNotEqual((self.bundle / 'repository' / self.record['path']).stat().st_ino,
                            (self.repository / self.record['path']).stat().st_ino)

    def test_module_leak_and_failed_or_empty_inspection_prevent_publication(self):
        cases = [(['java/lang/Object.class', 'org/hotswap/agent/plugin/Newer.class'], 0,
                  'bundled HotswapAgent in JDK module image'),
                 (['java/lang/Object.class'], 1, 'JDK module inspection failed'),
                 ([], 0, 'JDK module listing is incomplete')]
        for entries, status, error in cases:
            with self.subTest(entries=entries, status=status):
                self.archive = self.make_archive(module_entries=entries, inspector_status=status)
                self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
                self.write_locks()
                self.fetch()
                template = self.template.read_bytes()
                with self.assertRaisesRegex(ValueError, error):
                    self.install()
                self.assertFalse(self.repository.exists())
                self.assertFalse(self.java_home.exists())
                self.assertEqual(template, self.template.read_bytes())
                supply.shutil.rmtree(self.bundle)

    def test_source_and_jmod_archives_cannot_bypass_runtime_audit(self):
        for relative, entry in [('lib/src.zip', 'module/org/hotswap/agent/Plugin.java'),
                                ('jmods/agent.jmod', 'classes/org/hotswap/agent/Plugin.class')]:
            with self.subTest(relative=relative):
                data = io.BytesIO()
                with zipfile.ZipFile(data, 'w') as archive:
                    archive.writestr(entry, b'controlled unwanted code')
                contents = (b'JM\x01\x00' if relative.endswith('.jmod') else b'') + data.getvalue()
                member = tarfile.TarInfo('jdk/' + relative)
                member.size = len(contents)
                self.archive = self.make_archive([(member, contents)])
                self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
                self.write_locks()
                self.fetch()
                with self.assertRaisesRegex(ValueError, 'bundled HotswapAgent runtime archive'):
                    self.install()
                self.assertFalse(self.repository.exists())
                self.assertFalse(self.java_home.exists())
                supply.shutil.rmtree(self.bundle)

    def test_nested_and_multirelease_agent_jars_are_removed(self):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('META-INF/versions/11/org/hotswap/agent/Plugin.class', b'agent')
        outer = io.BytesIO()
        with zipfile.ZipFile(outer, 'w') as archive:
            archive.writestr('vendor/nested.jar', data.getvalue())
        member = tarfile.TarInfo('jdk/lib/vendor.jar')
        member.size = len(outer.getvalue())
        self.archive = self.make_archive([(member, outer.getvalue())])
        self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
        self.write_locks()
        self.fetch()
        result = self.install()
        self.assertIn('lib/vendor.jar', result['removed_bundled_agent_jars'])
        self.assertFalse((self.java_home / 'lib/vendor.jar').exists())

    def test_audit_requires_module_image_and_inspector(self):
        self.fetch()
        supply.unpack_jdk(self.bundle / 'jdk.tar.gz', self.java_home, self.lock['dcevm']['version'])
        inspector = self.java_home / 'bin/jimage'
        inspector.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'module inspector missing'):
            supply.audit_jdk(self.java_home)
        inspector.chmod(0o755)
        (self.java_home / 'lib/modules').unlink()
        with self.assertRaisesRegex(ValueError, 'module image missing'):
            supply.audit_jdk(self.java_home)

    def test_module_inspection_timeout_is_a_prerequisite_failure(self):
        self.fetch()
        output = io.StringIO()
        arguments = [str(SCRIPT), '--template', str(self.template), 'install',
                     '--bundle', str(self.bundle), '--repository', str(self.repository),
                     '--java-home', str(self.java_home)]
        with patch.object(sys, 'argv', arguments), contextlib.redirect_stdout(output), \
                patch.object(supply.subprocess, 'run', side_effect=subprocess.TimeoutExpired('jimage', 120)):
            self.assertEqual(2, supply.main())
        report = json.loads(output.getvalue())
        self.assertTrue(report['prerequisite_missing'])
        self.assertFalse(report['solver_failure'])
        self.assertFalse(report['ready'])
        self.assertFalse(self.repository.exists())
        self.assertFalse(self.java_home.exists())

    def test_clean_source_and_jmod_archives_are_preserved(self):
        extra = []
        for relative, entry in [('lib/src.zip', 'java.base/java/lang/Object.java'),
                                ('jmods/java.base.jmod', 'classes/java/lang/Object.class')]:
            data = io.BytesIO()
            with zipfile.ZipFile(data, 'w') as archive:
                archive.writestr(entry, b'controlled non-agent code')
            contents = (b'JM\x01\x00' if relative.endswith('.jmod') else b'') + data.getvalue()
            member = tarfile.TarInfo('jdk/' + relative)
            member.size = len(contents)
            extra.append((member, contents))
        self.archive = self.make_archive(extra, module_entries=[
            'java/lang/Object.class', 'com/example/org/hotswap/agentless/Other.class'])
        self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
        self.write_locks()
        self.fetch()
        result = self.install()
        self.assertEqual(['jmods/java.base.jmod', 'lib/src.zip'],
                         result['jdk_leakage_audit']['archives_checked'])
        for member, contents in extra:
            self.assertEqual(contents, (self.java_home / member.name.removeprefix('jdk/')).read_bytes())

    def test_missing_pin_fails_before_network_and_creates_no_bundle(self):
        self.lock['maven_artifacts'][0]['sha256'] = None
        self.approved.write_text(json.dumps(self.lock))
        with patch.object(supply.urllib.request, 'urlopen') as network:
            with self.assertRaisesRegex(ValueError, 'missing approved SHA256'):
                supply.fetch(self.approved, self.template, self.bundle)
            network.assert_not_called()
        self.assertFalse(self.bundle.exists())

    def test_contract_changes_and_repinning_are_rejected(self):
        template = copy.deepcopy(self.lock)
        for mutate in (
                lambda lock: lock['maven_artifacts'][0].update(sha256='0' * 64),
                lambda lock: lock['maven_artifacts'].clear(),
                lambda lock: lock['default_lifecycle'].update(junit_provider='anything:else:3.2.5'),
                lambda lock: lock['dcevm'].update(version='17'),
                lambda lock: lock['dcevm'].update(sha256='0' * 64),
                lambda lock: lock['dcevm'].update(archive_url='http://example.invalid/jdk.tar.gz')):
            lock = copy.deepcopy(self.lock)
            mutate(lock)
            with self.subTest(lock=lock), self.assertRaises(ValueError):
                supply.validate_lock(lock, template)

    def unselected_template(self):
        template = copy.deepcopy(self.lock)
        for field in ('version', 'release_url', 'archive_url', 'sha256'):
            template['dcevm'][field] = None
        return template

    def test_approved_release_tag_is_not_inferred_from_java_version(self):
        template = self.unselected_template()
        for version, tag in (('11.0.9', 'fixture-dcevm-11.0.9%2B2'),
                             ('11.0.11', 'fixture-dcevm-11.0.11+1')):
            with self.subTest(version=version):
                self.lock['dcevm']['version'] = version
                self.lock['dcevm']['release_url'] = supply.RELEASES + '/tag/' + tag
                self.lock['dcevm']['archive_url'] = supply.RELEASES + '/download/' + tag + '/fixture.tar.gz'
                self.archive = self.make_archive(version=version)
                self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
                self.approved.write_text(json.dumps(self.lock))
                self.template.write_text(json.dumps(template))
                self.fetch()
                result = self.install()
                self.assertEqual({field: self.lock['dcevm'][field]
                                  for field in ('version', 'release_url', 'archive_url', 'sha256')},
                                 result['runtime_selection'])
                self.assertIn('JAVA_VERSION="' + version + '"', (self.java_home / 'release').read_text())
                self.assertFalse(result['ready'])
                self.assertEqual(self.lock, json.loads(self.template.read_text()))
                supply.shutil.rmtree(self.java_home)
                supply.shutil.rmtree(self.bundle)

    def test_release_selection_rejects_missing_pins_before_network(self):
        template = self.unselected_template()
        for field in ('version', 'release_url', 'archive_url', 'sha256'):
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock['dcevm'][field] = None
                self.approved.write_text(json.dumps(lock))
                self.template.write_text(json.dumps(template))
                with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('unapproved network')):
                    with self.assertRaises(ValueError):
                        supply.fetch(self.approved, self.template, self.bundle)
                self.assertFalse(self.bundle.exists())

    def test_release_selection_rejects_other_hosts_tags_and_non_java11(self):
        template = self.unselected_template()
        for update in (
                {'release_url': supply.RELEASES + '/tag/latest'},
                {'release_url': supply.RELEASES + '/tag/../11.0.9'},
                {'release_url': supply.RELEASES + '/tag/11.0.9%2Fescape'},
                {'release_url': supply.RELEASES + '/tag/11.0.9?other=tag'},
                {'release_url': 'https://github.com/other/runtime/releases/tag/11.0.9'},
                {'archive_url': supply.RELEASES + '/download/other/fixture.tar.gz'},
                {'archive_url': supply.RELEASES + '/download/11.0.9/%2e%2e%2ffixture.tar.gz'},
                {'archive_url': supply.RELEASES + '/download/11.0.9/fixture.tar.gz#ignored'},
                {'version': '17.0.1'}, {'version': '11.latest'}, {'java_major': 17}):
            with self.subTest(update=update):
                lock = copy.deepcopy(self.lock)
                lock['dcevm'].update(update)
                with self.assertRaises(ValueError):
                    supply.validate_lock(lock, template)

    def test_completed_runtime_selection_cannot_be_repinned(self):
        for field, value in (('version', '11.0.11'),
                             ('release_url', supply.RELEASES + '/tag/other'),
                             ('archive_url', supply.RELEASES + '/download/11.0.9/other.tar.gz'),
                             ('sha256', '0' * 64)):
            with self.subTest(field=field):
                lock = copy.deepcopy(self.lock)
                lock['dcevm'][field] = value
                with self.assertRaisesRegex(ValueError, 'existing DCEVM pin changed'):
                    supply.validate_lock(lock, self.lock)

    def test_same_major_wrong_or_ambiguous_archive_version_is_not_published(self):
        for version in ('11.0.11', '11.0.9+2', '11.0.9"\nJAVA_VERSION="11.0.9'):
            with self.subTest(version=version):
                self.archive = self.make_archive(version=version)
                self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
                self.write_locks()
                self.fetch()
                original = self.template.read_bytes()
                try:
                    with self.assertRaisesRegex(ValueError, 'pinned Java version'):
                        self.install()
                    self.assertFalse(self.java_home.exists())
                    self.assertFalse(self.repository.exists())
                    self.assertEqual(original, self.template.read_bytes())
                finally:
                    for directory in (self.bundle, self.java_home, self.repository):
                        if directory.exists():
                            supply.shutil.rmtree(directory)

    def test_download_corruption_leaves_no_published_bundle(self):
        self.pom = b'corrupted download'
        with patch.object(supply.urllib.request, 'urlopen', side_effect=self.controlled_response):
            with self.assertRaisesRegex(ValueError, 'download checksum mismatch'):
                supply.fetch(self.approved, self.template, self.bundle)
        self.assertFalse(self.bundle.exists())
        self.assertEqual([], list(self.root.glob('runtime-fetch-*')))

    def test_tampered_bundle_fails_before_install(self):
        self.fetch()
        additional = tarfile.TarInfo('jdk/unapproved-file')
        additional.size = 1
        (self.bundle / 'jdk.tar.gz').write_bytes(self.make_archive([(additional, b'x')]))
        with self.assertRaisesRegex(ValueError, 'JDK archive checksum mismatch'):
            self.install()
        self.assertFalse(self.repository.exists())
        self.assertFalse(self.java_home.exists())

    def test_artifact_symlink_outside_bundle_cannot_be_installed(self):
        self.fetch()
        outside = self.root / 'outside.pom'
        outside.write_bytes(self.pom)
        source = self.bundle / 'repository' / self.record['path']
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'bundle symlink'):
            self.install()
        self.assertFalse(self.java_home.exists())
        self.assertEqual(self.pom, outside.read_bytes())

    def test_existing_repository_is_not_modified_if_jdk_version_is_wrong(self):
        self.archive = self.make_archive(version='17.0.1')
        self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
        self.write_locks()
        self.fetch()
        original = self.template.read_bytes()
        with self.assertRaisesRegex(ValueError, 'pinned Java version'):
            self.install()
        self.assertFalse(self.repository.exists())
        self.assertFalse(self.java_home.exists())
        self.assertEqual(original, self.template.read_bytes())

    def test_existing_maven_bytes_cannot_be_overwritten(self):
        self.fetch()
        target = self.repository / self.record['path']
        target.parent.mkdir(parents=True)
        target.write_bytes(b'preexisting bytes')
        with self.assertRaisesRegex(ValueError, 'existing Maven artifact differs'):
            self.install()
        self.assertEqual(b'preexisting bytes', target.read_bytes())
        self.assertFalse(self.java_home.exists())

    def test_archive_escape_and_wrong_java_version_are_rejected(self):
        traversal = tarfile.TarInfo('jdk/../../escaped')
        traversal.size = 1
        symlink = tarfile.TarInfo('jdk/lib/escape')
        symlink.type = tarfile.SYMTYPE
        symlink.linkname = '../../../escaped'
        hardlink = tarfile.TarInfo('jdk/lib/escape')
        hardlink.type = tarfile.LNKTYPE
        hardlink.linkname = 'outside/file'
        archives = [self.make_archive([(traversal, b'x')]), self.make_archive([(symlink, None)]),
                    self.make_archive([(hardlink, None)]), self.make_archive(version='17.0.1')]
        for index, archive in enumerate(archives):
            source = self.root / f'bad-{index}.tar.gz'
            source.write_bytes(archive)
            with self.subTest(archive=index), self.assertRaises(ValueError):
                supply.unpack_jdk(source, self.root / f'bad-jdk-{index}', self.lock['dcevm']['version'])
        self.assertFalse((self.root.parent / 'escaped').exists())

    def test_safe_archive_links_are_local_and_hardlinks_become_copies(self):
        symbolic = tarfile.TarInfo('jdk/bin/java-link')
        symbolic.type = tarfile.SYMTYPE
        symbolic.linkname = 'java'
        hard = tarfile.TarInfo('jdk/bin/java-copy')
        hard.type = tarfile.LNKTYPE
        hard.linkname = 'jdk/bin/java'
        self.archive = self.make_archive([(symbolic, None), (hard, None)])
        self.lock['dcevm']['sha256'] = hashlib.sha256(self.archive).hexdigest()
        self.write_locks()
        self.fetch()
        self.install()
        original = self.java_home / 'bin/java'
        self.assertEqual(original, (self.java_home / 'bin/java-link').resolve())
        copied = self.java_home / 'bin/java-copy'
        self.assertEqual(original.read_bytes(), copied.read_bytes())
        self.assertNotEqual(original.stat().st_ino, copied.stat().st_ino)

    def test_missing_bundle_cli_returns_prerequisite_not_solver_failure(self):
        result = subprocess.run([
            'python3', str(SCRIPT), '--template', str(self.template), 'install',
            '--bundle', str(self.bundle), '--repository', str(self.repository),
            '--java-home', str(self.java_home)], text=True, capture_output=True)
        self.assertEqual(2, result.returncode, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['prerequisite_missing'])
        self.assertFalse(report['solver_failure'])
        self.assertFalse(report['ready'])
        self.assertEqual({supply.LOCK_NAME, 'jdk.tar.gz', 'repository/' + self.record['path']},
                         set(report['missing_files']))
        self.assertEqual([self.record['source'], self.lock['dcevm']['release_url']],
                         report['missing_approvals'])

    def test_stage_check_install_roundtrip_preserves_readme_and_excludes_unlocked_files(self):
        self.fetch()
        (self.bundle / 'solution.patch').write_text('must not enter the task image')
        (self.bundle / 'repository/unlisted.jar').write_bytes(b'must not enter the task image')
        destination = self.root / 'runtime-supply'
        destination.mkdir()
        (destination / 'README.md').write_text('tracked supplier instructions')
        with patch.object(supply.urllib.request, 'urlopen', side_effect=AssertionError('staging network')):
            result = supply.stage(self.bundle, self.template, destination)
            self.assertTrue(result['bundle_integrity_verified'])
            self.assertFalse(result['ready'])
            self.assertEqual(self.lock, supply.verify_bundle(destination, self.template))
            self.assertEqual('tracked supplier instructions', (destination / 'README.md').read_text())
            self.assertFalse((destination / 'solution.patch').exists())
            self.assertFalse((destination / 'repository/unlisted.jar').exists())
            self.assertNotEqual((destination / 'jdk.tar.gz').stat().st_ino,
                                (self.bundle / 'jdk.tar.gz').stat().st_ino)
            supplied = supply.install(destination, self.template, self.repository, self.java_home)
        self.assertTrue(supplied['installed'])
        self.assertEqual(self.pom, (self.repository / self.record['path']).read_bytes())
        self.assertEqual(['lib/hotswap/agent.jar'], supplied['removed_bundled_agent_jars'])

    def test_stage_rejects_corruption_before_modifying_destination(self):
        self.fetch()
        (self.bundle / 'repository' / self.record['path']).write_bytes(b'corrupt artifact')
        destination = self.root / 'runtime-supply'
        destination.mkdir()
        readme = destination / 'README.md'
        readme.write_text('preserved')
        with self.assertRaisesRegex(ValueError, 'bundle checksum mismatch'):
            supply.stage(self.bundle, self.template, destination)
        self.assertEqual([readme], list(destination.iterdir()))
        self.assertEqual('preserved', readme.read_text())

    def test_stage_refuses_to_replace_existing_supply(self):
        self.fetch()
        destination = self.root / 'runtime-supply'
        supply.stage(self.bundle, self.template, destination)
        original = (destination / supply.LOCK_NAME).read_bytes()
        with self.assertRaisesRegex(ValueError, 'already contains supply files'):
            supply.stage(self.bundle, self.template, destination)
        self.assertEqual(original, (destination / supply.LOCK_NAME).read_bytes())

    def test_stage_refuses_destination_symlink_ancestor(self):
        self.fetch()
        outside = self.root / 'outside'
        outside.mkdir()
        link = self.root / 'linked'
        link.symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, 'destination symlink'):
            supply.stage(self.bundle, self.template, link / 'runtime-supply')
        self.assertEqual([], list(outside.iterdir()))

    def test_check_rejects_symlinked_manifest_and_repository_directory(self):
        self.fetch()
        for relative in (supply.LOCK_NAME, 'repository'):
            with self.subTest(relative=relative):
                target = self.bundle / relative
                outside = self.root / ('saved-' + relative)
                target.rename(outside)
                target.symlink_to(outside, target_is_directory=outside.is_dir())
                try:
                    with self.assertRaisesRegex(ValueError, 'bundle symlink'):
                        supply.verify_bundle(self.bundle, self.template)
                finally:
                    target.unlink()
                    outside.rename(target)

    def test_check_with_approved_lock_reports_all_missing_files(self):
        self.fetch()
        (self.bundle / 'jdk.tar.gz').unlink()
        (self.bundle / 'repository' / self.record['path']).unlink()
        with self.assertRaises(supply.SupplyPrerequisiteError) as caught:
            supply.verify_bundle(self.bundle, self.template)
        self.assertEqual({'jdk.tar.gz', 'repository/' + self.record['path']},
                         set(caught.exception.missing_files))
        self.assertEqual([], caught.exception.missing_approvals)

    def test_stage_and_check_cli_preserve_environment_acceptance_boundary(self):
        self.fetch()
        destination = self.root / 'runtime-supply'
        commands = [('stage', '--bundle', str(self.bundle), '--output', str(destination)),
                    ('check', '--bundle', str(destination))]
        for command in commands:
            with self.subTest(command=command[0]):
                result = subprocess.run(['python3', str(SCRIPT), '--template', str(self.template), *command],
                                        text=True, capture_output=True)
                self.assertEqual(0, result.returncode, result.stdout + result.stderr)
                report = json.loads(result.stdout)
                self.assertTrue(report['bundle_integrity_verified'])
                self.assertFalse(report['ready'])
                self.assertEqual(1, report['maven_artifact_count'])
                self.assertEqual(hashlib.sha256((destination / supply.LOCK_NAME).read_bytes()).hexdigest(),
                                 report['lock_sha256'])


if __name__ == '__main__':
    unittest.main()
