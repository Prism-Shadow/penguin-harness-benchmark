"""Fail closed if the installed PHP/Node dependencies differ from source locks."""
import json
import platform
from pathlib import Path

root = Path('/app/code')
lock = json.loads((root / 'composer.lock').read_text())
installed = json.loads((root / 'vendor/composer/installed.json').read_text())
installed = installed['packages'] if isinstance(installed, dict) else installed
expected = {p['name']: p for p in lock['packages'] + lock['packages-dev']}
actual = {p['name']: p for p in installed}
assert expected.keys() == actual.keys(), 'Composer package set differs from lock'
for name, package in expected.items():
    found = actual[name]
    assert package['version'] == found['version'], (name, package['version'], found['version'])
    assert package.get('source', {}).get('reference') == found.get('source', {}).get('reference'), name
print(f'Composer: {len(actual)} installed packages match locked versions and source references')
node = json.loads((root / 'package-lock.json').read_text())
cpu = {'x86_64': 'x64', 'aarch64': 'arm64'}.get(platform.machine(), platform.machine())
node_count = 0
omitted = []
for name, package in node['packages'].items():
    if not name or package.get('link'):
        continue
    path = root / name / 'package.json'
    if not path.is_file():
        unsupported = ('os' in package and 'linux' not in package['os']) or ('cpu' in package and cpu not in package['cpu'])
        assert package.get('optional') and unsupported, ('required Node dependency absent', name)
        omitted.append(name)
        continue
    found = json.loads(path.read_text())
    assert package['version'] == found['version'], (name, package['version'], found['version'])
    node_count += 1
print(f'Node: {node_count} installed packages match lock; {len(omitted)} optional foreign-platform packages omitted')
