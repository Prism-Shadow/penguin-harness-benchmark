import hashlib
import importlib.util
import json
import shlex
import shutil
from pathlib import Path
import zipfile

import pytest

from test_build_context import included_in_context


ENVIRONMENT = Path(__file__).resolve().parents[2] / 'environment'
SPEC = importlib.util.spec_from_file_location('prepare_nltk', ENVIRONMENT / 'development/prepare-nltk.py')
PREPARE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PREPARE)


def stage_preparation_inputs(context, destination, recipe=None):
    destination.mkdir()
    rules_file = context / 'Dockerfile.nltk.dockerignore'
    if not rules_file.is_file():
        rules_file = context / '.dockerignore'
    rules = rules_file.read_text().splitlines()
    recipe = recipe if recipe is not None else (context / 'Dockerfile.nltk').read_text()
    for line in recipe.replace('\\\n', ' ').splitlines():
        if line.lstrip().startswith('#'):
            continue
        fields = shlex.split(line)
        if not fields:
            continue
        if fields[0] == 'RUN' and any(field.endswith('/prepare-nltk.py') for field in fields):
            return destination
        if fields[0] != 'COPY' or fields[-1].rstrip('/') != '/opt/ragflow-development-inputs':
            continue
        for source in fields[1:-1]:
            path = context / source
            files = path.rglob('*') if path.is_dir() else [path]
            for child in files:
                if child.is_file() and included_in_context(child.relative_to(context).as_posix(), rules):
                    relative = child.relative_to(path) if path.is_dir() else Path(child.name)
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(child, target)
    raise AssertionError('No NLTK preparation command in Dockerfile')


def test_python_layer_runs_real_nltk_archive_preparation(tmp_path):
    source = stage_preparation_inputs(ENVIRONMENT, tmp_path / 'inputs')
    destination = tmp_path / 'installed'
    PREPARE.prepare_data(source, destination)
    for record in json.loads((source / 'nltk-data-sources.json').read_text()):
        with zipfile.ZipFile(source / (record['name'] + '.zip')) as package:
            for member in package.infolist():
                if not member.is_dir():
                    assert (destination / record['category'] / member.filename).read_bytes() == package.read(member)


@pytest.mark.parametrize('missing', ['nltk-data-sources.json', 'punkt_tab.zip', 'wordnet.zip'])
def test_data_copied_only_after_prepare_is_not_available(tmp_path, missing):
    recipe = (ENVIRONMENT / 'Dockerfile.nltk').read_text().replace('development/' + missing + ' ', '')
    source = stage_preparation_inputs(ENVIRONMENT, tmp_path / 'inputs', recipe)
    with pytest.raises(FileNotFoundError, match=missing):
        PREPARE.prepare_data(source, tmp_path / 'installed')


def test_equivalent_directory_copy_can_prepare_data(tmp_path):
    context = tmp_path / 'context'
    inputs = context / 'inputs'
    inputs.mkdir(parents=True)
    write_fixture(inputs, 'sample/resource.txt')
    (context / '.dockerignore').write_text('*\n!inputs\n!inputs/**\n')
    recipe = ("# This recipe's comments may contain unpaired quotes: ' \"\n"
              'COPY inputs/ /opt/ragflow-development-inputs/\n'
              'RUN python3 /opt/ragflow-development-inputs/prepare-nltk.py\n')
    source = stage_preparation_inputs(context, tmp_path / 'staged', recipe)
    PREPARE.prepare_data(source, tmp_path / 'installed')
    assert (tmp_path / 'installed/corpora/sample/resource.txt').read_bytes() == b'resource contents'


def write_fixture(source, member):
    archive = source / 'sample.zip'
    with zipfile.ZipFile(archive, 'w') as package:
        package.writestr(member, b'resource contents')
    record = dict(name='sample', category='corpora', sha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    (source / 'nltk-data-sources.json').write_text(json.dumps([record]))
    return archive


def test_archive_corruption_is_rejected_before_extraction(tmp_path):
    archive = write_fixture(tmp_path, 'sample/resource.txt')
    archive.write_bytes(archive.read_bytes() + b'corrupted')
    destination = tmp_path / 'installed'
    with pytest.raises(AssertionError):
        PREPARE.prepare_data(tmp_path, destination)
    assert not destination.exists()


@pytest.mark.parametrize('member', ['sample/../../escape', '/sample/resource.txt', 'wrong/resource.txt'])
def test_pinned_archive_unsafe_paths_are_rejected(tmp_path, member):
    write_fixture(tmp_path, member)
    destination = tmp_path / 'installed'
    with pytest.raises(AssertionError):
        PREPARE.prepare_data(tmp_path, destination)
    assert not list(destination.rglob('*.txt'))
    assert not (tmp_path / 'escape').exists()
