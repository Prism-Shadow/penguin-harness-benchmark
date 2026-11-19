import hashlib
import json
from pathlib import Path
import subprocess
import tarfile
import copy
import os
import sys

import pytest

import rebuild_repository as exporter
import restore_regression_assets as importer
import frozen_regression as verifier


def make_history(root, files, later=None):
    root.mkdir()
    subprocess.run(["git", "init", "--quiet", "--template=", str(root)], check=True)
    stream = bytearray()
    for number, contents in enumerate((files, later) if later else (files,), 1):
        stream.extend(f"commit refs/heads/main\nmark :{number}\ncommitter Asset test <test@localhost> {946684800 + number} +0000\ndata 8\nfixture\n".encode())
        if number > 1:
            stream.extend(f"from :{number - 1}\n".encode())
        stream.extend(b"deleteall\n")
        for name, (mode, content) in sorted(contents.items()):
            stream.extend(f"M {mode} inline {name}\ndata {len(content)}\n".encode())
            stream.extend(content + b"\n")
        stream.extend(b"\n")
    marks = root.parent / (root.name + "-marks")
    subprocess.run(["git", "-C", str(root), "fast-import", "--quiet", f"--export-marks={marks}"],
                   input=stream, check=True)
    subprocess.run(["git", "-C", str(root), "symbolic-ref", "HEAD", "refs/heads/main"], check=True)
    return dict(line.split() for line in marks.read_text().splitlines())


def frozen_files():
    files = {"src/icalendar/tests/" + name: ("100644", (name + "\r\n").encode())
             for name in importer.DEFAULTS}
    files["src/icalendar/tests/test_upstream.py"] = ("100644", b"def test_frozen():\n    assert True\n")
    files["src/icalendar/tests/binary.dat"] = ("100644", b"\x00\xff\x80\r\n")
    files["conftest.py"] = ("100755", b"def fixture_value():\n    return 1\n")
    files["src/icalendar/production.py"] = ("100644", b"def unfinished():\n    pass\n")
    return files


def test_import_reads_frozen_tree_not_future_head(tmp_path, monkeypatch):
    files = frozen_files()
    later = dict(files)
    later["src/icalendar/tests/test_upstream.py"] = ("100644", b"FUTURE_TEST = True\n")
    source = tmp_path / "source"
    revisions = make_history(source, files, later)
    monkeypatch.setattr(importer, "REVISION", revisions[":1"])
    destination = tmp_path / "public"
    importer.restore(source, destination)
    for name, (mode, content) in files.items():
        if name == "src/icalendar/production.py":
            assert not (destination / name).exists()
        else:
            assert (destination / name).read_bytes() == content
            assert (destination / name).stat().st_mode & 0o777 == int(mode, 8) & 0o777
    record = json.loads((destination / "UPSTREAM_REGRESSION.json").read_text())
    assert record["upstream_revision"] == revisions[":1"]
    assert len(record["files"]) == len(files) - 1
    assert verifier.verify_directory(destination, revisions[":1"])
    monkeypatch.setattr(exporter, "REVISION", revisions[":1"])
    assert exporter.upstream_manifest(destination)


def test_unavailable_declared_revision_is_rejected(tmp_path):
    source = tmp_path / "source"
    make_history(source, frozen_files())
    destination = tmp_path / "public"
    with pytest.raises(subprocess.CalledProcessError):
        importer.restore(source, destination)
    assert not destination.exists()


@pytest.mark.parametrize("mutation", ["missing-default", "symlink", "bytecode", "conflict"])
def test_rejects_incomplete_or_unsafe_assets_before_writing(tmp_path, monkeypatch, mutation):
    files = frozen_files()
    if mutation == "missing-default":
        del files["src/icalendar/tests/events/rfc_9074_example_3.ics"]
    elif mutation == "symlink":
        files["src/icalendar/tests/link"] = ("120000", b"/private/path")
    elif mutation == "bytecode":
        files["src/icalendar/tests/__pycache__/test.pyc"] = ("100644", b"forbidden cache")
    source = tmp_path / "source"
    revisions = make_history(source, files)
    monkeypatch.setattr(importer, "REVISION", revisions[":1"])
    destination = tmp_path / "public"
    if mutation == "conflict":
        destination.mkdir()
        (destination / "conftest.py").write_bytes(b"preserve me")
    with pytest.raises(ValueError):
        importer.restore(source, destination)
    assert not (destination / "UPSTREAM_REGRESSION.json").exists()
    assert not (destination / "src").exists()
    if mutation == "conflict":
        assert (destination / "conftest.py").read_bytes() == b"preserve me"


