"""Validate the exact, explicit build-source to public-package projection."""
import copy
import hashlib
import json
from pathlib import Path
import re
try:
    import tomllib
except ImportError:
    import tomli as tomllib
import yaml


SOURCE_TASK = 'runtime-lineage/build-task.toml'
SOURCE_COMPOSE = 'runtime-lineage/build-compose.yaml'
RECEIPT = 'runtime-lineage/publication.json'
SOURCE_ALIASES = {'task.toml': SOURCE_TASK, 'environment/docker-compose.yaml': SOURCE_COMPOSE}


def read_regular(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('Missing regular publication input: ' + str(path))
    return path.read_bytes()


def source_sha256(root, relative):
    return hashlib.sha256(read_regular(Path(root) / SOURCE_ALIASES.get(relative, relative))).hexdigest()


def validate(root):
    root = Path(root)
    source_task = tomllib.loads(read_regular(root / SOURCE_TASK).decode())
    task = tomllib.loads(read_regular(root / 'task.toml').decode())
    source_compose = yaml.safe_load(read_regular(root / SOURCE_COMPOSE))
    compose = yaml.safe_load(read_regular(root / 'environment/docker-compose.yaml'))
    if task == source_task and compose == source_compose:
        return {'status': 'build-source', 'task': source_task, 'compose': source_compose}
    receipt = json.loads(read_regular(root / RECEIPT))
    if set(receipt) != {'schema', 'task_version', 'source_sha256', 'images'}:
        raise ValueError('Unexpected publication receipt fields')
    if receipt['schema'] != 'xcodeproj-build-publication-v1':
        raise ValueError('Unsupported publication mapping schema')
    if receipt['task_version'] != source_task['metadata']['task_version']:
        raise ValueError('Publication mapping task version differs')
    expected_sources = {name: source_sha256(root, name) for name in SOURCE_ALIASES.values()}
    if receipt['source_sha256'] != expected_sources:
        raise ValueError('Publication build-source digest mismatch')
    images = receipt['images']
    if set(images) != {'environment', 'workplace'}:
        raise ValueError('Publication requires exactly two service images')
    for role, suffix in [('environment', 'env'), ('workplace', 'workplace')]:
        pattern = r'harbor\.tokenwave\.us/release/cowork-bench/087-' + suffix + r'@sha256:[0-9a-f]{64}'
        if not isinstance(images[role], str) or not re.fullmatch(pattern, images[role]):
            raise ValueError('Publication image is not an exact public role digest: ' + role)
    expected_task = copy.deepcopy(source_task)
    expected_task['environment']['docker_image'] = images['environment']
    metadata = expected_task['metadata']
    for name in ('repair_status', 'gpt_repair_status'):
        if name in metadata:
            metadata[name] = 'program-validated-published'
    if 'requires_environment_rebuild' in metadata:
        metadata['requires_environment_rebuild'] = False
    if 'source_package' in metadata:
        metadata['source_package'] = 'provenance:original-authoring-package'
    if task != expected_task:
        raise ValueError('Published task.toml changes fields outside the release projection')
    expected_compose = copy.deepcopy(source_compose)
    for name, role in [('main', 'environment'), ('workplace', 'workplace')]:
        service = expected_compose['services'][name]
        service.pop('build', None)
        service.update(image=images[role], pull_policy='missing', platform='linux/amd64')
    if compose != expected_compose:
        raise ValueError('Published compose changes fields outside the release projection')
    return {'status': 'published', 'task': source_task, 'compose': source_compose, 'images': images}
