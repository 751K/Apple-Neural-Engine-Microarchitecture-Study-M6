"""找出 Core ML 会把什么样的小卷积放到 ANE 上（数值测试需要）。
用法：python placement_probe.py <输出目录>；之后对每个 mlmodelc 跑 bondrun 看中断。"""
import os, subprocess, sys
import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

out = sys.argv[1]
os.makedirs(out, exist_ok=True)


def build(name, cin, cout, H, W, n_id, relu=False):
    wt = (np.random.default_rng(0).standard_normal((cout, cin, 1, 1)) * 0.05).astype(np.float16)
    eye = np.eye(cout, dtype=np.float16).reshape(cout, cout, 1, 1)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, cin, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.conv(x=x, weight=wt)
        for _ in range(n_id):
            y = mb.conv(x=y, weight=eye)
        if relu:
            y = mb.relu(x=y)
        return y

    m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                   compute_units=ct.ComputeUnit.CPU_AND_NE, compute_precision=ct.precision.FLOAT16)
    pkg = os.path.join(out, name + ".mlpackage")
    m.save(pkg)
    subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
    print("built", name, flush=True)


build("p_w16", 64, 256, 1, 16, 0)
build("p_w1024", 64, 256, 1, 1024, 0)
build("p_h32w32", 64, 256, 32, 32, 0)
build("p_w16_id1", 64, 256, 1, 16, 1)
build("p_w16_id2", 64, 256, 1, 16, 2)
build("p_w16_relu", 64, 256, 1, 16, 0, relu=True)
build("p_w64_id2", 64, 256, 1, 64, 2)
