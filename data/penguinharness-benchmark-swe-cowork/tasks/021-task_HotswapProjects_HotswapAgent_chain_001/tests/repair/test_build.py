import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / 'environment/task-environment/build-production.sh'


class ImageBuildContractTests(unittest.TestCase):
    def test_broker_can_inventory_literal_base_images(self):
        for relative in ('environment/Dockerfile', 'environment/Dockerfile.source',
                         'environment/workplace-service/Dockerfile'):
            with self.subTest(recipe=relative):
                references = [line.split()[1] for line in (ROOT / relative).read_text().splitlines()
                              if line.upper().startswith('FROM ')]
                self.assertTrue(references)
                for reference in references:
                    self.assertNotIn('$', reference)
                    self.assertRegex(reference, r'^[a-z0-9][a-z0-9./_-]*(?::[\w.-]+|@sha256:[0-9a-f]{64})$')

    def test_adapted_recipe_preserves_source_build_and_preflight(self):
        source = (ROOT / 'environment/Dockerfile.source').read_text()
        adapted = (ROOT / 'environment/Dockerfile').read_text()
        self.assertEqual(source, adapted.split('# BEGIN cowork-standard-harbor adapter', 1)[0])


class BuildOrchestrationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repo = self.root / 'repository'
        self.repo.mkdir()
        self.cache = self.repo / '.segpipe-build-cache'
        self.cache.mkdir()
        self.modules = ('hotswap-agent-parent', 'hotswap-agent-core', 'plugin/hotswap-agent-tomcat-plugin')
        for module, marker in zip(self.modules, ('parent', 'core', 'tomcat')):
            path = self.repo / module
            (path / 'target/classes').mkdir(parents=True)
            (path / 'pom.xml').write_text('<project/>')
            (path / 'target/classes/stale.class').write_text('stale')
            (self.cache / (marker + '.ready')).write_text('cached')
        binaries = self.root / 'bin'
        binaries.mkdir()
        executable = binaries / 'mvn'
        executable.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALL_LOG"\nexit "${MAVEN_EXIT:-0}"\n')
        executable.chmod(0o755)
        self.calls = self.root / 'calls.log'
        self.environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                                REPO_DIR_OVERRIDE=str(self.repo), SEGPIPE_FORCE_BUILD='1',
                                CALL_LOG=str(self.calls))

    def run_build(self):
        return subprocess.run(['bash', str(BUILD_SCRIPT), 'core_tomcat'], env=self.environment,
                              text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    def test_forced_build_replaces_stale_targets_without_clean_plugin(self):
        result = self.run_build()
        self.assertEqual(0, result.returncode, result.stdout)
        calls = self.calls.read_text().splitlines()
        self.assertEqual(3, len(calls))
        for command in calls:
            arguments = command.split()
            self.assertEqual('2', arguments[arguments.index('-T') + 1])
            self.assertNotIn('clean', arguments)
            self.assertEqual('install', arguments[-1])
        for module in self.modules:
            self.assertFalse((self.repo / module / 'target/classes/stale.class').exists())

    def test_failed_maven_does_not_leave_ready_marker(self):
        self.environment['MAVEN_EXIT'] = '37'
        result = self.run_build()
        self.assertEqual(37, result.returncode)
        self.assertFalse((self.cache / 'parent.ready').exists())

    def test_required_module_cannot_pass_with_only_cached_classes(self):
        for module, marker in zip(self.modules, ('parent', 'core', 'tomcat')):
            with self.subTest(module=module):
                pom = self.repo / module / 'pom.xml'
                pom.unlink()
                result = self.run_build()
                self.assertEqual(2, result.returncode, result.stdout)
                self.assertIn('required production POM is missing', result.stdout)
                self.assertFalse((self.cache / (marker + '.ready')).exists())
                pom.write_text('<project/>')

    def test_target_symlink_does_not_delete_external_content(self):
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'keep.txt'
        sentinel.write_text('keep')
        target = self.repo / self.modules[0] / 'target'
        (target / 'classes/stale.class').unlink()
        (target / 'classes').rmdir()
        target.rmdir()
        target.symlink_to(outside, target_is_directory=True)
        result = self.run_build()
        self.assertEqual(0, result.returncode, result.stdout)
        self.assertEqual('keep', sentinel.read_text())
        self.assertFalse(target.is_symlink())


class PrefetchTests(unittest.TestCase):
    def run_prefetch(self, failed_artifact=''):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / 'bin'
            binaries.mkdir()
            calls = root / 'calls.jsonl'
            executable = binaries / 'mvn'
            executable.write_text(
                '#!/usr/bin/env python3\nimport json, os, sys\n'
                'arguments = sys.argv[1:]\n'
                'with open(os.environ["CALL_LOG"], "a") as output:\n'
                '    output.write(json.dumps(arguments) + "\\n")\n'
                'for argument in arguments:\n'
                '    if argument.startswith("-Dartifact="):\n'
                '        coordinate = argument.split("=", 1)[1]\n'
                '        parts = coordinate.split(":")\n'
                '        if coordinate == "org.apache.maven.surefire:common-junit4:2.15": sys.exit(43)\n'
                '        if coordinate == os.environ.get("FAILED_ARTIFACT"): sys.exit(47)\n'
                '        if coordinate == "org.apache.maven.surefire:surefire-junit4:2.15":\n'
                '            if "-Dtransitive=true" not in arguments: sys.exit(48)\n'
                '        if parts[1] in ("surefire", "surefire-providers", "maven-parent"):\n'
                '            if len(parts) != 4 or parts[3] != "pom": sys.exit(42)\n')
            executable.chmod(0o755)
            (root / 'build-production.sh').write_text('#!/bin/sh\nexit 0\n')
            environment = dict(os.environ, PATH=str(binaries) + os.pathsep + os.environ['PATH'],
                               CALL_LOG=str(calls), REPO_DIR=str(root), SEGPIPE_PREFETCH_OFFLINE='1',
                               FAILED_ARTIFACT=failed_artifact)
            result = subprocess.run(['bash', str(ROOT / 'environment/task-environment/prefetch-dependencies.sh'),
                                     str(root)], env=environment, text=True, capture_output=True)
            commands = [json.loads(line) for line in calls.read_text().splitlines()]
            return result, commands

    def test_parent_poms_are_resolved_as_poms_and_execution_stays_offline(self):
        result, commands = self.run_prefetch()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        coordinates = {argument.split('=', 1)[1] for command in commands for argument in command
                       if argument.startswith('-Dartifact=')}
        for coordinate in ('org.apache.maven.surefire:surefire:2.15:pom',
                           'org.apache.maven.surefire:surefire-providers:2.15:pom',
                           'org.apache.maven:maven-parent:22:pom',
                           'org.apache.maven.surefire:surefire-junit4:2.15',
                           'org.apache.maven.surefire:surefire-junit4:3.2.5'):
            self.assertIn(coordinate, coordinates)
        self.assertTrue(commands)
        self.assertTrue(all('-o' in command for command in commands))
        self.assertTrue(all('-Dtransitive=true' in command for command in commands[:-1]))

    def test_real_provider_resolution_failure_stops_before_harness(self):
        for provider in ('2.15', '3.2.5'):
            with self.subTest(provider=provider):
                coordinate = 'org.apache.maven.surefire:surefire-junit4:' + provider
                result, commands = self.run_prefetch(coordinate)
                self.assertEqual(47, result.returncode, result.stdout + result.stderr)
                self.assertIn('-Dartifact=' + coordinate, commands[-1])
                self.assertFalse(any('test' in command for command in commands))


if __name__ == '__main__':
    unittest.main()
