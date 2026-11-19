import io
import click
from click.testing import CliRunner


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_progress_item_show_func_sees_current_item():
    observed = []
    yielded = []
    stream = Terminal()
    def show(item):
        observed.append(item)
        return '<rendered:{}>'.format(item)
    @click.command()
    def cli():
        with click.progressbar(range(3), file=stream, item_show_func=show) as progress:
            for item in progress:
                # The callback has already observed the item at this yield,
                # and its result reaches the terminal, regardless of layout.
                assert observed[-1] == item
                assert '<rendered:{}>'.format(item) in stream.getvalue()
                yielded.append(item)
    result = CliRunner().invoke(cli)
    assert result.exit_code == 0, result.exception
    assert yielded == [0, 1, 2]
