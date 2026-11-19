import io
import time
import click


class Terminal(io.StringIO):
    def isatty(self):
        return True


def test_progress_bar_renders_immediately_even_at_start(monkeypatch):
    monkeypatch.setattr(time, 'time', lambda: 1000.0)
    stream = Terminal()
    with click.progressbar(length=2, label='download', file=stream,
                           bar_template='%(label)s'):
        assert 'download' in stream.getvalue()
