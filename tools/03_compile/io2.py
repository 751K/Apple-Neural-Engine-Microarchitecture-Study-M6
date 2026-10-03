"""生成两输入、两输出的小模型，用于看输入 / 输出地址包（BAR 编号）的分配。

用法（M6，coremltools 环境）：python io2.py <输出目录>
模型 io2：输入 x、y（1×256×1×512）；o1 = relu(conv(x) + y)；o2 = relu(conv(y))。
"""
import os, subprocess, sys
import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, W = 256, 512
w = (np.random.default_rng(0).standard_normal((C, C, 1, 1)) / 16).astype(np.float16)


@mb.program(input_specs=[mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16), mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16)],
            opset_version=ct.target.iOS18)
def p(x, y):
    k = mb.const(val=w)
    o1 = mb.relu(x=mb.add(x=mb.conv(x=x, weight=k), y=y), name="o1")
    o2 = mb.relu(x=mb.conv(x=y, weight=k), name="o2")
    return o1, o2


out = sys.argv[1]
os.makedirs(out, exist_ok=True)
m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
pkg = os.path.join(out, "io2.mlpackage")
m.save(pkg)
subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
subprocess.run(["rm", "-rf", pkg])
print("built io2")
