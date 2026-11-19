import click
import pytest


@pytest.mark.parametrize('case_sensitive,prefix,expected', [
    (False, 'a', ['Alpha']), (False, 'A', ['Alpha']),
    (False, 'be', ['Beta']), (False, 'É', ['Éclair']),
    (False, 'é', ['Éclair']), (False, '中', ['中文']),
    (False, 'missing', []), (False, '', ['Alpha', 'Beta', 'Éclair', '中文']),
    (True, 'a', []), (True, 'A', ['Alpha']),
])
def test_choice_prefixes_keep_canonical_values_and_parameter_wiring(case_sensitive, prefix, expected):
    choices = click.Choice(['Alpha', 'Beta', 'Éclair', '中文'], case_sensitive=case_sensitive)
    parameter = click.Argument(['value'], type=choices)
    command = click.Command('choices', params=[parameter])
    with click.Context(command) as context:
        assert [item.value for item in choices.shell_complete(context, parameter, prefix)] == expected
        assert [item.value for item in parameter.shell_complete(context, prefix)] == expected
