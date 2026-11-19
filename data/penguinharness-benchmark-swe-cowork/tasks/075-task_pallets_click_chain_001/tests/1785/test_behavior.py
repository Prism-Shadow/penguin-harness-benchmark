import click
from click.testing import CliRunner

def test_prompt_callback_validates_and_reprompts():
    runner = CliRunner()
    def positive(ctx, param, value):
        if value <= 0:
            raise click.BadParameter("should be positive")
        return value
    @click.command()
    @click.option("--age", prompt=True, type=int, callback=positive)
    def cli(age):
        click.echo(f"age={age}")
    result = runner.invoke(cli, input="-12\n60\n")
    assert result.exit_code == 0
    assert "Error: should be positive" in result.output
    assert result.output.rstrip().endswith("age=60")
