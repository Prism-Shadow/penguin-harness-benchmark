import os
import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner


@pytest.mark.parametrize('arguments,expected', [([], (2, ('x',))), (['--count', '3', 'a', 'b'], (3, ('a', 'b')))])
def test_plain_options_variadic_arguments_and_callbacks(arguments, expected):
    seen = []
    @click.command()
    @click.option('--count', type=int, default=2)
    @click.argument('names', nargs=-1)
    def cli(count, names):
        seen.append((count, names or ('x',)))
    result = CliRunner().invoke(cli, arguments)
    assert result.exit_code == 0, result.exception
    assert seen == [expected]


def test_invalid_option_does_not_run_callback():
    seen = []
    @click.command()
    @click.option('--count', type=int)
    def cli(count):
        seen.append(count)
    result = CliRunner().invoke(cli, ['--count', 'invalid'])
    assert result.exit_code == 2
    assert 'Invalid value' in result.output
    assert seen == []


def test_file_parameter_writes_and_closes(tmp_path):
    opened = []
    @click.command()
    @click.argument('target', type=click.File('w', encoding='utf-8'))
    def cli(target):
        opened.append(target)
        target.write('héllo 中')
    destination = tmp_path / 'out.txt'
    result = CliRunner().invoke(cli, [str(destination)])
    assert result.exit_code == 0, result.exception
    assert destination.read_text() == 'héllo 中'
    assert opened[0].closed


def test_context_and_isolation_restore_after_failure():
    original = (sys.stdin, sys.stdout, sys.stderr, os.getcwd())
    failure = ValueError('expected')
    closed = []
    @click.command()
    @click.pass_context
    def cli(ctx):
        ctx.call_on_close(lambda: closed.append(True))
        raise failure
    result = CliRunner().invoke(cli)
    assert result.exception is failure
    assert result.exit_code != 0
    assert closed == [True]
    assert click.get_current_context(silent=True) is None
    assert (sys.stdin, sys.stdout, sys.stderr, os.getcwd()) == original


def test_legacy_command_and_parser_exports_remain_usable_without_warning():
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('error', DeprecationWarning)
        from click import BaseCommand, MultiCommand, OptionParser
        from click.core import BaseCommand as CoreBase
        from click.core import MultiCommand as CoreMulti
        from click.parser import OptionParser as Parser
        assert isinstance(click.Command('sub'), BaseCommand)
        assert isinstance(click.Group('cli'), MultiCommand)
        assert BaseCommand is CoreBase and MultiCommand is CoreMulti
        parser = OptionParser()
        parser.add_option(['--value'], 'value')
        values, rest, _ = parser.parse_args(['--value', 'data', 'tail'])
        assert values == {'value': 'data'} and rest == ['tail']
        assert isinstance(parser, Parser)


@pytest.mark.parametrize('chain', [False, True])
def test_legacy_resultcallback_processes_group_result(chain):
    seen = []
    @click.group(invoke_without_command=True, chain=chain)
    def cli():
        pass
    @cli.resultcallback()
    def process(value):
        seen.append(value)
        click.echo('processed')
        return value
    result = CliRunner().invoke(cli)
    assert result.exit_code == 0, result.exception
    assert seen == [([] if chain else None)]
    assert result.output == 'processed\n'


@pytest.mark.parametrize('parameter', [click.Argument(['value']), click.Option(['--value'])])
def test_full_process_value_compatibility_converts_and_uses_defaults(parameter):
    parameter.type = click.INT
    parameter.default = 7
    ctx = click.Context(click.Command('cli'))
    assert parameter.full_process_value(ctx, '3') == 3
    assert parameter.full_process_value(ctx, None) == 7
    with pytest.raises(click.BadParameter):
        parameter.full_process_value(ctx, 'wrong')


def test_parameter_source_validate_accepts_members_and_rejects_other_values():
    from click.core import ParameterSource
    ParameterSource.validate(ParameterSource.DEFAULT)
    with pytest.raises(ValueError):
        ParameterSource.validate(object())


@pytest.mark.parametrize('envvalue,exit_code,expected', [('', 2, []), ('one', 2, []), ('one two', 0, [('one','two')])])
def test_fixed_arity_environment_is_validated_before_callback(envvalue, exit_code, expected):
    seen = []
    @click.command()
    @click.option('--pair', nargs=2, type=str, envvar='CLICK_PAIR')
    def cli(pair):
        seen.append(pair)
    result = CliRunner().invoke(cli, env={'CLICK_PAIR': envvalue})
    assert result.exit_code == exit_code, result.exception
    assert seen == expected
    if exit_code:
        assert '2 values' in result.output


def test_command_alias_help_uses_canonical_name():
    class PrefixGroup(click.Group):
        def get_command(self, ctx, name):
            return super().get_command(ctx, 'push' if name == 'pu' else name)
    @click.group(cls=PrefixGroup)
    def cli():
        pass
    @cli.command()
    def push():
        click.echo('sent')
    runner = CliRunner()
    assert runner.invoke(cli, ['pu']).output == 'sent\n'
    assert runner.invoke(cli, ['pu','--help']).output.startswith('Usage: cli push [OPTIONS]')


def test_false_boolean_default_remains_visible():
    @click.command()
    @click.option('--cache', is_flag=True, default=False, show_default=True)
    def cli(cache):
        pass
    result = CliRunner().invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert '[default: False]' in result.output


@pytest.mark.parametrize('abort', [False, True])
def test_nested_isolation_restores_ansi_policies(monkeypatch, abort):
    from click import _compat, utils
    compat_policy = lambda *a, **k: True
    utils_policy = lambda *a, **k: False
    monkeypatch.setattr(_compat, 'should_strip_ansi', compat_policy)
    monkeypatch.setattr(utils, 'should_strip_ansi', utils_policy)
    failure = RuntimeError('isolation body failed')
    runner = CliRunner()
    try:
        with runner.isolation(color=True):
            outer = (_compat.should_strip_ansi, utils.should_strip_ansi)
            with runner.isolation(color=False):
                click.echo('\033[31minner\033[0m')
            assert (_compat.should_strip_ansi, utils.should_strip_ansi) == outer
            if abort:
                raise failure
    except RuntimeError as exc:
        assert exc is failure
    assert _compat.should_strip_ansi is compat_policy
    assert utils.should_strip_ansi is utils_policy
