from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "penguin_agent"))

import host_config

CONFIG = """\
[providers]
[providers.deepseek]
base_url = "https://api.deepseek.com"

[[models]]
provider = "deepseek"
model_id = "deepseek-flash"
api_key = "test-key"
"""


def _write(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(CONFIG, encoding="utf-8")


def test_project_config_path_prefers_projects_level(tmp_path: Path) -> None:
    modern = tmp_path / "projects" / "default_project" / ".project_config.toml"
    _write(modern)
    assert host_config.project_config_path(str(tmp_path), "default_project") == modern


def test_project_config_path_falls_back_to_legacy(tmp_path: Path) -> None:
    legacy = tmp_path / "default_project" / ".project_config.toml"
    _write(legacy)
    assert host_config.project_config_path(str(tmp_path), "default_project") == legacy


def test_read_model_reads_projects_level(tmp_path: Path) -> None:
    _write(tmp_path / "projects" / "default_project" / ".project_config.toml")
    entry, sources = host_config.read_model(
        "deepseek", "deepseek-flash", root=str(tmp_path), project="default_project"
    )
    assert entry["api_key"] == "test-key"
    assert entry["base_url"] == "https://api.deepseek.com"