def test_export_purges_cache_objects_and_is_reproducible(tmp_path):
    files = {"src/icalendar/production.py": ("100644", b"baseline\n"),
             "src/icalendar/__pycache__/production.cpython-311.pyc": ("100644", b"old compiled implementation")}
    source = tmp_path / "source"
    revisions = make_history(source, files)
    unreachable = subprocess.check_output(["git", "-C", str(source), "hash-object", "-w", "--stdin"],
                                          input=b"unreachable future implementation").decode().strip()
    public = tmp_path / "public"
    test = public / "src/icalendar/tests/test_local.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_local():\n    assert True\n")
    archives = []
    for suffix in ("one", "two"):
        archive = tmp_path / (suffix + ".tar.gz")
        provenance = tmp_path / (suffix + ".json")
        destination = tmp_path / suffix
        exporter.rebuild(source, public, destination, archive, provenance)
        record = json.loads(provenance.read_text())
        assert record["source_base_commit"] == revisions[":1"]
        assert record["upstream_behavioral_validation"] == "blocked_missing_assets"
        all_objects = exporter.git(destination, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").decode().splitlines()
        assert unreachable not in all_objects
        assert all(item["git_blob"] not in all_objects for item in record["removed_cache_blobs"])
        exporter.git(destination, "clean", "-fdx")
        assert (destination / test.relative_to(public)).read_bytes() == test.read_bytes()
        assert (destination / "src/icalendar/production.py").read_bytes() == b"baseline\n"
        with tarfile.open(archive) as packaged:
            assert all("__pycache__" not in member.name for member in packaged)
        archives.append(hashlib.sha256(archive.read_bytes()).hexdigest())
    assert archives[0] == archives[1]


@pytest.mark.parametrize("mutation", ["legacy", "forged-revision", "commit", "tree",
                                     "missing-test", "extra-test", "mode", "conftest"])
def test_authentication_rejects_invented_or_incomplete_trees(tmp_path, monkeypatch, mutation):
    source = tmp_path / "source"
    revisions = make_history(source, frozen_files())
    monkeypatch.setattr(importer, "REVISION", revisions[":1"])
    destination = tmp_path / "public"
    importer.restore(source, destination)
    record = json.loads((destination / "UPSTREAM_REGRESSION.json").read_text())
    contents = {name: (destination / name).read_bytes() for name in record["files"]}
    if mutation == "legacy":
        record["schema"] = "icalendar-frozen-regression-v1"
    elif mutation == "forged-revision":
        record["upstream_revision"] = verifier.REVISION
    elif mutation == "commit":
        record["git_proof"]["commit"] += "00"
    elif mutation == "tree":
        record["git_proof"]["trees"]["src"] += "00"
    elif mutation == "missing-test":
        del record["files"]["src/icalendar/tests/test_upstream.py"]
        del contents["src/icalendar/tests/test_upstream.py"]
    elif mutation == "extra-test":
        name = "src/icalendar/tests/test_forged.py"
        record["files"][name] = copy.deepcopy(record["files"]["src/icalendar/tests/test_upstream.py"])
        contents[name] = contents["src/icalendar/tests/test_upstream.py"]
    elif mutation == "mode":
        record["files"]["src/icalendar/tests/test_upstream.py"]["mode"] = "100755"
    elif mutation == "conftest":
        del record["files"]["conftest.py"]
        del contents["conftest.py"]
    with pytest.raises(ValueError):
        verifier.verify_record(record, contents, verifier.REVISION if mutation == "forged-revision" else revisions[":1"])


def test_asset_gate_rejects_smoke_only_even_with_optimization(tmp_path):
    public = tmp_path / "public"
    test = public / "src/icalendar/tests/test_smoke.py"
    test.parent.mkdir(parents=True)
    test.write_text("def test_smoke():\n    assert True\n")
    result = subprocess.run([sys.executable, "-O", str(Path(verifier.__file__)),
                             "--public-repo", str(public)], capture_output=True, text=True,
                            env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
    assert result.returncode == 1
    assert "smoke tests are not full regression" in result.stderr


def test_symlinked_parent_is_rejected(tmp_path, monkeypatch):
    source = tmp_path / "source"
    revisions = make_history(source, frozen_files())
    monkeypatch.setattr(importer, "REVISION", revisions[":1"])
    destination = tmp_path / "public"
    importer.restore(source, destination)
    (destination / "src").rename(destination / "real-src")
    (destination / "src").symlink_to("real-src", target_is_directory=True)
    with pytest.raises(ValueError, match="Symlinked asset"):
        verifier.verify_directory(destination, revisions[":1"])


def test_export_rejects_unanchored_manifest(tmp_path):
    public = tmp_path / "public"
    public.mkdir()
    files = {}
    for name, (mode, content) in frozen_files().items():
        if name == "src/icalendar/production.py":
            continue
        path = public / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        path.chmod(int(mode, 8) & 0o777)
        files[name] = {"mode": mode, "git_blob": verifier.object_id("blob", content),
                       "sha256": hashlib.sha256(content).hexdigest()}
    (public / "UPSTREAM_REGRESSION.json").write_text(json.dumps({
        "schema": "icalendar-frozen-regression-v1", "upstream_revision": verifier.REVISION,
        "upstream_tree": verifier.tests_tree(files), "files": files,
    }))
    with pytest.raises(ValueError, match="Missing authenticated v2 manifest"):
        exporter.upstream_manifest(public)


def test_authenticated_assets_survive_export_and_clean(tmp_path, monkeypatch):
    upstream = tmp_path / "upstream"
    revisions = make_history(upstream, frozen_files())
    monkeypatch.setattr(importer, "REVISION", revisions[":1"])
    monkeypatch.setattr(exporter, "REVISION", revisions[":1"])
    public = tmp_path / "public"
    importer.restore(upstream, public)
    baseline = tmp_path / "baseline"
    make_history(baseline, {"src/icalendar/production.py": ("100644", b"unfinished\n")})
    destination = tmp_path / "export"
    archive = tmp_path / "repository.tar.gz"
    provenance = tmp_path / "provenance.json"
    exporter.rebuild(baseline, public, destination, archive, provenance)
    exporter.git(destination, "clean", "-fdx")
    assert verifier.verify_directory(destination, revisions[":1"]) == verifier.verify_directory(public, revisions[":1"])
    assert (destination / "src/icalendar/production.py").read_bytes() == b"unfinished\n"
    assert json.loads(provenance.read_text())["upstream_behavioral_validation"] == "pending"
    object_ids = exporter.git(destination, "cat-file", "--batch-all-objects", "--batch-check=%(objectname)").decode().splitlines()
    assert revisions[":1"] not in object_ids
