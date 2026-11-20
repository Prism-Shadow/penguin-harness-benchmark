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


def test_5211_inline_with_opset_conversion() -> None:
    inliner = importlib.import_module("onnx.inliner")
    model = parser.parse_model(
        """
        <ir_version: 8, opset_import: [ "" : 18, "local" : 1 ]>
        graph (float[N,M] X) => (float[N,M] Y) { Y = local.foo (X) }
        <opset_import: [ "" : 17], domain: "local">
        foo (x) => (y) { y = ReduceLogSum <axes = [0]> (x) }
        """
    )
    result = inliner.inline_local_functions(model, convert_version=True)
    assert [node.op_type for node in result.graph.node] == [
        "Constant",
        "ReduceLogSum",
    ]
    reduced = result.graph.node[1]
    assert len(reduced.input) == 2
    assert len(reduced.attribute) == 0
    assert list(result.functions) == []

    # Verify the actual converted graph wiring and numerical behavior.
    from onnx.reference import ReferenceEvaluator
    x = np.array([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32)
    axes = numpy_helper.to_array(result.graph.node[0].attribute[0].t)
    assert axes.tolist() == [0]
    assert reduced.input[1] == result.graph.node[0].output[0]
    actual = ReferenceEvaluator(result).run(None, {"X": x})[0]
    np.testing.assert_allclose(actual, np.log(np.sum(x, axis=0, keepdims=True)))
    # Default policy preserves incompatible functions, without mutating input.
    preserved = inliner.inline_local_functions(model)
    assert preserved.graph.node[0].op_type == "foo"
    assert len(preserved.functions) == 1
    assert model.graph.node[0].op_type == "foo"
