import click
from click.core import ParameterSource
from click.testing import CliRunner

def test_prompt_source_is_recorded():
    @click.command()
    @click.option("--value", prompt=True)
    @click.pass_context
    def cli(ctx, value):
        click.echo(ctx.get_parameter_source("value").name)

    result = CliRunner().invoke(cli, input="answer\n")
    assert result.exit_code == 0
    assert result.output.rstrip().endswith(ParameterSource.PROMPT.name)
