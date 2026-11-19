from __future__ import annotations

import errno
import os
from pathlib import Path

import pytest

from onnx import checker, external_data_helper as external


@pytest.mark.parametrize("size", [0, 23, 4097])
def test_descriptor_reads_regular_files_and_caller_closes(tmp_path: Path, size: int) -> None:
    payload = os.urandom(size)
    (tmp_path / "nested").mkdir()
    location = "nested/arbitrary-data.bin"
    (tmp_path / location).write_bytes(payload)
    descriptor = external._open_external_data_fd(str(tmp_path), location, "tensor-a", True)
    with os.fdopen(descriptor, "rb") as stream:
        assert stream.read() == payload
    with pytest.raises(OSError) as caught:
        os.fstat(descriptor)
    assert caught.value.errno == errno.EBADF
    replacement = os.urandom(size + 1)
    (tmp_path / location).write_bytes(replacement)
    descriptor = external._open_external_data_fd(str(tmp_path), location, "tensor-b", True)
    with os.fdopen(descriptor, "rb") as stream:
        assert stream.read() == replacement


def test_modes_creation_no_truncation_and_independent_offsets(tmp_path: Path) -> None:
    location = "new-file.bin"
    with pytest.raises(checker.ValidationError):
        external._open_external_data_fd(str(tmp_path), location, "new", True)
    assert not (tmp_path / location).exists()
    descriptor = external._open_external_data_fd(str(tmp_path), location, "new", False)
    with os.fdopen(descriptor, "w+b") as stream:
        stream.write(b"original")
    descriptor = external._open_external_data_fd(str(tmp_path), location, "existing", False)
    with os.fdopen(descriptor, "r+b") as stream:
        assert stream.read() == b"original"
        stream.seek(0)
        stream.write(b"NEW")
    assert (tmp_path / location).read_bytes() == b"NEWginal"
    readonly = external._open_external_data_fd(str(tmp_path), location, "readonly", True)
    try:
        with pytest.raises(OSError):
            os.write(readonly, b"bad")
    finally:
        os.close(readonly)
    assert (tmp_path / location).read_bytes() == b"NEWginal"
    first = external._open_external_data_fd(str(tmp_path), location, "first", True)
    with os.fdopen(first, "rb", buffering=0) as first_stream:
        assert first_stream.read(2) == b"NE"
        second = external._open_external_data_fd(str(tmp_path), location, "second", True)
        with os.fdopen(second, "rb", buffering=0) as second_stream:
            assert second_stream.read() == b"NEWginal"
        assert first_stream.read() == b"Wginal"


@pytest.mark.parametrize("read_only", [True, False])
@pytest.mark.parametrize("kind", ["final", "parent", "escape", "absolute", "directory", "missing-parent", "escape-new", "empty"])
def test_rejected_paths_leave_files_unchanged(tmp_path: Path, read_only: bool, kind: str) -> None:
    root = tmp_path / "model"
    root.mkdir()
    sensitive = tmp_path / "sensitive.bin"
    payload = os.urandom(41)
    sensitive.write_bytes(payload)
    (root / "link.bin").symlink_to(sensitive)
    (root / "parent-link").symlink_to(tmp_path, target_is_directory=True)
    (root / "directory").mkdir()
    location = {
        "final": "link.bin",
        "parent": "parent-link/sensitive.bin",
        "escape": "../sensitive.bin",
        "absolute": str(sensitive),
        "directory": "directory",
        "missing-parent": "absent/new.bin",
        "escape-new": "../escaped.bin",
        "empty": "",
    }[kind]
    with pytest.raises(checker.ValidationError):
        external._open_external_data_fd(str(root), location, "protected", read_only)
    assert sensitive.read_bytes() == payload
    assert (root / "link.bin").is_symlink()
    assert not (root / "absent").exists()
    assert not (tmp_path / "escaped.bin").exists()


@pytest.mark.parametrize("read_only", [True, False])
def test_non_regular_fifo_is_not_returned_as_a_data_file(tmp_path: Path, read_only: bool) -> None:
    location = "named-pipe"
    os.mkfifo(tmp_path / location)
    with pytest.raises(checker.ValidationError):
        external._open_external_data_fd(str(tmp_path), location, "fifo", read_only)


@pytest.mark.parametrize("read_only", [True, False])
def test_regular_dot_names_and_hardlinks_remain_usable(tmp_path, read_only):
    (tmp_path / "checkpoint..v2.bin").write_bytes(b"payload")
    os.link(tmp_path / "checkpoint..v2.bin",tmp_path / "alias.bin")
    for location in ['checkpoint..v2.bin','alias.bin']:
        fd=external._open_external_data_fd(str(tmp_path),location,"regular",read_only)
        with os.fdopen(fd,'rb') as stream:assert stream.read()==b"payload"


@pytest.mark.parametrize("read_only", [True, False])
def test_nul_path_and_in_base_parent_symlink_rejected(tmp_path, read_only):
    (tmp_path / "weights.bin").write_bytes(b"unchanged")
    (tmp_path / "real").mkdir()
    (tmp_path / "real/weights.bin").write_bytes(b"private")
    (tmp_path / "link").symlink_to(tmp_path / "real",target_is_directory=True)
    for location in ['weights.bin\x00ignored', 'link/weights.bin']:
        with pytest.raises(checker.ValidationError):
            external._open_external_data_fd(str(tmp_path),location,"bad",read_only)
    assert (tmp_path / "weights.bin").read_bytes()==b"unchanged"
