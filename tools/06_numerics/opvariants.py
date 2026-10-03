"""生成只差一个运算的小模型，用于对比编译产物（A6：ALU 操作码、激活函数 LUT 的位置）。

用法（M6）：python opvariants.py <输出目录> <名字>   （每个名字单独一个进程）
形状 [1, 64, 1, 256]。逐元素模型有两个输入 a、b，激活函数模型只有一个输入 a。
  elt_<op>：先过一层固定的 1×1 卷积（保证有 MAC 层），再做 y = op(conv(a), b)
  act_<f>：y = f(conv(a))
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, W = 64, 256
out, name = sys.argv[1], sys.argv[2]
wt = (np.random.default_rng(0).standard_normal((C, C, 1, 1)) * 0.1).astype(np.float16)

ELT = {"add": mb.add, "sub": mb.sub, "mul": mb.mul, "maximum": mb.maximum, "minimum": mb.minimum,
       "real_div": mb.real_div, "greater": None}
ACT = {"relu": mb.relu, "sigmoid": mb.sigmoid, "tanh": mb.tanh, "gelu": mb.gelu, "silu": mb.silu, "exp": mb.exp,
       "sqrt": mb.sqrt, "rsqrt": mb.rsqrt, "inverse": mb.inverse, "abs": mb.abs, "erf": mb.erf, "sin": mb.sin,
       "cos": mb.cos, "log": mb.log, "floor": mb.floor, "sign": mb.sign, "square": mb.square}


kind, op = name.split("_", 1)
# 激活函数模型只有一个输入：多出一个没用到的输入时，ANECCompile 会失败（返回 1）
SPECS = [mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16)] * (2 if kind == "elt" else 1)


def body(a, b=None):
    x = mb.conv(x=a, weight=wt)
    if kind == "elt":
        return ELT[op](x=x, y=b)
    if op == "square":
        return mb.mul(x=x, y=x)
    if op in ("log", "sqrt", "rsqrt", "inverse"):  # 保证输入为正
        x = mb.add(x=mb.abs(x=x), y=np.float16(1.0))
    return ACT[op](x=x)


if kind == "elt":
    @mb.program(input_specs=SPECS, opset_version=ct.target.iOS18)
    def p(a, b):
        return body(a, b)
else:
    @mb.program(input_specs=SPECS, opset_version=ct.target.iOS18)
    def p(a):
        return body(a)


m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
               compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
pkg = os.path.join(out, name + ".mlpackage")
m.save(pkg)
subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
subprocess.run(["rm", "-rf", pkg])
print("built", name)
