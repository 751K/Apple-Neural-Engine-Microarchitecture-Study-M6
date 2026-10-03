"""按名字生成卷积链模型（共享权重，权重留在片上），用于计算阵列的微基准。

用法（M6，coremltools 环境）：python chain.py <输出目录> <名字> [<名字> ...]
名字格式：k{核}_c{通道}_h{H}w{W}_L{层数}[_u]，核可以写成 kH x kW，例如 k3x3、k1x9、k9x1
  - 所有层共用同一份 C×C×k×k 权重和 bias，每层 conv + bias + relu，pad 为 same。
  - 加 _u 表示每层权重各不相同（会从 DRAM 读权重）。
已经存在的 mlmodelc 会跳过。
"""
import os
import re
import subprocess
import sys

import torch  # noqa: F401  必须先于 coremltools 导入
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

PAT = re.compile(r"k(\d+(?:x\d+)?)_c(\d+)_h(\d+)w(\d+)_L(\d+)(_u)?$")


def ksize(k):
    """"3" → (3, 3)；"1x9" → (1, 9)。"""
    a = [int(v) for v in str(k).split("x")]
    return (a[0], a[-1])


def program(k, C, H, W, L, unique):
    kh, kw = ksize(k)
    rng = np.random.default_rng(0)
    scale = np.sqrt(2.0 / (C * kh * kw))  # He 初始化：经过 relu 后方差不变，避免深链里激活衰减到 0（W8A8 校准会失败），也避免溢出

    def wgt():
        return (rng.standard_normal((C, C, kh, kw)) * scale).astype(np.float16)

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        kw = mb.const(val=wgt())
        b = mb.const(val=np.zeros(C, np.float16))
        for _ in range(L):
            w_ = mb.const(val=wgt()) if unique else kw
            x = mb.relu(x=mb.conv(x=x, weight=w_, bias=b, pad_type="same"))
        return x
    return p


def flops(name):
    k, C, H, W, L, _ = PAT.match(name).groups()
    kh, kw = ksize(k)
    C, H, W, L = map(int, (C, H, W, L))
    return 2 * C * C * kh * kw * H * W * L


if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    for name in sys.argv[2:]:
        if os.path.isdir(os.path.join(out, name + ".mlmodelc")):
            continue
        k, C, H, W, L, u = PAT.match(name).groups()
        m = ct.convert(program(k, int(C), int(H), int(W), int(L), bool(u)), convert_to="mlprogram",
                       minimum_deployment_target=ct.target.iOS18, compute_units=ct.ComputeUnit.CPU_AND_NE,
                       skip_model_load=True)  # 生成时不加载：加载会触发一次 ANE 编译，大模型要十几分钟
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        subprocess.run(["rm", "-rf", pkg])
        print("built", name, flush=True)
