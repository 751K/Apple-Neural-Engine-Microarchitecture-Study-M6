"""ANE 数值行为：确定边界（numerics.py 的后续）。

用法（M6）：./anewho python numerics2.py <输出目录>
做法：x 为 [Cin, W]，每列一个用例；第 0 个输出通道的权重为 w0（默认全 1），输出 = Σ_i x[i, 列]·w0[i]。
输出通道补零到 2048、后接陪跑支路，保证在 ANE 上执行；同时跑 CPU_ONLY 作对照。
"""
import json
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types

OUT = sys.argv[1] if len(sys.argv) > 1 else "numerics2_out"
os.makedirs(OUT, exist_ok=True)
CIN, W = 64, 256
rng = np.random.default_rng(1)


def model(w0, name):
    wt = np.zeros((2048, CIN, 1, 1), np.float16)
    wt[0, :, 0, 0] = w0
    s0 = (rng.standard_normal((256, 2048, 1, 1)) * 0.01).astype(np.float16)
    sw = [(rng.standard_normal((256, 256, 1, 1)) * 0.05).astype(np.float16) for _ in range(3)]

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, CIN, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.conv(x=x, weight=wt, name="y")
        z = mb.relu(x=mb.conv(x=y, weight=s0))
        for k in sw:
            z = mb.relu(x=mb.conv(x=z, weight=k))
        return y, mb.identity(x=z, name="z")

    kw = dict(convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_precision=ct.precision.FLOAT16)
    m = ct.convert(p, compute_units=ct.ComputeUnit.CPU_AND_NE, **kw)
    m.save(os.path.join(OUT, name + ".mlpackage"))
    return m, ct.models.MLModel(os.path.join(OUT, name + ".mlpackage"), compute_units=ct.ComputeUnit.CPU_ONLY)


def run(mm, cols):
    """cols：每个用例一个加数列表（长度 ≤ CIN）。返回 (ANE 结果, CPU 结果)。"""
    x = np.zeros((CIN, W), np.float32)
    for j, c in enumerate(cols):
        x[:len(c), j] = c
    xin = x.astype(np.float16).reshape(1, CIN, 1, W)
    a = np.asarray(mm[0].predict({"x": xin})["y"])[0, 0, 0, :len(cols)].astype(np.float64)
    c = np.asarray(mm[1].predict({"x": xin})["y"])[0, 0, 0, :len(cols)].astype(np.float64)
    return a, c


ones = np.ones(CIN, np.float32)
m1 = model(ones, "sum")
R = {}

# 1. 溢出阈值：单个输入值（权重 1）
vals = [16384, 24576, 30000, 32000, 32736, 32752, 32768, 32784, 40000, 49152, 65504,
        -32752, -32768, -65504]
a, c = run(m1, [[v] for v in vals])
R["overflow_single"] = [[v, x, y] for v, x, y in zip(vals, a, c)]

# 2. 溢出阈值：两个加数之和
pairs = [(16000, 16000), (16376, 16376), (16384, 16368), (16384, 16376), (16384, 16384), (30000, 2752), (30000, 2768)]
a, c = run(m1, [list(p) for p in pairs])
R["overflow_sum"] = [[list(p), x, y] for p, x, y in zip(pairs, a, c)]

# 3. 非规格化数：单个输入 2^-k
ks = list(range(13, 25))
a, c = run(m1, [[2.0 ** -k] for k in ks])
R["subnormal_in"] = [[f"2^-{k}", x, y] for k, x, y in zip(ks, a, c)]
# 1.5·2^-k（看是否保留尾数）
a, c = run(m1, [[1.5 * 2.0 ** -k] for k in ks])
R["subnormal_in_1p5"] = [[f"1.5*2^-{k}", x, y] for k, x, y in zip(ks, a, c)]

# 4. 舍入：正负 tie、非 tie
tie_cases = {
    "2048+1": [2048, 1], "-2048-1": [-2048, -1], "2050+1": [2050, 1], "-2050-1": [-2050, -1],
    "1+2^-11": [1, 2 ** -11], "-1-2^-11": [-1, -(2 ** -11)], "1+2^-12": [1, 2 ** -12],
    "1+2^-11+2^-13": [1, 2 ** -11, 2 ** -13], "1+2^-11-2^-13": [1, 2 ** -11, -(2 ** -13)],
    "1+2^-12+2^-13 (0.75ulp)": [1, 2 ** -12, 2 ** -13], "1+2^-13 (0.25ulp)": [1, 2 ** -13],
    "-1-2^-12-2^-13 (-0.75ulp)": [-1, -(2 ** -12), -(2 ** -13)],
    "4096+2": [4096, 2], "4096+6": [4096, 6], "-4096-2": [-4096, -2],
}
a, c = run(m1, list(tie_cases.values()))
R["rounding"] = [[k, x, y] for k, x, y in zip(tie_cases, a, c)]

# 5. 累加器尾数位宽：B + 2^-j − B（B 放在第 0 个和最后一个通道，中间是小量）
rows = []
desc = []
for B in (1024.0, 16384.0):
    for j in range(0, 25, 2):
        rows.append([B] + [2.0 ** -j] + [0] * (CIN - 3) + [-B])
        desc.append(f"{int(B)}+2^-{j}-{int(B)}")
a, c = run(m1, rows)
R["acc_width"] = [[d, x, y] for d, x, y in zip(desc, a, c)]

# 6. 中间结果超过 32768 但最终结果不超：16384+16384+...−16384−16384
mid = [[16384, 16384, -16384, -16384, 1], [16384, 16384, 16384, -16384, -16384, -16384, 1],
       [30000, 30000, -30000, -30000, 1], [16384, 16384, 1] + [0] * (CIN - 5) + [-16384, -16384]]
a, c = run(m1, mid)
R["intermediate_overflow"] = [[str(m), x, y] for m, x, y in zip(mid, a, c)]

# 7. 乘积：x·w 的溢出 / 非规格化（权重不是 1）
for wv in (256.0, 2.0 ** -8):
    mw = model(np.full(CIN, 0, np.float32) + np.eye(1, CIN, 0)[0] * wv, f"mul_{wv}")
    xs = [127.0, 128.0, 129.0, 2.0 ** -8, 2.0 ** -10, 2.0 ** -14, 2.0 ** -16, 1.0, 3.0]
    a, c = run(mw, [[v] for v in xs])
    R[f"mul_w={wv}"] = [[v, x, y] for v, x, y in zip(xs, a, c)]

json.dump(R, open(os.path.join(OUT, "results.json"), "w"), indent=1, default=str)
for k, v in R.items():
    print(f"== {k}  （输入 / ANE / CPU）")
    for row in v:
        print("   ", row)
