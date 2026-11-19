import sys

import pytest


@pytest.mark.skipif(not hasattr(sys, 'monitoring'), reason='requires real Python 3.12+ monitoring')
def test_sysmon_collect_stop_restart(tmp_path, monkeypatch):
    import coverage
    from coverage.sysmon import SysMonitor

    monkeypatch.setenv('COVERAGE_CORE', 'sysmon')
    cov = coverage.Coverage(config_file=False, data_file=None)
    paths = [str(tmp_path / name) for name in ('first.py', 'stopped.py', 'resumed.py')]
    cov.start()
    try:
        tracer = cov._collector.tracers[0]
        assert isinstance(tracer, SysMonitor)
        assert hasattr(tracer, '__dict__')
        exec(compile('first = 1\n', paths[0], 'exec'), {})
    finally:
        cov.stop()
    exec(compile('stopped = 2\n', paths[1], 'exec'), {})
    cov.start()
    try:
        exec(compile('resumed = 3\n', paths[2], 'exec'), {})
    finally:
        cov.stop()
    data = cov.get_data()
    assert data.lines(paths[0]) == [1]
    assert data.lines(paths[2]) == [1]
    assert paths[1] not in data.measured_files()
