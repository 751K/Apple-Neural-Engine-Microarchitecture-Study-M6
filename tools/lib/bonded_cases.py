"""生成一组小 MIL 程序，用来观察 h18g 双 ANE（bonded）模式怎么切分不同类型的运算。

用法（M6，coremltools 环境）：python bonded_cases.py <输出目录>
每个用例生成 <输出目录>/<名字>.mlpackage，并编译成 <名字>.mlmodelc。
"""
import os
import subprocess
import sys

import torch  # noqa: F401  必须先于 coremltools 导入
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

rng = np.random.default_rng(0)


def w(*shape, scale=0.05):
    return (rng.standard_normal(shape) * scale).astype(np.float16)


def conv1x1_chain(C, H, W, L):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        for i in range(L):
            x = mb.relu(x=mb.conv(x=x, weight=w(C, C, 1, 1), bias=w(C)))
        return x
    return p


def conv3x3_chain(C, H, W, L):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        for i in range(L):
            x = mb.relu(x=mb.conv(x=x, weight=w(C, C, 3, 3), bias=w(C), pad_type="same"))
        return x
    return p


def matmul_const(M, K, N):
    """激活 [1, M, K] 乘常量权重 [K, N]（类似 linear）。"""
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, M, K), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        return mb.matmul(x=x, y=w(K, N))
    return p


def matmul_dyn(B, M, K, N):
    """两个动态输入相乘（类似 attention 的 QK^T）。"""
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, B, M, K), dtype=types.fp16),
                             mb.TensorSpec(shape=(1, B, K, N), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(a, b):
        return mb.matmul(x=a, y=b)
    return p


def softmax_w(C, H, W):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        return mb.softmax(x=x, axis=-1)
    return p


def reduce_h(C, H, W):
    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, H, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        return mb.reduce_sum(x=x, axes=[2], keep_dims=True)
    return p


CASES = {
    # 名字: (构造函数, 参数)
    "c1x1_64_h64w64_L3": (conv1x1_chain, (64, 64, 64, 3)),
    "c1x1_512_h32w32_L8": (conv1x1_chain, (512, 32, 32, 8)),
    "c1x1_1024_h1w64_L4": (conv1x1_chain, (1024, 1, 64, 4)),    # 只有一行：不能按 H 切
    "c1x1_1024_h1w1_L4": (conv1x1_chain, (1024, 1, 1, 4)),      # 单个向量
    "c3x3_64_h64w64_L3": (conv3x3_chain, (64, 64, 64, 3)),      # 需要相邻行（halo）
    "mm_const_M64_K1024_N1024": (matmul_const, (64, 1024, 1024)),
    "mm_const_M1_K2048_N2048": (matmul_const, (1, 2048, 2048)),
    "mm_dyn_B8_M128_K64_N128": (matmul_dyn, (8, 128, 64, 128)),
    "softmax_w_C64_H64_W256": (softmax_w, (64, 64, 256)),
    "reduce_h_C64_H64_W64": (reduce_h, (64, 64, 64)),
}

if __name__ == "__main__":
    out = sys.argv[1]
    os.makedirs(out, exist_ok=True)
    only = sys.argv[2:] or list(CASES)
    for name in only:
        fn, args = CASES[name]
        m = ct.convert(fn(*args), convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18,
                       compute_units=ct.ComputeUnit.CPU_AND_NE)
        pkg = os.path.join(out, name + ".mlpackage")
        m.save(pkg)
        subprocess.run(["xcrun", "coremlcompiler", "compile", pkg, out], check=True, capture_output=True)
        print("built", name, flush=True)
