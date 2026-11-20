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


def test_5238_attribute_binding_compatibility() -> None:
    model = parser.parse_model(
        """
        <ir_version: 8, opset_import: ["": 18, "local": 1]>
        graph (float[N] x) => (int32[N] y) {
          y = local.cast <target = 6> (x)
        }
        <domain: "local", opset_import: ["": 18]>
        cast <target: int = 1> (x) => (y) {
          y = Cast <to: int = @target> (x)
        }
        """
    )
    inferred = onnx.shape_inference.infer_shapes(model, strict_mode=True)
    tensor_type = inferred.graph.output[0].type.tensor_type
    assert tensor_type.elem_type == TensorProto.INT32
    assert tensor_type.shape.dim[0].dim_param == "N"


def test_constant_vector_and_scalar_data_propagation_compatibility():
    model = parser.parse_model('''
      <ir_version:7, opset_import:["":17]>
      graph (float[4,8,16] x) => (y) {
        dims = Constant <value_ints=[4,2,8]> ()
        two = Constant <value_int=2> ()
        shape = Mul (dims, two)
        y = Reshape (x, shape)
      }
    ''')
    inferred = onnx.shape_inference.infer_shapes(model, strict_mode=True, data_prop=True)
    assert [d.dim_value for d in inferred.graph.output[0].type.tensor_type.shape.dim] == [8,4,16]
