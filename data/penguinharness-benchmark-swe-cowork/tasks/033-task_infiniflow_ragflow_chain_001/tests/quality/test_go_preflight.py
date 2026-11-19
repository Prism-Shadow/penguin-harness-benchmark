import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ENVIRONMENT = Path(__file__).resolve().parents[2] / 'environment'


@pytest.fixture
def preflight(tmp_path):
    inputs = tmp_path / 'inputs'
    inputs.mkdir()
    native = tmp_path / 'native'
    native.mkdir()
    temporary = tmp_path / 'temporary'
    temporary.mkdir()
    repo = tmp_path / 'repo'
    repo.mkdir()
    for name in ('go.mod', 'go.sum'):
        (repo / name).write_bytes((ENVIRONMENT / 'base' / name).read_bytes())
    (repo / 'build.sh').write_text('set -eu\nshift\nexec go test "$@"\n')
    (inputs / 'offline-go-modules.txt').write_bytes(
        (ENVIRONMENT / 'development/offline-go-modules.txt').read_bytes())
    (inputs / 'select-go-proxy.py').write_text("print('https://verified.invalid')\n")
    (inputs / 'prepare-native.py').write_text('')
    audit = tmp_path / 'audit.py'
    audit.write_text("import argparse\nfrom pathlib import Path\n"
                     "parser = argparse.ArgumentParser()\n"
                     "parser.add_argument('--go-repo', required=True)\n"
                     "parser.add_argument('--go-module-cache', required=True)\n"
                     "parser.add_argument('root')\n"
                     "args = parser.parse_args()\n"
                     "assert Path(args.go_repo, 'go.mod').is_file()\n"
                     "assert args.root == args.go_module_cache\n"
                     "Path(__file__).with_suffix('.passed').touch()\n")
    binary = tmp_path / 'bin'
    binary.mkdir()
    driver = '#!' + sys.executable + '\n' + '''import json
import os
from pathlib import Path
import sys

arguments = sys.argv[1:]
state = Path(os.environ['PREFLIGHT_STATE'])
failure = os.environ['PREFLIGHT_FAILURE']
keys = ('GOPROXY', 'GOSUMDB', 'GOFLAGS', 'GOINSECURE', 'GONOSUMDB', 'GOPRIVATE',
        'GONOPROXY', 'GOMAXPROCS', 'GOTOOLCHAIN')
record = {'tool': Path(sys.argv[0]).name, 'args': arguments,
          'env': {key: os.environ.get(key) for key in keys}}
with (state / 'trace.jsonl').open('a') as stream:
    stream.write(json.dumps(record) + '\\n')
if record['tool'] == 'cmake':
    raise SystemExit(0)
if arguments == ['env', 'GOVERSION']:
    print('go1.27.0')
elif arguments == ['list', '-mod=readonly', '-m', 'all']:
    assert os.environ['GOPROXY'] == 'https://verified.invalid'
    if failure == 'metadata_unavailable':
        print('graph metadata unavailable', file=sys.stderr)
        raise SystemExit(61)
    (state / 'graph').touch()
    print('ragflow\\nexample.invalid/unimported v1.0.0')
    if failure == 'changed_sum':
        with Path('go.sum').open('a') as stream:
            stream.write('unexpected change\\n')
elif arguments[:4] == ['list', '-mod=readonly', '-deps', '-test']:
    (state / 'packages').touch()
    if './internal/service' in arguments:
        if failure == 'service_unavailable':
            print('service dependency unavailable', file=sys.stderr)
            raise SystemExit(64)
        (state / 'service').touch()
    print('ragflow/internal/agent/harness')
elif arguments[:3] == ['mod', 'download', '-json']:
    assert len(arguments) == 4 and '@' in arguments[3]
    print(json.dumps({'Path': arguments[3].split('@')[0]}))
elif arguments[:2] == ['mod', 'edit']:
    assert arguments[2].startswith('-require=')
elif arguments == ['list', '-mod=mod', '-m', 'all']:
    assert Path('go.mod').read_text().startswith('module ragflow-offline-options')
    if failure == 'optional_graph_unavailable':
        print('optional graph metadata unavailable', file=sys.stderr)
        raise SystemExit(65)
    (state / 'optional-graph').touch()
    print('ragflow-offline-options\\nexample.invalid/transitive v0.9.0')
elif arguments[0] == 'test':
    assert os.environ['GOPROXY'] == 'off'
    assert (state / 'packages').exists()
    print('ok ragflow/internal/agent/harness [no tests to run]')
elif arguments == ['mod', 'verify']:
    assert os.environ['GOPROXY'] == 'off'
    if not (state / 'graph').exists():
        print('module lookup disabled by GOPROXY=off', file=sys.stderr)
        raise SystemExit(62)
    if failure == 'tampered_cache':
        print('cached module dir has been modified', file=sys.stderr)
        raise SystemExit(63)
    if failure == 'changed_sum_after_verify':
        with Path('go.sum').open('a') as stream:
            stream.write('unexpected verification change\\n')
    print('all modules verified')
else:
    raise AssertionError(arguments)
'''
    for name in ('go', 'cmake'):
        executable = binary / name
        executable.write_text(driver)
        executable.chmod(0o755)

    def invoke(failure='', warm=False, remove_graph_priming=False):
        if warm:
            (tmp_path / 'graph').touch()
        script = (ENVIRONMENT / 'development/prepare-go.sh').read_text()
        if remove_graph_priming:
            script = '\n'.join(line for line in script.splitlines()
                               if not line.startswith('go list -mod=readonly -m all')) + '\n'
        replacements = {
            '/opt/ragflow-development-inputs': str(inputs),
            '/opt/ragflow-native-libs': str(native),
            '/opt/ragflow-go-modules': str(tmp_path / 'modules'),
            '/task/audit_runtime.py': str(audit),
            '/tmp/ragflow-': str(temporary / 'ragflow-'),
        }
        for original, replacement in replacements.items():
            script = script.replace(original, replacement)
        executable = tmp_path / 'prepare-go.sh'
        executable.write_text(script)
        environment = dict(os.environ, PATH=str(binary) + os.pathsep + os.environ['PATH'],
                           PREFLIGHT_STATE=str(tmp_path), PREFLIGHT_FAILURE=failure,
                           RAGFLOW_NATIVE_OFFLINE='0', GOSUMDB='off', GOINSECURE='*',
                           GONOSUMDB='*', GOPRIVATE='*', GONOPROXY='*')
        result = subprocess.run(['bash', str(executable), str(repo)], cwd=tmp_path,
                                env=environment, capture_output=True, text=True, timeout=15)
        calls = [json.loads(line) for line in (tmp_path / 'trace.jsonl').read_text().splitlines()]
        return result, calls, native, audit.with_suffix('.passed')

    return invoke


