import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

import materialize_regression as materializer
import rebuild_repository as exporter
import restore_regression_assets as importer
from test_repair_tools import frozen_files, make_history


def digests(root):
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in root.rglob("*") if path.is_file()}


def inputs(tmp_path, monkeypatch, upstream_files=None, repair_files=None):
    upstream = tmp_path / "upstream"
    revision = make_history(upstream, upstream_files or frozen_files())[":1"]
    for module in (materializer, exporter, importer):
        monkeypatch.setattr(module, "REVISION", revision)
    original = tmp_path / "baseline"
    files = {"src/icalendar/production.py": ("100644", b"unfinished = True\n")}
    files.update(repair_files or {})
    later = dict(files, **{"README.rst": ("100644", b"frozen baseline\n")})
    make_history(original, files, later)
    task = tmp_path / "input-task"
    public = task / "environment/repo"
    public.mkdir(parents=True)
    production = public / "src/icalendar/production.py"
    production.parent.mkdir(parents=True)
    production.write_bytes(files["src/icalendar/production.py"][1])
    for name, (mode, content) in (repair_files or {}).items():
        path = public / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(int(mode, 8) & 0o777)
    exporter.rebuild(original, public, tmp_path / "clean",
                     task / "environment/repository.tar.gz",
                     task / "environment/repository-provenance.json")
    record = json.loads((task / "environment/repository-provenance.json").read_text())
    for name, count in materializer.BINDINGS.items():
        path = task / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((record["baseline_head"] + "\n") * count)
    metadata = task / "task.toml"
    with metadata.open("a") as stream:
        stream.write(record["base_commit"] + '\nupstream_regression_status = "blocked_missing_frozen_upstream_assets"\n'
                     'repair_release_status = "blocked_missing_authenticated_regression_assets"\n')
    request = task / "tools/frozen-regression-request.json"
    request.parent.mkdir()
    request.write_text(json.dumps({"status": "blocked_missing_external_source_assets", "finding_disposition": "deferred"}))
    (task / "environment/task_README.md").write_text("Keep full regression required.\n" + materializer.PUBLIC_GAP + "\n")
    (task / "solution/solution.patch").write_text("preserve production solution\n")
    return task, upstream


def test_authenticated_import_publishes_archive_bindings_without_editing_inputs(tmp_path, monkeypatch):
    task, upstream = inputs(tmp_path, monkeypatch)
    before = digests(task), digests(upstream)
    destination = tmp_path / "output-task"
    materializer.materialize(task, upstream, destination)
    assert (digests(task), digests(upstream)) == before
    record = json.loads((destination / "environment/repository-provenance.json").read_text())
    assert materializer.sha256(destination / "environment/repository.tar.gz") == record["archive_sha256"]
    assert record["upstream_behavioral_validation"] == "pending"
    for name, count in materializer.BINDINGS.items():
        assert (destination / name).read_text().count(record["baseline_head"]) == count
    assert "blocked_pending_independent_validation" in (destination / "task.toml").read_text()
    assert (destination / "environment/task_README.md").read_text() == (
        "Keep full regression required.\n" + materializer.PUBLIC_RESTORED + "\n")
    assert (destination / "solution/solution.patch").read_bytes() == (task / "solution/solution.patch").read_bytes()
    extracted = tmp_path / "replay"
    materializer.unpack(destination / "environment/repository.tar.gz", extracted)
    for revision in exporter.git(extracted, "rev-list", "--all").decode().splitlines():
        exporter.git(extracted, "reset", "--hard", revision)
        exporter.git(extracted, "clean", "-fdx")
        materializer.verify_directory(extracted, materializer.REVISION)
        assert (extracted / "src/icalendar/production.py").read_bytes() == b"unfinished = True\n"
    assert not list(tmp_path.glob("regression-import-*"))


@pytest.mark.parametrize("mutation", ["missing-revision", "stale-binding", "archive-digest", "conflicting-fixture",
                                    "archive-head", "archive-base"])
def test_failed_import_does_not_publish_partial_task(tmp_path, monkeypatch, mutation):
    task, upstream = inputs(tmp_path, monkeypatch)
    if mutation == "missing-revision":
        monkeypatch.setattr(importer, "REVISION", "0" * 40)
    elif mutation == "stale-binding":
        (task / "pre_artifacts.sh").write_text("wrong-baseline\n")
    elif mutation == "archive-digest":
        with (task / "environment/repository.tar.gz").open("ab") as stream:
            stream.write(b"modified archive")
    elif mutation == "conflicting-fixture":
        (task / "environment/repo/conftest.py").write_text("do not overwrite\n")
    else:
        record_path = task / "environment/repository-provenance.json"
        record = json.loads(record_path.read_text())
        key = "baseline_head" if mutation == "archive-head" else "base_commit"
        old_value = record[key]
        record[key] = "0" * 40
        record_path.write_text(json.dumps(record))
        for name in materializer.BINDINGS:
            path = task / name
            path.write_text(path.read_text().replace(old_value, record[key]))
    before = digests(task), digests(upstream)
    destination = tmp_path / "output-task"
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        materializer.materialize(task, upstream, destination)
    assert not destination.exists()
    assert not list(tmp_path.glob("regression-import-*"))
    assert (digests(task), digests(upstream)) == before


