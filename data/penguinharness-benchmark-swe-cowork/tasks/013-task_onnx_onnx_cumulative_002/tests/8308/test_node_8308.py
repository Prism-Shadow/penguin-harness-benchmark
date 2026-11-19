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


def test_8308_float16_raw_initializer_printing() -> None:
    values = np.array([1.0, -2.0, 0.5], dtype=np.float16)
    initializer = numpy_helper.from_array(values, name="weights")
    graph = helper.make_graph([], "graph", [], [], [initializer])
    text = printer.to_text(graph)
    assert "{15360,49152,14336}" in text.replace(" ", "")
    restored = parser.parse_graph(text)
    assert restored.initializer[0].name == "weights"
    np.testing.assert_array_equal(numpy_helper.to_array(restored.initializer[0]), values)


@pytest.mark.parametrize('bits,shape,name', [
    ([0, 32768, 1, 65504], [2, 2], 'other_weights'),
    ([31744, 64512, 32256, 15361], [4], 'edge_weights'),
    ([], [0], 'empty_weights'),
])
def test_float16_payload_roundtrip_for_distinct_inputs(bits, shape, name):
    values = np.asarray(bits, dtype=np.uint16).view(np.float16).reshape(shape)
    graph = helper.make_graph([], 'roundtrip', [], [], [numpy_helper.from_array(values, name=name)])
    restored = parser.parse_graph(printer.to_text(graph))
    tensor = restored.initializer[0]
    assert tensor.name == name and list(tensor.dims) == shape
    assert tensor.data_type == TensorProto.FLOAT16
    np.testing.assert_array_equal(numpy_helper.to_array(tensor).view(np.uint16), values.view(np.uint16))
