import os
from pathlib import Path
import subprocess
import sys

import click
import pytest

def test_completion_instruction_uses_shell_first_format(tmp_path):
    assert_real_bash_completion(tmp_path, None, False, 'cli', '_CLI_COMPLETE')


@pytest.mark.parametrize('instruction', ['source_bash', 'bash_source'])
@pytest.mark.parametrize('empty', [False, True])
@pytest.mark.parametrize('prog_name,complete_var', [('cli', '_CLI_COMPLETE'), ('worker', '_CUSTOM_COMPLETE')])
def test_generated_bash_source_executes_real_completion(tmp_path, instruction, empty, prog_name, complete_var):
    assert_real_bash_completion(tmp_path, instruction, empty, prog_name, complete_var)


def assert_real_bash_completion(tmp_path, instruction, empty, prog_name, complete_var):
    observed = tmp_path / 'callback.txt'
    program = tmp_path / prog_name
    program.write_text('#!' + sys.executable + f'''
import os
from pathlib import Path
import click

callback_instruction = os.environ.get({complete_var!r}, '')

def candidates(ctx, parameter, incomplete):
    Path({str(observed)!r}).write_text(callback_instruction)
    if os.environ.get('COMPLETION_EMPTY') == '1':
        return []
    return [value for value in ['alpha', 'a space', 'a,comma', 'a中文'] if value.startswith(incomplete)]

@click.command()
@click.argument('value', shell_complete=candidates)
def worker(value):
    raise AssertionError('normal callback ran')

worker.main(prog_name={prog_name!r}, complete_var={complete_var!r})
''', encoding='utf-8')
    program.chmod(0o755)
    environment = dict(os.environ, PYTHONPATH=str(Path(click.__file__).resolve().parents[1]),
                       PATH=str(tmp_path) + os.pathsep + os.environ.get('PATH', ''),
                       COMPLETION_EMPTY='1' if empty else '0', PYTHONDONTWRITEBYTECODE='1')
    environment.pop(complete_var, None)
    script = tmp_path / 'completion.bash'
    if instruction is None:
        from click.shell_completion import BashComplete

        cli = click.Group(prog_name, commands=[click.Command('alpha'), click.Command('beta')])
        completion = BashComplete(cli, {}, prog_name, complete_var)
        script.write_text(completion.source(), encoding='utf-8')
    else:
        result = subprocess.run([str(program)], env=dict(environment, **{complete_var: instruction}),
                                capture_output=True, timeout=15)
        assert result.returncode == 0, result.stderr.decode(errors='replace')
        script.write_bytes(result.stdout)
    assert not observed.exists()
    shell = '''set -eu
source "$1"
binding=$(complete -p "$2")
[[ "$binding" =~ -F[[:space:]]+([^[:space:]]+) ]]
callback=${BASH_REMATCH[1]}
COMP_WORDS=("$2" a)
COMP_CWORD=1
COMPREPLY=()
response=outside
"$callback" "$2"
[[ "$response" == outside ]]
if ((${#COMPREPLY[@]})); then printf '%s\\0' "${COMPREPLY[@]}"; fi
'''
    completed = subprocess.run(['bash', '--noprofile', '--norc', '-c', shell, 'completion', str(script), prog_name],
                               env=environment, capture_output=True, timeout=15)
    assert completed.returncode == 0, completed.stderr.decode(errors='replace')
    assert observed.read_text() == 'bash_complete'
    values = [] if empty else ['alpha', 'a space', 'a,comma', 'a中文']
    assert completed.stdout == b''.join(value.encode('utf-8') + b'\0' for value in values)
