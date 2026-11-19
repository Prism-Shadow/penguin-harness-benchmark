import hashlib
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    'offline_runtime', ROOT / 'environment/task-environment/prepare-offline-runtime.py')
runtime = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runtime)


class RuntimePreflightTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.repository = Path(temporary.name) / 'isolated repository'
        self.repository.mkdir()
        self.artifact = self.repository / 'provider.jar'
        self.artifact.write_bytes(b'controlled provider fixture')
        self.lock = {
            'revision': 'test',
            'default_lifecycle': {'junit_provider': 'example:provider:1'},
            'maven_artifacts': [{
                'coordinate': 'example:provider:1', 'extension': 'jar',
                'path': 'provider.jar',
                'sha256': hashlib.sha256(self.artifact.read_bytes()).hexdigest(),
            }],
            'dcevm': {
                'vendor': 'fixture', 'distribution': 'fixture', 'version': '11',
                'release_url': 'fixture', 'sha256': None,
            },
        }

    def inspect_without_java(self, output=(0, 'controlled resolver pass')):
        with patch.object(runtime, 'java_command', return_value=None), \
                patch.object(runtime, 'command_output', return_value=output) as command:
            result = runtime.inspect_runtime(self.lock, self.repository, maven='controlled-mvn')
        return result, command

    def test_resolver_uses_only_selected_repository(self):
        result, command = self.inspect_without_java()
        arguments = command.call_args.args[0]
        repository_option = '-Dmaven.repo.local=' + str(self.repository.resolve())
        self.assertEqual([repository_option], [argument for argument in arguments
                                              if argument.startswith('-Dmaven.repo.local=')])
        self.assertIn('-o', arguments)
        self.assertIn('-Dtransitive=true', arguments)
        self.assertEqual(str(self.repository.resolve()), result['maven_repository'])
        self.assertEqual(arguments, result['dependency_resolver_probe']['command'])
        self.assertTrue(result['dependency_closure_verified'])
        self.assertFalse(result['ready'])
        self.assertFalse(result['solver_failure'])

    def test_artifact_defects_prevent_resolution(self):
        for defect, field in (('missing', 'missing_artifacts'),
                              ('unpinned', 'unpinned_artifacts'),
                              ('mismatched', 'mismatched_artifacts')):
            with self.subTest(defect=defect):
                if defect == 'missing':
                    self.artifact.unlink()
                elif defect == 'unpinned':
                    self.lock['maven_artifacts'][0]['sha256'] = None
                else:
                    self.lock['maven_artifacts'][0]['sha256'] = '0' * 64
                result, command = self.inspect_without_java()
                command.assert_not_called()
                self.assertEqual(['example:provider:1:jar'], result[field])
                self.assertFalse(result['dependency_closure_verified'])
                self.assertFalse(result['ready'])
                self.assertFalse(result['solver_failure'])
                self.artifact.write_bytes(b'controlled provider fixture')

    def test_resolver_failure_is_not_a_solver_failure(self):
        result, command = self.inspect_without_java((19, 'missing transitive fixture'))
        command.assert_called_once()
        self.assertEqual('failed', result['dependency_resolver_probe']['status'])
        self.assertEqual(19, result['dependency_resolver_probe']['exit_code'])
        self.assertFalse(result['dependency_closure_verified'])
        self.assertTrue(result['prerequisite_missing'])
        self.assertFalse(result['solver_failure'])

    def test_main_probe_compilation_can_see_agent(self):
        compiled_sources = {}

        def controlled_tools(command):
            if command[0] == 'controlled-javac':
                source = Path(command[-1])
                output = command[command.index('-d') + 1]
                if source.name == 'Main.java':
                    classpath = command[command.index('-cp') + 1].split(os.pathsep)
                    if compiled_sources['ProbeAgent.java'] not in classpath:
                        return 1, 'cannot find symbol: ProbeAgent'
                    self.assertIn(compiled_sources['TargetV1.java'], classpath)
                compiled_sources[source.name] = output
                return 0, ''
            if command[0] == 'controlled-java':
                self.assertTrue(any(argument.startswith('-javaagent:') for argument in command))
                return 0, 'DCEVM_REDEFINITION_PASS'
            return 0, ''

        with patch.object(runtime, 'command_output', side_effect=controlled_tools):
            result = runtime.run_redefinition_probe(
                'controlled-java', 'controlled-javac', 'controlled-jar')
        self.assertEqual('passed', result['status'], result)
        self.assertEqual(6, len(result['steps']))

    def test_probe_reports_distinct_failure_stages(self):
        for failing_index, expected in ((0, 'probe_compile_failed'),
                                        (3, 'probe_compile_failed'),
                                        (4, 'probe_packaging_failed'),
                                        (5, 'probe_failed')):
            with self.subTest(stage=failing_index):
                responses = [(0, '')] * failing_index + [(31, 'controlled failure')]
                with patch.object(runtime, 'command_output', side_effect=responses):
                    result = runtime.run_redefinition_probe('java', 'javac', 'jar')
                self.assertEqual(expected, result['status'])
                self.assertEqual(31, result['steps'][-1]['exit_code'])
                self.assertEqual(failing_index + 1, len(result['steps']))

    def test_probe_requires_execution_marker_and_tools(self):
        with patch.object(runtime, 'command_output', return_value=(0, '')) as command:
            result = runtime.run_redefinition_probe(None, 'javac', 'jar')
            self.assertEqual('prerequisite_missing', result['status'])
            command.assert_not_called()
            result = runtime.run_redefinition_probe('java', 'javac', 'jar')
            self.assertEqual('probe_failed', result['status'])

    def inspect_selected_java(self, version_output, version_code=0, probe_status='passed'):
        self.lock['dcevm'].update(version='11.0.11', sha256='1' * 64)
        responses = [(0, 'resolved'), (version_code, version_output), (0, 'flags accepted')]
        with patch.object(runtime, 'command_output', side_effect=responses), \
                patch.object(runtime, 'run_redefinition_probe', return_value={'status': probe_status}) as probe:
            result = runtime.inspect_runtime(self.lock, self.repository, java='fixture-java', maven='fixture-mvn')
        return result, probe

    def test_runtime_preflight_requires_exact_approved_java_version(self):
        for output, code in [('openjdk version "11.0.9"', 0),
                             ('openjdk version "11.0.11+2"', 0),
                             ('openjdk version "11.0.11"', 1),
                             ('openjdk version "11.0.11"\njava version "11.0.11"', 0)]:
            with self.subTest(output=output, code=code):
                result, probe = self.inspect_selected_java(output, code)
                probe.assert_not_called()
                self.assertFalse(result['dcevm']['version_matches_pin'])
                self.assertFalse(result['ready'])
                self.assertTrue(result['prerequisite_missing'])
                self.assertFalse(result['solver_failure'])

    def test_matching_runtime_still_requires_structural_redefinition(self):
        for probe_status in ('failed', 'passed'):
            with self.subTest(probe_status=probe_status):
                result, probe = self.inspect_selected_java('openjdk version "11.0.11"', probe_status=probe_status)
                probe.assert_called_once()
                self.assertTrue(result['dcevm']['version_matches_pin'])
                self.assertEqual(probe_status == 'passed', result['ready'])


if __name__ == '__main__':
    unittest.main()
