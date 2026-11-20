import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


ENVIRONMENT = Path(__file__).resolve().parents[2] / 'environment'
SPEC = importlib.util.spec_from_file_location('runtime_audit', ENVIRONMENT / 'audit_runtime.py')
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def invoke(monkeypatch, capsys, root, *options):
    monkeypatch.setattr(sys, 'argv', ['audit_runtime.py', *map(str, options), str(root)])
    status = AUDIT.main()
    return status, json.loads(capsys.readouterr().out)


def write_zip(path, member):
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, 'fixture content')


@pytest.fixture
def verified_cache(monkeypatch, tmp_path):
    cache = tmp_path / 'modules'
    module = cache / 'example.invalid/format@v1.2.3'
    fixture = module / 'testdata/truncated.zip'
    fixture.parent.mkdir(parents=True)
    fixture.write_bytes(b'PK\x03\x04intentionally incomplete format fixture')
    repo = tmp_path / 'repo'
    repo.mkdir()
    (repo / 'go.mod').write_text('module caller\n')
    (repo / 'go.sum').write_text('pinned input\n')
    calls = []
    records = [{'Path': 'caller', 'Main': True, 'Dir': str(repo)},
               {'Path': 'example.invalid/format', 'Version': 'v1.2.3', 'Dir': str(module)}]

    def run(command, **kwargs):
        calls.append((command, kwargs))
        assert command in (['go', 'list', '-mod=readonly', '-m', '-json', 'all'],
                           ['go', 'mod', 'verify'])
        output = '\n'.join(json.dumps(record) for record in records)
        if command == ['go', 'mod', 'verify']:
            output = 'all modules verified\n'
        return subprocess.CompletedProcess(command, 0, output, '')

    monkeypatch.setattr(subprocess, 'run', run)
    return cache, module, fixture, repo, calls, records


def test_malformed_archive_reports_path_instead_of_crashing(monkeypatch, capsys, tmp_path):
    damaged = tmp_path / 'damaged.zip'
    damaged.write_bytes(b'not a ZIP container')
    status, report = invoke(monkeypatch, capsys, tmp_path)
    assert status == 1
    assert any(str(damaged) in error for error in report['errors'])
    assert report['checked_files'] == 1


def test_verified_upstream_format_fixture_is_scanned_as_data(monkeypatch, capsys, verified_cache):
    cache, module, fixture, repo, calls, records = verified_cache
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 0, report
    assert not report['errors'] and not report['findings']
    assert report['non_zip_fixtures'][0]['path'] == str(fixture)
    assert len(report['non_zip_fixtures'][0]['sha256']) == 64
    assert [command for command, options in calls] == [
        ['go', 'list', '-mod=readonly', '-m', '-json', 'all'], ['go', 'mod', 'verify']]
    for command, options in calls:
        assert options['cwd'] == repo
        assert options['timeout'] == 120
        assert options['env']['GOPROXY'] == 'off'
        assert options['env']['GOSUMDB'] == 'sum.golang.org'
        assert options['env']['GOTOOLCHAIN'] == 'local'
        assert options['env']['GOMAXPROCS'] == '2'
        assert options['env']['GOMODCACHE'] == str(cache)
        for key in ('GOFLAGS', 'GOINSECURE', 'GOPRIVATE', 'GONOSUMDB', 'GONOPROXY'):
            assert options['env'][key] == ''


@pytest.mark.parametrize('target', AUDIT.TARGETS)
def test_targets_in_raw_fixture_are_not_exempt(monkeypatch, capsys, verified_cache, target):
    cache, module, fixture, repo, calls, records = verified_cache
    fixture.write_bytes(b'x' * 65530 + target.encode() + b'payload')
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1
    assert any(str(fixture) in finding and target in finding for finding in report['findings'])


@pytest.mark.parametrize('location', ['outside.zip', 'testdata/broken.whl',
                                     'cache/download/example/@v/v1.2.3.zip'])
def test_package_archives_and_nonfixture_zip_remain_fail_closed(
        monkeypatch, capsys, verified_cache, location):
    cache, module, fixture, repo, calls, records = verified_cache
    root = cache if location.startswith('cache/') else module
    damaged = root / location
    damaged.parent.mkdir(parents=True, exist_ok=True)
    damaged.write_bytes(b'invalid package')
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1
    assert any(str(damaged) in error for error in report['errors'])


