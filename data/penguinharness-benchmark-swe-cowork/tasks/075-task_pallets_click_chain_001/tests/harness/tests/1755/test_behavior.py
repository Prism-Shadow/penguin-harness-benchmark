import click
import pytest
from click.testing import CliRunner


@pytest.mark.parametrize('text', ['computed later', 'different value', '稍后'])
def test_string_show_default_is_rendered_without_a_computed_default(text):
    @click.command()
    @click.option("--value", default=None, show_default=text)
    def cli(value):
        click.echo(value or "none")

    result = CliRunner().invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert f"[default: ({text})]" in result.output
