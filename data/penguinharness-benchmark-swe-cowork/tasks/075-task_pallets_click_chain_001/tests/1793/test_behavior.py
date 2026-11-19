import io
import sys
import pytest
import click
import click._compat as compat


class KernelOutput(io.StringIO):
    pass


class KernelBuffer(io.BytesIO):
    pass


KernelOutput.__module__ = KernelBuffer.__module__ = 'ipykernel.iostream'


@pytest.mark.parametrize('wrapped', [False, True])
@pytest.mark.parametrize('color', [None, False, True])
def test_jupyter_ansi_policy_through_public_stream_and_echo(monkeypatch, wrapped, color):
    # Exercise the Windows policy on this host; the native-console FFI and
    # Colorama path have a separate integration test. No private wrapper class
    # or detection helper is required here: get_text_stream creates its own.
    monkeypatch.setattr(compat, 'WIN', True)
    stream = KernelBuffer() if wrapped else KernelOutput()
    with monkeypatch.context() as scoped:
        scoped.setattr(sys, 'stdout', stream)
        text = click.get_text_stream('stdout', encoding='utf-8')
        click.echo('\x1b[31mred Ω\x1b[0m', file=text, color=color)
    expected = 'red Ω\n' if color is False else '\x1b[31mred Ω\x1b[0m\n'
    assert stream.getvalue() == (expected.encode() if wrapped else expected)


def test_ordinary_redirected_stream_still_strips_ansi():
    stream = io.StringIO()
    click.echo('\x1b[31mred\x1b[0m', file=stream)
    assert stream.getvalue() == 'red\n'
