import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit


root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('regression_setup', root / 'environment/install-regressions.py')
setup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(setup)


class RegressionEnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.manifest = json.loads((root / 'environment/regression-required-gems.json').read_text())
        self.repo = root / 'environment/base'
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.destination = Path(self.temporary.name) / 'bundle'

    def test_platform_bundle_is_frozen_equivalent_and_original_inputs_unchanged(self):
        expected = setup.prepare_bundle(self.repo, self.destination, self.manifest)
        environment = {key: value for key, value in os.environ.items() if not key.startswith('BUNDLE_')}
        environment.update(BUNDLE_GEMFILE=str(self.destination / 'Gemfile'), BUNDLE_FROZEN='true')
        program = '''
require 'bundler'
definition = Bundler.definition
definition.ensure_equivalent_gemfile_and_lockfile(true)
abort 'debugging group missing' unless definition.dependencies.any? { |dep| dep.name == 'kicker' }
abort 'Darwin-only dependency activated' if definition.dependencies.any? { |dep| dep.name == 'libxml-ruby' }
puts "FROZEN_METADATA_EQUIVALENT Bundler=#{Bundler::VERSION}"
'''
        result = subprocess.run(['ruby', '-e', program], cwd=self.repo, env=environment,
                                capture_output=True, text=True)
        print(result.stdout, result.stderr)
        self.assertEqual(0, result.returncode)
        self.assertEqual(expected, hashlib.sha256((self.destination / 'Gemfile.lock').read_bytes()).hexdigest())
        for filename, digest in self.manifest['source_sha256'].items():
            self.assertEqual(digest, hashlib.sha256((self.repo / filename).read_bytes()).hexdigest())
        original_gems = (self.repo / 'Gemfile.lock').read_text().split('\nGEM\n')[1].split('\nPLATFORMS\n')[0]
        platform_gems = (self.destination / 'Gemfile.lock').read_text().split('\nGEM\n')[1].split('\nPLATFORMS\n')[0]
        self.assertEqual(original_gems.replace('http://', 'https://'), platform_gems)

    def test_inventory_version_change_or_omission_fails(self):
        for mutation in ('upgrade', 'omit', 'duplicate'):
            with self.subTest(mutation=mutation):
                manifest = copy.deepcopy(self.manifest)
                if mutation == 'upgrade':
                    manifest['gems'][0]['version'] = '2.3.6'
                elif mutation == 'omit':
                    manifest['gems'].pop()
                else:
                    manifest['gems'].append(manifest['gems'][0])
                with self.assertRaisesRegex(ValueError, 'inventory differs'):
                    setup.prepare_bundle(self.repo, self.destination, manifest)

    def test_changed_original_metadata_fails_before_any_network(self):
        self.manifest['source_sha256']['Gemfile.lock'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'Unexpected regression input'):
            setup.prepare_bundle(self.repo, self.destination, self.manifest)

    def package_case(self, transform=None, shipped=False):
        content = (root / 'environment/repair-gem-cache/colored-1.2.gem').read_bytes()
        metadata = dict(name='colored', version='1.2', platform='ruby', sha=hashlib.sha256(content).hexdigest())
        if transform:
            metadata, content = transform(metadata, content)
        requests = []

        def transport(url):
            requests.append(url)
            self.assertTrue(url.startswith('https://rubygems.org/'))
            if '/api/v2/' in url:
                self.assertEqual({'platform': ['ruby']}, parse_qs(urlsplit(url).query))
            return json.dumps(metadata).encode() if '/api/v2/' in url else content

        shipped_cache = root / 'environment/repair-gem-cache' if shipped else self.destination / 'empty'
        with patch.object(setup, 'download', side_effect=transport):
            receipt = setup.stage_gems({'gems': [dict(name='colored', version='1.2')]},
                                       self.destination / 'cache', shipped_cache)
        self.assertEqual(hashlib.sha256(content).hexdigest(), receipt[0]['sha256'])
        self.assertEqual('ruby', receipt[0]['platform'])
        self.assertEqual(content, (self.destination / 'cache/colored-1.2.gem').read_bytes())
        self.assertEqual(1 if shipped else 2, len(requests))

    def test_source_platform_selected_when_publisher_default_is_binary(self):
        for name, version, default_platform in [('ffi', '1.9.3', 'x86-mingw32'),
                                                 ('ffi', '1.17.0', 'java'),
                                                 ('rb-kqueue', '0.2.3', 'x86_64-darwin')]:
            with self.subTest(name=name, version=version, platform=default_platform):
                content = os.urandom(128)
                source_metadata = dict(name=name, version=version, platform='ruby',
                                       sha=hashlib.sha256(content).hexdigest())
                binary_metadata = dict(source_metadata, platform=default_platform, sha='0' * 64)
                metadata_path = '/api/v2/rubygems/{}/versions/{}.json'.format(name, version)
                package_path = '/downloads/{}-{}.gem'.format(name, version)
                requests = []

                def transport(url):
                    requests.append(url)
                    parsed = urlsplit(url)
                    self.assertEqual(('https', 'rubygems.org'), (parsed.scheme, parsed.netloc))
                    if parsed.path == metadata_path:
                        selected = source_metadata if parse_qs(parsed.query) == {'platform': ['ruby']} else binary_metadata
                        return json.dumps(selected).encode()
                    self.assertEqual(package_path, parsed.path)
                    self.assertEqual('', parsed.query)
                    return content

                cache = self.destination / name / version
                with patch.object(setup, 'download', side_effect=transport):
                    receipts = setup.stage_gems({'gems': [dict(name=name, version=version)]},
                                                cache, self.destination / 'empty')
                self.assertEqual(2, len(requests))
                self.assertEqual(content, (cache / '{}-{}.gem'.format(name, version)).read_bytes())
                self.assertEqual(source_metadata['sha'], receipts[0]['sha256'])
                self.assertEqual('ruby', receipts[0]['platform'])
                self.assertEqual(requests[0], receipts[0]['metadata_url'])

    def test_missing_source_platform_does_not_fall_back_to_binary(self):
        url = 'https://rubygems.org/api/v2/rubygems/ffi/versions/1.9.3.json?platform=ruby'
        failure = HTTPError(url, 404, 'Source platform unavailable', {}, None)
        with patch.object(setup, 'download', side_effect=failure) as transport:
            with self.assertRaises(HTTPError):
                setup.stage_gems({'gems': [dict(name='ffi', version='1.9.3')]},
                                 self.destination / 'cache', self.destination / 'empty')
        transport.assert_called_once_with(url)
        self.assertEqual([], list((self.destination / 'cache').iterdir()))

    def test_exact_publisher_package_is_staged(self):
        self.package_case()

    def test_shipped_package_still_requires_publisher_digest(self):
        self.package_case(shipped=True)

    def test_corrupted_payload_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'SHA256 mismatch'):
            self.package_case(lambda metadata, content: (metadata, content[:-1] + bytes([content[-1] ^ 1])))

    def test_wrong_identity_or_platform_is_rejected(self):
        for key, value in [('name', 'xcodeproj'), ('version', '9.9'), ('platform', 'x86_64-linux')]:
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'identity mismatch'):
                self.package_case(lambda metadata, content: ({**metadata, key: value}, content))

    def test_absent_or_wrong_digest_is_rejected_even_for_shipped_cache(self):
        for digest in ['', '0' * 64]:
            with self.subTest(digest=digest), self.assertRaisesRegex(ValueError, 'SHA256'):
                self.package_case(lambda metadata, content: ({**metadata, 'sha': digest}, content), shipped=True)

    def test_insecure_transport_and_redirect_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'require HTTPS'):
            setup.download('http://rubygems.org/downloads/colored-1.2.gem')
        with self.assertRaisesRegex(ValueError, 'non-HTTPS'):
            setup.HTTPSRedirect().redirect_request(None, None, 302, '', {}, 'http://rubygems.org/')


if __name__ == '__main__':
    unittest.main(verbosity=2)
