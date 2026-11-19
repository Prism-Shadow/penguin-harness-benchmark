#!/usr/bin/env python3
"""Ignored implementation files eligible for source capture and progress.

Tracked files are handled by Git. This adds ignored new source/data under the
repository's implementation roots, without traversing dependencies or secrets.
"""
import os
from pathlib import Path
import subprocess
import sys

SUFFIXES = {'.ts', '.tsx', '.js', '.jsx', '.cjs', '.mjs', '.json', '.yaml', '.yml', '.wasm'}
EXCLUDED = {'node_modules', '.git', '.cache', '__pycache__', 'coverage', '.venv', 'venv', '.ssh'}
CREDENTIAL_NAMES = {'credentials.json', 'service-account.json', 'application_default_credentials.json'}


def ignored_sources(repo):
    result = subprocess.run(['git', '-C', str(repo), 'ls-files', '--others', '--ignored',
                             '--exclude-standard', '-z', '--', 'src', 'scripts', 'templates', 'schema'],
                            check=True, stdout=subprocess.PIPE, timeout=30)
    return [raw for raw in result.stdout.split(b'\0') if raw
            and Path(os.fsdecode(raw)).suffix in SUFFIXES
            and not EXCLUDED.intersection(Path(os.fsdecode(raw)).parts)
            and Path(os.fsdecode(raw)).name not in CREDENTIAL_NAMES
            and not any(part.startswith('.env') for part in Path(os.fsdecode(raw)).parts)]


if __name__ == '__main__':
    for raw in ignored_sources(Path(sys.argv[1])):
        sys.stdout.buffer.write(raw + b'\0')
