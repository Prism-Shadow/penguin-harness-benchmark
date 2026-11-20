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


def test_7737_zero_length_reads_zero_bytes(tmp_path: Path) -> None:
    external = importlib.import_module("onnx.external_data_helper")
    (tmp_path / "weights.bin").write_bytes(b"must-not-be-read")
    tensor = _external_tensor()
    external.set_external_data(tensor, location="weights.bin", offset=0, length=0)
    tensor.ClearField("raw_data")
    external.load_external_data_for_tensor(tensor, str(tmp_path))
    assert tensor.raw_data == b""


@pytest.mark.parametrize("offset,length,expected", [(2,3,b"ABC"),(2,None,b"ABCxyz"),(8,0,b""),(8,None,b""),(3,2,b"BC")])
def test_successful_nonzero_slices_replace_stale_data(tmp_path, offset, length, expected):
    from onnx import external_data_helper as external
    (tmp_path / "weights.bin").write_bytes(b"pqABCxyz")
    tensor = _external_tensor(b"stale data from a previous load")
    external.set_external_data(tensor,"weights.bin",offset=offset,length=length)
    external.load_external_data_for_tensor(tensor,str(tmp_path))
    assert tensor.raw_data == expected


@pytest.mark.parametrize("offset,length", [(9,None),(8,1),(2,7),(0,9)])
def test_out_of_bounds_load_is_atomic(tmp_path, offset, length):
    from onnx import external_data_helper as external
    (tmp_path / "weights.bin").write_bytes(b"pqABCxyz")
    tensor = _external_tensor(b"unchanged")
    external.set_external_data(tensor,"weights.bin",offset=offset,length=length)
    with pytest.raises(ValueError):
        external.load_external_data_for_tensor(tensor,str(tmp_path))
    assert tensor.raw_data == b"unchanged"


def test_two_tensor_save_load_lifecycle(tmp_path):
    from onnx import external_data_helper as external
    a,b = _external_tensor(b"FIRST"), _external_tensor(b"second!")
    a.name,b.name = "a","b"
    for t in (a,b):
        external.set_external_data(t,"shared.bin")
        external.save_external_data(t,str(tmp_path))
    assert (tmp_path / "shared.bin").read_bytes() == b"FIRSTsecond!"
    assert (external.ExternalDataInfo(a).offset, external.ExternalDataInfo(b).offset) == (0,5)
    for t,expected in [(b,b"second!"),(a,b"FIRST"),(b,b"second!"),(a,b"FIRST")]:
        t.raw_data = b"stale"
        external.load_external_data_for_tensor(t,str(tmp_path))
        assert t.raw_data == expected
    # A subsequent save explicitly requests append; old locations remain readable.
    a.raw_data = b"THIRD"
    external.set_external_data(a,"shared.bin")
    external.save_external_data(a,str(tmp_path))
    assert (tmp_path / "shared.bin").read_bytes() == b"FIRSTsecond!THIRD"
    for t,expected in [(b,b"second!"),(a,b"THIRD")]:
        t.ClearField("raw_data")
        external.load_external_data_for_tensor(t,str(tmp_path))
        assert t.raw_data == expected
