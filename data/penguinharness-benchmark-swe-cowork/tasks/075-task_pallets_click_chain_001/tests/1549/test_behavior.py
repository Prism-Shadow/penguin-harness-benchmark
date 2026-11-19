import click
from click.testing import CliRunner

def test_default_map_value_is_used_in_help():
    runner = CliRunner()
    @click.command()
    @click.option("--arg", default="a", show_default=True)
    def cli(arg):
        click.echo(arg)
    result = runner.invoke(cli, ["--help"], default_map={"arg":"b"})
    assert result.exit_code == 0
    assert "[default: b]" in result.output
