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


def test_8195_exact_float_print_roundtrip_and_underflow() -> None:
    original = np.float32(1.2345678)
    node = helper.make_node("LeakyRelu", ["x"], ["y"], alpha=float(original))
    parsed = parser.parse_node(printer.to_text(node))
    actual = parsed.attribute[0].f
    assert struct.pack("<f", actual) == struct.pack("<f", original)
    tiny = parser.parse_node("y = LeakyRelu <alpha = 1e-45> (x)")
    assert 0.0 <= tiny.attribute[0].f <= np.nextafter(np.float32(0), np.float32(1))


@pytest.mark.parametrize('value', [2.0, -0.0, 0.0, -7.0, 3.4028234663852886e38])
def test_integral_float_attributes_keep_type_and_bits(value):
    node = helper.make_node('LeakyRelu', ['x'], ['y'], alpha=value)
    restored = parser.parse_node(printer.to_text(node))
    attr = restored.attribute[0]
    assert attr.type == onnx.AttributeProto.FLOAT
    assert struct.pack('<f', attr.f) == struct.pack('<f', value)
    assert not attr.HasField('i')


@pytest.mark.parametrize('value', [b'quote"slash\\tail', b'embedded\0byte'])
def test_string_attributes_keep_bytes(value):
    node = helper.make_node('Custom', ['x'], ['y'], label=value)
    restored = parser.parse_node(printer.to_text(node))
    # Proto2 absent/default domain encodings are the same public ONNX domain.
    # A text parser may set the empty default explicitly.
    for attr in restored.attribute:
        for graph in attr.graphs:
            for inner in graph.node:
                if not inner.domain:
                    inner.ClearField('domain')
    assert restored.attribute == node.attribute


@pytest.mark.parametrize('kind', [onnx.AttributeProto.FLOATS, onnx.AttributeProto.INTS, onnx.AttributeProto.STRINGS])
def test_typed_empty_default_attribute_roundtrip(kind):
    attribute = onnx.AttributeProto(name='values', type=kind)
    function = helper.make_function('local', 'empty_default', ['x'], ['y'],
        [helper.make_node('Identity', ['x'], ['y'])], [helper.make_opsetid('', 17)],
        attribute_protos=[attribute])
    restored = parser.parse_function(printer.to_text(function))
    assert restored.attribute_proto == function.attribute_proto


@pytest.mark.parametrize('attribute', [
    helper.make_attribute('floats', [2.0, -0.0, 3.5]),
    helper.make_attribute('strings', [b'escaped"value', b'slash\\value']),
    helper.make_attribute('tensors', [helper.make_tensor('a', TensorProto.INT64, [2], [7, 9]),
                                      helper.make_tensor('b', TensorProto.FLOAT, [1], [2.5])]),
    helper.make_attribute('graphs', [helper.make_graph([helper.make_node('Identity', ['x'], ['y'])],
        'body', [helper.make_tensor_value_info('x', TensorProto.FLOAT, [2])],
        [helper.make_tensor_value_info('y', TensorProto.FLOAT, [2])])]),
])
def test_list_attributes_preserve_all_elements(attribute):
    node = helper.make_node('Custom', ['x'], ['y'])
    node.attribute.append(attribute)
    restored = parser.parse_node(printer.to_text(node))
    # Proto2 absent/default domain encodings are the same public ONNX domain.
    # A text parser may set the empty default explicitly.
    for attr in restored.attribute:
        for graph in attr.graphs:
            for inner in graph.node:
                if not inner.domain:
                    inner.ClearField('domain')
    assert restored.attribute == node.attribute
