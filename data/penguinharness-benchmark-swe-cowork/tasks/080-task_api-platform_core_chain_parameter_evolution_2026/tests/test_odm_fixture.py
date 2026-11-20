import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch


specification = importlib.util.spec_from_file_location('odm_fixture', Path(__file__).parent / 'segpipe_tests/odm_fixture.py')
fixture = importlib.util.module_from_spec(specification)
specification.loader.exec_module(fixture)
REAL_POPEN = subprocess.Popen


class OdmFixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.environment = {'TASK_ODM_RUN_DIR': self.temporary.name}
        self.process = MagicMock()
        self.process.poll.return_value = None
        for target, value in [
            ('shutil.which', '/usr/local/bin/mongod'),
            ('subprocess.Popen', self.process),
            ('socket.socket', MagicMock()),
            ('socket.create_connection', MagicMock()),
        ]:
            module, attribute = target.split('.')
            replacement = patch.object(getattr(fixture, module), attribute, return_value=value)
            mocked = replacement.start()
            setattr(self, target.split('.')[-1], mocked)
            self.addCleanup(replacement.stop)

    def assert_cleaned(self):
        self.process.terminate.assert_called_once()
        self.process.wait.assert_called()
        self.assertFalse(list(Path(self.temporary.name).glob('*/data')))
        self.assertEqual(1, len(list(Path(self.temporary.name).glob('*/mongod.log'))))

    def test_owned_process_binds_only_loopback_and_cleans_its_data(self):
        with fixture.fixture_environment(self.environment) as environment:
            self.assertEqual('mongodb://127.0.0.1:27017', environment['TASK_MONGODB_URI'])
            self.assertNotIn('TASK_MONGODB_URI', self.environment)
            command = self.Popen.call_args.args[0]
            self.assertEqual('127.0.0.1', command[command.index('--bind_ip') + 1])
            self.assertEqual('0.25', command[command.index('--wiredTigerCacheSizeGB') + 1])
            self.assertIn('--nounixsocket', command)
            self.assertTrue(Path(command[command.index('--dbpath') + 1]).is_dir())
            self.process.terminate.assert_not_called()
        self.assert_cleaned()

    def test_explicit_broker_uri_is_left_for_php_preflight(self):
        environment = dict(self.environment, TASK_MONGODB_URI='mongodb://mongo:27017')
        with fixture.fixture_environment(environment) as result:
            self.assertEqual(environment, result)
        self.Popen.assert_not_called()
        self.socket.assert_not_called()

    def test_missing_binary_fails_closed(self):
        self.which.return_value = None
        with self.assertRaisesRegex(fixture.FixtureError, 'rebuild'):
            with fixture.fixture_environment(self.environment):
                self.fail('must not run PHPUnit')
        self.Popen.assert_not_called()

    def test_busy_port_does_not_reuse_an_unowned_service(self):
        self.socket.return_value.__enter__.return_value.bind.side_effect = OSError('busy port')
        with self.assertRaisesRegex(fixture.FixtureError, 'busy port'):
            with fixture.fixture_environment(self.environment):
                self.fail('must not run PHPUnit')
        self.Popen.assert_not_called()

    def test_spawn_error_cleans_only_the_new_data_directory(self):
        self.Popen.side_effect = OSError('cannot exec')
        preserved = Path(self.temporary.name) / 'other-run'
        preserved.mkdir()
        with self.assertRaisesRegex(fixture.FixtureError, 'cannot exec'):
            with fixture.fixture_environment(self.environment):
                self.fail('must not run PHPUnit')
        self.assertTrue(preserved.is_dir())
        self.assertFalse(list(Path(self.temporary.name).glob('*/data')))

    def test_early_exit_is_not_readiness(self):
        self.process.poll.return_value = 1
        self.process.returncode = 1
        with self.assertRaisesRegex(fixture.FixtureError, 'exited 1'):
            with fixture.fixture_environment(self.environment):
                self.fail('must not run PHPUnit')
        self.process.terminate.assert_not_called()
        self.assertFalse(list(Path(self.temporary.name).glob('*/data')))

    def test_readiness_timeout_stops_owned_process(self):
        self.create_connection.side_effect = ConnectionRefusedError('not ready')
        with patch.object(fixture.time, 'monotonic', side_effect=[0, 31]):
            with self.assertRaisesRegex(fixture.FixtureError, 'timed out'):
                with fixture.fixture_environment(self.environment):
                    self.fail('must not run PHPUnit')
        self.assert_cleaned()

    def test_phpunit_exception_still_stops_owned_process(self):
        with self.assertRaisesRegex(ValueError, 'test failure'):
            with fixture.fixture_environment(self.environment):
                raise ValueError('test failure')
        self.assert_cleaned()

    def test_unresponsive_process_is_killed_without_global_cleanup(self):
        self.process.wait.side_effect = [subprocess.TimeoutExpired('mongod', 10), 0]
        with fixture.fixture_environment(self.environment):
            pass
        self.process.kill.assert_called_once()
        self.assert_cleaned()

    def test_cleanup_failure_is_reported_as_infrastructure(self):
        with patch.object(fixture.shutil, 'rmtree', side_effect=OSError('read only')):
            with self.assertRaisesRegex(fixture.FixtureError, 'clean up owned mongod'):
                with fixture.fixture_environment(self.environment):
                    pass
        self.process.terminate.assert_called_once()

    def test_real_substitute_process_is_reaped_with_mocked_readiness(self):
        executable = Path(self.temporary.name) / 'substitute-server'
        executable.write_text('#!' + sys.executable + '\nimport time\ntime.sleep(60)\n')
        executable.chmod(0o700)
        self.which.return_value = str(executable)
        processes = []

        def launch(*arguments, **options):
            process = REAL_POPEN(*arguments, **options)
            processes.append(process)
            return process

        self.Popen.side_effect = launch
        with fixture.fixture_environment(self.environment):
            self.assertIsNone(processes[0].poll())
        self.assertIsNotNone(processes[0].poll())
        self.assertFalse(list(Path(self.temporary.name).glob('*/data')))
        self.assertTrue(executable.is_file())


if __name__ == '__main__':
    unittest.main()
