import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ENVIRONMENT = Path(__file__).resolve().parents[2] / 'environment'
SCRIPT = ENVIRONMENT / 'development/select-go-proxy.py'
SPEC = importlib.util.spec_from_file_location('go_proxy', SCRIPT)
PROXY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROXY)


@pytest.fixture
def repo(tmp_path):
    target = tmp_path / 'repo'
    target.mkdir()
    for filename in ('go.mod', 'go.sum'):
        (target / filename).write_bytes((ENVIRONMENT / 'base' / filename).read_bytes())
    return target


@pytest.fixture
def fake_go(tmp_path, monkeypatch, repo):
    version, expected = PROXY.probe_target(repo)
    responses = {
        'https://goproxy.cn': {'exit': 1, 'error': 'tls: failed to verify certificate: x509: hostname mismatch'},
        'https://goproxy.io': {'exit': 0, 'record': {
            'Path': PROXY.PROBE_MODULE, 'Version': version, **expected}},
        'https://proxy.golang.org': {'exit': 1, 'error': 'DNS unavailable'},
    }
    config = tmp_path / 'responses.json'
    config.write_text(json.dumps(responses))
    trace = tmp_path / 'trace.jsonl'
    binary = tmp_path / 'bin'
    binary.mkdir()
    executable = binary / 'go'
    executable.write_text('#!' + sys.executable + '\n' + '''import json
import os
from pathlib import Path
import sys

configuration = json.loads(Path(os.environ['PROXY_TEST_RESPONSES']).read_text())
response = configuration[os.environ['GOPROXY']]
keys = ('GOPROXY', 'GOSUMDB', 'GOINSECURE', 'GOPRIVATE', 'GONOSUMDB', 'GONOPROXY',
        'GOENV', 'GOAUTH', 'GOWORK', 'GO111MODULE', 'GOFLAGS', 'GOMAXPROCS', 'GOMODCACHE')
record = {'argv': sys.argv[1:], 'cwd': os.getcwd(), 'env': {key: os.environ[key] for key in keys},
          'fresh_cache': not Path(os.environ['GOMODCACHE']).exists(),
          'no_go_sum': not Path('go.sum').exists(), 'no_go_mod': not Path('go.mod').exists()}
with Path(os.environ['PROXY_TEST_TRACE']).open('a') as stream:
    stream.write(json.dumps(record) + '\\n')
if response['exit']:
    print(response['error'], file=sys.stderr)
else:
    print(json.dumps(response['record']))
raise SystemExit(response['exit'])
''')
    executable.chmod(0o755)
    monkeypatch.setenv('PATH', str(binary) + os.pathsep + os.environ.get('PATH', ''))
    monkeypatch.setenv('PROXY_TEST_RESPONSES', str(config))
    monkeypatch.setenv('PROXY_TEST_TRACE', str(trace))
    monkeypatch.delenv('RAGFLOW_GOPROXY', raising=False)
    return config, trace


def invoke(repo, tmp_path, *options):
    return subprocess.run([sys.executable, str(SCRIPT), '--repo', str(repo),
                           '--receipt', str(tmp_path / 'receipt.json'),
                           '--temporary-root', str(tmp_path), *options],
                          capture_output=True, text=True, timeout=10)


def test_tls_failure_selects_next_verified_endpoint_and_records_pins(repo, fake_go, tmp_path, monkeypatch):
    for name, value in {'GOINSECURE': '*', 'GOPRIVATE': '*', 'GONOSUMDB': '*', 'GONOPROXY': '*',
                        'GOSUMDB': 'off', 'GOFLAGS': '-mod=mod', 'GOENV': '/nonexistent',
                        'GOAUTH': 'bad-command', 'GO111MODULE': 'off', 'GOWORK': '/nonexistent',
                        'GOMODCACHE': str(tmp_path / 'old-cache')}.items():
        monkeypatch.setenv(name, value)
    (tmp_path / 'old-cache').mkdir()
    (tmp_path / 'old-cache/preserve').write_text('not a valid verification cache')
    result = invoke(repo, tmp_path)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == 'https://goproxy.io'
    receipt = json.loads((tmp_path / 'receipt.json').read_text())
    assert receipt['sumdb'] == 'sum.golang.org https://goproxy.io/sumdb/sum.golang.org'
    assert receipt['failed_probes'][0]['proxy'] == 'https://goproxy.cn'
    assert 'hostname mismatch' in receipt['failed_probes'][0]['error']
    version, expected = PROXY.probe_target(repo)
    assert all(receipt[key] == digest for key, digest in expected.items())
    calls = [json.loads(line) for line in fake_go[1].read_text().splitlines()]
    assert len(calls) == 2
    assert calls[0]['env']['GOMODCACHE'] != calls[1]['env']['GOMODCACHE']
    for call in calls:
        assert call['argv'] == ['mod', 'download', '-json', PROXY.PROBE_MODULE + '@' + version]
        assert call['fresh_cache'] and call['no_go_sum'] and call['no_go_mod']
        environment = call['env']
        assert environment['GOSUMDB'] == 'sum.golang.org ' + environment['GOPROXY'] + '/sumdb/sum.golang.org'
        for name in ('GOINSECURE', 'GONOSUMDB', 'GOPRIVATE', 'GONOPROXY'):
            assert environment[name] == ''
        assert environment['GOENV'] == environment['GOAUTH'] == environment['GOWORK'] == 'off'
        assert environment['GO111MODULE'] == 'on'
        assert environment['GOFLAGS'] == '-modcacherw'
        assert environment['GOMAXPROCS'] == '2'
    assert not list(tmp_path.glob('ragflow-go-proxy-*'))
    assert (tmp_path / 'old-cache/preserve').read_text() == 'not a valid verification cache'


