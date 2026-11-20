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


def test_5105_inline_nested_local_functions() -> None:
    inliner = importlib.import_module("onnx.inliner")
    model = parser.parse_model(
        """
        <ir_version: 8, opset_import: [ "" : 17, "local" : 1 ]>
        graph (float[N] X) => (float[N] Y) { Y = local.foo (X) }
        <opset_import: [ "" : 17, "local" : 1 ], domain: "local">
        foo (x) => (y) { temp = Add(x, x) y = local.bar(temp) }
        <opset_import: [ "" : 17 ], domain: "local">
        bar (x) => (y) { y = Mul (x, x) }
        """
    )
    result = inliner.inline_local_functions(model)
    assert [node.op_type for node in result.graph.node] == ["Add", "Mul"]
    assert list(result.functions) == []
