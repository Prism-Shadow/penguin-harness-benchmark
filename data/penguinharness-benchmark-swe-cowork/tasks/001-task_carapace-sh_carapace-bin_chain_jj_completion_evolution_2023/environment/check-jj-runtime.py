#!/usr/bin/env python3
"""Exercise the external CLI on a temporary local repository, with no network."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--jj', default=shutil.which('jj') or '/missing-jj')
parser.add_argument('--lock', default='/opt/task-dependencies/jj/jj-lock.json')
args = parser.parse_args()
binary = Path(args.jj).resolve()
lock = json.loads(Path(args.lock).read_text())
assert hashlib.sha256(binary.read_bytes()).hexdigest() == lock['binary_sha256']
with tempfile.TemporaryDirectory(prefix='jj-dependency-probe-') as temporary:
    root = Path(temporary)
    config = root / 'jj.toml'
    config.write_text('[user]\nname = "Local dependency probe"\nemail = "probe@example.invalid"\n')
    env = dict(os.environ, JJ_CONFIG=str(config), NO_COLOR='1', XDG_CONFIG_HOME=str(root / 'config'))
    def run(*args):
        return subprocess.check_output([str(binary), *args], cwd=root, env=env,
                                       stderr=subprocess.STDOUT, text=True, timeout=20)
    run('init', '--git', str(root / 'repo'))
    (root / 'repo/file.txt').write_text('local probe\n')
    run('-R', str(root / 'repo'), 'describe', '-m', 'parent probe')
    parent = run('-R', str(root / 'repo'), 'log', '--no-graph', '-r', '@', '-T', 'commit_id').strip()
    run('-R', str(root / 'repo'), 'new', '-m', 'child probe')
    current = run('-R', str(root / 'repo'), 'log', '--no-graph', '-r', '@', '-T', 'commit_id').strip()
    assert run('-R', str(root / 'repo'), 'log', '--no-graph', '-r', 'parents(@)', '-T', 'commit_id').strip() == parent
    assert run('-R', str(root / 'repo'), 'log', '--no-graph', '-r', 'children(@-)', '-T', 'commit_id').strip() == current
    run('-R', str(root / 'repo'), 'branch', 'create', 'probe-branch', '-r', '@-')
    assert 'probe-branch' in run('-R', str(root / 'repo'), 'branch', 'list')
    run('-R', str(root / 'repo'), 'git', 'remote', 'add', 'probe-remote', 'https://example.invalid/probe')
    assert 'probe-remote' in run('-R', str(root / 'repo'), 'git', 'remote', 'list')
    assert 'default:' in run('-R', str(root / 'repo'), 'workspace', 'list')
    assert run('-R', str(root / 'repo'), 'op', 'log', '--no-graph', '--limit', '1').strip()
print('JJ_RUNTIME_OK version=' + lock['version'])
