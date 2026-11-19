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


def test_7628_load_rejects_final_component_symlink(tmp_path: Path) -> None:
    external = importlib.import_module("onnx.external_data_helper")
    (tmp_path / "target.bin").write_bytes(b"secret")
    (tmp_path / "link.bin").symlink_to(tmp_path / "target.bin")
    tensor = _external_tensor()
    external.set_external_data(tensor, location="link.bin")
    tensor.ClearField("raw_data")
    with pytest.raises(checker.ValidationError):
        external.load_external_data_for_tensor(tensor, str(tmp_path))
