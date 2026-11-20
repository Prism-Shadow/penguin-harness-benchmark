import click
from click.testing import CliRunner
import inspect
import pytest


@pytest.mark.parametrize('value,expected', [('\ud800', '\\ud800'), ('\udfff', '\\udfff'), ('é中文', 'é中文'), ('', '')])
def test_stderr_capture_backslash_replaces_invalid_surrogates(value, expected):
    @click.command()
    def cli():
        click.echo(value, err=True)

    runner_kwargs = {}
    if "mix_stderr" in inspect.signature(CliRunner).parameters:
        runner_kwargs["mix_stderr"] = False
    result = CliRunner(**runner_kwargs).invoke(cli)
    assert result.exit_code == 0
    assert result.stderr == expected + '\n'
