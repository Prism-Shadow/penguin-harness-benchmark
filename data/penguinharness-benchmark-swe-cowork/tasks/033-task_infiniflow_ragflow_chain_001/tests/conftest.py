import sys

import pytest


@pytest.fixture(autouse=True)
def restore_import_boundaries():
    prefixes = ('rag', 'common', 'api', 'deepdoc', 'langgraph', 'pdfplumber', '_behavior')
    original = {name: module for name, module in sys.modules.items() if name.startswith(prefixes)}
    yield
    for name in list(sys.modules):
        if name.startswith(prefixes) and name not in original:
            del sys.modules[name]
    sys.modules.update(original)
