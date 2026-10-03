"""maderix Part 4 §4.9 的形状实验：低通道、大空间的卷积链，经 space_to_depth 变成高通道、小空间后的效率。

用法（M6）：python s2d.py <输出目录>
生成的模型（都是 1×1 卷积 + relu，共享权重，32 层）：
  s2d_base_c64_128      输入 64×128×128，直接跑
  s2d_b4_c1024_32       64×128×128 → S2D(4) → 1024×32×32 跑 32 层 → D2S(4) → 64×128×128
  s2d_b2_c256_64        64×128×128 → S2D(2) → 256×64×64 跑 32 层 → D2S(2)
  s2d_only_b4 / _b2     只做 S2D + D2S（开销）
  s2d_direct_c1024_32   直接输入 1024×32×32，32 层（不含 S2D，对照）
"""
import os
import subprocess
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

out = sys.argv[1] if len(sys.argv) > 1 else "s2d_out"
os.makedirs(out, exist_ok=True)
rng = np.random.default_rng(0)
L = 32


def chain(x, C):
    k = mb.const(val=(rng.standard_normal((C, C, 1, 1)) * np.sqrt(2.0 / C)).astype(np.float16))
    b = mb.const(val=np.zeros(C, np.float16))
    for _ in range(L):
        x = mb.relu(x=mb.conv(x=x, weight=k, bias=b))
    return x


def build(name, shape, body):
    @mb.program(input_specs=[mb.TensorSpec(shape=shape, dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        return body(x)
    m = ct.convert(p, convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                   compute_units=ct.ComputeUnit.CPU_AND_NE,
                       skip_model_load=True)  # 生成时不加载：加载会触发一次 ANE 编译，大模型要十几分钟
    pkg = os.path.join(out, name + ".mlpackage")
    m.save(pkg)
    subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
    subprocess.run(["rm", "-rf", pkg])
    print("built", name, flush=True)


build("s2d_base_c64_128", (1, 64, 128, 128), lambda x: chain(x, 64))
build("s2d_b4_c1024_32", (1, 64, 128, 128),
      lambda x: mb.depth_to_space(x=chain(mb.space_to_depth(x=x, block_size=4), 1024), block_size=4))
build("s2d_b2_c256_64", (1, 64, 128, 128),
      lambda x: mb.depth_to_space(x=chain(mb.space_to_depth(x=x, block_size=2), 256), block_size=2))
build("s2d_direct_c1024_32", (1, 1024, 32, 32), lambda x: chain(x, 1024))
build("s2d_direct_c256_64", (1, 256, 64, 64), lambda x: chain(x, 256))
# 只有 S2D + D2S：中间加一个 relu，避免两者被直接消掉
build("s2d_only_b4", (1, 64, 128, 128),
      lambda x: mb.depth_to_space(x=mb.relu(x=mb.space_to_depth(x=x, block_size=4)), block_size=4))
build("s2d_only_b2", (1, 64, 128, 128),
      lambda x: mb.depth_to_space(x=mb.relu(x=mb.space_to_depth(x=x, block_size=2)), block_size=2))
build("s2d_relu_only", (1, 64, 128, 128), lambda x: mb.relu(x=x))
