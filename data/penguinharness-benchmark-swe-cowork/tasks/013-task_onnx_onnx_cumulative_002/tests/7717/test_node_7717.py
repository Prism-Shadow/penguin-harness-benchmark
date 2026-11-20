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


def test_7717_load_rejects_parent_directory_symlink(tmp_path: Path) -> None:
    external = importlib.import_module("onnx.external_data_helper")
    model_dir = tmp_path / "model"
    outside = tmp_path / "outside"
    model_dir.mkdir()
    outside.mkdir()
    (outside / "secret.bin").write_bytes(b"secret")
    (model_dir / "subdir").symlink_to(outside, target_is_directory=True)
    tensor = _external_tensor()
    external.set_external_data(tensor, location="subdir/secret.bin")
    tensor.ClearField("raw_data")
    with pytest.raises(checker.ValidationError):
        external.load_external_data_for_tensor(tensor, str(model_dir))
