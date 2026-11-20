"""Exercise the shipped adapter, including repeated use of one log directory."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

TESTS = Path(__file__).parents[1]


def test_repeated_adapter_and_failed_source(tmp_path):
    bundle = tmp_path / 'bundle'
    bundle.mkdir()
    for name in ('test.sh', 'normalize_reward.py'):
        shutil.copy2(TESTS / name, bundle / name)
    source = bundle / 'source-test.sh'
    source.write_text('''#!/bin/bash
python3 - <<'INNER'
import json,os
from pathlib import Path
p=Path(os.environ['VERIFIER_LOG_DIR'])/'rewards.json'
mode=os.environ['CASE']
if mode != 'missing':
 p.write_text('bad json' if mode == 'malformed' else json.dumps({
   'reward': 0 if mode == 'fail' else 1,
   'run_id': 'previous' if mode == 'stale' else os.environ['VERIFIER_RUN_ID']}))
INNER
[ "$CASE" != "crash" ]
''')
    logs = tmp_path / 'logs'
    env = {**os.environ, 'VERIFIER_LOG_DIR': str(logs)}
    ids = set()
    for case, code, reward in [('pass',0,1), ('fail',0,0), ('pass',0,1),
                               ('missing',2,0), ('malformed',2,0), ('stale',2,0), ('crash',2,0)]:
        logs.mkdir(exist_ok=True)
        (logs / 'reward.json').write_text('{"reward":1}')
        (logs / 'rewards.json').write_text('{"reward":1,"run_id":"previous"}')
        (logs / 'reward.txt').write_text('1')
        result = subprocess.run(['bash', str(bundle / 'test.sh')], env={**env, 'CASE':case},
                                text=True, capture_output=True)
        assert result.returncode == code, (case, result.stderr)
        assert json.loads((logs / 'reward.json').read_text())['reward'] == reward, case
        ident = (logs / 'adapter-status.txt').read_text().splitlines()[0]
        assert ident not in ids
        ids.add(ident)
        assert not (logs / 'reward.txt').exists()


@pytest.mark.parametrize('value', ['NaN', 'true', '1.5', '"1"'])
def test_invalid_reward_fails_closed(tmp_path, value):
    (tmp_path / 'rewards.json').write_text('{"reward":' + value + ',"run_id":"current"}')
    result = subprocess.run(['python3', str(TESTS / 'normalize_reward.py'), '--exit-code', '0'],
             env={**os.environ, 'VERIFIER_LOG_DIR':str(tmp_path), 'VERIFIER_RUN_ID':'current'})
    assert result.returncode == 2
    assert json.loads((tmp_path / 'reward.json').read_text())['reward'] == 0