@pytest.mark.parametrize("location", ["existing", "in-task", "in-upstream", "symlink", "traversal"])
def test_unsafe_publication_destination_is_rejected(tmp_path, monkeypatch, location):
    task, upstream = inputs(tmp_path, monkeypatch)
    destination = {"existing": task, "in-task": task / "output", "in-upstream": upstream / "output",
                   "symlink": tmp_path / "linked/output", "traversal": tmp_path / "unused/../input-task/output"}[location]
    if location == "symlink":
        (tmp_path / "linked").symlink_to(task, target_is_directory=True)
    before = digests(task), digests(upstream)
    with pytest.raises(ValueError):
        materializer.materialize(task, upstream, destination)
    assert (digests(task), digests(upstream)) == before


def collision_files():
    upstream = frozen_files()
    upstream[materializer.REPAIR_INIT] = ("100644", b'"""Authenticated upstream helpers."""\n')
    # This fixture models the pre-restoration repair shim. A materialized package
    # correctly contains executable upstream helpers, which are not that shim.
    repair = {materializer.REPAIR_INIT: (
        "100644", b'"""Repair-owned regression checks before corpus restoration."""\n')}
    for number, name in enumerate(materializer.REPAIR_TESTS):
        upstream[name] = ("100644", f"def test_upstream_{number}():\n    assert {number} + 1 == {number + 1}\n".encode())
        repair[name] = ("100644", f"def test_repair_{number}():\n    assert {number} + 2 == {number + 2}\n".encode())
    return upstream, repair


def test_authenticated_collisions_preserve_upstream_and_execute_both_suites(tmp_path, monkeypatch):
    upstream_files, repair_files = collision_files()
    task, upstream = inputs(tmp_path, monkeypatch, upstream_files, repair_files)
    before = digests(task), digests(upstream)
    with pytest.raises(ValueError, match="Conflicting asset"):
        importer.restore(upstream, task / "environment/repo")
    assert (digests(task), digests(upstream)) == before
    destination = tmp_path / "output"
    materializer.materialize(task, upstream, destination)
    assert (digests(task), digests(upstream)) == before
    record = json.loads((destination / "environment/repository-provenance.json").read_text())
    assert record["repair_asset_relocations"] == dict(materializer.REPAIR_TESTS, **{materializer.REPAIR_INIT: None})
    replay = tmp_path / "replay"
    materializer.unpack(destination / "environment/repository.tar.gz", replay)
    for revision in exporter.git(replay, "rev-list", "--all").decode().splitlines():
        exporter.git(replay, "reset", "--hard", revision)
        exporter.git(replay, "clean", "-fdx")
        materializer.verify_directory(replay, materializer.REVISION)
        for name in (materializer.REPAIR_INIT, *materializer.REPAIR_TESTS):
            assert (replay / name).read_bytes() == upstream_files[name][1]
        for name, replacement in materializer.REPAIR_TESTS.items():
            assert (replay / replacement).read_bytes() == repair_files[name][1]
        assert (replay / "src/icalendar/production.py").read_bytes() == b"unfinished = True\n"
    command = [sys.executable, "-B", "-m", "pytest", "-q", "-p", "no:cacheprovider",
               *materializer.REPAIR_TESTS, *materializer.REPAIR_TESTS.values()]
    result = subprocess.run(command, cwd=replay, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "4 passed" in result.stdout


@pytest.mark.parametrize("mutation", ["unregistered", "modified", "executable-init",
                                    "upstream-relocation", "local-relocation", "missing-revision"])
def test_collision_resolution_rejects_untrusted_or_nonempty_replacements(tmp_path, monkeypatch, mutation):
    upstream_files, repair_files = collision_files()
    if mutation == "executable-init":
        repair_files[materializer.REPAIR_INIT] = ("100644", b"raise RuntimeError('must not be removed')\n")
    if mutation == "upstream-relocation":
        upstream_files[next(iter(materializer.REPAIR_TESTS.values()))] = ("100644", b"preserve upstream\n")
    task, upstream = inputs(tmp_path, monkeypatch, upstream_files, repair_files)
    if mutation == "unregistered":
        path = task / "environment/repository-provenance.json"
        record = json.loads(path.read_text())
        del record["public_files"][materializer.REPAIR_INIT]
        path.write_text(json.dumps(record))
    elif mutation == "modified":
        path = task / "environment/repo" / next(iter(materializer.REPAIR_TESTS))
        path.write_bytes(b"modified repair code\n")
    elif mutation == "local-relocation":
        path = task / "environment/repo" / next(iter(materializer.REPAIR_TESTS.values()))
        path.write_bytes(b"preserve local\n")
    elif mutation == "missing-revision":
        monkeypatch.setattr(importer, "REVISION", "0" * 40)
    before = digests(task), digests(upstream)
    with pytest.raises((ValueError, subprocess.CalledProcessError)):
        materializer.materialize(task, upstream, tmp_path / "output")
    assert (digests(task), digests(upstream)) == before
    assert not (tmp_path / "output").exists()
    assert not list(tmp_path.glob("regression-import-*"))
