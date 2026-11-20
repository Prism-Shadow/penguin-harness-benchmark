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


def test_7627_save_rejects_parent_traversal(tmp_path: Path) -> None:
    external = importlib.import_module("onnx.external_data_helper")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    tensor = _external_tensor(b"must-not-escape")
    external.set_external_data(tensor, location="../escaped.bin")
    with pytest.raises(checker.ValidationError):
        external.save_external_data(tensor, str(model_dir))
    assert not (tmp_path / "escaped.bin").exists()
