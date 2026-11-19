import click
from click.testing import CliRunner

def test_prompt_required_false_prompts_for_bare_flag():
    runner = CliRunner()
    @click.command()
    @click.option("--value", prompt=True, prompt_required=False)
    def cli(value):
        click.echo(value)
    result = runner.invoke(cli, ["--value"], input="from-prompt\n")
    assert result.exit_code == 0
    assert result.output.endswith("from-prompt\n")
