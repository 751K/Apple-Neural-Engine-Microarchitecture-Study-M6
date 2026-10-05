"""由 lut_err.py 保存的 npz 重新计算激活函数在 ANE 上的最大误差，以 FP16 的实际 ulp 为单位。

ulp 取精确值所在指数区间内相邻两个 FP16 可表示数之间的距离：|y| ∈ [2^e, 2^(e+1)) 时为 2^(e−10)，
|y| < 2^−14（非规格化区）时为 2^−24。它随指数区间分段变化，与 numpy.spacing 对 FP16 的定义一致。
用法：python3 lut_ulp.py <npz 目录>   （报告用的数据：data/06_numerics/lut_m6/，输出见 data/06_numerics/lut_ulp_m6.txt）
"""
import os
import sys

import numpy as np
from scipy.special import erf

EX = {
    "sigmoid": lambda x: 1 / (1 + np.exp(-x)), "tanh": np.tanh,
    "gelu": lambda x: 0.5 * x * (1 + erf(x / np.sqrt(2))),
    "gelu_tanh": lambda x: 0.5 * x * (1 + np.tanh(np.sqrt(2 / np.pi) * (x + 0.044715 * x ** 3))),
    "silu": lambda x: x / (1 + np.exp(-x)), "erf": erf, "sin": np.sin, "exp": np.exp, "log": np.log,
    "sqrt": np.sqrt, "rsqrt": lambda x: 1 / np.sqrt(x), "inverse": lambda x: 1 / x,
}


def fp16_ulp(y):
    a = np.abs(y)
    e = np.floor(np.log2(np.where(a > 0, a, 2.0 ** -24)))
    return 2.0 ** (np.maximum(e, -14) - 10)


src = sys.argv[1]
print(f"{'函数':10s} {'最大误差(ulp)':>14s}  出现位置")
for n, f in EX.items():
    d = np.load(os.path.join(src, n + ".npz"))
    ux, i = np.unique(d["x"], return_index=True)
    ye = f(ux)
    ea = d["ane"][i] - ye
    u = np.abs(ea) / fp16_ulp(ye)
    k = int(np.argmax(u))
    print(f"{n:10s} {u[k]:14.1f}  x = {ux[k]:.4g}，精确值 {ye[k]:.3g}，ANE 输出 {d['ane'][i][k]:.3g}")
