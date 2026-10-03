"""PE（平面引擎）吞吐：逐元素运算链，数据留在 L2，用层数斜率求每层耗时。

用法（M6）：/opt/miniconda3/envs/mps/bin/python pe.py <目录>
生成 pe_{op}_c{C}_h{H}w{W}_L{L}.mlmodelc，输入 x、y 均为 [1, C, H, W] fp16：
  add：x ← x + y；mul：x ← x × y；am：加、乘交替（防止相邻同类运算被合并）。
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

SHAPES = [(64, 32, 32), (256, 32, 32), (256, 64, 64)]
SHAPES2 = [(32, 32, 32), (128, 32, 32), (256, 32, 32), (256, 48, 48)]
OPS = ("add", "mul", "am")
LAYERS = (16, 64)


def program(op, C, H, W, L):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16) for _ in range(2)], opset_version=ct.target.iOS18)
    def p(x, y):
        if op == "sc":
            for i in range(L):
                x = mb.abs(x=x) if i % 2 == 0 else mb.mul(x=x, y=np.float16(-1.0)) if i % 4 == 1 else mb.relu(x=x)
            return mb.add(x=x, y=y)
        for i in range(L):
            if op == "add" or (op == "am" and i % 2 == 0):
                x = mb.add(x=x, y=y)
            else:
                x = mb.mul(x=x, y=y)
        return x
    return p


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    jobs = [(C, H, W, op, LAYERS) for C, H, W in SHAPES for op in OPS] + [(C, H, W, op, LAYERS) for C, H, W in SHAPES2 for op in ("add", "sc")]
    jobs += [(256, h, h, op, (32, 96)) for h in (32, 40, 48, 56, 64) for op in ("add", "sc")]
    for C, H, W, op, Ls in jobs:
        if True:
            for L in Ls:
                name = f"pe_{op}_c{C}_h{H}w{W}_L{L}"
                if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
                    continue
                m = ct.convert(program(op, C, H, W, L), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                               compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
                pkg = os.path.join(out, name + ".mlpackage")
                m.save(pkg)
                subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
                subprocess.run(["rm", "-rf", pkg])
                print("built", name, flush=True)
