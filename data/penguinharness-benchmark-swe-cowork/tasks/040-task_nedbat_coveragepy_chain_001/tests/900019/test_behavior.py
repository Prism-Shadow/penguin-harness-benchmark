import os
import subprocess
import sys
import textwrap

import pytest


@pytest.mark.parametrize('make_pth', [False, True])
@pytest.mark.parametrize('from_file', [False, True])
@pytest.mark.parametrize('relative_data', [False, True])
def test_fresh_interpreter_startup_and_cleanup(tmp_path, make_pth, from_file, relative_data):
    import coverage

    site_dir = tmp_path / 'site'
    site_dir.mkdir()
    unrelated = site_dir / 'existing.pth'
    unrelated.write_text('# keep this file\n', encoding='utf-8')
    other_cwd = tmp_path / 'other'
    other_cwd.mkdir()
    measured = tmp_path / 'measured.py'
    measured.write_text('value = 17\nvalue += 29\n', encoding='utf-8')
    data_file = tmp_path / 'data' / '.coverage'
    data_file.parent.mkdir()
    config_file = tmp_path / 'actual.coveragerc'
    if from_file:
        config_file.write_text('[run]\nbranch = True\ncontext = configured-context\n', encoding='utf-8')
    child = textwrap.dedent('''
        import pathlib, site, sys
        site.addsitedir(sys.argv[1])
        import coverage
        if sys.argv[3] == 'False':
            assert coverage.Coverage.current() is None
            coverage.process_startup()
        assert coverage.Coverage.current() is not None
        assert coverage.Coverage.current().config.context == sys.argv[4]
        filename = sys.argv[2]
        exec(compile(pathlib.Path(filename).read_text(), filename, 'exec'), {})
    ''')
    launcher = textwrap.dedent('''
        import os, pathlib, site, subprocess, sys
        import coverage
        from coverage.patch import apply_patches
        site_dir, data_file, measured, other_cwd, make_pth, child, config_file, relative_data = sys.argv[1:]
        enabled = make_pth == 'True'
        site.getsitepackages = lambda: [site_dir]
        if relative_data == 'True':
            os.chdir(pathlib.Path(data_file).parent.parent)
            data_file = os.path.relpath(data_file)
        cov = coverage.Coverage(config_file=config_file or False, data_file=data_file)
        cov.config.patch = ['subprocess']
        if not config_file:
            assert cov.config.config_file is None
            cov.set_option('run:context', 'constructor-context')
        cov.config.parallel = True
        before = set(pathlib.Path(site_dir).glob('*.pth'))
        if enabled:
            apply_patches(cov, cov.config, cov._debug)
        else:
            apply_patches(cov, cov.config, cov._debug, make_pth_file=False)
        after = set(pathlib.Path(site_dir).glob('*.pth'))
        assert bool(after - before) == enabled
        assert os.environ.get('COVERAGE_PROCESS_CONFIG')
        subprocess.run([sys.executable, '-c', child, site_dir, measured, make_pth, cov.config.context],
                       cwd=other_cwd, check=True, timeout=30)
    ''')
    result = subprocess.run(
        [sys.executable, '-c', launcher, str(site_dir), str(data_file),
         str(measured), str(other_cwd), str(make_pth), child,
         str(config_file) if from_file else "", str(relative_data)],
        env=os.environ.copy(), capture_output=True, text=True, timeout=60,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert list(site_dir.glob('*.pth')) == [unrelated]
    assert unrelated.read_text() == '# keep this file\n'
    files = list(data_file.parent.glob('.coverage*'))
    assert files
    lines = set()
    for filename in files:
        data = coverage.CoverageData(basename=str(filename))
        data.read()
        lines.update(data.lines(str(measured)) or [])
        assert data.measured_contexts() == {'configured-context' if from_file else 'constructor-context'}
    assert lines == {1, 2}
    assert not list(other_cwd.glob('.coverage*'))
