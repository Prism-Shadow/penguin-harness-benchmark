from __future__ import annotations

import importlib
import locale
import math
import os
import struct
import warnings
from pathlib import Path

import numpy as np
import pytest

import onnx
from onnx import TensorProto, checker, helper, numpy_helper, parser, printer


def _external_tensor(raw: bytes = b"payload") -> onnx.TensorProto:
    tensor = onnx.TensorProto()
    tensor.name = "weight"
    tensor.data_type = TensorProto.UINT8
    tensor.dims.extend([len(raw)])
    tensor.raw_data = raw
    return tensor


def test_6402_regular_external_file_compatibility(tmp_path: Path) -> None:
    external = importlib.import_module("onnx.external_data_helper")
    expected = b"regular-file-payload"
    (tmp_path / "weights.bin").write_bytes(expected)
    tensor = _external_tensor(expected)
    external.set_external_data(tensor, location="weights.bin", length=len(expected))
    tensor.ClearField("raw_data")
    external.load_external_data_for_tensor(tensor, str(tmp_path))
    assert tensor.raw_data == expected


@pytest.mark.parametrize("location", ["snapshot..v1.bin", "alias.bin"])
def test_ordinary_filename_and_hardlink_load_compatibility(tmp_path, location):
    from onnx import external_data_helper as external
    original = tmp_path / "snapshot..v1.bin"
    original.write_bytes(b"regular hardlinked file")
    os.link(original, tmp_path / "alias.bin")
    tensor = _external_tensor()
    external.set_external_data(tensor,location)
    external.load_external_data_for_tensor(tensor,str(tmp_path))
    assert tensor.raw_data == b"regular hardlinked file"
