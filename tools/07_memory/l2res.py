"""生成残差块链（迫使多个张量同时留在 L2），用于从编译产物看 L2 基址的分布。

用法（M6，coremltools 环境）：python l2res.py <输出目录> <名字> [...]
名字：r_c{通道}_h{H}w{W}_B{块数}；每块：a = relu(conv1x1(x))；b = relu(conv1x1(a))；x = b + a + x（共享权重）。
"""
import os
import re
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

PAT = re.compile(r"r_c(\d+)_h(\d+)w(\d+)_B(\d+)$")


def program(C, H, W, B):
    rng = np.random.default_rng(0)
    w1 = (rng.standard_normal((C, C, 1, 1)) * np.sqrt(1.0 / C)).astype(np.float16)
    w2 = (rng.standard_normal((C, C, 1, 1)) * np.sqrt(1.0 / C)).astype(np.float16)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        k1, k2 = mb.const(val=w1), mb.const(val=w2)
        for _ in range(B):
            a = mb.relu(x=mb.conv(x=x, weight=k1))
            b = mb.relu(x=mb.conv(x=a, weight=k2))
            x = mb.add(x=mb.add(x=b, y=a), y=x)
        return x
    return p


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        C, H, W, B = map(int, PAT.match(name).groups())
        m = ct.convert(program(C, H, W, B), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
