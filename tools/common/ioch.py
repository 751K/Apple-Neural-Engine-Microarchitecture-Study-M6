"""生成"输入 / 输出通道数可变"的 1×4 卷积链：第一层 Cin→256，中间 256→256，最后一层 256→Cout。

用法（M6，coremltools 环境）：python ioch.py <输出目录> <名字> [...]
名字：io_ci{Cin}_co{Cout}_h{H}w{W}_L{层数}（L ≥ 2）
用途：只改变子图输入 + 输出张量的大小，检验双 ANE 切分开销是否以"输入 + 输出 ≤ 256 KiB"为界（bonded_measure.md §2.2）。
"""
import os, re, subprocess, sys
import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

PAT = re.compile(r"io_ci(\d+)_co(\d+)_h(\d+)w(\d+)_L(\d+)$")
out = sys.argv[1]
os.makedirs(out, exist_ok=True)
for name in sys.argv[2:]:
    if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
        continue
    ci, co, H, W, L = map(int, PAT.match(name).groups())
    rng = np.random.default_rng(0)
    wf = lambda a, b: (rng.standard_normal((b, a, 1, 4)) * np.sqrt(2.0 / (4 * a))).astype(np.float16)
    w1, wm, wl = wf(ci, 256), wf(256, 256), wf(256, co)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, ci, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        k1, km, kl = mb.const(val=w1), mb.const(val=wm), mb.const(val=wl)
        x = mb.relu(x=mb.conv(x=x, weight=k1, pad_type="same"))
        for _ in range(L - 2):
            x = mb.relu(x=mb.conv(x=x, weight=km, pad_type="same"))
        return mb.relu(x=mb.conv(x=x, weight=kl, pad_type="same"))
    m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
    pkg = os.path.join(out, name + ".mlpackage")
    m.save(pkg)
    subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
    subprocess.run(["rm", "-rf", pkg])
    print("built", name, flush=True)
