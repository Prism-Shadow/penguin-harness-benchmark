import click
from click.testing import CliRunner


def test_confirmation_prompt_accepts_a_custom_message():
    @click.command()
    @click.option("--value", prompt=True, confirmation_prompt="Confirm value")
    def cli(value):
        click.echo(value)

    result = CliRunner().invoke(cli, input="first\nfirst\n")
    assert result.exit_code == 0
    assert "Confirm value: first" in result.output
    assert "Repeat for confirmation" not in result.output
