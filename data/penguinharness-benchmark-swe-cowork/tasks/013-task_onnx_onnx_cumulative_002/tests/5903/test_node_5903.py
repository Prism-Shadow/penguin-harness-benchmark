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


def test_5903_function_value_info_parser_contract() -> None:
    function = parser.parse_function(
        """
        <opset_import: ["": 10], domain: "local">
        f (float[N] y, float[N] z) => (float[N] w)
        <float[N] intermediate> {
          intermediate = Add(y, z)
          w = Mul(intermediate, y)
        }
        """
    )
    assert list(function.input) == ["y", "z"]
    assert list(function.output) == ["w"]
    values = {value.name: value.type for value in function.value_info}
    assert set(values) == {"y", "z", "w", "intermediate"}
    for typ in values.values():
        assert typ.tensor_type.elem_type == TensorProto.FLOAT
        assert typ.tensor_type.shape.dim[0].dim_param == "N"
    restored = parser.parse_function(printer.to_text(function))
    assert {v.name: v.type for v in restored.value_info} == values
    assert list(restored.input) == list(function.input)
    assert list(restored.output) == list(function.output)
    assert list(restored.node) == list(function.node)


def test_mixed_typed_and_untyped_function_and_helper_serialization():
    function = parser.parse_function('''
      <opset_import: ["":17], domain:"local", overload:"typed">
      transform <alpha: float = 2.5> (float[N,2] x, spare) => (double[N,2] y)
      <int64[2] dims> { y = Cast <to=11> (x) }
    ''')
    assert list(function.input) == ["x", "spare"]
    values = {v.name:v.type for v in function.value_info}
    assert set(values) == {"x","y","dims"}
    assert values["y"].tensor_type.elem_type == TensorProto.DOUBLE
    assert values["dims"].tensor_type.elem_type == TensorProto.INT64
    assert values["x"].tensor_type.shape.dim[1].dim_value == 2
    restored = parser.parse_function(printer.to_text(function))
    assert {v.name:v.type for v in restored.value_info} == values
    assert restored.attribute_proto == function.attribute_proto
    assert restored.overload == "typed"
    made = helper.make_function("local", "made", ["x"], ["y"], function.node,
        function.opset_import, value_info=list(function.value_info), overload="typed")
    parsed = onnx.FunctionProto.FromString(made.SerializeToString())
    assert parsed.value_info == made.value_info
    assert parsed.overload == "typed"


def test_function_protocol_fields_interoperate_with_canonical_wire_payload():
    value = helper.make_tensor_value_info('x', TensorProto.FLOAT, ['N'])
    encoded = value.SerializeToString()
    assert len(encoded) < 128
    # Canonical wire fields: FunctionProto.value_info=12, overload=13;
    # NodeProto.overload=8. Feed real bytes through the public generated types.
    function = onnx.FunctionProto.FromString(bytes([0x62, len(encoded)]) + encoded + b'\x6a\x05typed')
    assert len(function.value_info) == 1
    assert function.value_info[0] == value
    assert function.overload == 'typed'
    node = onnx.NodeProto.FromString(b'\x42\x05typed')
    assert node.overload == 'typed'
