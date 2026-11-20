"""Install a hash-bound third-party offline closure into the published runtime."""
import hashlib
import json
from pathlib import Path
import shutil
import sys

ALLOWED = ('bazel-registry/', 'gradle/caches/modules-2/', 'home/.m2/repository/')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def runtime_immutable(relative):
    # Gradle rewrites metadata during ordinary offline builds. Validate its
    # transport bytes during installation, and retain only immutable payloads
    # in the repeatedly checked runtime inventory, as the original preparer does.
    return (not relative.startswith('gradle/caches/modules-2/') or
            Path(relative).suffix in {'.jar', '.pom', '.module'})


def main(source, root):
    receipt = json.loads((source / 'closure-manifest.json').read_text())
    if receipt.get('schema') != 'junit-offline-closure-assets-v1' or not receipt.get('files'):
        raise ValueError('invalid offline closure manifest')
    entries = receipt['files']
    paths = [entry['path'] for entry in entries]
    if len(paths) != len(set(paths)):
        raise ValueError('duplicate closure path')
    for entry in entries:
        relative = Path(entry['path'])
        if (relative.is_absolute() or '..' in relative.parts or
                not entry['path'].startswith(ALLOWED) or relative.suffix == '.lock'):
            raise ValueError('unsafe offline closure path')
        original = source / relative
        if original.is_symlink() or not original.is_file() or digest(original) != entry['sha256']:
            raise ValueError('offline closure checksum mismatch: ' + str(relative))
        if any(path.is_symlink() for path in original.parents if path != source.parent):
            raise ValueError('symlink in offline closure source')
        destination = root / relative
        if destination.is_symlink() or any(path.is_symlink() for path in destination.parents if path != root.parent):
            raise ValueError('symlink in offline closure destination')
    # Validate the entire source before changing any installed dependency.
    for entry in entries:
        destination = root / entry['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / entry['path'], destination)
    runtime = root / 'runtime'
    runtime.mkdir(exist_ok=True)
    (runtime / 'coursier-mirror.properties').write_text(
        'central.from=https://repo1.maven.org/maven2;https://repo.maven.apache.org/maven2\n'
        'central.to=file:///opt/junit-offline/home/.m2/repository\n'
        'central.type=maven\n')
    shutil.copyfile(source / 'closure-manifest.json', runtime / 'closure-manifest.json')
    manifest = json.loads((root / 'manifest.json').read_text())
    files = {entry['path']: entry for entry in manifest['files'] if runtime_immutable(entry['path'])}
    for entry in entries:
        if runtime_immutable(entry['path']):
            files[entry['path']] = {'path': entry['path'], 'sha256': entry['sha256']}
    for path in sorted(runtime.iterdir()):
        if path.is_file() and not path.is_symlink():
            relative = path.relative_to(root).as_posix()
            files[relative] = {'path': relative, 'sha256': digest(path)}
    manifest['files'] = [files[name] for name in sorted(files)]
    manifest['supplement'] = {'schema': receipt['schema'], 'manifest_sha256': digest(source / 'closure-manifest.json')}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print('Installed', len(entries), 'verified third-party closure files', flush=True)


if __name__ == '__main__':
    main(Path(sys.argv[1]), Path(sys.argv[2]))
