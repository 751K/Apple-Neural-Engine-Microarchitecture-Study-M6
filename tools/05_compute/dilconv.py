"""3×3 卷积链的对照：普通 / 膨胀率 2（Winograd 不适用于膨胀卷积）。共享权重，512 通道，16×16。

用法（M6）：python dilconv.py <输出目录> <层数> [<层数> ...]
生成 dil{d}_k3_c512_h16w16_L{层数}.mlmodelc，d = 1、2。
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

C, H, W = 512, 16, 16
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for L in map(int, sys.argv[2:]):
    for d in (1, 2):
        name = f"dil{d}_k3_c{C}_h{H}w{W}_L{L}"
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        rng = np.random.default_rng(0)
        wt = (rng.standard_normal((C, C, 3, 3)) * np.sqrt(2.0 / (C * 9))).astype(np.float16)

        @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
        def p(x):
            w = mb.const(val=wt)
            b = mb.const(val=np.zeros(C, np.float16))
            for _ in range(L):
                x = mb.relu(x=mb.conv(x=x, weight=w, bias=b, pad_type="same", dilations=[d, d]))
            return x
        m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
