import os
from pathlib import Path
import pytest
from click.testing import CliRunner


def test_isolated_filesystem_can_keep_temp_directory(tmp_path):
    runner = CliRunner()
    original = Path.cwd()
    children = []
    try:
        for content in ['first Ω', 'second 中文']:
            with runner.isolated_filesystem(temp_dir=tmp_path) as directory:
                path = Path(directory)
                children.append(path)
                assert path.parent == tmp_path and path != tmp_path
                assert Path.cwd() == path
                Path('output.txt').write_text(content)
            assert Path.cwd() == original
            assert (path/'output.txt').read_text() == content
        assert children[0] != children[1]
    finally:
        os.chdir(original)


def test_isolated_filesystem_restores_cwd_and_keeps_files_after_exception(tmp_path):
    original = Path.cwd()
    failure = ValueError('inside isolated filesystem')
    try:
        with pytest.raises(ValueError) as caught:
            with CliRunner().isolated_filesystem(temp_dir=tmp_path) as directory:
                path = Path(directory)
                Path('partial.txt').write_text('prefix')
                raise failure
        assert caught.value is failure
        assert Path.cwd() == original
        assert (path/'partial.txt').read_text() == 'prefix'
    finally:
        os.chdir(original)
