import click
from click.testing import CliRunner

def test_confirm_without_default_repeats_after_empty_input():
    runner = CliRunner()
    @click.command()
    def cli():
        click.echo(click.confirm("Proceed?", default=None))
    result = runner.invoke(cli, input="\ny\n")
    assert result.exit_code == 0
    assert result.output.count("Proceed?") >= 2
    assert result.output.rstrip().endswith("True")
