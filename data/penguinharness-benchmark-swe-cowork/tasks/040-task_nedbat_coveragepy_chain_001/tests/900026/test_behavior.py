import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.skipif(not hasattr(os, 'register_at_fork'), reason='POSIX fork required')
def test_fork_registers_child_callback(monkeypatch):
    import coverage
    from coverage.patch import apply_patches

    callbacks = []

    def register(**kwargs):
        callbacks.append(kwargs)

    monkeypatch.setattr(os, 'register_at_fork', register)
    cov = coverage.Coverage(config_file=False)
    cov.config.patch = ['fork']
    apply_patches(cov, cov.config, cov._debug, make_pth_file=False)
    assert os.register_at_fork is register
    assert len(callbacks) == 1
    assert callable(callbacks[0]['after_in_child'])


@pytest.mark.skipif(not hasattr(os, 'fork'), reason='POSIX fork required')
def test_fork_restarts_child_measurement(tmp_path):
    import coverage

    script = textwrap.dedent('''
        import os, pathlib, sys
        import coverage
        from coverage.patch import apply_patches
        root = pathlib.Path(sys.argv[1])
        cov = coverage.Coverage(config_file=False, data_file=str(root / '.coverage'),
                                data_suffix=True)
        cov.start()
        exec(compile('parent = 1\\n', str(root / 'parent.py'), 'exec'), {})
        cov.config.patch = []
        os.environ['COVERAGE_PROCESS_CONFIG'] = cov.config.serialize()
        cov.config.patch = ['fork']
        apply_patches(cov, cov.config, cov._debug, make_pth_file=False)
        child = os.fork()
        if child == 0:
            current = coverage.Coverage.current()
            if current is None or current is cov:
                os._exit(41)
            exec(compile('child = 2\\n', str(root / 'child.py'), 'exec'), {})
            current.stop()
            current.save()
            os._exit(0)
        _, status = os.waitpid(child, 0)
        assert os.waitstatus_to_exitcode(status) == 0
        cov.stop()
        cov.save()
    ''')
    result = subprocess.run([sys.executable, '-c', script, str(tmp_path)],
                            capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    measured = []
    for filename in tmp_path.glob('.coverage*'):
        data = coverage.CoverageData(basename=str(filename))
        data.read()
        measured.append(set(data.measured_files()))
    assert len(measured) == 2
    assert {str(tmp_path / 'parent.py')} in measured
    assert {str(tmp_path / 'child.py')} in measured
