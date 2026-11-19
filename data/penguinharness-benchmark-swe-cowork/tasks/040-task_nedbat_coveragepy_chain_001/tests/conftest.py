import os
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def production_environment():
    repository = Path(os.environ['REPO_DIR']).resolve()
    import coverage

    assert Path(coverage.__file__).resolve().is_relative_to(repository)
    previous_environment = os.environ.copy()
    previous_path = sys.path[:]
    previous_directory = Path.cwd()
    bindings = {name: getattr(os, name) for name in ('_exit', 'execv', 'execve')}
    yield
    current = coverage.Coverage.current()
    if current is not None:
        current.stop()
    os.environ.clear()
    os.environ.update(previous_environment)
    sys.path[:] = previous_path
    os.chdir(previous_directory)
    for name, function in bindings.items():
        setattr(os, name, function)
