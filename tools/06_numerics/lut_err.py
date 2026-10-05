"""激活函数的误差曲线（maderix Part 4 §4.6：33 点 LUT + 线性插值）。

用法（M6）：./anewho python lut_err.py <输出目录>
每个激活函数一个模型：y = f(x)，后接陪跑支路保证放到 ANE 上。x 为 [-R, R] 上的稠密网格（fp16）。
输出 <输出目录>/<名字>.npz（x、ANE 输出、CPU 输出），并打印误差统计和误差为零的点（推测的采样点）。
"""
import os
import sys

import torch  # noqa: F401
import numpy as np
import coremltools as ct
from coremltools.converters.mil import Builder as mb
from coremltools.converters.mil.mil import types
from scipy.special import erf

OUT = sys.argv[1] if len(sys.argv) > 1 else "lut_out"
os.makedirs(OUT, exist_ok=True)
C, W = 2048, 256
rng = np.random.default_rng(1)


def sidecar(y):
    z = mb.relu(x=mb.conv(x=y, weight=(rng.standard_normal((256, C, 1, 1)) * 0.01).astype(np.float16)))
    for _ in range(3):
        z = mb.relu(x=mb.conv(x=z, weight=(rng.standard_normal((256, 256, 1, 1)) * 0.05).astype(np.float16)))
    return mb.identity(x=z, name="z")


def gelu_exact(x):
    return 0.5 * x * (1 + erf(x / np.sqrt(2)))


OPS = {  # 名字: (MIL 构造, 精确函数, 输入范围)
    "sigmoid": (lambda x: mb.sigmoid(x=x), lambda x: 1 / (1 + np.exp(-x)), (-12, 12)),
    "tanh": (lambda x: mb.tanh(x=x), np.tanh, (-6, 6)),
    "gelu": (lambda x: mb.gelu(x=x, mode="EXACT"), gelu_exact, (-8, 8)),
    "gelu_tanh": (lambda x: mb.gelu(x=x, mode="TANH_APPROXIMATION"),
                  lambda x: 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3))), (-8, 8)),
    "silu": (lambda x: mb.silu(x=x), lambda x: x / (1 + np.exp(-x)), (-12, 12)),
    "exp": (lambda x: mb.exp(x=x), np.exp, (-12, 10)),
    "log": (lambda x: mb.log(x=x), np.log, (2 ** -10, 1000)),
    "sqrt": (lambda x: mb.sqrt(x=x), np.sqrt, (2 ** -10, 1000)),
    "rsqrt": (lambda x: mb.rsqrt(x=x), lambda x: 1 / np.sqrt(x), (2 ** -6, 1000)),
    "inverse": (lambda x: mb.inverse(x=x), lambda x: 1 / x, (2 ** -6, 1000)),
    "erf": (lambda x: mb.erf(x=x), erf, (-4, 4)),
    "sin": (lambda x: mb.sin(x=x), np.sin, (-8, 8)),
}

names = sys.argv[2:] or list(OPS)
for name in names:
    build, exact, (lo, hi) = OPS[name]

    @mb.program(input_specs=[mb.TensorSpec(shape=(1, C, 1, W), dtype=types.fp16)], opset_version=ct.target.iOS18)
    def p(x):
        y = mb.identity(x=build(x), name="y")
        return y, sidecar(y)

    kw = dict(convert_to="mlprogram", minimum_deployment_target=ct.target.iOS18, compute_precision=ct.precision.FLOAT16)
    m = ct.convert(p, compute_units=ct.ComputeUnit.CPU_AND_NE, **kw)
    m.save(os.path.join(OUT, name + ".mlpackage"))
    mc = ct.models.MLModel(os.path.join(OUT, name + ".mlpackage"), compute_units=ct.ComputeUnit.CPU_ONLY)
    if lo > 0:  # 正值域用对数网格
        xs = np.geomspace(lo, hi, C * W)
    else:
        xs = np.linspace(lo, hi, C * W)
    x16 = xs.astype(np.float16)
    xin = x16.reshape(1, C, 1, W)
    ya = np.asarray(m.predict({"x": xin})["y"]).reshape(-1).astype(np.float64)
    yc = np.asarray(mc.predict({"x": xin})["y"]).reshape(-1).astype(np.float64)
    xe = x16.astype(np.float64)
    ye = exact(xe)
    np.savez_compressed(os.path.join(OUT, name + ".npz"), x=xe, ane=ya, cpu=yc)
    # 去重（fp16 网格上很多重复值）
    ux, idx = np.unique(xe, return_index=True)
    ea = ya[idx] - ye[idx]
    ec = yc[idx] - ye[idx]
    # FP16 的实际 ulp：精确值所在指数区间内相邻可表示数的间距（非规格化区为 2^-24），见 lut_ulp.py
    a_ = np.abs(ye[idx])
    e_ = np.maximum(np.floor(np.log2(np.where(a_ > 0, a_, 2.0 ** -24))), -14)
    ulp = np.abs(ea) / 2.0 ** (e_ - 10)
    print(f"== {name}  点数 {len(ux)}  ANE 最大绝对误差 {np.max(np.abs(ea)):.3e}  最大相对误差(ulp) {np.max(ulp):.1f}  "
          f"CPU 最大绝对误差 {np.max(np.abs(ec)):.3e}  ANE≠CPU 的点 {np.mean(ya[idx] != yc[idx]) * 100:.1f}%")
    # 误差的局部极小（推测采样点）：|误差| 平滑后的局部最小值
    k = 9
    sm = np.convolve(np.abs(ea), np.ones(k) / k, mode="same")
    loc = [i for i in range(k, len(sm) - k) if sm[i] == sm[i - k:i + k + 1].min() and sm[i] < 0.3 * np.max(sm)]
    knots = ux[loc]
    if len(knots) > 1:
        d = np.diff(knots)
        print(f"   误差极小点 {len(knots)} 个，前 20 个：{np.round(knots[:20], 4).tolist()}")
        print(f"   相邻间距中位数 {np.median(d):.4f}，范围 {d.min():.4f}–{d.max():.4f}")
