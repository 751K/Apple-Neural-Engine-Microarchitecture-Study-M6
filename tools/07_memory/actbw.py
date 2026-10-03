"""C3 激活数据的读写带宽、C4 独立输入数量的影响。

用法（M6）：python actbw.py <输出目录> <名字>   （每个名字单独一个进程）
  relu_<MB>：y = relu(x)，x 为 [1, 256, 1, W]，大小 MB（读一份、写一份）
  add_<MB>：y = a + b，a、b 各 MB（读两份、写一份）
  sum<N>：N 个 [1, 256, 64, 64]（各 2 MB）的输入相加，后接 4 层 1×1 卷积（保证放到 ANE 上；各 N 相同）
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

out, name = sys.argv[1], sys.argv[2]
C = 256


def spec(shape):
    return mb.TensorSpec(shape=shape, dtype=types.fp16)


if name.startswith(("relu_", "add_")):
    kind, mbs = name.split("_")
    W = int(mbs) * (1 << 20) // (C * 2)
    shape = (1, C, 1, W)
    if kind == "relu":
        @mb.program(input_specs=[spec(shape)], opset_version=ct.target.iOS18)
        def p(x):
            return mb.relu(x=x)
    else:
        @mb.program(input_specs=[spec(shape), spec(shape)], opset_version=ct.target.iOS18)
        def p(a, b):
            return mb.add(x=a, y=b)
elif name.startswith("sum"):
    n = int(name[3:])
    shape = (1, C, 64, 64)
    # coremltools 不接受 *args 形式的函数，按输入个数生成固定参数的函数
    args = ", ".join(f"x{i}" for i in range(n))
    body = "    y = x0\n" + "".join(f"    y = mb.add(x=y, y=x{i})\n" for i in range(1, n))
    body += "    for _ in range(4):\n        y = mb.relu(x=mb.conv(x=y, weight=K))\n    return y\n"
    K = (np.random.default_rng(0).standard_normal((C, C, 1, 1)) * np.sqrt(2.0 / C)).astype(np.float16)
    ns = {"mb": mb, "K": K}
    exec(f"def f({args}):\n{body}", ns)
    specs = [spec(shape) for _ in range(n)]  # 每个输入一个独立的 TensorSpec 对象；共用同一个对象会让输入名字对不上
    p = mb.program(input_specs=specs, opset_version=ct.target.iOS18)(ns["f"])
else:
    raise ValueError(name)

m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
               compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
pkg = os.path.join(out, name + ".mlpackage")
m.save(pkg)
subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
subprocess.run(["rm", "-rf", pkg])
print("built", name)
