import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('native_export', ROOT / 'tools/export_native_tests.py')
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def test_node_manifests_bind_exact_assets():
    for path, content in EXPORT.support_manifests(ROOT).items():
        assert path.read_text() == content


def test_native_patch_is_exact_export():
    assert (ROOT / 'tests/test.patch').read_text() == EXPORT.render(ROOT)
