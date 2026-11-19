"""Fail closed when the offline production development imports are incomplete."""
import argparse
import ctypes
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('repository', type=Path)
    args = parser.parse_args()
    repository = args.repository.resolve(strict=True)
    if sys.version_info[:2] != (3, 13):
        raise RuntimeError('Use the Python 3.13 development environment')
    sys.path.insert(0, str(repository))
    ctypes.CDLL('libodbc.so.2')
    ctypes.CDLL('libGL.so.1')
    import pyodbc  # noqa: F401: native driver-manager import must work
    import nltk
    for resource in ('tokenizers/punkt_tab', 'corpora/wordnet'):
        nltk.data.find(resource)
    modules = {}
    for name in (
        'rag.flow.chunker.token_chunker',
        'rag.flow.chunker.title_chunker.group_chunker',
        'rag.flow.chunker.title_chunker.hierarchy_chunker',
        'rag.advanced_rag.agentic_rag',
        'rag.advanced_rag.knowlege_compile.runner',
    ):
        module = importlib.import_module(name)
        location = Path(module.__file__).resolve(strict=True)
        if not location.is_relative_to(repository):
            raise RuntimeError('Production module came from outside the worktree: ' + str(location))
        modules[name] = str(location.relative_to(repository))
    from common.token_utils import num_tokens_from_string
    count = num_tokens_from_string('A live tokenizer is required for development checks.')
    if count <= 0:
        raise RuntimeError('Tokenizer silently returned zero tokens')
    try:
        distribution = importlib.metadata.distribution('ragflow')
    except importlib.metadata.PackageNotFoundError:
        distribution = None
    if distribution is not None:
        raise RuntimeError('Do not install a separate copy of the target project')
    print(json.dumps({'python': sys.version.split()[0], 'modules': modules,
                      'tokenizer_probe_tokens': count, 'nltk_data_ready': True,
                      'odbc_and_gl_loaded': True, 'installed_target_distribution': False}, indent=2))


if __name__ == '__main__':
    main()
