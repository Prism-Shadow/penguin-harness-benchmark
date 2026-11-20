import json
from pathlib import Path
import subprocess
import sys

import pytest

import prepare_build as preparation
import restore_regression_assets as importer
from test_acquire_regression_assets import pin
from test_materialize_regression import digests, inputs


@pytest.mark.parametrize("source_kind", ["git", "export", "embedded", "acquire"])
def test_broker_receives_new_authenticated_task_not_raw_input(tmp_path, monkeypatch, source_kind):
    task, source = inputs(tmp_path, monkeypatch)
    pin(monkeypatch, importer.REVISION)
    before = digests(task), digests(source)
    if source_kind == "export":
        public = tmp_path / "authenticated"
        importer.restore(source, public)
        source = public
    if source_kind == "embedded":
        restored = tmp_path / "restored-task"
        preparation.materializer.materialize(task, source, restored)
        task, source = restored, None
        before = digests(task), None
    if source_kind == "acquire":
        acquire = preparation.acquisition.acquire
        remote = source.as_uri()
        monkeypatch.setattr(preparation.acquisition, "acquire", lambda path: acquire(path, remote))
    destination = tmp_path / "build-task"
    receipt = preparation.prepare(task, destination, None if source_kind == "acquire" else source,
                                  acquire=source_kind == "acquire")
    assert receipt["build_allowed"], receipt
    assert receipt["whole_task_ready"] is False
    assert receipt["phase"] == "prepared"
    assert Path(receipt["task_directory"]) == destination != task
    assert preparation.fingerprint(destination) == receipt["task_sha256"]
    assert preparation.fingerprint(task) == receipt["input_task_sha256"]
    assert digests(task) == before[0]
    if source_kind == "git":
        assert digests(source) == before[1]
    assert (destination / "environment/repo/src/icalendar/production.py").read_bytes() == b"unfinished = True\n"
    assert (destination / "solution/solution.patch").read_bytes() == (task / "solution/solution.patch").read_bytes()
    assert not list(tmp_path.glob("build-preparation-*"))


@pytest.mark.parametrize("failure", ["missing", "transport", "bad-manifest", "stale-archive", "invalid-archive",
                                     "stale-binding", "changed-input"])
def test_failed_preparation_cannot_handoff_a_build_directory(tmp_path, monkeypatch, failure):
    task, upstream = inputs(tmp_path, monkeypatch)
    source = upstream
    acquire = False
    if failure == "missing":
        source = None
    elif failure == "transport":
        source, acquire = None, True
        def broken_transport(path):
            raise subprocess.CalledProcessError(128, ["git", "fetch", "pinned-revision"])
        monkeypatch.setattr(preparation.acquisition, "acquire", broken_transport)
    elif failure in ("bad-manifest", "stale-archive", "invalid-archive", "stale-binding"):
        prepared = tmp_path / "prepared"
        preparation.materializer.materialize(task, upstream, prepared)
        task, source = prepared, None
        if failure == "bad-manifest":
            (task / "environment/repo/UPSTREAM_REGRESSION.json").write_text("{}")
        elif failure == "stale-archive":
            with (task / "environment/repository.tar.gz").open("ab") as stream:
                stream.write(b"tampered")
        elif failure == "invalid-archive":
            archive = task / "environment/repository.tar.gz"
            archive.write_text("not a tar archive")
            provenance = task / "environment/repository-provenance.json"
            record = json.loads(provenance.read_text())
            record["archive_sha256"] = preparation.materializer.sha256(archive)
            provenance.write_text(json.dumps(record))
        else:
            (task / "pre_artifacts.sh").write_text("stale baseline\n")
    else:
        materialize = preparation.materializer.materialize
        def change_input(*arguments):
            materialize(*arguments)
            (task / "solution/solution.patch").write_text("changed by other actor\n")
        monkeypatch.setattr(preparation.materializer, "materialize", change_input)
    destination = tmp_path / "build-task"
    receipt = preparation.prepare(task, destination, source, acquire)
    assert receipt["build_allowed"] is False
    assert receipt["whole_task_ready"] is False
    assert receipt["task_directory"] is None
    assert receipt["error"]
    assert not destination.exists()
    assert not list(tmp_path.glob("build-preparation-*"))


def test_successful_acquisition_cli_emits_only_json_stdout(tmp_path, monkeypatch, capfd):
    task, source = inputs(tmp_path, monkeypatch)
    pin(monkeypatch, importer.REVISION)
    acquire = preparation.acquisition.acquire
    monkeypatch.setattr(preparation.acquisition, "acquire", lambda path: acquire(path, source.as_uri()))
    monkeypatch.setattr(sys, "argv", ["prepare_build.py", "--task", str(task), "--acquire",
                                     "--destination", str(tmp_path / "published")])
    capfd.readouterr()
    assert preparation.main() == 0
    streams = capfd.readouterr()
    receipt = json.loads(streams.out)
    assert receipt["build_allowed"] is True and receipt["whole_task_ready"] is False
    assert "Recovered" in streams.err


def test_cli_missing_assets_is_classified_before_any_build(tmp_path, monkeypatch):
    candidate = Path(__file__).resolve().parents[1]
    unprepared, _ = inputs(tmp_path, monkeypatch)
    destination = tmp_path / "not-published"
    result = subprocess.run([sys.executable, "-B", str(candidate / "tools/prepare_build.py"),
                             "--task", str(unprepared), "--destination", str(destination)],
                            capture_output=True, text=True)
    assert result.returncode == 78, result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["phase"] == "asset_preparation"
    assert receipt["build_allowed"] is False and receipt["task_directory"] is None
    assert not destination.exists()


@pytest.mark.parametrize("destination_kind", ["existing", "inside-task", "symlink"])
def test_invalid_destination_cannot_overwrite_input(tmp_path, monkeypatch, destination_kind):
    task, upstream = inputs(tmp_path, monkeypatch)
    destination = tmp_path / "output"
    if destination_kind == "existing":
        destination.mkdir()
        (destination / "keep").write_text("unchanged")
    elif destination_kind == "inside-task":
        destination = task / "nested"
    else:
        destination.symlink_to(tmp_path / "absent", target_is_directory=True)
    before = digests(task)
    receipt = preparation.prepare(task, destination, upstream)
    assert receipt["phase"] == "input_validation" and not receipt["build_allowed"]
    assert digests(task) == before