@pytest.mark.parametrize('change', ['unlisted', 'local-replace', 'outside-cache'])
def test_unverified_fixture_cannot_gain_exception(monkeypatch, capsys, verified_cache, change):
    cache, module, fixture, repo, calls, records = verified_cache
    if change == 'unlisted':
        records.pop()
    elif change == 'local-replace':
        records[-1]['Replace'] = {'Path': str(module), 'Dir': str(module)}
    else:
        records[-1]['Dir'] = str(cache.parent)
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1
    assert report['errors']
    assert not report['non_zip_fixtures']


@pytest.mark.parametrize('failure', ['checksum', 'timeout', 'changed-pins', 'invalid-json'])
def test_failed_integrity_never_authorizes_fixtures(monkeypatch, capsys, verified_cache, failure):
    cache, module, fixture, repo, calls, records = verified_cache
    original_run = subprocess.run

    def run(command, **kwargs):
        if failure == 'timeout':
            raise subprocess.TimeoutExpired(command, 120)
        result = original_run(command, **kwargs)
        if failure == 'checksum' and command == ['go', 'mod', 'verify']:
            return subprocess.CompletedProcess(command, 1, '', 'cached module dir has been modified')
        if failure == 'changed-pins':
            (repo / 'go.sum').write_text('changed checksum')
        if failure == 'invalid-json':
            return subprocess.CompletedProcess(command, 0, 'not JSON', '')
        return result

    monkeypatch.setattr(subprocess, 'run', run)
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1 and report['errors']
    assert not report['non_zip_fixtures']


@pytest.mark.parametrize('target', AUDIT.TARGETS)
def test_valid_archives_are_scanned_even_inside_verified_testdata(
        monkeypatch, capsys, verified_cache, target):
    cache, module, fixture, repo, calls, records = verified_cache
    write_zip(fixture, 'vendored/' + target + 'source.py')
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1 and report['findings']
    assert not report['non_zip_fixtures']


def test_scan_continues_after_bad_archive(monkeypatch, capsys, tmp_path):
    (tmp_path / 'bad.zip').write_bytes(b'invalid')
    write_zip(tmp_path / 'ordinary.whl', 'vendor/rag/advanced_rag/stats.py')
    status, report = invoke(monkeypatch, capsys, tmp_path)
    assert status == 1 and report['errors'] and report['findings']
    assert report['checked_files'] == 2


def test_good_archive_and_ordinary_file_pass(monkeypatch, capsys, tmp_path):
    write_zip(tmp_path / 'clean.whl', 'package/utility.py')
    (tmp_path / 'readme.txt').write_text('ordinary data')
    status, report = invoke(monkeypatch, capsys, tmp_path)
    assert status == 0 and not report['findings']


def test_missing_scan_root_fails_closed(monkeypatch, capsys, tmp_path):
    status, report = invoke(monkeypatch, capsys, tmp_path / 'missing')
    assert status == 1 and report['errors']


def test_module_replacement_and_alternative_fixture_name_remain_supported(
        monkeypatch, capsys, verified_cache):
    cache, module, fixture, repo, calls, records = verified_cache
    replacement = dict(records[-1])
    records[-1] = {'Path': 'example.invalid/original', 'Version': 'v0.1.0', 'Replace': replacement}
    renamed = fixture.with_name('different-invalid-archive.zip')
    fixture.rename(renamed)
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 0, report
    assert report['non_zip_fixtures'][0]['path'] == str(renamed)


def test_symlink_cannot_borrow_verified_fixture_identity(monkeypatch, capsys, verified_cache):
    cache, module, fixture, repo, calls, records = verified_cache
    outside = cache.parent / 'outside.zip'
    outside.write_bytes(b'unverified data')
    fixture.unlink()
    fixture.symlink_to(outside)
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1 and report['errors']
    assert not report['non_zip_fixtures']


def test_backslash_path_in_raw_fixture_is_rejected(monkeypatch, capsys, verified_cache):
    cache, module, fixture, repo, calls, records = verified_cache
    fixture.write_bytes(b'vendor\\rag\\advanced_rag\\stats.py')
    status, report = invoke(monkeypatch, capsys, cache, '--go-repo', repo, '--go-module-cache', cache)
    assert status == 1 and report['findings']


@pytest.mark.parametrize('option', ['--go-repo', '--go-module-cache'])
def test_partial_verification_configuration_fails_closed(monkeypatch, capsys, tmp_path, option):
    status, report = invoke(monkeypatch, capsys, tmp_path, option, tmp_path)
    assert status == 1 and report['errors']
