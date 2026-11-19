"""Packaging checks, not substitutes for constrained inverse execution."""
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_verifier_assets_match():
    path = ROOT / 'tools/sync_verifier_assets.py'
    spec = importlib.util.spec_from_file_location('inverse_assets', path)
    renderer = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(renderer)
    for output, content in renderer.render(ROOT).items():
        assert output.read_text() == content