@pytest.mark.parametrize('warm', [False, True])
def test_complete_graph_precedes_offline_verification(preflight, warm):
    result, calls, native, audit = preflight(warm=warm)
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [call['args'] for call in calls]
    graph = commands.index(['list', '-mod=readonly', '-m', 'all'])
    verify = commands.index(['mod', 'verify'])
    compile_index = next(index for index, command in enumerate(commands) if command[0] == 'test')
    assert graph < compile_index < verify
    assert 'example.invalid/unimported v1.0.0' in (native / 'go-module-graph.txt').read_text()
    assert audit.exists()
    assert 'all modules verified' in result.stdout
    assert result.stdout.count('go.sum: OK') == 2
    for call in calls[graph:]:
        assert call['env']['GOSUMDB'] == 'sum.golang.org https://verified.invalid/sumdb/sum.golang.org'
        assert call['env']['GOMAXPROCS'] == '2'
        assert call['env']['GOTOOLCHAIN'] == 'local'
        for key in ('GOINSECURE', 'GONOSUMDB', 'GOPRIVATE', 'GONOPROXY'):
            assert call['env'][key] == ''
    optional = (ENVIRONMENT / 'development/offline-go-modules.txt').read_text().splitlines()
    downloaded = [command[3] for command in commands if command[:2] == ['mod', 'download']]
    assert downloaded == optional


@pytest.mark.parametrize('failure, expected, verification_reached', [
    ('metadata_unavailable', 'graph metadata unavailable', False),
    ('service_unavailable', 'service dependency unavailable', False),
    ('optional_graph_unavailable', 'optional graph metadata unavailable', False),
    ('changed_sum', 'go.sum: FAILED', False),
    ('tampered_cache', 'cached module dir has been modified', True),
    ('changed_sum_after_verify', 'go.sum: FAILED', True),
])
def test_setup_fails_closed_without_rewriting_pins_or_skipping_integrity(
        preflight, failure, expected, verification_reached):
    result, calls, native, audit = preflight(failure=failure)
    assert result.returncode != 0
    assert expected in result.stdout + result.stderr
    assert (any(call['args'] == ['mod', 'verify'] for call in calls)) == verification_reached
    assert not audit.exists()


def test_missing_graph_priming_reproduces_offline_failure_after_compile(preflight):
    result, calls, native, audit = preflight(remove_graph_priming=True)
    assert result.returncode != 0
    assert 'ok ragflow/internal/agent/harness [no tests to run]' in result.stdout
    assert 'module lookup disabled by GOPROXY=off' in result.stderr
    assert not audit.exists()


def test_public_service_dependencies_are_available_for_cross_module_changes(preflight):
    result, calls, native, audit = preflight()
    assert result.returncode == 0, result.stdout + result.stderr
    assert (native.parent / 'service').exists(), 'offline service dependency closure was not prepared'


def test_optional_transitive_metadata_is_prepared_before_offline(preflight):
    result, calls, native, audit = preflight()
    assert result.returncode == 0, result.stdout + result.stderr
    commands = [call['args'] for call in calls]
    assert commands.index(['list', '-mod=mod', '-m', 'all']) < commands.index(['mod', 'verify'])
    assert 'example.invalid/transitive v0.9.0' in (native / 'optional-module-graph.txt').read_text()
    optional = (ENVIRONMENT / 'development/offline-go-modules.txt').read_text().splitlines()
    assert [command[2].removeprefix('-require=') for command in commands
            if command[:2] == ['mod', 'edit']] == optional
