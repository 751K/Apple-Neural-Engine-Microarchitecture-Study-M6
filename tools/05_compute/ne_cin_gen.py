"""只改变输入通道数的卷积链：每层取上一层输出（512 通道）的前 c 个通道，做 c → 512 的 1×1 卷积（+ relu），各层共享权重。
名字：cin{c}[d3]_h{H}w{W}_L{层数}（d3 = 3×3 膨胀 2）。用法：python cin_gen.py <输出目录> <名字> ...（有 Xcode 时用 coremlcompiler，否则用当前目录的 mlcompile，见 tools/common/mlcompile.m）"""
import os, re, subprocess, sys
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

CO = 512
PAT = re.compile(r"cin(\d+)(d3)?_h(\d+)w(\d+)_L(\d+)$")   # d3：3×3、膨胀 2、pad same（不用 Winograd），归约长度为 9c


def program(c, H, W, L, d3=False):
    rng = np.random.default_rng(0)
    k = 3 if d3 else 1
    w = (rng.standard_normal((CO, c, k, k)) * np.sqrt(2.0 / (c * k * k))).astype(np.float16)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, CO, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        kw = mb.const(val=w)
        b = mb.const(val=np.zeros(CO, np.float16))
        for _ in range(L):
            xs = mb.slice_by_index(x=x, begin=[0, 0, 0, 0], end=[1, c, H, W])
            x = mb.relu(x=mb.conv(x=xs, weight=kw, bias=b, dilations=[2, 2], pad_type="same") if d3 else mb.conv(x=xs, weight=kw, bias=b))
        return x
    return p


if __name__ == "__main__":
    out = sys.argv[1]; os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        g = PAT.match(name).groups()
        c, d3, H, W, L = int(g[0]), bool(g[1]), int(g[2]), int(g[3]), int(g[4])
        m = ct.convert(program(c, H, W, L, d3), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE, skip_model_load=True)
        pkg = os.path.join(out, name + ".mlpackage"); m.save(pkg)
        if subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], capture_output=True).returncode:
            subprocess.run([os.path.abspath("mlcompile"), pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
