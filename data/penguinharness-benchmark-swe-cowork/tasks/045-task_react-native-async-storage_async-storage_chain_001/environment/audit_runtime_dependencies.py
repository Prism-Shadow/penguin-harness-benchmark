import json
import os
import sys
from pathlib import Path


def audit(root):
    target_name = '@react-native-async-storage/async-storage'
    target = (root / 'packages/async-storage').resolve()
    violations = []
    lock = (root / 'yarn.lock').read_text()
    resolutions = [line.strip() for line in lock.splitlines()
                   if 'resolution:' in line and target_name + '@' in line]
    if not resolutions or any('@workspace:packages/async-storage' not in line for line in resolutions):
        violations.append({'kind': 'non-workspace-target-resolution', 'resolutions': resolutions})
    found = []
    for directory, children, filenames in os.walk(root / 'node_modules', followlinks=False):
        current = Path(directory)
        for child in children:
            path = current / child
            if path.is_symlink() and path.name == 'async-storage' and path.parent.name == '@react-native-async-storage':
                found.append(str(path))
                if path.resolve() != target:
                    violations.append({'kind': 'target-link-outside-workspace', 'path': str(path)})
        if 'package.json' not in filenames:
            continue
        manifest = current / 'package.json'
        try:
            name = json.loads(manifest.read_text()).get('name')
        except (ValueError, OSError):
            continue
        if name == target_name:
            found.append(str(manifest))
            if current.resolve() != target:
                violations.append({'kind': 'vendored-target-package', 'path': str(manifest)})
    result = {'target': target_name, 'workspace': str(target), 'node_modules_present': (root / 'node_modules').is_dir(),
              'found': found, 'violations': violations}
    print(json.dumps(result, sort_keys=True))
    return 1 if violations else 0


if __name__ == '__main__':
    raise SystemExit(audit(Path(sys.argv[1]).resolve()))
