"""生成双 ANE 实测用的模型：计算量相同、只改变空间形状，看 Core ML 运行时用一个还是两个 ANE。

用法（M6，coremltools 环境）：python bond_sweep.py <输出目录> [用例名 ...]
- 1×1 卷积链：512 通道、8 层，H×W 固定为 4096，H 取 1/2/4/16/64。
  按 bonded_cases 的编译结果，H=1 时编译器只生成 ANE0 的程序，H≥2 时可按高度切成两半。
- 3×3 卷积链：256 通道、4 层，64×64 和 1×4096 两种形状。
"""
import os as _os, sys as _sys  # 仓库里按目录存放、部署到 M6 时平铺：两种布局都能找到公共模块
_here = _os.path.dirname(_os.path.abspath(__file__))
_sys.path[:0] = [_here, _os.path.join(_here, "..", "lib"), _os.path.join(_here, "..", "common")]
import os
import subprocess
import sys

import torch  # noqa: F401  必须先于 coremltools 导入
import coremltools as ct

from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

from bonded_cases import conv1x1_chain, conv3x3_chain, w


def conv1x1_shared(C, H, W, L):
    """所有层共用同一份权重（同一个 const），让权重留在片上，测纯计算速度。"""
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        k = mb.const(val=w(C, C, 1, 1))
        b = mb.const(val=w(C))
        for i in range(L):
            x = mb.relu(x=mb.conv(x=x, weight=k, bias=b))
        return x
    return p


CASES = {f"s1x1_512_h{h}w{4096 // h}_L8": (conv1x1_chain, (512, h, 4096 // h, 8)) for h in (1, 2, 4, 16, 64)}
# 宽度扫描：H=1，512 通道，16 层，找编译器从单 ANE 切换到双 ANE 的阈值
for wd in (64, 128, 256, 512, 1024, 2048, 4096):
    CASES[f"w1x1_512_h1w{wd}_L16"] = (conv1x1_chain, (512, 1, wd, 16))
# 深度扫描：阈值两侧（W=128 单 ANE，W=256 双 ANE）各取几种层数，用斜率扣掉每次调用的固定开销
for wd in (128, 256):
    for n in (16, 48, 128):
        CASES[f"d1x1_512_h1w{wd}_L{n}"] = (conv1x1_chain, (512, 1, wd, n))
# 共享权重的深度扫描
for wd in (128, 256):
    for n in (16, 48, 128, 256, 384):
        CASES[f"k1x1_512_h1w{wd}_L{n}"] = (conv1x1_shared, (512, 1, wd, n))
CASES["s3x3_256_h64w64_L4"] = (conv3x3_chain, (256, 64, 64, 4))
CASES["s3x3_256_h1w4096_L4"] = (conv3x3_chain, (256, 1, 4096, 4))

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:] or list(CASES):
        fn, args = CASES[name]
        m = ct.convert(fn(*args), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE,
                       skip_model_load=True)  # 生成时不加载：加载会触发一次 ANE 编译，大模型要十几分钟
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        print("built", name, flush=True)
