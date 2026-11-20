from pathlib import Path
import pytest

from click.types import Path as ClickPath


@pytest.mark.parametrize('name', ['relative/file', '目录/空 格', ''])
def test_path_type_converts_to_pathlib_objects(name):
    parameter_type = ClickPath(path_type=Path)
    converted = parameter_type.convert(name, None, None)
    assert isinstance(converted, Path)
    assert converted == Path(name)


def test_dash_and_missing_file_policy(tmp_path):
    import click
    assert ClickPath(exists=True, allow_dash=True).convert('-', None, None) == '-'
    with pytest.raises(click.BadParameter):
        ClickPath(exists=True).convert(str(tmp_path / 'absent'), None, None)
    existing = tmp_path / 'present'
    existing.write_text('value')
    assert ClickPath(exists=True, path_type=Path).convert(str(existing), None, None) == existing