def test_all_endpoints_fail_without_receipt(repo, fake_go, tmp_path):
    responses = json.loads(fake_go[0].read_text())
    responses['https://goproxy.io'] = {'exit': 1, 'error': 'verifying module: invalid sumdb signature'}
    fake_go[0].write_text(json.dumps(responses))
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    assert 'No verified HTTPS Go proxy/sumdb endpoint' in result.stderr
    assert 'invalid sumdb signature' in result.stderr
    assert not (tmp_path / 'receipt.json').exists()
    assert not list(tmp_path.glob('ragflow-go-proxy-*'))


@pytest.mark.parametrize('key', ['Path', 'Version', 'Sum', 'GoModSum', 'Error'])
def test_success_exit_cannot_mask_wrong_identity_or_checksum(repo, fake_go, tmp_path, key):
    responses = json.loads(fake_go[0].read_text())
    responses['https://goproxy.io']['record'][key] = 'invalid'
    fake_go[0].write_text(json.dumps(responses))
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    assert 'disagrees with pinned go.sum' in result.stderr
    assert not (tmp_path / 'receipt.json').exists()
    assert len(fake_go[1].read_text().splitlines()) == 2


@pytest.mark.parametrize('value', ['http://proxy.test', 'direct', 'off', 'file:///modules',
                                  'https://user:password@proxy.test', 'https://proxy.test|direct',
                                  'https://proxy.test,https://other.test', 'https://proxy.test?x=1',
                                  'https://proxy.test#fragment', 'https://', 'https://proxy.test\n'])
def test_invalid_override_never_invokes_go(repo, fake_go, tmp_path, value, monkeypatch):
    monkeypatch.setenv('RAGFLOW_GOPROXY', value)
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    assert not fake_go[1].exists()
    assert not (tmp_path / 'receipt.json').exists()


def test_override_is_verified_not_silently_replaced(repo, fake_go, tmp_path, monkeypatch):
    monkeypatch.setenv('RAGFLOW_GOPROXY', 'https://proxy.golang.org')
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    calls = [json.loads(line) for line in fake_go[1].read_text().splitlines()]
    assert [call['env']['GOPROXY'] for call in calls] == ['https://proxy.golang.org']
    assert not (tmp_path / 'receipt.json').exists()


def test_no_checksum_cannot_bypass_authentication(repo, fake_go, tmp_path):
    (repo / 'go.sum').write_text('')
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    assert 'Both pinned module and go.mod checksums are required' in result.stderr
    assert not fake_go[1].exists()


def test_existing_receipt_cannot_be_reused(repo, fake_go, tmp_path):
    (tmp_path / 'receipt.json').write_text('stale receipt')
    result = invoke(repo, tmp_path)
    assert result.returncode != 0
    assert not fake_go[1].exists()
    assert (tmp_path / 'receipt.json').read_text() == 'stale receipt'


def test_timeout_is_bounded_and_fails_closed(repo, tmp_path):
    def timeout(command, **options):
        assert options['timeout'] == 180
        raise subprocess.TimeoutExpired(command, options['timeout'])

    with pytest.raises(RuntimeError, match='No verified HTTPS Go proxy/sumdb endpoint'):
        PROXY.select_proxy(repo, ['https://proxy.test'], tmp_path, runner=timeout)
    assert not list(tmp_path.glob('ragflow-go-proxy-*'))
